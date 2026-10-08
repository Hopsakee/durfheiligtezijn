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
