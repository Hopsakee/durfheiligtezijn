import re
import subprocess
import sys
from pathlib import Path

from starlette.testclient import TestClient

from durfheilig import db as spel
from durfheilig.dev import maak_dev_app


def client():
    return TestClient(maak_dev_app(spel.open_db(), None), follow_redirects=True)


def test_zonder_keuze_gaat_alles_naar_de_keuzepagina():
    r = client().get("/")
    assert r.url.path == "/dev" and "Lokaal testen" in r.text


def test_kiezen_wie_je_bent_geeft_de_quiz_en_een_leider_ziet_beheer():
    c = client()
    assert "Welkom" in c.get("/dev/als/kind1").text
    assert c.get("/beheer").status_code == 403
    c.get("/dev/als/leiding1")
    assert c.get("/beheer").status_code == 200


def test_zelf_meegestuurde_headers_tellen_niet():
    c = client()
    c.get("/dev/als/kind1")
    assert c.get("/beheer", headers={"remote-groups": "admins"}).status_code == 403


def test_vreemde_namen_worden_geweigerd():
    assert client().get("/dev/als/a b;c", follow_redirects=False).status_code in (400, 404)
    assert client().get("/dev/als/" + "x" * 40).status_code == 400


def test_een_andere_site_kan_niet_wisselen_wie_je_bent():
    c = client()
    r = c.get("/dev/als/leiding1", headers={"sec-fetch-site": "cross-site"}, follow_redirects=False)
    assert r.status_code == 403 and "set-cookie" not in r.headers


def test_groepen_komen_niet_uit_een_cookie_en_dev_prefix_is_exact():
    c = client()
    c.cookies.set("dev_user", "kind1"); c.cookies.set("dev_groups", "admins")
    assert c.get("/beheer").status_code == 403
    r = c.get("/devil")                       # goes to the app (404 there), not to the chooser
    assert "Lokaal testen" not in r.text and r.status_code == 404


def test_de_echte_app_importeert_dev_nooit():
    code = "import sys, durfheilig.app; assert 'durfheilig.dev' not in sys.modules"
    subprocess.run([sys.executable, "-c", code], check=True)
    assert "durfheilig.dev" not in (Path(__file__).resolve().parents[1] / "Dockerfile").read_text()


def test_env_bestand_wordt_gelezen_zonder_bestaande_waarden_te_overschrijven(tmp_path):
    from durfheilig.dev import laad_env

    f = tmp_path / ".env"
    f.write_text('# opmerking\nGEMINI_API_KEY="geheim"\nGEMINI_MODEL = model-x\nLEEG=\nBESTAAT=nieuw\nzonder gelijkteken\n')
    env = {"BESTAAT": "oud"}
    assert sorted(laad_env(f, env)) == ["GEMINI_API_KEY", "GEMINI_MODEL"]
    assert env == {"BESTAAT": "oud", "GEMINI_API_KEY": "geheim", "GEMINI_MODEL": "model-x"}
    assert laad_env(tmp_path / "bestaat-niet", {}) == []


def test_voorbeeld_env_bevat_geen_echte_waarden_en_wordt_niet_genegeerd_door_git():
    root = Path(__file__).resolve().parents[1]
    regels = [r for r in (root / ".env.example").read_text().splitlines() if "=" in r and not r.startswith("#")]
    assert regels == ["GEMINI_API_KEY=", "GEMINI_MODEL="]
    ignore = (root / ".gitignore").read_text().splitlines()
    assert ".env" in ignore and "!.env.example" in ignore


def test_dummies_spelen_de_hele_quiz_en_kiezen_elk_een_andere_heilige():
    import random
    from durfheilig import db as spel
    from durfheilig.app import maak_app
    from durfheilig.data import laad_heiligen, laad_vragen
    from durfheilig.dummies import maak_dummies
    db = spel.open_db()
    app = maak_app(db, laad_heiligen(), laad_vragen(), None, random.Random(1))
    namen = maak_dummies(app, laad_vragen(), 8)
    assert namen == [f"dummy{i}" for i in range(1, 9)]
    assert len(spel.gekozen_heiligen(db)) == 8                      # every dummy has a saint, and no saint twice
    assert all(spel.invulling(db, spel.speler_voor(db, n)["id"])["stap"] == "klaar" for n in namen)


def test_de_app_importeert_dummies_nooit():
    import durfheilig.app as app
    assert "dummies" not in open(app.__file__).read().replace("# ", "")  # same rule as dev.py: not part of the image


def test_dummies_stemmen_alleen_in_een_stemfase_en_de_knop_werkt_alleen_met_post():
    import random
    from starlette.testclient import TestClient
    from durfheilig import db as spel
    from durfheilig.app import maak_app
    from durfheilig.data import laad_heiligen, laad_vragen
    from durfheilig.dummies import laat_stemmen, maak_dummies
    db = spel.open_db()
    kern = maak_app(db, laad_heiligen(), laad_vragen(), None, random.Random(1))
    namen = maak_dummies(kern, laad_vragen(), 6)
    assert laat_stemmen(kern, db, namen) == 0                       # no game yet: nothing to vote in
    boss = TestClient(kern, headers={"remote-user": "leiding1", "remote-groups": "durfte,durfte-leiding"}, follow_redirects=True)
    boss.post("/beheer/spel/start", data={"eerste": ""})
    html = boss.get("/beheer/spel/inhoud", headers={"hx-request": "true"}).text
    boss.post("/beheer/spel/volgende", data={"van": re.search(r'name="van" value="([^"]*)"', html).group(1)})   # board -> first round
    assert laat_stemmen(kern, db, namen, seed=1) in range(1, 6)     # everyone but the round's subject (and readers) may vote
    dev = TestClient(maak_dev_app(db=db, dummies=namen), follow_redirects=True)
    assert dev.get("/dev/stem").status_code == 403                  # GET changes nothing
    assert dev.post("/dev/stem", headers={"sec-fetch-site": "cross-site"}).status_code == 403   # nor can another site press it
    r = dev.post("/dev/stem")
    assert r.status_code == 200 and "dummies hebben gestemd" in r.text


def test_main_vindt_de_dummies_terug_in_de_database(tmp_path, monkeypatch):
    """main() reads the dummy names from the database (rows are tuples); a crash here once stopped the launcher before it started."""
    import durfheilig.dev as dev
    monkeypatch.setenv("DURFHEILIG_DEV_DB", str(tmp_path / "d.db"))
    gestart = {}
    monkeypatch.setattr("uvicorn.run", lambda app, host, port: gestart.update(host=host, port=port, stem=app.stem))
    monkeypatch.setattr(dev, "laad_env", lambda *a, **k: [])
    monkeypatch.setattr(dev, "llm_uit_omgeving", lambda *a, **k: None)
    assert dev.main(["--dummies", "3", "--lan"]) == 0
    assert gestart["host"] == "0.0.0.0" and gestart["stem"] is not None
    gestart.clear()
    assert dev.main([]) == 0 and gestart["host"] == "127.0.0.1"      # without --lan only this computer can reach it


def test_pollregels_verdwijnen_uit_het_log_maar_fouten_en_andere_paden_niet():
    import logging
    from durfheilig.app import _ZonderPolling
    f = _ZonderPolling()
    def regel(pad, status):
        return logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d', ("1.2.3.4:5", "GET", pad, "1.1", status), None)
    assert not f.filter(regel("/spel/inhoud", 200)) and not f.filter(regel("/beheer/tv/inhoud?x=1", 200))
    assert f.filter(regel("/spel/inhoud", 500)) and f.filter(regel("/spel/stem", 200)) and f.filter(regel("/", 200))


def test_dev_pagina_toont_de_dummies_zodat_een_telefoon_ze_kan_kiezen():
    dev = TestClient(maak_dev_app(db=spel.open_db(), dummies=["dummy1", "dummy2"]), follow_redirects=True)
    t = dev.get("/dev").text
    assert 'href="/dev/als/dummy1"' in t and 'href="/dev/als/dummy2"' in t


def test_firewallregels_openen_en_sluiten_alleen_het_eigen_netwerk():
    from durfheilig.dev import firewall_regels
    open_, sluit = firewall_regels("192.168.50.99", 8000)
    assert open_ == "sudo ufw allow from 192.168.50.0/24 to any port 8000 proto tcp"
    assert sluit == "sudo ufw delete allow from 192.168.50.0/24 to any port 8000 proto tcp"
    assert "Anywhere" not in open_ and "from any" not in open_


def test_lan_toont_de_firewallopdracht_bij_start_en_bij_stoppen(tmp_path, monkeypatch, capsys):
    import durfheilig.dev as dev
    monkeypatch.setenv("DURFHEILIG_DEV_DB", str(tmp_path / "d.db"))
    monkeypatch.setenv("PORT", "8123")
    monkeypatch.setattr("uvicorn.run", lambda *a, **k: None)
    monkeypatch.setattr(dev, "laad_env", lambda *a, **k: [])
    monkeypatch.setattr(dev, "llm_uit_omgeving", lambda *a, **k: None)
    monkeypatch.setattr(dev, "_lan_ip", lambda: "10.1.2.3")
    dev.main(["--lan"])
    uit = capsys.readouterr().out
    assert uit.count("sudo ufw allow from 10.1.2.0/24 to any port 8123 proto tcp") == 1
    assert uit.count("sudo ufw delete allow from 10.1.2.0/24 to any port 8123 proto tcp") == 2     # at start and again when stopping
    dev.main([])
    assert "ufw" not in capsys.readouterr().out                      # without --lan nothing about a firewall
