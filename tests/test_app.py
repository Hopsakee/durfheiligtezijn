import json
import random
import re

import pytest
from starlette.testclient import TestClient

from durfheilig import db as spel
from durfheilig.app import maak_app
from durfheilig.data import laad_heiligen, laad_vragen

H, V = laad_heiligen(), laad_vragen()


def maak(llm=None, db=None):
    db = db or spel.open_db()
    return db, maak_app(db, H, V, llm, random.Random(1))


def kind(app, naam="kind1"):
    return TestClient(app, headers={"remote-user": naam}, follow_redirects=True)


def speel(c, nick, voorkeur="maakt niet uit", interesses=None, kiezen=0, extra_ronde=False):
    """Play the quiz as a scripted kid. Returns the page after the last step."""
    assert c.get("/").status_code == 200
    c.post("/welkom", data={"nickname": nick})
    c.post("/voorkeur", data={"voorkeur": voorkeur})
    for _ in range(12):
        html = c.get("/").text
        vid = re.search(r'name="vid" value="(\w+)"', html).group(1)
        c.post("/vraag", data={"vid": vid, "kant": "plus"})
    c.post("/interesses", data={"interesse": interesses or V.interesses[:2]})
    r = c.post("/open", data={"a1": "tekenen", "a2": "eerlijkheid"})
    assert "Nog drie vragen" in r.text
    ids = re.findall(r'name="(v\d)"', r.text)
    r = c.post("/vervolg", data={i: "min" for i in dict.fromkeys(ids)})
    assert "Drie heiligen voor jou" in r.text
    if extra_ronde:
        r = c.post("/geen-past")
        assert "Nog drie vragen" in r.text
        ids = re.findall(r'name="(v\d)"', r.text)
        r = c.post("/vervolg", data={i: "plus" for i in dict.fromkeys(ids)})
        assert "Er past er geen bij mij" not in r.text    # only one extra round
    qids = re.findall(r'name="gekozen" value="([^"]+)"', r.text)
    assert len(qids) == 3
    r = c.post("/keuze", data={"gekozen": qids[kiezen], "want": "ik ook", f"niet_{qids[(kiezen + 1) % 3]}": "te streng"})
    return r, qids[kiezen], qids


def test_zonder_remote_user_is_alles_401():
    _, app = maak()
    anon = TestClient(app, follow_redirects=True)
    for pad in ("/", "/mijn", "/beheer"):
        assert anon.get(pad).status_code == 401
    for pad in ("/welkom", "/voorkeur", "/vraag", "/interesses", "/open", "/vervolg", "/keuze", "/geen-past"):
        assert anon.post(pad, data={"nickname": "x"}).status_code == 401, pad
    # Name and e-mail headers are not an identity; only Remote-User is.
    assert anon.get("/", headers={"remote-name": "Piet", "remote-email": "p@x.nl", "remote-groups": "admins"}).status_code == 401
    assert anon.get("/health").status_code == 200


def test_een_hele_quiz_zonder_llm_geeft_drie_heiligen_en_een_keuze():
    db, app = maak(None)
    c = kind(app)
    r, gekozen, qids = speel(c, "Vos")
    assert "Houd je heilige geheim" in r.text
    assert spel.gekozen_heiligen(db) == {gekozen}
    assert "✔ Jouw keuze" in c.get("/mijn").text


def test_voortgang_blijft_bewaard_en_hervat_op_dezelfde_stap():
    _, app = maak()
    c = kind(app)
    c.post("/welkom", data={"nickname": "Uil"})
    c.post("/voorkeur", data={"voorkeur": "man"})
    html = c.get("/").text
    vid = re.search(r'name="vid" value="(\w+)"', html).group(1)
    c.post("/vraag", data={"vid": vid, "kant": "min"})
    nieuw = kind(app)                       # same account, new browser
    assert "Vraag 2 van 12" in nieuw.get("/").text


def test_stappen_overslaan_kan_niet():
    _, app = maak()
    c = kind(app)
    c.post("/voorkeur", data={"voorkeur": "man"})        # still on the welcome screen
    assert "Welkom" in c.get("/").text
    c.post("/vervolg", data={})
    assert "Welkom" in c.get("/").text
    assert c.get("/mijn").url.path == "/"


def test_interesses_moeten_twee_of_drie_zijn():
    _, app = maak()
    c = kind(app)
    c.post("/welkom", data={"nickname": "Uil"}); c.post("/voorkeur", data={"voorkeur": "man"})
    for _ in range(12):
        vid = re.search(r'name="vid" value="(\w+)"', c.get("/").text).group(1)
        c.post("/vraag", data={"vid": vid, "kant": "min"})
    for aantal in (0, 1, 4):
        assert "Kies 2 of 3" in c.post("/interesses", data={"interesse": V.interesses[:aantal]}).text
    assert "Nog twee dingen" in c.post("/interesses", data={"interesse": V.interesses[:3]}).text


def test_bijnaam_is_uniek_zonder_hoofdletters():
    _, app = maak()
    kind(app, "a").post("/welkom", data={"nickname": "Vos"})
    assert "al gebruikt" in kind(app, "b").post("/welkom", data={"nickname": "vos"}).text


def test_een_heilige_wordt_maar_door_een_speler_gekozen():
    db, app = maak(None)
    a, b = kind(app, "a"), kind(app, "b")
    _, gekozen_a, _ = speel(a, "Aap")
    r, gekozen_b, qids_b = speel(b, "Beer")      # identical answers: would have the same top-3 without exclusion
    assert gekozen_a != gekozen_b and gekozen_a not in qids_b
    assert spel.gekozen_heiligen(db) == {gekozen_a, gekozen_b}


def test_database_weigert_dezelfde_heilige_twee_keer_en_app_biedt_dan_een_nieuwe_top3():
    db, app = maak(None)
    a, b = kind(app, "a"), kind(app, "b")
    # b reaches the choice screen with the same top-3 a is about to confirm, so exclusion has not kicked in yet.
    def tot_keuze(c, nick):
        c.post("/welkom", data={"nickname": nick}); c.post("/voorkeur", data={"voorkeur": "man"})
        for _ in range(12):
            vid = re.search(r'name="vid" value="(\w+)"', c.get("/").text).group(1)
            c.post("/vraag", data={"vid": vid, "kant": "plus"})
        c.post("/interesses", data={"interesse": V.interesses[:2]}); r = c.post("/open", data={})
        ids = list(dict.fromkeys(re.findall(r'name="(v\d)"', r.text)))
        return c.post("/vervolg", data={i: "min" for i in ids})
    ra, rb = tot_keuze(a, "Aap"), tot_keuze(b, "Beer")
    qa = re.findall(r'name="gekozen" value="([^"]+)"', ra.text)
    qb = re.findall(r'name="gekozen" value="([^"]+)"', rb.text)
    a.post("/keuze", data={"gekozen": qa[0], "want": "x"})
    r = b.post("/keuze", data={"gekozen": qb[0], "want": "x"})          # same saint, taken a moment ago
    assert "Drie heiligen voor jou" in r.text and qa[0] not in re.findall(r'name="gekozen" value="([^"]+)"', r.text)
    assert spel.gekozen_heiligen(db) == {qa[0]}
    with pytest.raises(spel.AlGekozen):
        spel.kies(db, spel.speler_voor(db, "b")["id"], qa[0], "", {})


def test_extra_ronde_een_keer_en_afgewezen_komen_niet_terug():
    db, app = maak(None)
    c = kind(app)
    r, gekozen, qids = speel(c, "Vos", extra_ronde=True)
    sp = spel.speler_voor(db, "kind1")
    eerste = set(spel.match_van(db, sp["id"])["afgewezen"])
    assert len(eerste) == 3 and not eerste & set(qids)
    assert "Houd je heilige geheim" in r.text
    m = spel.match_van(db, spel.speler_voor(db, "kind1")["id"])
    assert not set(m["afgewezen"]) & {m["gekozen"]} and m["gekozen"] not in set(m["afgewezen"])
    assert set(m["afgewezen"]) and len(m["afgewezen"]) == 3



def test_mijn_heilige_toont_alleen_de_eigen_heiligen():
    _, app = maak(None)
    a, b = kind(app, "a"), kind(app, "b")
    _, ga, _ = speel(a, "Aap")
    _, gb, qb = speel(b, "Beer")
    pagina_b = b.get("/mijn").text
    assert ga not in pagina_b and "Aap" not in pagina_b


def test_beheer_alleen_voor_admins_en_toont_voortgang_en_markering():
    db, app = maak(None)
    speel(kind(app, "a"), "Aap")
    gewoon = kind(app, "a")
    assert gewoon.get("/beheer").status_code == 403
    assert gewoon.get("/beheer", headers={"remote-groups": "durfheilig"}).status_code == 403
    r = gewoon.get("/beheer", headers={"remote-groups": "admins,durfheilig"})
    assert r.status_code == 200 and "1 van 1 klaar" in r.text and "Aap" in r.text


def test_met_llm_gaat_markering_naar_de_begeleider_en_nooit_naar_de_jongere():
    db, app0 = maak(None)
    h = [x for x in H if x.geslacht in ("mannelijk", "vrouwelijk")][:3]

    def llm(systeem, gegevens):
        kand = [k["qid"] for k in json.loads(gegevens)["kandidaten"]]
        if "Bedenk" in systeem:
            return json.dumps({"vragen": [{"vraag": f"Vraag {i}?", "min": "A", "plus": "B", "stijgt_bij_min": kand[:1], "stijgt_bij_plus": kand[1:2]} for i in range(3)]})
        return json.dumps({"keuzes": [{"qid": q, "uitleg": "LLM-uitleg"} for q in kand[:3]], "markering": "zorgelijke zin"})
    db, app = maak(llm)
    c = kind(app)
    r, gekozen, _ = speel(c, "Vos")
    assert "zorgelijke zin" not in c.get("/").text and "zorgelijke zin" not in c.get("/mijn").text
    assert "LLM-uitleg" in c.get("/mijn").text
    assert "zorgelijke zin" in kind(app, "x").get("/beheer", headers={"remote-groups": "admins"}).text


def naar_keuze(c, nick):
    c.post("/welkom", data={"nickname": nick}); c.post("/voorkeur", data={"voorkeur": "man"})
    for _ in range(12):
        vid = re.search(r'name="vid" value="(\w+)"', c.get("/").text).group(1)
        c.post("/vraag", data={"vid": vid, "kant": "plus"})
    c.post("/interesses", data={"interesse": V.interesses[:2]})
    r = c.post("/open", data={"a1": "x", "a2": "y"})
    ids = list(dict.fromkeys(re.findall(r'name="(v\d)"', r.text)))
    return c.post("/vervolg", data={i: "min" for i in ids})


def stap_van(db, naam):
    return spel.invulling(db, spel.speler_voor(db, naam)["id"])["stap"]


def test_vreemde_vraag_of_kant_wordt_genegeerd_en_blokkeert_niets():
    db, app = maak()
    c = kind(app)
    c.post("/welkom", data={"nickname": "Uil"}); c.post("/voorkeur", data={"voorkeur": "man"})
    ids = spel.invulling(db, spel.speler_voor(db, "kind1")["id"])["vraag_ids"]
    vreemd = next(v.id for v in V.vragen if v.id not in ids)
    c.post("/vraag", data={"vid": vreemd, "kant": "plus"})
    c.post("/vraag", data={"vid": ids[0], "kant": "stijgers"})
    assert spel.invulling(db, spel.speler_voor(db, "kind1")["id"])["antwoorden"] == {}
    assert "Vraag 1 van 12" in c.get("/").text


def test_vervolgantwoord_met_vreemde_waarde_telt_niet_en_het_spel_loopt_door():
    db, app = maak()
    c = kind(app)
    for _ in range(1):
        pass
    c.post("/welkom", data={"nickname": "Uil"}); c.post("/voorkeur", data={"voorkeur": "man"})
    for _ in range(12):
        vid = re.search(r'name="vid" value="(\w+)"', c.get("/").text).group(1)
        c.post("/vraag", data={"vid": vid, "kant": "plus"})
    c.post("/interesses", data={"interesse": V.interesses[:2]})
    r = c.post("/open", data={})
    ids = list(dict.fromkeys(re.findall(r'name="(v\d)"', r.text)))
    r = c.post("/vervolg", data={i: "stijgers" for i in ids})
    assert "Drie heiligen voor jou" in r.text


def test_keuze_buiten_de_eigen_top3_wordt_genegeerd():
    db, app = maak()
    c = kind(app)
    r = naar_keuze(c, "Uil")
    top = set(re.findall(r'name="gekozen" value="([^"]+)"', r.text))
    vreemd = next(h.qid for h in H if h.qid not in top)
    c.post("/keuze", data={"gekozen": vreemd, "want": "x"})
    assert stap_van(db, "kind1") == "keuze" and not spel.gekozen_heiligen(db)


def test_geen_past_mag_maar_een_keer_ook_met_een_directe_post():
    gesteld = []

    def llm(systeem, gegevens):
        gesteld.append(systeem[:20])
        raise __import__("durfheilig.llm", fromlist=["LlmFout"]).LlmFout("uit")
    db, app = maak(llm)
    c = kind(app)
    naar_keuze(c, "Uil")
    c.post("/geen-past")
    aantal = len(gesteld)
    ids = list(dict.fromkeys(re.findall(r'name="(v\d)"', c.get("/").text)))
    c.post("/vervolg", data={i: "plus" for i in ids})
    na_ronde_twee = len(gesteld)
    c.post("/geen-past"); c.post("/geen-past")
    assert len(gesteld) == na_ronde_twee and aantal > 0
    assert spel.invulling(db, spel.speler_voor(db, "kind1")["id"])["extra_ronde"] == 1


def test_nee_want_uit_de_keuzepagina_bereikt_de_tweede_ronde():
    db, app = maak(None)
    c = kind(app)
    r = naar_keuze(c, "Uil")
    assert 'formaction="/geen-past"' in r.text
    qids = re.findall(r'name="gekozen" value="([^"]+)"', r.text)
    c.post("/geen-past", data={f"niet_{qids[0]}": "te streng", f"niet_{qids[1]}": "saai"})
    m = spel.match_van(db, spel.speler_voor(db, "kind1")["id"])
    assert m["afgewezen"] == {qids[0]: "te streng", qids[1]: "saai", qids[2]: ""}


@pytest.mark.parametrize("groepen,toegestaan", [("notadmins", False), ("admins", True), ("durfheilig, admins", True), ("administrators", False)])
def test_beheer_vergelijkt_groepen_exact(groepen, toegestaan):
    _, app = maak()
    assert (kind(app).get("/beheer", headers={"remote-groups": groepen}).status_code == 200) is toegestaan


def test_te_lange_tekst_wordt_afgekapt():
    db, app = maak(None)
    c = kind(app)
    c.post("/welkom", data={"nickname": "N" * 80})
    sp = spel.speler_voor(db, "kind1")
    assert len(db.q("select nickname from speler where id = ?", [sp["id"]])[0]["nickname"]) == 20
    naar_keuze(kind(app, "x"), "Kort")
    c2 = kind(app, "y")
    c2.post("/welkom", data={"nickname": "Lang"}); c2.post("/voorkeur", data={"voorkeur": "man"})
    for _ in range(12):
        vid = re.search(r'name="vid" value="(\w+)"', c2.get("/").text).group(1)
        c2.post("/vraag", data={"vid": vid, "kant": "min"})
    c2.post("/interesses", data={"interesse": V.interesses[:2]})
    c2.post("/open", data={"a1": "a" * 5000, "a2": "b" * 5000})
    antw = spel.invulling(db, spel.speler_voor(db, "y")["id"])["open_antwoorden"]
    assert [len(t) for t in antw] == [200, 200]


def test_bijnaam_botsing_in_de_database_geeft_melding_geen_fout():
    db = spel.open_db()
    a, b = spel.speler_voor(db, "a"), spel.speler_voor(db, "b")
    spel.zet_nickname(db, a["id"], "Vos")
    with pytest.raises(spel.NicknameBezet):
        spel.zet_nickname(db, b["id"], "VOS")


def test_bewaar_weigert_een_onbekende_kolom():
    db = spel.open_db()
    sp = spel.speler_voor(db, "a")
    with pytest.raises(ValueError):
        spel.bewaar(db, sp["id"], **{"stap = 'klaar', speler_id": 1})


def test_twee_keer_eerste_bezoek_maakt_een_speler():
    db = spel.open_db()
    assert spel.speler_voor(db, "a")["id"] == spel.speler_voor(db, "a")["id"]
    assert len(db.q("select * from invulling")) == 1
