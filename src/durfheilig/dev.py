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

from starlette.responses import HTMLResponse, RedirectResponse

from . import db as spel
from .app import maak_app
from .data import laad_heiligen, laad_vragen
from .llm import llm_uit_omgeving

NAAM = re.compile(r"^[a-z0-9_-]{1,30}$")
VOORBEELDEN = ["kind1", "kind2", "kind3", "kind4"]


def _pagina(huidig: str | None) -> HTMLResponse:
    kinderen = "".join(f'<li><a href="/dev/als/{n}">{n}</a></li>' for n in VOORBEELDEN)
    return HTMLResponse(
        "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
        "<body style='font:18px system-ui;max-width:32rem;margin:2rem auto;padding:0 16px'>"
        "<h1>Lokaal testen</h1><p>Je bent nu: <b>" + (huidig or "niemand") + "</b></p>"
        f"<h2>Kind</h2><ul>{kinderen}</ul>"
        "<h2>Begeleider</h2><ul><li><a href='/dev/als/leiding1'>leiding1 (ziet /beheer)</a></li></ul>"
        "<p><a href='/'>Naar de app</a></p>")


class AlsGebruiker:
    """ASGI-laag: zet Remote-User en Remote-Groups uit het cookie `dev_user`. Wie `leiding…` heet is begeleider."""

    def __init__(self, app):
        self.app = app

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
            return await _pagina(gebruiker)(scope, receive, send)
        if gebruiker is None:
            return await RedirectResponse("/dev", status_code=303)(scope, receive, send)
        groepen = "durfte,durfte-leiding" if gebruiker.startswith("leiding") else "durfte"
        headers = [(k, v) for k, v in scope["headers"] if k not in (b"remote-user", b"remote-groups", b"remote-name", b"remote-email")]
        headers = [(k, v) for k, v in headers if k != b"x-durfte-dev"]
        headers += [(b"remote-user", gebruiker.encode()), (b"remote-groups", groepen.encode()), (b"x-durfte-dev", b"1")]
        await self.app({**scope, "headers": headers}, receive, send)


def maak_dev_app(db=None, llm=None):
    return AlsGebruiker(maak_app(db or spel.open_db(Path(os.environ.get("DURFHEILIG_DEV_DB", "data/spel-dev.db"))),
                                 laad_heiligen(), laad_vragen(), llm))


def laad_env(pad: str | Path = ".env", env=os.environ) -> list[str]:
    """Lees KEY=waarde-regels uit een .env en zet ze in `env`, behalve wat al gezet is. Geeft de gezette namen terug."""
    pad = Path(pad)
    gezet = []
    if not pad.is_file():
        return gezet
    for regel in pad.read_text(encoding="utf-8").splitlines():
        regel = regel.strip()
        if not regel or regel.startswith("#") or "=" not in regel:
            continue
        naam, waarde = (x.strip() for x in regel.split("=", 1))
        waarde = waarde.strip("\"'")
        if naam and waarde and naam not in env:
            env[naam] = waarde
            gezet.append(naam)
    return gezet


def main() -> int:
    import uvicorn

    gezet = laad_env()
    if gezet:
        print(".env gelezen:", ", ".join(gezet))
    llm = llm_uit_omgeving()
    print("LLM:", "Gemini" if llm else "geen sleutel, de vaste terugval (vul GEMINI_API_KEY en GEMINI_MODEL in `.env` in, zie `.env.example`)")
    poort = int(os.environ.get("PORT", "8000"))
    print(f"Open http://127.0.0.1:{poort}/dev")
    uvicorn.run(maak_dev_app(llm=llm), host="127.0.0.1", port=poort)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
