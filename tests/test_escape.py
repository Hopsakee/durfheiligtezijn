import html
import json
import re

import pytest

from durfheilig import db as spel
from durfheilig.app import maak_app
from durfheilig.data import DataFout, data_dir
from durfheilig.escape import (HINTS_PER_PUZZEL, Klok, alles_gevonden, klopt, laad_escape, mmss, nieuwe_extra, normaliseer, slotcode,
                               speeltijd, team_stand, winnaar)
from test_app import H, V, kind

ESC = laad_escape()
LEIDING = {"remote-groups": "durfte-leiding"}


class NepTijd:
    """A clock the test moves by hand."""
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


def opzet():
    db, tijd = spel.open_db(), NepTijd()
    app = maak_app(db, H, V, None, tijd=tijd)
    boss = kind(app, "boss")
    boss.headers.update(LEIDING)
    return db, app, tijd, boss


def antwoord_van(nr):
    return ESC.per_nr[nr].antwoorden[0]


# ------------------------------------------------------------------ de inhoud

def test_de_escaperoom_laadt_met_vijf_bewijzen_elk_met_drie_hints_en_een_slot_van_vier_cijfers():
    assert [p.nr for p in ESC.puzzels] == [1, 2, 3, 4, 5]
    assert all(isinstance(p.cijfer, int) for p in ESC.puzzels[:4]) and sorted(ESC.per_nr[5].volgorde) == [1, 2, 3, 4]
    assert slotcode(ESC) == "".join(str(ESC.per_nr[n].cijfer) for n in ESC.per_nr[5].volgorde) and len(slotcode(ESC)) == 4
    assert all(len(p.hints) == HINTS_PER_PUZZEL and p.antwoorden and p.dossier for p in ESC.puzzels)
    assert ESC.speeltijd_minuten == 45 and ESC.hintstraf_minuten == 3


def test_de_antwoorden_uit_het_bronmateriaal_en_de_cijfercodes_worden_geaccepteerd():
    bron = {1: "made by kids", 2: "minimaal twaalf uur per dag", 3: "slechte kwaliteit", 4: "alleen samen houden we de prijzen hoog",
            5: "vijfenzeventighonderd liter water nodig"}
    for nr, a in bron.items():
        assert klopt(a, ESC.per_nr[nr]), nr
    assert klopt("7500", ESC.per_nr[5]) and klopt("7.500 liter", ESC.per_nr[5]) and klopt("12", ESC.per_nr[2])
    assert not klopt("3000", ESC.per_nr[5]) and not klopt("", ESC.per_nr[1]) and not klopt("!!!", ESC.per_nr[1])
    assert not klopt("made by kids", ESC.per_nr[2])


def kapotte_kopie(tmp_path, wijzig):
    doc = json.loads((data_dir() / "escape.json").read_text(encoding="utf-8"))
    wijzig(doc)
    pad = tmp_path / "escape.json"
    pad.write_text(json.dumps(doc), encoding="utf-8")
    return pad


@pytest.mark.parametrize("wijzig, melding", [
    (lambda d: d["puzzels"][1].update(hints=["een", "twee"]), "puzzel 2: precies 3 hints"),
    (lambda d: d["puzzels"][2].update(antwoorden=["...", "x"]), "puzzel 3: antwoorden"),
    (lambda d: d["puzzels"][2].update(antwoorden=[]), "puzzel 3: antwoorden"),
    (lambda d: d["puzzels"][3]["antwoorden"].append("Made-by-kids"), "hoort ook bij puzzel 1"),
    (lambda d: d["puzzels"][0].update(dossier=" "), "puzzel 1: dossier"),
    (lambda d: d["puzzels"][4].update(nr=7), "verwacht 5"),
    (lambda d: d.update(speeltijd_minuten=0), "speeltijd_minuten"),
    (lambda d: d.update(puzzels=[]), "geen puzzels"),
    (lambda d: d["puzzels"][0].update(cijfer=10), "puzzel 1: cijfer 10"),
    (lambda d: d["puzzels"][0].update(cijfer=True), "puzzel 1: cijfer True"),
    (lambda d: d["puzzels"][0].update(cijfer="7"), "puzzel 1: cijfer '7'"),
    (lambda d: d["puzzels"][4].update(volgorde=[3, 1, 1, 2]), "precies één keer"),
    (lambda d: d["puzzels"][4].update(volgorde=[3, 1, 4]), "precies één keer"),
    (lambda d: d["puzzels"][4].update(volgorde=[3, 1, 4, 2, 5]), "precies één keer"),
    (lambda d: d["puzzels"][4].update(volgorde="3142"), "lijst puzzelnummers"),
    (lambda d: d["puzzels"][0].update(volgorde=[1, 2, 3, 4]), "niet allebei"),
    (lambda d: d["puzzels"][3].pop("cijfer") and d["puzzels"][3].update(volgorde=[1, 2, 3]), "alleen één puzzel"),
])
def test_een_fout_in_de_inhoud_faalt_luid_met_het_puzzelnummer(tmp_path, wijzig, melding):
    with pytest.raises(DataFout, match=melding):
        laad_escape(kapotte_kopie(tmp_path, wijzig))


# ------------------------------------------------------------------ de regels

def test_normaliseren_houdt_alleen_kleine_letters_en_cijfers():
    assert normaliseer("  Made by Kids! ") == "madebykids"
    assert normaliseer("7.500") == "7500" and normaliseer("12 uur") == "12uur"
    assert normaliseer("Één, twéé") == "eentwee" and normaliseer("ĳs") == "ijs"


def test_speeltijd_telt_pauzes_niet_mee():
    k = Klok(duur=2700, gestart=1000.0)
    assert speeltijd(None, 5000) == 0 and speeltijd(k, 1000) == 0 and speeltijd(k, 1600) == 600
    gepauzeerd = Klok(duur=2700, gestart=1000.0, gepauzeerd_op=1600.0)
    assert speeltijd(gepauzeerd, 1600) == speeltijd(gepauzeerd, 9999) == 600          # a paused clock stands still
    hervat = Klok(duur=2700, gestart=1000.0, pauze_totaal=100.0)                      # paused 1600-1700, now running again
    assert speeltijd(hervat, 1900) == 800


def test_resterende_tijd_is_speeltijd_plus_extra_min_strafminuten_min_gespeeld():
    k = Klok(duur=2700, gestart=0.0)
    s = team_stand(k, 600, duur=2700, straf=360, extra=60, klaar_speeltijd=None)
    assert s.rest == 2700 + 60 - 360 - 600 and s.loopt and not s.op and not s.klaar
    voor = team_stand(None, 600, duur=2700, straf=0, extra=0, klaar_speeltijd=None)
    assert voor.rest == 2700 and not voor.gestart and not voor.loopt and not voor.op


def test_de_tijd_is_op_als_de_strafminuten_de_rest_opeten():
    k = Klok(duur=600, gestart=0.0)
    s = team_stand(k, 500, duur=600, straf=180, extra=0, klaar_speeltijd=None)
    assert s.op and not s.loopt and s.rest == 0 and s.rest_ruw == -80


def test_een_klaar_team_staat_stil_met_eindtijd_inclusief_straf():
    k = Klok(duur=2700, gestart=0.0)
    s = team_stand(k, 2600, duur=2700, straf=180, extra=0, klaar_speeltijd=1200.0)
    assert s.klaar and not s.loopt and not s.op and s.eindtijd == 1380 and s.rest == 2700 - 180 - 1200
    assert alles_gevonden({1, 2, 3, 4, 5}, ESC.puzzels) and not alles_gevonden({1, 2, 3, 4}, ESC.puzzels)


def test_extra_minuten_na_de_tijd_tellen_vanaf_nu():
    assert nieuwe_extra(0, 300.0, 60) == 60             # still running: just add
    extra = nieuwe_extra(0, -125.0, 120)                # 125 s past zero: forgive that first, then two minutes
    s = team_stand(Klok(duur=600, gestart=0.0), 725, duur=600, straf=0, extra=extra, klaar_speeltijd=None)
    assert 119 <= s.rest <= 121 and s.loopt


def test_de_winnaar_is_pas_bekend_als_iedereen_klaar_of_af_is():
    k = Klok(duur=2700, gestart=0.0)
    a = team_stand(k, 2000, duur=2700, straf=0, extra=0, klaar_speeltijd=1500.0)
    b_bezig = team_stand(k, 2000, duur=2700, straf=0, extra=0, klaar_speeltijd=None)
    b_klaar_met_straf = team_stand(k, 2000, duur=2700, straf=600, extra=0, klaar_speeltijd=1400.0)
    assert winnaar({"A": a, "B": b_bezig}) is None
    assert winnaar({"A": a, "B": b_klaar_met_straf}) == "A"          # B was faster on the clock but took hints
    b_af = team_stand(k, 2800, duur=2700, straf=0, extra=0, klaar_speeltijd=None)
    assert winnaar({"A": a, "B": b_af}) == "A"
    assert mmss(61.2) == "1:02" and mmss(-5) == "0:00" and mmss(2700) == "45:00"


# ------------------------------------------------------------------ routes

def teamaccount(app, boss, naam, team):
    """A team phone: an ordinary account that opened /escape and that the leader put in a team."""
    c = kind(app, naam)
    c.get("/escape")
    boss.post("/beheer/escape/account", data={"gebruikersnaam": naam, "team": team})
    return c


def frag(c, pad):
    return c.get(pad, headers={"hx-request": "true"}).text


def klokken(html_tekst):
    return json.loads(html.unescape(re.search(r"data-klokken='([^']*)'", html_tekst).group(1)))


def events(html_tekst):
    return json.loads(html.unescape(re.search(r"data-events='([^']*)'", html_tekst).group(1)))


def team_a(tv):
    return re.search(r'<section id="team-A".*?</section>', tv, re.S).group(0)


def test_kinderen_komen_niet_bij_de_bediening_of_de_schermen():
    db, app, tijd, boss = opzet()
    k = kind(app, "k1")
    for pad in ("/beheer/escape", "/beheer/escape/inhoud", "/beheer/escape/tv", "/beheer/escape/tv?team=A", "/beheer/escape/tv/inhoud"):
        assert k.get(pad).status_code == 403, pad
        assert boss.get(pad).status_code == 200, pad
    for pad in ("/beheer/escape/start", "/beheer/escape/pauze", "/beheer/escape/tijd", "/beheer/escape/terug", "/beheer/escape/account",
                "/beheer/escape/reset"):
        assert k.post(pad, data={"minuten": "45", "team": "A", "nr": "1", "gebruikersnaam": "k1", "actie": "pauze", "bevestig": "OPNIEUW"}).status_code == 403, pad
    assert spel.escape_klok(db) is None


def test_een_account_zonder_team_wacht_en_kan_niets_insturen():
    db, app, tijd, boss = opzet()
    k = kind(app, "team-telefoon-1")
    assert "Wacht op de recherche" in k.get("/escape").text and 'data-wacht="1"' in frag(k, "/escape/inhoud")
    assert spel.escape_account(db, "team-telefoon-1")["team"] is None                 # it now waits in the leader's list
    assert "team-telefoon-1" in frag(boss, "/beheer/escape/inhoud")
    boss.post("/beheer/escape/start", data={})
    k.post("/escape/antwoord", data={"nr": "1", "antwoord": antwoord_van(1)})
    k.post("/escape/hint", data={"nr": "2"})
    assert spel.escape_opgelost(db) == {} and spel.escape_hints(db) == {}
    assert kind(app, "ander").get("/escape", headers={"sec-fetch-site": "cross-site"}).status_code == 200
    assert spel.escape_account(db, "ander") is None                                     # another site cannot sign an account up


def test_een_ingedeeld_account_speelt_alleen_voor_het_eigen_team_en_de_leiding_kan_het_verplaatsen():
    db, app, tijd, boss = opzet()
    a, b = teamaccount(app, boss, "tel-a", "A"), teamaccount(app, boss, "tel-b", "B")
    assert "TEAM A" in frag(a, "/escape/inhoud") and "TEAM B" in frag(b, "/escape/inhoud") and "data-wacht" not in frag(a, "/escape/inhoud")
    boss.post("/beheer/escape/start", data={})
    a.post("/escape/antwoord", data={"nr": "1", "antwoord": antwoord_van(1)})
    b.post("/escape/antwoord", data={"nr": "2", "antwoord": antwoord_van(2)})
    a.post("/escape/hint", data={"nr": "3"})
    assert spel.escape_opgelost(db) == {"A": {1: 0.0}, "B": {2: 0.0}} and spel.escape_hints(db) == {"A": {3: 1}}

    boss.post("/beheer/escape/account", data={"gebruikersnaam": "tel-a", "team": "B"})        # move
    a.post("/escape/antwoord", data={"nr": "3", "antwoord": antwoord_van(3)})
    assert 3 in spel.escape_opgelost(db)["B"] and 3 not in spel.escape_opgelost(db)["A"]
    boss.post("/beheer/escape/account", data={"gebruikersnaam": "tel-a", "team": ""})         # take out
    assert 'data-wacht="1"' in frag(a, "/escape/inhoud")
    a.post("/escape/antwoord", data={"nr": "4", "antwoord": antwoord_van(4)})
    assert 4 not in spel.escape_opgelost(db)["A"] and 4 not in spel.escape_opgelost(db)["B"]
    boss.post("/beheer/escape/account", data={"gebruikersnaam": "nooit-gezien", "team": "A"})  # only accounts that opened /escape
    assert spel.escape_account(db, "nooit-gezien") is None
    boss.post("/beheer/escape/account", data={"gebruikersnaam": "tel-b", "team": "C"})          # no such team
    assert spel.escape_account(db, "tel-b")["team"] == "B"


def test_de_leiding_speelt_niet_mee_en_kan_niets_insturen():
    db, app, tijd, boss = opzet()
    r = boss.get("/escape")
    assert "kunnen hier niets insturen" in r.text and 'href="/beheer/escape"' in r.text
    boss.post("/beheer/escape/account", data={"gebruikersnaam": "boss", "team": "A"})
    spel.escape_meld(db, "boss", 0.0)
    spel.escape_zet_account(db, "boss", "A")                                                # even when the database says so
    boss.post("/beheer/escape/start", data={})
    boss.post("/escape/antwoord", data={"nr": "1", "antwoord": antwoord_van(1)})
    boss.post("/escape/hint", data={"nr": "2"})
    assert spel.escape_opgelost(db) == {} and spel.escape_hints(db) == {}
    assert boss.get("/escape/puzzel/1").url.path == "/escape"


def test_wat_iets_verandert_is_alleen_post_en_een_pagina_is_geen_actie():
    db, app, tijd, boss = opzet()
    tel = teamaccount(app, boss, "tel-a", "A")
    for pad in ("/escape/antwoord", "/escape/hint"):
        assert tel.get(pad).status_code == 405, pad
    for pad in ("/beheer/escape/start", "/beheer/escape/pauze", "/beheer/escape/tijd", "/beheer/escape/terug", "/beheer/escape/account",
                "/beheer/escape/reset"):
        assert boss.get(pad).status_code == 405, pad
    for pad in ("/escape", "/escape/inhoud", "/escape/puzzel/1", "/escape/hint/1"):
        assert tel.post(pad, data={}).status_code == 405, pad
    assert boss.post("/beheer/escape/tv", data={}).status_code == 405
    # A request started on another site changes nothing (the app's login check).
    assert boss.post("/beheer/escape/account", data={"gebruikersnaam": "tel-a", "team": "B"}, headers={"sec-fetch-site": "cross-site"}).status_code == 403
    assert spel.escape_account(db, "tel-a")["team"] == "A"


def test_een_heel_spel_fout_goed_hint_pauze_en_klaar():
    db, app, tijd, boss = opzet()
    a, b = teamaccount(app, boss, "tel-a", "A"), teamaccount(app, boss, "tel-b", "B")
    assert "Wacht op de start" in frag(a, "/escape/inhoud")
    a.post("/escape/antwoord", data={"nr": "1", "antwoord": antwoord_van(1)})          # before the start nothing counts
    assert spel.escape_opgelost(db) == {}

    boss.post("/beheer/escape/start", data={"minuten": "45"})
    assert spel.escape_klok(db)["duur"] == 2700
    tijd.t += 60
    r = a.post("/escape/antwoord", data={"nr": "1", "antwoord": "made by adults"})
    assert "Afgewezen" in r.text and spel.escape_opgelost(db) == {}
    r = a.post("/escape/antwoord", data={"nr": "1", "antwoord": "  MADE by kids!"})
    assert "Ontvangen" in r.text and f"<b>{ESC.per_nr[1].cijfer}</b>" in r.text and spel.escape_opgelost(db) == {"A": {1: 60.0}}
    a.post("/escape/antwoord", data={"nr": "1", "antwoord": "made by kids"})           # twice counts once
    assert [e["soort"] for e in spel.escape_gebeurtenissen(db)] == ["fout", "goed"]

    assert "Kost 3 minuten" in a.get("/escape/hint/2").text and spel.escape_hints(db) == {}   # the question page takes nothing
    r = a.post("/escape/hint", data={"nr": "2"})
    assert ESC.per_nr[2].hints[0] in r.text and ESC.per_nr[2].hints[1] not in r.text
    for _ in range(5):
        a.post("/escape/hint", data={"nr": "2"})
    assert spel.escape_hints(db) == {"A": {2: 3}}                                         # never more than three

    tv = frag(boss, "/beheer/escape/tv/inhoud")
    assert "✔ Gemaakt door kinderen" in team_a(tv) and "−9 min" in team_a(tv)
    assert klokken(tv)["A"] == {"rest": 2700 - 60 - 9 * 60, "loopt": 1}
    ev = events(tv)
    assert any(e["soort"] == "goed" and e["tekst"] == ESC.per_nr[1].dossier for e in ev)
    assert [e["tekst"] for e in ev if e["soort"] == "hint"] == list(ESC.per_nr[2].hints)   # each hint, in order, for the room screen

    # Team A's room: its own board with the post-it and its digit; team B small in the corner.
    b.post("/escape/antwoord", data={"nr": "5", "antwoord": "7500"})
    kamer = frag(boss, "/beheer/escape/tv/inhoud?team=A")
    assert kamer.count('class="postit"') == 1 and f'<div class="pc">{ESC.per_nr[1].cijfer}</div>' in kamer
    assert kamer.count('class="postit leeg"') == 4 and kamer.count("<line") == 1
    hoek = re.search(r'<div class="hoek">.*', kamer, re.S).group(0)
    assert "Team B" in hoek and hoek.count('<i class=""></i>') == 1 and 'data-klok="B"' in hoek
    kamer_b = frag(boss, "/beheer/escape/tv/inhoud?team=B")
    assert 'class="pv"' in kamer_b and "→" in kamer_b                                       # puzzle 5's post-it gives the order

    boss.post("/beheer/escape/pauze", data={"actie": "pauze"})
    tijd.t += 600
    a.post("/escape/antwoord", data={"nr": "3", "antwoord": antwoord_van(3)})          # paused: no answers
    assert 3 not in spel.escape_opgelost(db)["A"]
    boss.post("/beheer/escape/pauze", data={"actie": "hervat"})
    assert klokken(frag(boss, "/beheer/escape/tv/inhoud"))["A"]["rest"] == 2700 - 60 - 540   # the pause did not count

    for nr in (2, 3, 4, 5):
        tijd.t += 30
        a.post("/escape/antwoord", data={"nr": str(nr), "antwoord": antwoord_van(nr)})
    assert spel.escape_teams(db)["A"]["klaar_speeltijd"] == 60 + 120
    assert "Klaar in" in frag(boss, "/beheer/escape/tv/inhoud") and "klaar" in [e["soort"] for e in spel.escape_gebeurtenissen(db)]
    tijd.t += 300
    assert "Klaar in 12:00" in frag(boss, "/beheer/escape/tv/inhoud")                     # 3 min play + 9 min penalty, frozen

    # Undo a wrongly accepted answer: the box goes grey and the team is no longer finished.
    boss.post("/beheer/escape/terug", data={"team": "A", "nr": "4"})
    assert 4 not in spel.escape_opgelost(db)["A"] and spel.escape_teams(db)["A"]["klaar_speeltijd"] is None


def test_het_scherm_verandert_tussen_twee_polls_alleen_als_er_iets_gebeurt():
    db, app, tijd, boss = opzet()
    a = teamaccount(app, boss, "tel-a", "A")
    boss.post("/beheer/escape/start", data={})
    binnen = lambda: re.search(r"<div[^>]*id=\"esc-frag\"[^>]*>(.*)", frag(boss, "/beheer/escape/tv/inhoud?team=A"), re.S).group(1)  # noqa: E731
    eerst = binnen()
    tijd.t += 7
    assert binnen() == eerst                                                              # only the clock moved, and that rides in an attribute
    a.post("/escape/antwoord", data={"nr": "1", "antwoord": antwoord_van(1)})
    assert binnen() != eerst


def test_tijd_op_weigert_antwoorden_tot_de_leiding_minuten_geeft():
    db, app, tijd, boss = opzet()
    a = teamaccount(app, boss, "tel-a", "A")
    boss.post("/beheer/escape/start", data={"minuten": "1"})
    tijd.t += 90
    assert "Tijd is op" in team_a(frag(boss, "/beheer/escape/tv/inhoud"))
    a.post("/escape/antwoord", data={"nr": "1", "antwoord": antwoord_van(1)})
    assert spel.escape_opgelost(db) == {}
    boss.post("/beheer/escape/tijd", data={"team": "A", "minuten": "1"})
    assert "Tijd is op" not in team_a(frag(boss, "/beheer/escape/tv/inhoud"))
    assert "Tijd is op" in frag(boss, "/beheer/escape/tv/inhoud")                        # team B still is out
    a.post("/escape/antwoord", data={"nr": "1", "antwoord": antwoord_van(1)})
    assert 1 in spel.escape_opgelost(db)["A"]


def test_opnieuw_beginnen_vraagt_om_het_woord_en_houdt_de_telefoons():
    db, app, tijd, boss = opzet()
    a = teamaccount(app, boss, "tel-a", "A")
    boss.post("/beheer/escape/start", data={})
    a.post("/escape/antwoord", data={"nr": "1", "antwoord": antwoord_van(1)})
    assert "Niets gewist" in boss.post("/beheer/escape/reset", data={"bevestig": "ja"}).text and spel.escape_klok(db)
    boss.post("/beheer/escape/reset", data={"bevestig": "OPNIEUW"})
    assert spel.escape_klok(db) is None and spel.escape_opgelost(db) == {} and "TEAM A" in frag(a, "/escape/inhoud")   # the teams stay


def test_groep_verwijderen_wist_ook_de_escaperoom_en_de_export_bevat_hem():
    db, app, tijd, boss = opzet()
    a = teamaccount(app, boss, "tel-a", "A")
    boss.post("/beheer/escape/start", data={})
    a.post("/escape/antwoord", data={"nr": "1", "antwoord": "fout"})
    export = boss.get("/beheer/export").json()
    assert export["escape"]["escape_account"][0]["gebruikersnaam"] == "tel-a" and export["escape"]["escape_account"][0]["team"] == "A"
    assert export["escape"]["escape_gebeurtenis"]
    boss.post("/beheer/verwijder", data={"bevestig": "VERWIJDER"})
    for tabel in (*spel.ESCAPE_TABELLEN, "escape_account"):
        assert not db.q(f"select * from {tabel}"), tabel


def test_de_escaperoom_staat_alleen_in_het_menu_van_de_leiding_en_de_teamtelefoon_heeft_geen_menu():
    from test_app import menu_hrefs
    db, app, tijd, boss = opzet()
    assert not any(x.startswith(("/escape", "/beheer")) for x in menu_hrefs(kind(app, "k").get("/menu").text))
    links = menu_hrefs(boss.get("/menu").text)
    assert {"/escape", "/beheer/escape", "/beheer/escape/tv"} <= set(links)
    tel = teamaccount(app, boss, "tel-a", "A")
    for pad in ("/escape", "/escape/puzzel/1", "/escape/hint/1"):
        assert menu_hrefs(tel.get(pad).text) is None, pad                                # a team phone does not invite wandering
    assert menu_hrefs(kind(app, "wachter").get("/escape").text) is None
    assert tel.get("/beheer/escape").status_code == 403                                   # a team account is no leader
    assert menu_hrefs(boss.get("/beheer/escape/tv?team=A").text) is None
    assert db.q("select * from speler") == []                                             # looking around creates no participant


# ------------------------------------------------------------------ het prikbord op de laptop van een team

def test_een_teamaccount_ziet_op_de_laptop_alleen_het_eigen_prikbord():
    db, app, tijd, boss = opzet()
    a, b = teamaccount(app, boss, "tel-a", "A"), teamaccount(app, boss, "tel-b", "B")
    for c, eigen, ander in ((a, "A", "B"), (b, "B", "A")):
        pagina_, blok_ = c.get("/escape/bord").text, frag(c, "/escape/bord/inhoud")
        for tekst in (pagina_, blok_):
            assert f'id="team-{eigen}" class="prikbord"' in tekst and f'id="team-{ander}"' not in tekst
            assert f"Team {ander}" in re.search(r'<div class="hoek">.*', tekst, re.S).group(0)      # the other team, small
        assert 'id="esc-geluid"' in pagina_ and f'data-team="{eigen}"' in pagina_
    assert 'id="team-B"' not in a.get("/escape/bord?team=B").text and 'id="team-B"' not in frag(a, "/escape/bord/inhoud?team=B")


def test_een_account_zonder_team_wacht_ook_op_de_laptop_en_de_leiding_gaat_naar_de_eigen_tv():
    db, app, tijd, boss = opzet()
    k = kind(app, "laptop-zonder-team")
    assert "Wacht op de recherche" in k.get("/escape/bord").text and 'data-wacht="1"' in frag(k, "/escape/bord/inhoud")
    assert 'class="prikbord"' not in k.get("/escape/bord").text
    assert spel.escape_account(db, "laptop-zonder-team")["team"] is None                  # it shows up in the leader's list
    assert boss.get("/escape/bord").url.path == "/beheer/escape/tv"
    t = teamaccount(app, boss, "tel-a", "A")
    for pad in ("/beheer/escape/tv", "/beheer/escape/tv?team=A", "/beheer/escape/tv/inhoud"):
        assert t.get(pad).status_code == 403 and k.get(pad).status_code == 403, pad


def test_het_andere_team_geeft_op_het_prikbord_nooit_hints_of_antwoorden_weg():
    db, app, tijd, boss = opzet()
    a, b = teamaccount(app, boss, "tel-a", "A"), teamaccount(app, boss, "tel-b", "B")
    boss.post("/beheer/escape/start", data={})
    for _ in range(3):
        b.post("/escape/hint", data={"nr": "2"})                                              # all three hints for puzzle 2
    b.post("/escape/antwoord", data={"nr": "3", "antwoord": antwoord_van(3)})
    b.post("/escape/antwoord", data={"nr": "4", "antwoord": "fout"})
    a.post("/escape/hint", data={"nr": "1"})
    geheim = [*ESC.per_nr[2].hints, ESC.per_nr[3].bewijs, ESC.per_nr[3].dossier]
    for tekst in (a.get("/escape/bord").text, frag(a, "/escape/bord/inhoud"), frag(boss, "/beheer/escape/tv/inhoud?team=A")):
        for g in geheim:
            assert g not in html.unescape(tekst), g
        ev = events(tekst)
        assert {e["soort"] for e in ev if e["team"] == "B"} == {"goed"} and all(not e["tekst"] for e in ev if e["team"] == "B")
        assert [e["tekst"] for e in ev if e["team"] == "A" and e["soort"] == "hint"] == [ESC.per_nr[1].hints[0]]   # its own hint, in full
    assert ESC.per_nr[2].hints[2] in html.unescape(frag(b, "/escape/bord/inhoud"))           # team B does see its own
    assert ESC.per_nr[2].hints[0] in html.unescape(frag(boss, "/beheer/escape/tv/inhoud"))  # and the leader's both-teams view everything


def test_de_teamtelefoon_en_de_laptop_delen_een_account_tegelijk():
    db, app, tijd, boss = opzet()
    tel = teamaccount(app, boss, "tel-a", "A")
    laptop = kind(app, "tel-a")                                                              # same account, other device
    boss.post("/beheer/escape/start", data={})
    tel.post("/escape/antwoord", data={"nr": "1", "antwoord": antwoord_van(1)})
    bord = frag(laptop, "/escape/bord/inhoud")
    assert bord.count('class="postit"') == 1 and "TEAM A" in frag(tel, "/escape/inhoud")
    assert "/escape/bord" not in tel.get("/escape").text                                     # no link on the phone to wander off
    assert "/escape/bord" in boss.get("/beheer/escape").text                                 # the leader page names the laptop address


# ------------------------------------------------------------------ de knoppen voor een teamaccount

TEAMKNOPPEN = ('href="/escape"', 'href="/escape/bord"')


def lijf(r):
    """The page without its head (the inline stylesheet names the button classes on every page)."""
    return r.text.split("</head>", 1)[1]


def test_een_teamaccount_landt_op_de_startpagina_met_de_twee_knoppen_bovenaan_en_in_het_menu():
    from test_app import menu_hrefs
    db, app, tijd, boss = opzet()
    for team in ("A", None):                                                               # assigned or still waiting: both get them
        naam = f"tel-{team or 'wacht'}"
        c = teamaccount(app, boss, naam, team) if team else kind(app, naam)
        if not team:
            c.get("/escape")
        for pad in ("/", "/menu"):
            r = c.get(pad)
            assert r.url.path == pad and "📱 Teamtelefoon" in lijf(r) and "🖥️ Recherchebord" in lijf(r), (naam, pad)
            boven = lijf(r).split("<h2>Voor jou</h2>")[0]                                    # on top, before the rest of the start page
            assert all(k in boven.split("</header>")[-1] for k in TEAMKNOPPEN), (naam, pad)
            assert menu_hrefs(r.text)[:2] == ["/escape", "/escape/bord"], (naam, pad)
        for pad in ("/escape", "/escape/bord"):
            assert menu_hrefs(c.get(pad).text) is None, pad                               # the escape pages stay without a menu


def test_een_gewoon_kind_merkt_niets_van_de_teamknoppen():
    from test_app import menu_hrefs
    db, app, tijd, boss = opzet()
    k = kind(app, "gewoon-kind")
    r = k.get("/")
    assert "Welkom" in lijf(r) and "Teamtelefoon" not in lijf(r) and "Recherchebord" not in lijf(r) and "teamknop" not in lijf(r)   # still straight into the quiz
    assert menu_hrefs(r.text) == ["/menu", "/quiz", "/spel"]
    m = lijf(k.get("/menu"))
    assert not any(knop in m for knop in TEAMKNOPPEN) and "Recherchebord" not in m and "teamknop" not in m
    assert spel.escape_account(db, "gewoon-kind") is None


def test_de_leiding_houdt_haar_eigen_startpagina():
    from test_app import menu_hrefs
    db, app, tijd, boss = opzet()
    spel.escape_meld(db, "boss", 0.0)                                                       # even a leader in escape_account
    r = boss.get("/")
    assert "Voor begeleiders" in lijf(r) and "Recherchebord" not in lijf(r) and "teamknop" not in lijf(r)
    links = menu_hrefs(r.text)
    assert "/escape/bord" not in links and "/beheer/escape" in links and links.count("/escape") == 1   # only its own explanation page
