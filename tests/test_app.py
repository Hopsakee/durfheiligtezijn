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
    assert c.get("/quiz").status_code == 200
    c.post("/welkom", data={"nickname": nick})
    c.post("/voorkeur", data={"voorkeur": voorkeur})
    for _ in range(12):
        html = c.get("/quiz").text
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
    assert "✔ Jouw heilige" in c.get("/mijn").text


def test_voortgang_blijft_bewaard_en_hervat_op_dezelfde_stap():
    _, app = maak()
    c = kind(app)
    c.post("/welkom", data={"nickname": "Uil"})
    c.post("/voorkeur", data={"voorkeur": "man"})
    html = c.get("/quiz").text
    vid = re.search(r'name="vid" value="(\w+)"', html).group(1)
    c.post("/vraag", data={"vid": vid, "kant": "min"})
    nieuw = kind(app)                       # same account, new browser
    assert "Vraag 2 van 12" in nieuw.get("/").text


def test_stappen_overslaan_kan_niet():
    _, app = maak()
    c = kind(app)
    c.post("/voorkeur", data={"voorkeur": "man"})        # still on the welcome screen
    assert "Welkom" in c.get("/quiz").text
    c.post("/vervolg", data={})
    assert "Welkom" in c.get("/quiz").text
    assert c.get("/mijn").url.path == "/quiz"


def test_interesses_moeten_twee_of_drie_zijn():
    _, app = maak()
    c = kind(app)
    c.post("/welkom", data={"nickname": "Uil"}); c.post("/voorkeur", data={"voorkeur": "man"})
    for _ in range(12):
        vid = re.search(r'name="vid" value="(\w+)"', c.get("/quiz").text).group(1)
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
            vid = re.search(r'name="vid" value="(\w+)"', c.get("/quiz").text).group(1)
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
    assert gewoon.get("/beheer", headers={"remote-groups": "durfte"}).status_code == 403
    r = gewoon.get("/beheer", headers={"remote-groups": "admins,durfte"})
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
    assert "zorgelijke zin" not in c.get("/quiz").text and "zorgelijke zin" not in c.get("/mijn").text
    assert "LLM-uitleg" in c.get("/mijn").text
    assert "zorgelijke zin" in kind(app, "x").get("/beheer", headers={"remote-groups": "admins"}).text


def naar_keuze(c, nick):
    c.post("/welkom", data={"nickname": nick}); c.post("/voorkeur", data={"voorkeur": "man"})
    for _ in range(12):
        vid = re.search(r'name="vid" value="(\w+)"', c.get("/quiz").text).group(1)
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
    assert "Vraag 1 van 12" in c.get("/quiz").text


def test_vervolgantwoord_met_vreemde_waarde_telt_niet_en_het_spel_loopt_door():
    db, app = maak()
    c = kind(app)
    for _ in range(1):
        pass
    c.post("/welkom", data={"nickname": "Uil"}); c.post("/voorkeur", data={"voorkeur": "man"})
    for _ in range(12):
        vid = re.search(r'name="vid" value="(\w+)"', c.get("/quiz").text).group(1)
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
    ids = list(dict.fromkeys(re.findall(r'name="(v\d)"', c.get("/quiz").text)))
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


@pytest.mark.parametrize("groepen,toegestaan", [("notadmins", False), ("admins", True), ("durfte, admins", True), ("administrators", False), ("durfte", False), ("durfheilig-leiding", False), ("durfte-leiding", True), ("leiding", False)])
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
        vid = re.search(r'name="vid" value="(\w+)"', c2.get("/quiz").text).group(1)
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


def test_export_en_verwijderen_alleen_voor_leiding_en_alleen_met_bevestiging():
    db, app = maak(None)
    c = kind(app, "a")
    speel(c, "Aap")
    assert c.get("/beheer/export").status_code == 403
    assert c.post("/beheer/verwijder", data={"bevestig": "VERWIJDER"}).status_code == 403
    assert len(db.q("select * from speler")) == 1
    leiding = {"remote-groups": "durfte-leiding"}
    data = c.get("/beheer/export", headers=leiding).json()
    assert [s["gebruikersnaam"] for s in data["spelers"]] == ["a"] and data["matches"][0]["gekozen"]
    c.post("/beheer/verwijder", data={"bevestig": "nee"}, headers=leiding)
    assert len(db.q("select * from speler")) == 1
    c.post("/beheer/verwijder", data={"bevestig": "VERWIJDER"}, headers=leiding)
    assert not db.q("select * from speler") and not db.q("select * from invulling") and not db.q("select * from match")
    assert spel.gekozen_heiligen(db) == set()
    assert "Welkom" in kind(app, "a").get("/").text      # same account can start afresh


def test_verwijderen_weigert_een_verzoek_van_een_andere_site_en_meldt_een_verkeerd_woord():
    db, app = maak(None)
    c = kind(app, "a")
    speel(c, "Aap")
    leiding = {"remote-groups": "durfte-leiding"}
    assert c.post("/beheer/verwijder", data={"bevestig": "VERWIJDER"}, headers={**leiding, "sec-fetch-site": "cross-site"}).status_code == 403
    assert "Niets gewist" in c.post("/beheer/verwijder", data={"bevestig": "nee"}, headers=leiding).text
    assert len(db.q("select * from speler")) == 1


def test_na_verwijderen_staan_de_antwoorden_niet_meer_in_het_bestand(tmp_path):
    pad = tmp_path / "spel.db"
    db = spel.open_db(pad)
    app = maak_app(db, H, V, None, random.Random(1))
    c = kind(app, "a")
    speel(c, "GeheimeBijnaam")
    c.post("/beheer/verwijder", data={"bevestig": "VERWIJDER"}, headers={"remote-groups": "admins"})
    alles = b"".join(f.read_bytes() for f in tmp_path.iterdir())      # database and write-ahead log
    assert b"GeheimeBijnaam" not in alles and b"tekenen" not in alles


def test_begeleider_ziet_een_link_naar_het_overzicht_en_een_kind_niet():
    _, app = maak(None)
    assert "/beheer" not in kind(app, "k").get("/").text
    assert 'href="/beheer"' in kind(app, "l").get("/", headers={"remote-groups": "durfte-leiding"}).text


def test_afbeeldingen_worden_helemaal_getoond_niet_bijgesneden():
    from durfheilig.app import CSS
    assert "object-fit:contain" in CSS and "object-fit:cover" not in CSS


def test_gekozen_heilige_staat_bovenaan_en_heeft_de_dikke_rand():
    from durfheilig.app import CSS
    db, app = maak(None)
    c = kind(app)
    _, gekozen, qids = speel(c, "Vos", kiezen=2)          # the third card
    pagina = c.get("/mijn").text
    eerste = re.findall(r'href="/heilige/([^"]+)"', pagina)
    assert eerste[0] == gekozen and set(eerste) == set(qids)
    assert pagina.count("kaart gekozen") == 1 and pagina.index("kaart gekozen") < pagina.index(f"/heilige/{qids[0]}")
    assert "border:6px solid" in CSS


def test_meer_over_een_heilige_alleen_voor_de_eigen_drie_en_zonder_leidingsnotities():
    db, app = maak(None)
    c = kind(app)
    r, gekozen, qids = speel(c, "Vos")
    h = next(x for x in H if x.qid == gekozen)
    pagina = c.get(f"/heilige/{gekozen}")
    assert pagina.status_code == 200 and h.naam in pagina.text
    assert "Waarom een voorbeeld?" in pagina.text and "<details" in pagina.text
    for veld in ("waarschuwing_voor_leiding", "gespreksvraag", "open_vragen", "verdieping"):
        waarde = h.record.get(veld)
        stukken = [waarde] if isinstance(waarde, str) else list(waarde.values()) if isinstance(waarde, dict) else list(waarde or [])
        assert all(str(x)[:40] not in pagina.text for x in stukken), veld
    vreemd = next(x.qid for x in H if x.qid not in qids)
    assert c.get(f"/heilige/{vreemd}").status_code == 404
    assert c.get("/heilige/Q0").status_code == 404
    assert c.get(f"/heilige/{vreemd}", headers={"remote-groups": "durfte-leiding"}).status_code == 200


def test_meer_info_toont_alleen_wikipedia_links_met_veilige_attributen():
    from durfheilig.app import info
    h = next(x for x in H if x.record.get("lees_zelf"))
    bron = h.record["lees_zelf"] + [{"titel": "Evil", "url": "https://evil.example/x"}, {"titel": "Http", "url": "http://nl.wikipedia.org/x"}]
    nep = type(h)(h.qid, h.naam, h.geslacht, h.assen, h.interesses, {**h.record, "lees_zelf": bron})
    html = str(info(nep))
    assert "evil.example" not in html and "http://nl.wikipedia" not in html
    assert 'rel="noopener noreferrer"' in html


def test_trage_stappen_tonen_een_laadscherm_en_snelle_niet():
    _, app = maak(None)
    c = kind(app)
    assert 'id="laden"' in c.get("/quiz").text and 'data-laad="' not in c.get("/quiz").text
    c.post("/welkom", data={"nickname": "Uil"}); c.post("/voorkeur", data={"voorkeur": "man"})
    for _ in range(12):
        vid = re.search(r'name="vid" value="(\w+)"', c.get("/quiz").text).group(1)
        c.post("/vraag", data={"vid": vid, "kant": "min"})
    c.post("/interesses", data={"interesse": V.interesses[:2]})
    assert 'data-laad="' in c.get("/quiz").text                                    # the open-questions step calls Gemini
    r = c.post("/open", data={})
    assert 'data-laad="' in r.text
    ids = list(dict.fromkeys(re.findall(r'name="(v\d)"', r.text)))
    r = c.post("/vervolg", data={i: "min" for i in ids})
    assert 'formaction="/geen-past"' in r.text and 'data-laad="' in r.text


def test_mislukte_gemini_poging_wordt_gelogd_zonder_tekst_van_de_jongere(caplog):
    import logging
    from durfheilig.llm import LlmFout
    def llm(systeem, gegevens):
        raise LlmFout("Gemini-aanroep mislukt: HTTPStatusError (HTTP 404)")
    db, app = maak(llm)
    c = kind(app)
    with caplog.at_level(logging.INFO, logger="durfheilig.llm"):
        naar_keuze(c, "Uil")
    tekst = caplog.text
    assert "HTTP 404" in tekst and "vaste terugval" in tekst and "tekenen" not in tekst and "Uil" not in tekst
    sp = spel.speler_voor(db, "kind1")
    assert spel.match_van(db, sp["id"])["via_llm"] == 0


def test_beheer_toont_of_de_uitleg_van_gemini_kwam():
    db, app = maak(None)
    speel(kind(app, "a"), "Aap")
    assert "vaste tekst" in kind(app, "x").get("/beheer", headers={"remote-groups": "admins"}).text


def test_alle_kinderen_krijgen_alle_verhalen_van_hun_heilige_te_lezen():
    from durfheilig.app import info
    for h in H:
        html = str(info(h))
        for x in h.record.get("haakjes", []):
            assert x["kort"] in html
            if x.get("meer"):
                assert f"<summary>{x['kort']}" in html, h.naam
        if h.record.get("wat_er_nog_van_over_is"):
            assert "Wat er nog van over is" in html, h.naam
        for veld in ("waarschuwing_voor_leiding", "gespreksvraag"):
            assert str(h.record.get(veld) or "x")[:40] not in html, (h.naam, veld)


def test_linkfilter_weigert_lookalike_hosts_en_backslash_trucs():
    from durfheilig.app import info
    h = H[0]
    bron = [{"titel": t, "url": u} for t, u in [("ok", "https://nl.wikipedia.org/wiki/X"), ("nep", "https://notwikipedia.org/x"),
            ("slash", "https://evil.example\\@nl.wikipedia.org/x"), ("sub", "https://evil.wikipedia.org.evil.example/x")]]
    nep = type(h)(h.qid, h.naam, h.geslacht, h.assen, h.interesses, {**h.record, "lees_zelf": bron})
    html = str(info(nep))
    assert "nl.wikipedia.org/wiki/X" in html and "notwikipedia" not in html and "evil" not in html


def test_het_laadscherm_sluit_zichzelf_en_met_een_tik():
    _, app = maak()
    html = kind(app).get("/").text
    assert "setTimeout" in html and 'onclick="this.hidden=true"' in html


def menu_hrefs(html):
    blok = re.search(r'<details class="menu geen-print">(.*?)</details>', html, re.S)
    return re.findall(r'href="([^"]+)"', blok.group(1)) if blok else None


def test_kind_landt_in_de_quiz_en_vindt_alles_via_het_menu_en_de_startpagina():
    db, app = maak(None)
    c = kind(app)
    assert "Welkom" in c.get("/").text                                   # the group-app link goes straight to the quiz
    assert menu_hrefs(c.get("/").text) == ["/menu", "/quiz", "/spel"]    # no 'Mijn heilige' before a choice was made
    start = c.get("/menu").text
    assert 'href="/quiz"' in start and 'href="/spel"' in start and "/beheer" not in start and "Je quiz is nog bezig" in start
    speel(c, "Vos")
    assert menu_hrefs(c.get("/").text) == ["/menu", "/quiz", "/mijn", "/spel"]
    assert 'href="/mijn"' in c.get("/menu").text and "Je quiz is af" in c.get("/menu").text


def test_leiding_landt_op_de_startpagina_met_alles_erin_en_kan_de_quiz_nog_spelen():
    db, app = maak(None)
    c = kind(app, "l")
    c.headers.update({"remote-groups": "durfte-leiding"})
    start = c.get("/").text
    for pad in ("/quiz", "/spel", "/beheer", "/beheer/spel", "/beheer/tv", "/beheer/print", "/beheer/export"):
        assert f'href="{pad}"' in start, pad
    assert "Voor begeleiders" in start and "Welkom" not in start
    assert "Welkom" in c.get("/quiz").text
    speel(c, "Lead")                                                       # leaders keep their quiz flow through /quiz
    assert "Houd je heilige geheim" in c.get("/quiz").text


def test_het_menu_staat_op_elke_pagina_behalve_de_tv_en_toont_een_kind_nooit_beheerlinks():
    db, app = maak(None)
    k = kind(app, "k")
    _, gekozen, _ = speel(k, "Vos")
    for pad in ("/", "/quiz", "/menu", "/mijn", f"/heilige/{gekozen}", "/spel"):
        links = menu_hrefs(k.get(pad).text)
        assert links and "/menu" in links, pad
        assert not any(x.startswith("/beheer") for x in links), pad
    l = kind(app, "boss")
    l.headers.update({"remote-groups": "durfte-leiding"})
    for pad in ("/", "/menu", "/beheer", "/beheer/spel", "/beheer/print", "/spel"):
        links = menu_hrefs(l.get(pad).text)
        assert links and "/beheer/tv" in links and "/beheer/spel" in links, pad
    assert menu_hrefs(l.get("/beheer/tv").text) is None                    # the tv screen is clean


def test_het_menu_van_de_ene_bezoeker_lekt_niet_naar_de_volgende():
    db, app = maak(None)
    l = kind(app, "boss"); l.headers.update({"remote-groups": "durfte-leiding"})
    k = kind(app, "kid")
    for _ in range(3):
        assert "/beheer/tv" in menu_hrefs(l.get("/menu").text)
        assert not any(x.startswith("/beheer") for x in menu_hrefs(k.get("/menu").text))


def test_een_leider_die_alleen_rondkijkt_komt_niet_in_de_lijst_met_deelnemers():
    db, app = maak(None)
    l = kind(app, "kijker"); l.headers.update({"remote-groups": "durfte-leiding"})
    for pad in ("/", "/menu", "/beheer/tv", "/beheer/spel", "/beheer/print"):
        l.get(pad)
    assert db.q("select * from speler") == []


def test_dev_link_in_het_menu_komt_alleen_uit_de_dev_laag():
    from durfheilig.dev import maak_dev_app
    dev = TestClient(maak_dev_app(spel.open_db(), None), follow_redirects=True)
    dev.get("/dev/als/kind1")
    assert "/dev" in menu_hrefs(dev.get("/menu").text)
    _, app = maak()
    assert "/dev" not in menu_hrefs(kind(app).get("/menu").text)


def test_de_polls_vragen_het_profiel_voor_het_menu_niet_op(monkeypatch):
    db, app = maak(None)
    c = kind(app)
    speel(c, "Vos")
    aanroepen = []
    echt = spel.profiel_van
    monkeypatch.setattr(spel, "profiel_van", lambda *a: aanroepen.append(1) or echt(*a))
    c.get("/spel/inhoud", headers={"hx-request": "true"})
    assert aanroepen == []                      # fragments have no menu, so no lookup
    c.get("/menu")
    assert len(aanroepen) == 1                  # a page with a menu looks the viewer up once, however often it asks


def test_de_centrale_controle_in_de_login_dekt_elk_beheerpad_en_elke_post():
    db, app = maak(None)
    c = kind(app)
    for pad in ("/beheer", "/beheer/export", "/beheer/spel/inhoud"):
        assert c.get(pad).status_code == 403, pad
    @app.route("/beheer/proef")                                              # a route added later is covered without any check of its own
    def proef():
        return "geheim"
    assert c.get("/beheer/proef").status_code == 403 and "geheim" not in c.get("/beheer/proef").text
    boss = kind(app, "boss"); boss.headers.update({"remote-groups": "durfte-leiding"})
    assert boss.get("/beheer/proef").text == "geheim"
    assert kind(app).get("/beheerx").status_code == 404                     # only the /beheer prefix is guarded
    assert c.post("/welkom", data={"nickname": "Vos"}, headers={"sec-fetch-site": "cross-site"}).status_code == 403
    assert c.post("/welkom", data={"nickname": "Vos"}, headers={"sec-fetch-site": "same-site"}).status_code == 403
    assert c.post("/welkom", data={"nickname": "Vos"}, headers={"sec-fetch-site": "same-origin"}).status_code == 200
    assert c.get("/quiz", headers={"sec-fetch-site": "cross-site"}).status_code == 200      # reading is not state-changing
