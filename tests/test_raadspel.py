import random
import re

import pytest

from durfheilig import db as spel
from durfheilig.app import maak_app
from durfheilig.data import laad_heiligen, laad_vragen
from durfheilig.raadspel import MIN_SPELERS, meerderheid, punten, trek_bord, volgende_fase, volgorde_rondes
from test_app import H, V, kind, speel

LEIDING = {"remote-groups": "durfte-leiding"}


def spel_met(namen, leiding_namen=(), llm=None):
    """A database with finished players (each chose a saint) and the app on top of it."""
    db = spel.open_db()
    app = maak_app(db, H, V, llm, random.Random(7))
    clients = {}
    for n in list(namen) + list(leiding_namen):
        c = kind(app, f"acct-{n}")
        if n in leiding_namen:
            c.headers.update(LEIDING)
        speel(c, f"Nick-{n}")
        clients[n] = c
    return db, app, clients


def frag(c, pad):
    """What a polling page gets: the fragment, as htmx asks for it."""
    return c.get(pad, headers={"hx-request": "true"}).text


def volgende(boss):
    """Press the leader's button the way the page does, with the token of the step it shows."""
    html = frag(boss, "/beheer/spel/inhoud")
    van = re.search(r'name="van" value="([^"]*)"', html)
    return boss.post("/beheer/spel/volgende", data={"van": van.group(1) if van else ""})


def leider(app, naam="boss"):
    c = kind(app, naam)
    c.headers.update(LEIDING)
    return c


def juist_van(db):
    return {s["id"]: s["gekozen"] for s in spel.spelers_klaar(db)}


def huidige(db):
    st = spel.spel_status(db)
    return next(r for r in spel.rondes(db) if r["id"] == st["huidige_ronde"])


def stem(db, clients, qid_voor, ronde, alleen=None):
    for naam, c in clients.items():
        if alleen is None or naam in alleen:
            c.post("/spel/stem", data={"qid": qid_voor(naam)})


# ------------------------------------------------------------------ de regels

def test_bord_heeft_2n_heiligen_met_alle_gekozen_en_geen_dubbele():
    alle = [h.qid for h in H]
    gekozen = alle[:8]
    bord = trek_bord(gekozen, alle, random.Random(1))
    assert len(bord) == 16 and len({q for q, _ in bord}) == 16
    assert {q for q, g in bord if g} == set(gekozen) and not {q for q, g in bord if not g} & set(gekozen)


def test_bord_zet_de_gekozen_heiligen_niet_vooraan():
    alle = [h.qid for h in H]
    eerste_is_gekozen = [trek_bord(alle[:6], alle, random.Random(s))[0][1] for s in range(40)]
    assert 0 < sum(eerste_is_gekozen) < 40
    posities = {i for s in range(40) for i, (_, g) in enumerate(trek_bord(alle[:6], alle, random.Random(s))) if g}
    assert len(posities) > 6


def test_bord_weigert_als_er_te_weinig_heiligen_over_zijn():
    with pytest.raises(ValueError):
        trek_bord(["a", "b", "c"], ["a", "b", "c", "d"], random.Random(1))


def test_meerderheid_is_meer_dan_de_helft_en_precies_de_helft_telt_niet():
    assert meerderheid("a", ["a", "a", "b"]) and not meerderheid("a", ["a", "b"]) and not meerderheid("a", [])
    assert not meerderheid("a", ["a", "b", "c", "d"])


def test_punten_twee_na_ronde_een_een_na_ronde_twee_anders_nul():
    assert punten("a", ["a", "a", "b"], ["b"]) == 2
    assert punten("a", ["b", "b", "a"], ["a", "a", "b"]) == 1
    assert punten("a", ["b", "c"], ["c", "b"]) == 0
    assert punten("a", [], []) == 0


def test_fasen_volgen_elkaar_op_en_eindigen_na_onthulling():
    assert [volgende_fase(f) for f in ("overleg1", "uitslag1", "vragen", "overleg2", "uitslag2")] == ["uitslag1", "vragen", "overleg2", "uitslag2", "onthuld"]
    assert volgende_fase("onthuld") is None


def test_volgorde_is_willekeurig_maar_de_gekozen_eerste_staat_voorop():
    assert volgorde_rondes([1, 2, 3, 4], 3, random.Random(1))[0] == 3
    assert len({tuple(volgorde_rondes([1, 2, 3, 4, 5], None, random.Random(s))) for s in range(20)}) > 5


# ------------------------------------------------------------------ het spel zelf

def test_start_vraagt_minstens_drie_deelnemers_en_alleen_van_de_leiding():
    db, app, clients = spel_met(["a", "b"])
    boss = leider(app)
    boss.post("/beheer/spel/start", data={"eerste": ""})
    assert spel.spel_status(db) is None and len(spel.spelers_klaar(db)) < MIN_SPELERS
    assert clients["a"].post("/beheer/spel/start", data={}).status_code == 403


def test_kinderen_komen_niet_bij_tv_bediening_print_of_uitleg():
    db, app, clients = spel_met(["a", "b", "c"])
    c = clients["a"]
    for pad in ("/beheer/tv", "/beheer/tv/inhoud", "/beheer/spel", "/beheer/spel/inhoud", "/beheer/print", "/beheer/speler/1"):
        assert c.get(pad).status_code == 403, pad
    for pad in ("/beheer/spel/start", "/beheer/spel/volgende", "/beheer/spel/reset"):
        assert c.post(pad, data={}).status_code == 403, pad


def test_een_heel_spel_van_start_tot_groepsscore():
    db, app, clients = spel_met(["a", "b", "c", "d"])
    boss, tv = leider(app), leider(app, "tv")
    juist = juist_van(db)
    uit = {s["id"]: s["nickname"] for s in spel.spelers_klaar(db)}
    boss.post("/beheer/spel/start", data={"eerste": ""})
    bord = spel.bord_rijen(db)
    assert len(bord) == 8 and {juist[i] for i in juist} <= {b["qid"] for b in bord}
    assert "Het bord" in frag(tv, "/beheer/tv/inhoud") and "Doe mee op je telefoon" in frag(tv, "/beheer/tv/inhoud")
    boss.post("/beheer/spel/start", data={"eerste": ""})                               # a second start changes nothing
    assert spel.bord_rijen(db) == bord
    volgende(boss)                                                  # board -> round 1
    totaal = 0
    for n in range(4):
        r = huidige(db)
        nick = r["nickname"]
        assert r["volgorde"] == n and r["fase"] == "overleg1"
        eigenaar = next(naam for naam, c in clients.items() if frag(c, "/spel/inhoud").count("gaat over jou"))
        goed = juist[r["speler_id"]]
        # stemronde 1: round 1 everyone but the subject votes the right saint
        for naam, c in clients.items():
            if naam != eigenaar:
                c.post("/spel/stem", data={"qid": goed})
        tvtekst = frag(tv, "/beheer/tv/inhoud")
        assert "3 van 3 hebben gestemd" in tvtekst and "×" not in tvtekst and "juist" not in tvtekst and f"✔ {nick}" not in tvtekst
        volgende(boss)                                              # uitslag1
        assert "3×" in frag(tv, "/beheer/tv/inhoud")
        volgende(boss); volgende(boss)         # vragen, overleg2
        volgende(boss); volgende(boss)         # uitslag2, onthuld
        assert huidige(db)["fase"] == "onthuld" and huidige(db)["punten"] == 2
        tvtekst = frag(tv, "/beheer/tv/inhoud")
        assert f"✔ {nick}" in tvtekst and "tegel juist" in tvtekst and "2 punten" in tvtekst
        totaal += 2
        volgende(boss)
    assert spel.spel_status(db)["status"] == "plaat"
    plaat = frag(tv, "/beheer/tv/inhoud")
    assert all(nick in plaat for nick in uit.values())
    volgende(boss)
    einde = frag(tv, "/beheer/tv/inhoud")
    assert f"{totaal} van de 8 punten" in einde and spel.spel_status(db)["status"] == "einde"
    assert "Bedankt voor het spelen" in frag(clients["a"], "/spel/inhoud")


def test_de_deelnemer_van_de_ronde_stemt_niet_en_ziet_dat_de_ronde_over_haar_gaat():
    db, app, clients = spel_met(["a", "b", "c"])
    boss = leider(app)
    boss.post("/beheer/spel/start", data={"eerste": ""}); volgende(boss)
    r = huidige(db)
    eigen = next(n for n, c in clients.items() if "gaat over jou" in frag(c, "/spel/inhoud"))
    assert "tegelknop" not in frag(clients[eigen], "/spel/inhoud")
    clients[eigen].post("/spel/stem", data={"qid": spel.bord_rijen(db)[0]["qid"]})
    assert spel.stemmen(db, r["id"], 1) == []
    for n, c in clients.items():
        if n != eigen:
            assert "tegelknop" in frag(c, "/spel/inhoud") and r["nickname"] in frag(c, "/spel/inhoud")


def test_stemmen_mag_alleen_in_een_stemfase_op_een_heilige_van_het_bord_en_opnieuw_stemmen_vervangt():
    db, app, clients = spel_met(["a", "b", "c"])
    boss = leider(app)
    boss.post("/beheer/spel/start", data={"eerste": ""})
    clients["a"].post("/spel/stem", data={"qid": spel.bord_rijen(db)[0]["qid"]})         # board shown, no round yet
    volgende(boss)
    r = huidige(db)
    stemmer = next(n for n, c in clients.items() if "tegelknop" in frag(c, "/spel/inhoud"))
    c = clients[stemmer]
    assert spel.stemmen(db, r["id"], 1) == []
    buiten = next(h.qid for h in H if h.qid not in {b["qid"] for b in spel.bord_rijen(db)})
    c.post("/spel/stem", data={"qid": buiten}); c.post("/spel/stem", data={"qid": ""})
    assert spel.stemmen(db, r["id"], 1) == []
    q1, q2 = [b["qid"] for b in spel.bord_rijen(db)[:2]]
    c.post("/spel/stem", data={"qid": q1}); c.post("/spel/stem", data={"qid": q2})
    assert [x["qid"] for x in spel.stemmen(db, r["id"], 1)] == [q2]
    volgende(boss)                                                    # uitslag1: voting closed
    c.post("/spel/stem", data={"qid": q1})
    assert [x["qid"] for x in spel.stemmen(db, r["id"], 1)] == [q2]


def test_punten_een_na_ronde_twee_en_nul_als_de_groep_het_mist():
    db, app, clients = spel_met(["a", "b", "c"])
    boss = leider(app)
    juist = juist_van(db)
    boss.post("/beheer/spel/start", data={"eerste": ""}); volgende(boss)
    scores = []
    for _ in range(3):
        r = huidige(db)
        goed = juist[r["speler_id"]]
        fout = next(b["qid"] for b in spel.bord_rijen(db) if b["qid"] != goed)
        stemmers = [c for n, c in clients.items() if "tegelknop" in frag(c, "/spel/inhoud")]
        wat = {0: (fout, goed), 1: (fout, fout), 2: (goed, goed)}[len(scores)]
        for c in stemmers:
            c.post("/spel/stem", data={"qid": wat[0]})
        volgende(boss); volgende(boss); volgende(boss)   # -> overleg2
        for c in stemmers:
            c.post("/spel/stem", data={"qid": wat[1]})
        volgende(boss); volgende(boss)
        scores.append(huidige(db)["punten"])
        volgende(boss)
    assert scores == [1, 0, 2]


def test_nooit_te_zien_wie_op_wat_stemde():
    db, app, clients = spel_met(["a", "b", "c", "d"])
    boss, tv = leider(app), leider(app, "tv")
    boss.post("/beheer/spel/start", data={"eerste": ""}); volgende(boss)
    r = huidige(db)
    stemmers = [n for n, c in clients.items() if "gaat over jou" not in frag(c, "/spel/inhoud")]
    q = spel.bord_rijen(db)
    for i, n in enumerate(stemmers):
        clients[n].post("/spel/stem", data={"qid": q[i]["qid"]})                      # everyone votes differently
    accounts = {s["gebruikersnaam"] for s in spel.spelers_klaar(db)}
    for _ in range(5):
        for tekst in (frag(tv, "/beheer/tv/inhoud"), frag(boss, "/beheer/spel/inhoud"), frag(clients[stemmers[0]], "/spel/inhoud")):
            for n in stemmers:
                assert f"Nick-{n}" not in tekst, n                                       # no voter's nickname next to votes
            assert not any(acc in tekst for acc in accounts)
        volgende(boss)
        if huidige(db)["fase"] == "onthuld":
            break


def test_wie_de_uitleg_las_stemt_in_die_ronde_niet_mee():
    db, app, clients = spel_met(["a", "b", "c"], leiding_namen=["lead"])
    ids = {s["gebruikersnaam"]: s["id"] for s in spel.spelers_klaar(db)}
    boss = leider(app)
    assert "stem je niet mee" in clients["lead"].get(f"/beheer/speler/{ids['acct-a']}").text      # opening it is reading it
    boss.post("/beheer/spel/start", data={"eerste": str(ids["acct-a"])}); volgende(boss)
    assert huidige(db)["speler_id"] == ids["acct-a"]
    assert "stemt deze ronde niet mee" in frag(clients["lead"], "/spel/inhoud") and "tegelknop" not in frag(clients["lead"], "/spel/inhoud")
    clients["lead"].post("/spel/stem", data={"qid": spel.bord_rijen(db)[0]["qid"]})
    assert spel.stemmen(db, huidige(db)["id"], 1) == []
    assert "tegelknop" in frag(clients["b"], "/spel/inhoud")


def test_wie_nog_geen_heilige_koos_doet_niet_mee():
    db, app, clients = spel_met(["a", "b", "c"])
    laat = kind(app, "acct-laat")
    laat.post("/welkom", data={"nickname": "Laat"})
    leider(app).post("/beheer/spel/start", data={"eerste": ""})
    assert "doe je niet mee" in frag(laat, "/spel/inhoud").replace("Je doet niet mee", "doe je niet mee")
    assert "Het spel begint straks" not in frag(laat, "/spel/inhoud")


def test_voor_de_start_wachten_de_telefoons():
    db, app, clients = spel_met(["a", "b", "c"])
    assert "begint straks" in frag(clients["a"], "/spel/inhoud")
    assert "nog niet gestart" in leider(app).get("/beheer/tv/inhoud").text


def test_spel_opnieuw_beginnen_wist_het_spel_maar_niet_de_deelnemers_en_vraagt_om_het_woord():
    db, app, clients = spel_met(["a", "b", "c"])
    boss = leider(app)
    boss.post("/beheer/spel/start", data={"eerste": ""}); volgende(boss)
    boss.post("/beheer/spel/reset", data={"bevestig": "nee"})
    assert spel.spel_status(db) is not None
    assert boss.post("/beheer/spel/reset", data={"bevestig": "OPNIEUW"}, headers={"sec-fetch-site": "cross-site"}).status_code == 403
    boss.post("/beheer/spel/reset", data={"bevestig": "OPNIEUW"})
    assert spel.spel_status(db) is None and not spel.bord_rijen(db) and not spel.rondes(db) and len(spel.spelers_klaar(db)) == 3


def test_groep_verwijderen_wist_ook_het_spel_en_de_export_bevat_het():
    db, app, clients = spel_met(["a", "b", "c"])
    boss = leider(app)
    boss.post("/beheer/spel/start", data={"eerste": ""}); volgende(boss)
    clients["b"].post("/spel/stem", data={"qid": spel.bord_rijen(db)[0]["qid"]})
    data = boss.get("/beheer/export").json()
    assert len(data["bord"]) == 6 and len(data["rondes"]) == 3 and data["spel"][0]["status"] == "ronde"
    boss.post("/beheer/verwijder", data={"bevestig": "VERWIJDER"})
    for tabel in ("stem", "spelronde", "bord", "spel", "gelezen", "speler"):
        assert not db.q(f"select * from {tabel}"), tabel


def test_printversie_toont_het_genummerde_bord_pas_na_de_start():
    db, app, clients = spel_met(["a", "b", "c"])
    boss = leider(app)
    assert "nog niet" in boss.get("/beheer/print").text
    boss.post("/beheer/spel/start", data={"eerste": ""})
    t = boss.get("/beheer/print").text
    assert "1. " in t and "6. " in t and "Stembriefje" in t


def test_bediening_toont_voortgang_en_de_juiste_knoptekst_per_fase():
    db, app, clients = spel_met(["a", "b", "c"])
    boss = leider(app)
    assert "3 deelnemers hebben hun quiz af" in frag(boss, "/beheer/spel/inhoud")
    boss.post("/beheer/spel/start", data={"eerste": ""})
    assert "Start ronde 1" in frag(boss, "/beheer/spel/inhoud")
    volgende(boss)
    assert "0 van 2 hebben gestemd (nog niet iedereen)" in frag(boss, "/beheer/spel/inhoud")
    assert "Stemming sluiten en uitslag tonen" in frag(boss, "/beheer/spel/inhoud")


def test_leiding_ziet_het_raadspel_in_het_overzicht_en_de_pagina_polt_elke_twee_seconden():
    db, app, clients = spel_met(["a", "b", "c"])
    boss = leider(app)
    assert 'href="/beheer/spel"' in boss.get("/beheer").text and 'href="/beheer/speler/' in boss.get("/beheer").text
    for pad, c in (("/spel", clients["a"]), ("/beheer/tv", boss), ("/beheer/spel", boss)):
        assert 'hx-trigger="every 2s"' in c.get(pad).text, pad


def naar_fase(db, boss, fase):
    while huidige(db)["fase"] != fase:
        volgende(boss)


def test_een_tweede_tik_op_dezelfde_stap_en_een_verouderd_scherm_doen_niets():
    db, app, clients = spel_met(["a", "b", "c"])
    boss = leider(app)
    boss.post("/beheer/spel/start", data={"eerste": ""})
    html = frag(boss, "/beheer/spel/inhoud")
    van = re.search(r'name="van" value="([^"]*)"', html).group(1)
    boss.post("/beheer/spel/volgende", data={"van": van})
    boss.post("/beheer/spel/volgende", data={"van": van})                                  # the same tap again
    assert huidige(db)["fase"] == "overleg1"
    boss.post("/beheer/spel/volgende", data={})                                            # no token at all
    assert huidige(db)["fase"] == "overleg1"
    volgende(boss)
    assert huidige(db)["fase"] == "uitslag1"


def test_voor_de_onthulling_staat_nergens_welke_heilige_juist_is_en_zijn_de_tegels_gelijk():
    db, app, clients = spel_met(["a", "b", "c", "d"])
    boss, tv = leider(app), leider(app, "tv")
    boss.post("/beheer/spel/start", data={"eerste": ""}); volgende(boss)
    stemmers = [n for n, c in clients.items() if "gaat over jou" not in frag(c, "/spel/inhoud")]
    for fase in ("overleg1", "uitslag1", "vragen", "overleg2", "uitslag2"):
        naar_fase(db, boss, fase)
        for tekst in (frag(tv, "/beheer/tv/inhoud"), frag(clients[stemmers[0]], "/spel/inhoud")):
            assert "tegel juist" not in tekst and "✔ " not in tekst.replace("✔ Jouw", "") and "gekozen" not in tekst.lower().replace("gekozen: ", "")
            assert set(re.findall(r'class="(tegel[^"]*)"', tekst)) <= {"tegel", "tegel stem", "tegelknop"}
        if fase in ("overleg1", "overleg2"):
            assert "×" not in frag(tv, "/beheer/tv/inhoud")
        if fase == "uitslag2":
            assert "Punten tot nu toe: 0" in frag(tv, "/beheer/tv/inhoud")
        elif fase in ("uitslag1", "vragen", "uitslag2"):
            assert "×" in frag(tv, "/beheer/tv/inhoud")
    assert huidige(db)["punten"] is None
    volgende(boss)
    assert huidige(db)["punten"] is not None


def test_opnieuw_beginnen_houdt_gelezen_vast_en_de_export_laat_niet_zien_wie_wat_stemde():
    db, app, clients = spel_met(["a", "b", "c"], leiding_namen=["lead"])
    ids = {s["gebruikersnaam"]: s["id"] for s in spel.spelers_klaar(db)}
    boss = leider(app)
    clients["lead"].get(f"/beheer/speler/{ids['acct-a']}")
    boss.post("/beheer/spel/start", data={"eerste": ""}); volgende(boss)
    stemmer = next(n for n, c in clients.items() if "tegelknop" in frag(c, "/spel/inhoud"))
    clients[stemmer].post("/spel/stem", data={"qid": spel.bord_rijen(db)[0]["qid"]})
    data = boss.get("/beheer/export").json()
    assert data["stemmen"] and all(set(x) == {"spelronde_id", "qid", "stemronde"} for x in data["stemmen"]) and data["gelezen"]
    boss.post("/beheer/spel/reset", data={"bevestig": "OPNIEUW"})
    assert spel.lezers(db, ids["acct-a"]) == {"acct-lead"}


def test_wie_halverwege_klaar_komt_doet_niet_mee_en_telt_niet_mee_in_de_noemer():
    db, app, clients = spel_met(["a", "b", "c"])
    boss, tv = leider(app), leider(app, "tv")
    boss.post("/beheer/spel/start", data={"eerste": ""}); volgende(boss)
    voor = frag(tv, "/beheer/tv/inhoud")
    laat = kind(app, "acct-laat")
    speel(laat, "Nick-laat")
    assert "Je doet niet mee aan het spel" in frag(laat, "/spel/inhoud")
    laat.post("/spel/stem", data={"qid": spel.bord_rijen(db)[0]["qid"]})
    assert spel.stemmen(db, huidige(db)["id"], 1) == []
    assert "0 van 2 hebben gestemd" in frag(tv, "/beheer/tv/inhoud") and "Nick-laat" not in frag(tv, "/beheer/tv/inhoud")
    while spel.spel_status(db)["status"] != "plaat":
        volgende(boss)
    assert "Nick-laat" not in frag(tv, "/beheer/tv/inhoud")


def test_onbekende_of_enorme_deelnemer_geeft_404_voor_de_leiding():
    db, app, clients = spel_met(["a", "b", "c"])
    boss = leider(app)
    for sid in ("999", "0", "-5", "99999999999999999999999"):
        assert boss.get(f"/beheer/speler/{sid}").status_code == 404, sid


def test_stappen_die_de_stand_veranderen_weigeren_een_verzoek_van_een_andere_site():
    db, app, clients = spel_met(["a", "b", "c"])
    boss = leider(app)
    vreemd = {"sec-fetch-site": "cross-site"}
    assert boss.post("/beheer/spel/start", data={"eerste": ""}, headers=vreemd).status_code == 403 and spel.spel_status(db) is None
    boss.post("/beheer/spel/start", data={"eerste": ""}); volgende(boss)
    html = frag(boss, "/beheer/spel/inhoud")
    van = re.search(r'name="van" value="([^"]*)"', html).group(1)
    assert boss.post("/beheer/spel/volgende", data={"van": van}, headers=vreemd).status_code == 403 and huidige(db)["fase"] == "overleg1"
    stemmer = next(c for n, c in clients.items() if "tegelknop" in frag(c, "/spel/inhoud"))
    assert stemmer.post("/spel/stem", data={"qid": spel.bord_rijen(db)[0]["qid"]}, headers=vreemd).status_code == 403
    assert spel.stemmen(db, huidige(db)["id"], 1) == []


def test_een_bijnaam_wijzigen_kan_niet_meer_zodra_het_spel_loopt():
    db, app, clients = spel_met(["a", "b", "c"])
    leider(app).post("/beheer/spel/start", data={"eerste": ""})
    clients["a"].post("/welkom", data={"nickname": "Nieuw-naam"})
    assert next(s for s in spel.spelers_klaar(db) if s["gebruikersnaam"] == "acct-a")["nickname"] == "Nick-a"


def test_een_heilige_die_uit_de_data_verdwijnt_breekt_geen_scherm():
    db, app, clients = spel_met(["a", "b", "c"])
    boss = leider(app)
    boss.post("/beheer/spel/start", data={"eerste": ""})
    db.execute("update bord set qid = 'Q-bestaat-niet' where volgorde = 0")
    assert boss.get("/beheer/tv/inhoud", headers={"hx-request": "true"}).status_code == 200
    assert clients["a"].get("/spel/inhoud", headers={"hx-request": "true"}).status_code == 200


def test_veel_gelijktijdige_polls_geven_nooit_een_serverfout():
    """Phones and the tv all poll every 2 seconds; the one SQLite connection must survive that."""
    from concurrent.futures import ThreadPoolExecutor
    from starlette.testclient import TestClient
    db, app, clients = spel_met(["a", "b", "c"])
    leider(app).post("/beheer/spel/start", data={"eerste": ""})
    kop = {"hx-request": "true"}
    fouten = []

    def poll(i):
        with TestClient(app, headers={"remote-user": f"acct-{'abc'[i % 3]}", **({"remote-groups": "durfte-leiding"} if i % 2 else {})}) as c:
            for _ in range(40):
                for pad in ("/spel/inhoud", "/beheer/tv/inhoud" if i % 2 else "/spel/inhoud"):
                    r = c.get(pad, headers=kop)
                    if r.status_code != 200:
                        fouten.append((pad, r.status_code))
    with ThreadPoolExecutor(16) as pool:
        list(pool.map(poll, range(16)))
    assert fouten == []


def test_een_trage_gemini_aanroep_houdt_de_andere_telefoons_niet_vast():
    """The slow call runs off the event loop: while it waits, another request is answered at once.
    One client for both, so both share one event loop, as they do under uvicorn."""
    import threading
    import time
    from starlette.testclient import TestClient
    from durfheilig.llm import LlmFout

    def traag(systeem, gegevens):
        if "Bedenk" not in systeem:
            time.sleep(0.6)                                      # the final call is slow
        raise LlmFout("traag")
    db = spel.open_db()
    app = maak_app(db, H, V, traag, random.Random(7))
    with TestClient(app) as c:
        trage = {"remote-user": "acct-slow"}
        speel_tot_vervolg(c, trage)
        gedaan = []
        t = threading.Thread(target=lambda: gedaan.append(c.post("/vervolg", data={"v1": "min", "v2": "min", "v3": "min"}, headers=trage)))
        t.start()
        time.sleep(0.15)
        begin = time.monotonic()
        c.get("/health", headers={"remote-user": "acct-fast"})
        duur = time.monotonic() - begin
        t.join()
    assert duur < 0.3 and gedaan


def speel_tot_vervolg(c, kop):
    c.post("/welkom", data={"nickname": "Trage"}, headers=kop); c.post("/voorkeur", data={"voorkeur": "man"}, headers=kop)
    for _ in range(12):
        vid = re.search(r'name="vid" value="(\w+)"', c.get("/quiz", headers=kop).text).group(1)
        c.post("/vraag", data={"vid": vid, "kant": "min"}, headers=kop)
    c.post("/interesses", data={"interesse": V.interesses[:2]}, headers=kop)
    c.post("/open", data={}, headers=kop)


def test_een_uitleg_openen_via_een_link_van_een_andere_site_telt_niet_als_lezen():
    db, app, clients = spel_met(["a", "b", "c"])
    sid = spel.spelers_klaar(db)[0]["id"]
    boss = leider(app)
    r = boss.get(f"/beheer/speler/{sid}", headers={"sec-fetch-site": "cross-site"}, follow_redirects=False)
    assert spel.lezers(db, sid) == set() and r.status_code == 303 and r.headers["location"] == "/beheer"     # sent back, nothing shown
    boss.get(f"/beheer/speler/{sid}", headers={"sec-fetch-site": "same-origin"})
    assert spel.lezers(db, sid) == {"boss"}


def test_stemtegel_is_zelf_de_knop_zonder_losse_stemknop_eronder():
    """On a phone a separate "Stem op ..." button under each card overlapped the card: the card itself is the button now."""
    db, app, clients = spel_met(["a", "b", "c"])
    boss = leider(app)
    boss.post("/beheer/spel/start", data={"eerste": ""})
    volgende(boss)
    stemmer = next(n for n, c in clients.items() if "tegelknop" in frag(c, "/spel/inhoud"))
    c = clients[stemmer]
    html = frag(c, "/spel/inhoud")
    bord = spel.bord_rijen(db)
    assert html.count("<button") == len(bord)                         # one button per saint, no extra "Stem op" button
    assert "Stem op " not in html
    assert all(re.search(r'<button[^>]*class="tegel"[^>]*>.*?<img', html, re.S) for _ in [0])   # the card (image and name) sits inside the button
    qid = bord[0]["qid"]
    c.post("/spel/stem", data={"qid": qid})
    html = frag(c, "/spel/inhoud")
    assert html.count('aria-pressed="true"') == 1 and "Jouw keuze" in html
