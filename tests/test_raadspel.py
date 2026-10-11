import random
import re

import pytest

from durfheilig import db as spel
from durfheilig.app import maak_app
from durfheilig.data import laad_heiligen, laad_vragen
from durfheilig.raadspel import MIN_SPELERS, meerderheid, punten_voor, score_ronde, toeval_punten, trek_bord, volgende_fase, volgorde_rondes
from test_app import H, V, kind, speel

H_PER_QID = {h.qid: h for h in H}

LEIDING = {"remote-groups": "durfte-leiding"}


def spel_met(namen, leiding_namen=(), llm=None, voorkeuren=None):
    """A database with finished players (each chose a saint, optionally with a gender preference per name) and the app on top of it."""
    db = spel.open_db()
    app = maak_app(db, H, V, llm, random.Random(7))
    clients = {}
    for n in list(namen) + list(leiding_namen):
        c = kind(app, f"acct-{n}")
        if n in leiding_namen:
            c.headers.update(LEIDING)
        speel(c, f"Nick-{n}", voorkeur=(voorkeuren or {}).get(n, "maakt niet uit"))
        clients[n] = c
    return db, app, clients


def een_stemmer(clients):
    """A client whose page currently offers voting tiles."""
    return next(c for c in clients.values() if "tegelknop" in frag(c, "/spel/inhoud"))


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


def test_punten_per_stemmer_een_of_twee_goede_stemmen():
    assert [punten_voor(k) for k in (0, 1, 2)] == [0, 1, 3]


def test_score_ronde_telt_elke_stem_en_kent_geen_gelijkspel():
    """Points are per voter, so a tie between saints needs no ruling; a voter who did not vote counts as wrong."""
    s = score_ronde("a", [1, 2, 3, 4], {1: "a", 2: "a", 3: "b", 4: "b"}, {1: "a", 2: "b", 3: "a", 4: "b"})   # 2-2 tie in both rounds
    assert s == {"stemmers": 4, "goed1": 2, "goed2": 2, "punten": 3 + 1 + 1 + 0, "max": 12}
    assert score_ronde("a", [1, 2], {1: "a"}, {})["punten"] == 1 and score_ronde("a", [], {}, {}) == {"stemmers": 0, "goed1": 0, "goed2": 0, "punten": 0, "max": 0}
    assert score_ronde("a", [1], {1: "b"}, {1: "a"})["punten"] == 1      # only the later vote right: still a point, the group may learn from the questions
    assert score_ronde("a", [1], {2: "a"}, {2: "a"})["punten"] == 0      # a vote of someone who may not vote does not count


def test_toeval_punten_is_de_verwachting_bij_gokken_op_een_bord():
    assert toeval_punten(10, 5) == pytest.approx(5 * (2 * 0.1 * 0.9 + 3 * 0.01))
    assert toeval_punten(1, 3) == 9                                          # one saint on the board: everybody is right twice


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
        assert huidige(db)["fase"] == "onthuld" and huidige(db)["punten"] == 3
        tvtekst = frag(tv, "/beheer/tv/inhoud")
        assert f"✔ {nick}" in tvtekst and "tegel juist" in tvtekst and "Stemronde 1: 3 van 3 goed, stemronde 2: 0 van 3" in tvtekst and "Samen 3 van maximaal 9 punten" in tvtekst
        totaal += 3
        volgende(boss)
    assert spel.spel_status(db)["status"] == "plaat"
    plaat = frag(tv, "/beheer/tv/inhoud")
    assert all(nick in plaat for nick in uit.values())
    volgende(boss)
    einde = frag(tv, "/beheer/tv/inhoud")
    assert f"{totaal} van de 36 punten" in einde and spel.spel_status(db)["status"] == "einde"
    assert "Eindscore" in einde and "Stemronde 1 goed" in einde and "Ter vergelijking" in einde
    assert all(nick in einde for nick in uit.values()) and "3 van 3 ✔" in einde and "0 van 3" in einde      # who was guessed, in which round
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


def test_punten_per_stem_over_de_twee_stemrondes():
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
    assert scores == [2, 0, 6]               # 2 voters: one right vote each = 1 point, none = 0, both right = 3 points


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
    assert "Je doet niet mee aan dit spel" in frag(laat, "/spel/inhoud")
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
    assert "Haal het vinkje weg bij wie er niet bij is" in boss.get("/beheer/spel").text      # the start form is part of the page itself
    boss.post("/beheer/spel/start", data={"eerste": ""})
    assert "Start ronde 1" in frag(boss, "/beheer/spel/inhoud")
    volgende(boss)
    assert "0 van 2 hebben gestemd (nog niet iedereen)" in frag(boss, "/beheer/spel/inhoud")
    assert "Stemming sluiten en uitslag tonen" in frag(boss, "/beheer/spel/inhoud")


def test_leiding_ziet_het_raadspel_in_het_overzicht_en_de_pagina_polt_elke_twee_seconden():
    db, app, clients = spel_met(["a", "b", "c"])
    boss = leider(app)
    assert 'href="/beheer/spel"' in boss.get("/beheer").text and 'href="/beheer/speler/' in boss.get("/beheer").text
    assert 'hx-trigger="every 2s"' not in boss.get("/beheer/spel").text       # before the start the form must not refresh under the leader
    boss.post("/beheer/spel/start", data={"eerste": ""})
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
            assert set(re.findall(r'class="(tegel[^"]*)"', tekst)) <= {"tegel", "tegel stem", "tegelknop", "tegelwrap"}
        if fase in ("overleg1", "overleg2"):
            assert "×" not in frag(tv, "/beheer/tv/inhoud")
        if fase == "uitslag2":
            assert "Punten tot nu toe: 0 van 0" in frag(tv, "/beheer/tv/inhoud")
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
    assert "Je doet niet mee aan dit spel" in frag(laat, "/spel/inhoud")
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


def test_zichtbaar_bord_filtert_op_geslacht_met_ondergrens_en_zonder_het_antwoord_te_verbergen():
    from durfheilig.raadspel import MIN_ZICHT, zichtbaar_bord
    per_qid = {h.qid: h for h in H}
    man = [h.qid for h in H if h.geslacht == "mannelijk"]
    vrouw = [h.qid for h in H if h.geslacht == "vrouwelijk"]
    bord = [{"qid": q} for q in man[:8] + vrouw[:8]]
    assert [b["qid"] for b in zichtbaar_bord(bord, per_qid, "man", man[0])] == man[:8]
    assert [b["qid"] for b in zichtbaar_bord(bord, per_qid, "vrouw", vrouw[0])] == vrouw[:8]
    assert zichtbaar_bord(bord, per_qid, "maakt niet uit", man[0]) == bord and zichtbaar_bord(bord, per_qid, None, man[0]) == bord
    assert zichtbaar_bord(bord, per_qid, "man", vrouw[0]) == bord                  # the right saint is never hidden
    klein = [{"qid": q} for q in man[:MIN_ZICHT - 1] + vrouw[:8]]
    assert zichtbaar_bord(klein, per_qid, "man", man[0]) == klein                  # too few left to guess from: the whole board, not the answer


def test_het_bord_van_een_ronde_toont_alleen_heiligen_van_het_gewenste_geslacht():
    """Phones and tv show only saints of the gender the round's subject asked for; "maakt niet uit" and tiny boards show everything."""
    from durfheilig.raadspel import MIN_ZICHT
    namen = [f"p{i}" for i in range(10)]
    voork = {n: ["man", "vrouw", "maakt niet uit"][i % 3] for i, n in enumerate(namen)}
    db, app, clients = spel_met(namen, voorkeuren=voork)
    boss = leider(app)
    boss.post("/beheer/spel/start", data={"eerste": ""})
    volgende(boss)
    toegestaan = {"man": {"mannelijk"}, "vrouw": {"vrouwelijk"}, "maakt niet uit": {"mannelijk", "vrouwelijk"}}
    gefilterd = set()
    for _ in range(80):
        if spel.spel_status(db)["status"] != "ronde":
            break
        r = huidige(db)
        if r["fase"] == "overleg1":
            v = spel.invulling(db, r["speler_id"])["voorkeur"]
            bord = [b["qid"] for b in spel.bord_rijen(db)]
            eigen = [q for q in bord if H_PER_QID[q].geslacht in toegestaan[v]]
            juist = {s["id"]: s["gekozen"] for s in spel.spelers_klaar(db)}[r["speler_id"]]
            verwacht = eigen if len(eigen) >= MIN_ZICHT and juist in eigen else bord      # the rule, written out independently of the code
            tv = boss.get("/beheer/tv/inhoud", headers={"hx-request": "true"}).text
            telefoon = frag(een_stemmer(clients), "/spel/inhoud")
            assert telefoon.count("<button") == len(verwacht) == len(re.findall(r'class="tegel[ "]', tv))
            for q in bord:
                if q not in verwacht:
                    assert H_PER_QID[q].naam not in tv and H_PER_QID[q].naam not in telefoon
                    een_stemmer(clients).post("/spel/stem", data={"qid": q})            # a hidden saint cannot be voted for either
                    assert spel.stemmen(db, r["id"], 1) == []
                    assert een_stemmer(clients).get(f"/spel/heilige/{q}").status_code == 404   # nor can its info page be opened
            if len(verwacht) < len(bord):
                gefilterd.add(v)
        volgende(boss)
    assert gefilterd >= {"man", "vrouw"}                                                  # the filter really cut the board for both kinds


def test_info_link_en_detailpagina_voor_heiligen_op_het_bord():
    db, app, clients = spel_met(["a", "b", "c"])
    nieuw = kind(app, "acct-buiten")
    boss = leider(app)
    assert clients["a"].get("/spel/heilige/x").status_code == 404                # no game yet
    boss.post("/beheer/spel/start", data={"eerste": ""})
    volgende(boss)
    bord = [b["qid"] for b in spel.bord_rijen(db)]
    stemmer = een_stemmer(clients)
    html = frag(stemmer, "/spel/inhoud")
    assert all(f'href="/spel/heilige/{q}"' in html for q in bord)                # an info link on every card, beside the button
    h = H_PER_QID[bord[0]]
    r = stemmer.get(f"/spel/heilige/{bord[0]}")
    assert r.status_code == 200 and h.naam in r.text and h.record["levensverhaal"][:40] in r.text and "Alles over" in r.text
    assert "waarschuwing_voor_leiding" not in r.text and "gespreksvraag" not in r.text      # nothing meant for leaders
    assert boss.get(f"/spel/heilige/{bord[0]}").status_code == 200
    assert stemmer.get("/spel/heilige/onbekend").status_code == 404
    buiten = next(h.qid for h in H if h.qid not in set(bord))
    assert stemmer.get(f"/spel/heilige/{buiten}").status_code == 404             # only saints on the board
    assert nieuw.get(f"/spel/heilige/{bord[0]}").status_code == 404              # someone who is not in the game


def test_stemtegel_is_zelf_de_knop_zonder_losse_stemknop_eronder():
    """On a phone a separate "Stem op ..." button under each card overlapped the card: the card itself is the button now."""
    db, app, clients = spel_met(["a", "b", "c"])
    boss = leider(app)
    boss.post("/beheer/spel/start", data={"eerste": ""})
    volgende(boss)
    c = een_stemmer(clients)
    html = frag(c, "/spel/inhoud")
    bord = spel.bord_rijen(db)
    assert html.count("<button") == len(bord)                         # one button per saint, no extra "Stem op" button
    assert "Stem op " not in html
    assert re.search(r'<button[^>]*class="tegel"[^>]*>.*?<img', html, re.S)   # the card (image and name) sits inside the button
    c.post("/spel/stem", data={"qid": bord[0]["qid"]})
    html = frag(c, "/spel/inhoud")
    assert html.count('aria-pressed="true"') == 1 and "Jouw keuze" in html


def test_begeleider_kiest_wie_meedoet_voor_het_spel_start():
    db, app, clients = spel_met(["a", "b", "c", "d", "e"])
    boss = leider(app)
    ids = {n: spel.speler_voor(db, f"acct-{n}")["id"] for n in clients}
    pagina = boss.get("/beheer/spel").text
    assert pagina.count('name="meedoen"') == 5 and pagina.count("checked") >= 5 and "every 2s" not in pagina      # all ticked, and not refreshing under the leader
    boss.post("/beheer/spel/start", data={"lijst": "1"})                                                        # nobody ticked: refused
    assert spel.spel_status(db) is None
    boss.post("/beheer/spel/start", data={"lijst": "1", "meedoen": [str(ids[n]) for n in "abcd"], "eerste": str(ids["e"])})   # e is not coming
    assert spel.spel_status(db) is not None and len(spel.bord_rijen(db)) == 8        # 4 players: 4 chosen saints plus 4 decoys
    assert {r["speler_id"] for r in spel.rondes(db)} == {ids[n] for n in "abcd"}
    assert huidige_ronde_onderwerp(db) != ids["e"]                                 # the absent one was also not picked as first
    afwezig = frag(clients["e"], "/spel/inhoud")
    assert "Je doet niet mee aan dit spel" in afwezig and "tegelknop" not in afwezig
    assert "Nick-e" not in "".join(frag(c, "/spel/inhoud") for c in clients.values())


def huidige_ronde_onderwerp(db):
    return spel.rondes(db)[0]["speler_id"]


def test_een_formulier_zonder_lijst_neemt_iedereen_mee():
    db, app, clients = spel_met(["a", "b", "c"])
    leider(app).post("/beheer/spel/start", data={"eerste": ""})
    assert len(spel.rondes(db)) == 3


def test_uitleg_over_rondes_en_punten_staat_op_tv_telefoon_en_bediening():
    db, app, clients = spel_met(["a", "b", "c"])
    boss = leider(app)
    assert "Zo werkt het" in boss.get("/beheer/spel").text and "3 punten" in boss.get("/beheer/spel").text
    boss.post("/beheer/spel/start", data={"eerste": ""})
    tv, tel = frag(boss, "/beheer/tv/inhoud"), frag(clients["a"], "/spel/inhoud")
    for tekst in (tv, tel, boss.get("/beheer/spel").text):
        assert "Zo werkt het" in tekst and "Stemronde 1" in tekst and "Vragenronde" in tekst and "Stemronde 2" in tekst and "1 punt" in tekst and "3 punten" in tekst


def speel_uit(boss, db):
    for _ in range(200):
        if spel.spel_status(db)["status"] == "einde":
            return
        volgende(boss)
    raise AssertionError("het spel kwam niet aan het einde")


def test_eindbord_en_maximum_horen_bij_het_huidige_spel_ook_na_opnieuw_beginnen():
    db, app, clients = spel_met(["a", "b", "c", "d"])
    boss = leider(app)
    ids = {n: spel.speler_voor(db, f"acct-{n}")["id"] for n in clients}
    boss.post("/beheer/spel/start", data={"lijst": "1", "meedoen": [str(ids[n]) for n in "abc"]})
    speel_uit(boss, db)
    assert "0 van de 18 punten" in frag(boss, "/beheer/tv/inhoud")          # 3 rounds x 2 voters x 3 points
    boss.post("/beheer/spel/reset", data={"bevestig": "OPNIEUW"})
    boss.post("/beheer/spel/start", data={"lijst": "1", "meedoen": [str(ids[n]) for n in "abcd"]})
    speel_uit(boss, db)
    assert "0 van de 36 punten" in frag(boss, "/beheer/tv/inhoud")          # 4 rounds x 3 voters x 3 points, not the cached old board


def test_startformulier_toont_geen_heiligen_en_markeert_niemand_als_lezer():
    """A leader who also plays must not learn everybody's saint from the start form (that would be reading all explanations without being excluded)."""
    db, app, clients = spel_met(["a", "b", "c"])
    boss = leider(app)
    pagina = boss.get("/beheer/spel").text
    namen = [H_PER_QID[s["gekozen"]].naam for s in spel.spelers_klaar(db)]
    assert namen and not any(naam in pagina for naam in namen) and "Nick-a" in pagina
    assert spel.lezers(db, spel.speler_voor(db, "acct-a")["id"]) == set()


def test_uitslag_van_een_ronde_ligt_vast_ook_als_een_leider_daarna_een_uitleg_opent():
    db, app, clients = spel_met(["a", "b", "c", "d"])
    boss = leider(app)
    boss.post("/beheer/spel/start", data={"eerste": ""})
    speel_uit(boss, db)
    voor = frag(boss, "/beheer/tv/inhoud")
    assert "0 van de 36 punten" in voor
    for r in spel.rondes(db):
        boss.get(f"/beheer/speler/{r['speler_id']}")                    # opening an explanation marks the opener as reader
    na = frag(boss, "/beheer/tv/inhoud")
    assert na == voor and "0 van de 36 punten" in na
    assert all(r["stemmers"] == 3 and r["max_punten"] == 9 for r in spel.rondes(db))      # stored with the round at the reveal


def test_vreemde_id_s_in_de_startlijst_geven_geen_500_en_starten_niets():
    db, app, clients = spel_met(["a", "b", "c"])
    boss = leider(app)
    for slecht in (["²"], ["9" * 5000], ["-1"], ["abc", ""], [" 3"]):
        r = boss.post("/beheer/spel/start", data={"lijst": "1", "meedoen": slecht, "eerste": "²"})
        assert r.status_code == 200
        assert spel.spel_status(db) is None
    ids = [spel.speler_voor(db, f"acct-{n}")["id"] for n in "abc"]
    assert boss.post("/beheer/spel/start", data={"lijst": "1", "meedoen": [str(i) for i in ids], "eerste": "9" * 5000}).status_code == 200
    assert spel.spel_status(db) is not None                                      # a bad `eerste` is ignored, the rest starts


def test_oude_database_zonder_uitslagkolommen_krijgt_ze_bij_het_openen(tmp_path):
    import apsw
    pad = tmp_path / "oud.db"
    c = apsw.Connection(str(pad))
    c.execute("create table spelronde (id integer primary key, speler_id integer not null unique, volgorde integer not null, "
              "fase text not null default 'overleg1', punten integer)")
    c.close()
    db = spel.open_db(pad)
    assert {"stemmers", "goed1", "goed2", "max_punten"} <= {r["name"] for r in db.q("pragma table_info(spelronde)")}
    spel.open_db(pad)                                                              # a second open changes nothing and does not fail
