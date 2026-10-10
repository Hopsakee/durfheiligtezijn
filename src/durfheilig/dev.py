"""Lokaal proberen op je eigen computer, zonder Authelia.

    python -m durfheilig.dev        daarna http://127.0.0.1:8000/dev

De echte app vertrouwt de headers die Authelia en Caddy meesturen. Een browser stuurt die niet,
dus dit startje zet ze zelf, uit een cookie die je kiest op /dev. Het luistert alleen op
127.0.0.1 en de echte app (`durfheilig.app`, de Docker-image) importeert dit bestand nooit.
Gebruik per kind een eigen privévenster of browser, want het cookie hoort bij de browser.
"""

import os
import re
from http.cookies import SimpleCookie
from pathlib import Path

from .env import laad_env  # noqa: F401  (also imported from here by tests)

from starlette.responses import HTMLResponse, RedirectResponse

from . import db as spel
from .app import maak_app, stil_pollregels
from .data import laad_heiligen, laad_vragen
from .llm import beschrijving, llm_uit_omgeving

NAAM = re.compile(r"^[a-z0-9_-]{1,30}$")
VOORBEELDEN = ["kind1", "kind2", "kind3", "kind4"]


def _pagina(huidig: str | None, dummies: list[str] = ()) -> HTMLResponse:
    kinderen = "".join(f'<li><a href="/dev/als/{n}">{n}</a></li>' for n in [*VOORBEELDEN, *dummies])
    return HTMLResponse(
        "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
        "<body style='font:18px system-ui;max-width:32rem;margin:2rem auto;padding:0 16px'>"
        "<h1>Lokaal testen</h1><p>Je bent nu: <b>" + (huidig or "niemand") + "</b></p>"
        f"<h2>Kind</h2><ul>{kinderen}</ul>"
        "<h2>Begeleider</h2><ul><li><a href='/dev/als/leiding1'>leiding1 (ziet /beheer)</a></li></ul>"
        "<h2>Nepdeelnemers stemmen</h2><form method=post action='/dev/stem'><button style='font:inherit;padding:.6rem 1rem'>Laat de dummies stemmen</button></form>"
        "<p>Zo test je het raadspel zonder telefoons: de dummies stemmen in de ronde die nu loopt.</p>"
        "<p><a href='/'>Naar de app</a></p>")


class AlsGebruiker:
    """ASGI-laag: zet Remote-User en Remote-Groups uit het cookie `dev_user`. Wie `leiding…` heet is begeleider."""

    def __init__(self, app, stem=None, dummies: list[str] = ()):
        self.app = app
        self.dummies = list(dummies)   # listed on /dev so a phone can tap one: to vote you must be a player, a leader is none
        self.stem = stem   # called by POST /dev/stem; returns how many dummies voted

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        kop = dict(scope["headers"])
        cookies = SimpleCookie(kop.get(b"cookie", b"").decode())
        gebruiker = cookies["dev_user"].value if "dev_user" in cookies else None
        gebruiker = gebruiker if gebruiker and NAAM.match(gebruiker) else None
        pad = scope["path"]
        if pad == "/dev" or pad.startswith("/dev/"):
            if pad.startswith("/dev/als/"):
                # A page on another site must not be able to switch who you are.
                if kop.get(b"sec-fetch-site", b"same-origin") not in (b"same-origin", b"none"):
                    return await HTMLResponse("Niet toegestaan.", status_code=403)(scope, receive, send)
                naam = pad.removeprefix("/dev/als/")
                if not NAAM.match(naam):
                    return await HTMLResponse("Alleen a-z, 0-9, - en _.", status_code=400)(scope, receive, send)
                r = RedirectResponse("/", status_code=303)
                r.set_cookie("dev_user", naam, httponly=True, samesite="lax")
                return await r(scope, receive, send)
            if pad == "/dev/stem" and self.stem is not None:
                if scope["method"] != "POST" or kop.get(b"sec-fetch-site", b"same-origin") not in (b"same-origin", b"none"):
                    return await HTMLResponse("Niet toegestaan.", status_code=403)(scope, receive, send)
                n = self.stem()
                return await HTMLResponse(f"<meta charset=utf-8><body style='font:18px system-ui;margin:2rem'>{n} dummies hebben gestemd. "
                                          "<a href='/dev'>Terug</a>")(scope, receive, send)
            return await _pagina(gebruiker, self.dummies)(scope, receive, send)
        if gebruiker is None:
            return await RedirectResponse("/dev", status_code=303)(scope, receive, send)
        groepen = "durfte,durfte-leiding" if gebruiker.startswith("leiding") else "durfte"
        headers = [(k, v) for k, v in scope["headers"] if k not in (b"remote-user", b"remote-groups", b"remote-name", b"remote-email")]
        headers += [(b"remote-user", gebruiker.encode()), (b"remote-groups", groepen.encode())]
        await self.app({**scope, "headers": headers}, receive, send)


def maak_dev_app(db=None, llm=None, dummies: list[str] | None = None):
    db = db or spel.open_db(Path(os.environ.get("DURFHEILIG_DEV_DB", "data/spel-dev.db")))
    app = maak_app(db, laad_heiligen(), laad_vragen(), llm, extra_menu=[("/dev", "Wissel van persoon (alleen lokaal)")])
    stem = None
    if dummies:
        from .dummies import laat_stemmen
        stem = lambda: laat_stemmen(app, db, dummies)   # noqa: E731
    return AlsGebruiker(app, stem, dummies or [])


def _lan_ip() -> str:
    """The address of this computer on the local network (the interface a packet to the outside would leave from; nothing is sent)."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sk:
        try:
            sk.connect(("192.0.2.1", 9))    # documentation address: no traffic, it only makes the OS choose an interface
            return sk.getsockname()[0]
        except OSError:
            return "<jouw-ip>"


def wis_dev_db(pad: Path) -> None:
    """Remove the dev database with its SQLite side files. The -wal and -shm files belong to the database: deleting only the main file leaves
    them behind and the next start fails with "disk I/O error"."""
    for suffix in ("", "-wal", "-shm", "-journal"):
        Path(f"{pad}{suffix}").unlink(missing_ok=True)


def firewall_regels(ip: str, poort: int) -> tuple[str, str]:
    """The ufw commands that open the port for this network only, and close it again. Printed for the person running the app, never run by it:
    changing a firewall needs sudo and is the administrator's call. Assumes a /24 network, which is what home routers use."""
    net = ".".join(ip.split(".")[:3]) + ".0/24"
    regel = f"from {net} to any port {poort} proto tcp"
    return f"sudo ufw allow {regel}", f"sudo ufw delete allow {regel}"


def main(argv: list[str] | None = None) -> int:
    import argparse
    import uvicorn

    ap = argparse.ArgumentParser(description="Lokaal proberen zonder Authelia")
    ap.add_argument("--dummies", type=int, default=0, metavar="N", help="maak eerst N nepdeelnemers die de quiz doorlopen en een heilige kiezen")
    ap.add_argument("--lan", action="store_true", help="luister op je netwerk zodat telefoons kunnen meedoen (iedereen op dat netwerk kan dan een persoon kiezen)")
    ap.add_argument("--schoon", action="store_true", help="begin met een lege lokale database (alleen het dev-bestand)")
    a = ap.parse_args(argv)
    if a.schoon:
        wis_dev_db(Path(os.environ.get("DURFHEILIG_DEV_DB", "data/spel-dev.db")))
    gezet = laad_env()
    if gezet:
        print(".env gelezen:", ", ".join(gezet))
    stil_pollregels()
    llm = llm_uit_omgeving()
    print("LLM:", beschrijving(llm))
    db = spel.open_db(Path(os.environ.get("DURFHEILIG_DEV_DB", "data/spel-dev.db")))
    if a.dummies:
        from .dummies import maak_dummies
        # Their own app on the same database and without an LLM: dummies cost nothing and never touch a provider.
        namen = maak_dummies(maak_app(db, laad_heiligen(), laad_vragen(), None), laad_vragen(), a.dummies)
        print(f"{len(namen)} nepdeelnemers gemaakt ({namen[0]} t/m {namen[-1]}); wissel met /dev/als/<naam>")
    with db.lock:
        alle = [r[0] for r in db.execute("select gebruikersnaam from speler where gebruikersnaam like 'dummy%'").fetchall()]
    app = maak_dev_app(db=db, llm=llm, dummies=alle)
    poort = int(os.environ.get("PORT", "8000"))
    sluit = None
    if a.lan:
        ip = _lan_ip()
        open_, sluit = firewall_regels(ip, poort)
        print("LET OP: iedereen op dit netwerk kan zich nu als elke persoon voordoen, ook als begeleider. Gebruik dit alleen op een netwerk dat je vertrouwt.")
        print(f"Open op de tv en de telefoons: http://{ip}:{poort}/dev   (zelfde wifi)")
        print("Tijdelijk de firewall openen (alleen nodig als `sudo ufw status` aan staat; geeft een telefoon een time-out, dan is dit de oorzaak):")
        print(f"    {open_}")
        print(f"Daarna weer sluiten (dit wordt ook getoond als je stopt):\n    {sluit}")
        print("Controleer het netwerk met `ip -4 addr show`: dit gaat uit van een /24-netwerk.")
    else:
        print(f"Open http://127.0.0.1:{poort}/dev")
    try:
        uvicorn.run(app, host="0.0.0.0" if a.lan else "127.0.0.1", port=poort)
    finally:
        if sluit:
            print(f"\nGestopt. Heb je de firewall geopend, sluit hem dan weer:\n    {sluit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
