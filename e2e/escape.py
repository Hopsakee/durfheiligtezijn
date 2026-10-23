# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright"]
# ///
"""End-to-end check of the escape room in a real (headless) browser.

    uv run e2e/escape.py [--uit <map voor screenshots>] [--chromium /usr/bin/chromium]

Starts the dev server on a free port with an empty database of its own and plays: two ordinary team accounts open /escape and wait, the
leader puts them in team A and B (their screens switch by themselves), starts; team A sends a wrong and a right answer (with the "encrypted" send), takes a hint, finds more evidence; team B
finds one. Checks the room laptops, logged in with the team accounts (waiting, then the team's own detective board, landing post-its, hint shown big, the other team in the corner), the leader's
both-teams screen and control page, taking an account out of its team, and pause. Collects console errors, counts the tones the screens start, and saves
screenshots. The CDN scripts FastHTML adds (htmx) are answered with an empty file: the escape pages do not use them, and the box has no CDN.
"""
import argparse
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

REPO = Path(__file__).resolve().parents[1]

# Counts every tone a page starts, so the script can check that a screen made sound without anyone listening.
TELGELUID = """
(function () {
  window.__tonen = 0;
  var C = window.AudioContext || window.webkitAudioContext;
  if (!C) return;
  var echt = C.prototype.createOscillator;
  C.prototype.createOscillator = function () { window.__tonen++; return echt.apply(this, arguments); };
})();
"""

TELEFOON = dict(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
LAPTOP = dict(viewport={"width": 1366, "height": 768})
GROOT = dict(viewport={"width": 1600, "height": 900})


def vrije_poort() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wacht_op(poort: int, proc, sec: float = 30) -> None:
    eind = time.time() + sec
    while time.time() < eind:
        if proc.poll() is not None:
            raise SystemExit(f"dev-server stopte: {proc.stdout.read()}")
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", poort)) == 0:
                return
        time.sleep(0.2)
    raise SystemExit("dev-server kwam niet op")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--uit", default=str(REPO / "e2e" / "screenshots"))
    ap.add_argument("--chromium", default="/usr/bin/chromium")
    a = ap.parse_args()
    uit = Path(a.uit)
    uit.mkdir(parents=True, exist_ok=True)
    for oud in uit.glob("*.png"):
        oud.unlink()
    poort = vrije_poort()
    basis = f"http://127.0.0.1:{poort}"
    env = {**os.environ, "PORT": str(poort), "DURFHEILIG_DEV_DB": f"{tempfile.mkdtemp()}/e2e.db", "PYTHONUNBUFFERED": "1"}
    for k in ("GEMINI_API_KEY", "LLM_PROVIDER", "OPENAI_API_KEY"):
        env.pop(k, None)
    server = subprocess.Popen(["uv", "run", "--frozen", "--no-sync", "python", "-m", "durfheilig.dev"], cwd=REPO, env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    fouten: list[str] = []
    try:
        wacht_op(poort, server)
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=a.chromium, headless=True)

            def apparaat(naam: str, wie: str, soort: dict):
                """A device of its own (own cookies), logged in as `wie` through the dev layer."""
                ctx = browser.new_context(**soort)
                for cdn in ("https://cdn.jsdelivr.net/**", "https://unpkg.com/**"):
                    ctx.route(cdn, lambda r: r.fulfill(status=200, body="", content_type="text/javascript"))
                ctx.add_init_script(TELGELUID)
                pg = ctx.new_page()
                pg.on("console", lambda m: fouten.append(f"{naam}: {m.text}") if m.type == "error" else None)
                pg.on("pageerror", lambda e: fouten.append(f"{naam}: {e}"))
                pg.on("dialog", lambda d: d.accept())
                pg.goto(f"{basis}/dev/als/{wie}")
                return pg

            leiding = apparaat("leiding", "leiding1", GROOT)
            tel_a = apparaat("telefoon A", "teamtelefoon-a", TELEFOON)     # ordinary accounts (group durfte), no leader
            tel_b = apparaat("telefoon B", "teamtelefoon-b", TELEFOON)
            leider_tel = apparaat("leider op telefoon", "leiding2", TELEFOON)

            # The team phones open /escape and wait for the leader.
            tel_a.goto(f"{basis}/escape")
            expect(tel_a.get_by_text("Wacht op de recherche")).to_be_visible()
            tel_a.screenshot(path=uit / "telefoon-1-wachten.png")
            tel_b.goto(f"{basis}/escape")
            expect(tel_b.get_by_text("Wacht op de recherche")).to_be_visible()

            # The room laptops log in with the same team accounts (no leader login in a room) and wait too.
            kamer_a = apparaat("laptop A", "teamtelefoon-a", LAPTOP)
            kamer_a.goto(f"{basis}/escape/bord")
            expect(kamer_a.get_by_text("Wacht op de recherche")).to_be_visible()
            kamer_a.screenshot(path=uit / "laptop-a-00-wachten.png")
            kamer_b = apparaat("laptop B", "teamtelefoon-b", LAPTOP)
            kamer_b.goto(f"{basis}/escape/bord")
            expect(kamer_b.get_by_text("Wacht op de recherche")).to_be_visible()
            assert kamer_a.context.request.get(f"{basis}/beheer/escape/tv").status == 403   # a team account has no leader screens

            # A leader's phone cannot play.
            leider_tel.goto(f"{basis}/escape")
            expect(leider_tel.get_by_text("kunnen hier niets insturen")).to_be_visible()
            leider_tel.goto(f"{basis}/escape/puzzel/1")
            expect(leider_tel.get_by_label("Antwoord")).to_have_count(0)

            # The leader puts them in a team; the phones switch by themselves.
            leiding.goto(f"{basis}/beheer/escape")
            wacht = leiding.locator(".wachtend")
            expect(wacht.get_by_text("teamtelefoon-a")).to_be_visible(timeout=5000)
            expect(wacht.get_by_text("teamtelefoon-b")).to_be_visible()
            leiding.screenshot(path=uit / "beheer-0-indelen.png", full_page=True)
            wacht.locator("li", has_text="teamtelefoon-a").get_by_role("button", name="→ team A").click()
            leiding.locator(".wachtend li", has_text="teamtelefoon-b").get_by_role("button", name="→ team B").click()
            expect(tel_a.locator(".lijnkop")).to_contain_text("Team A", timeout=8000)
            expect(tel_b.locator(".lijnkop")).to_contain_text("Team B", timeout=8000)
            expect(kamer_a.locator("#team-A.prikbord")).to_be_visible(timeout=8000)   # the laptops switch by themselves
            expect(kamer_b.locator("#team-B.prikbord")).to_be_visible(timeout=8000)
            expect(kamer_a.locator("#team-B")).to_have_count(0)

            # A team account that lands on / gets its two buttons on top; they lead to the phone and the board.
            tel_a.goto(f"{basis}/")
            expect(tel_a.locator(".teamknoppen a")).to_have_count(2)
            tel_a.screenshot(path=uit / "team-start.png")
            tel_a.get_by_role("link", name="🖥️ Recherchebord").first.click()
            expect(tel_a.locator("#team-A.prikbord")).to_be_visible()
            tel_a.goto(f"{basis}/")
            tel_a.locator(".teamknoppen").get_by_role("link", name="📱 Teamtelefoon").click()
            expect(tel_a.locator(".lijnkop")).to_contain_text("Team A")
            expect(leiding.locator("section.team-a").get_by_text("teamtelefoon-a")).to_be_visible()

            leiding.get_by_role("button", name="▶ Start beide klokken").click()
            expect(leiding.get_by_text("De klokken lopen")).to_be_visible()

            # The room laptops and the leader's tv, sound on.
            kamer_a.screenshot(path=uit / "laptop-a-0-geluid-aan.png")
            kamer_a.locator("#esc-geluid").click()
            kamer_b.locator("#esc-geluid").click()
            tv = leiding.context.new_page()
            tv.on("console", lambda m: fouten.append(f"tv: {m.text}") if m.type == "error" else None)
            tv.goto(f"{basis}/beheer/escape/tv")
            tv.locator("#esc-geluid").click()

            t1 = kamer_a.locator(".zij [data-klok=A]").inner_text()
            kamer_a.wait_for_timeout(1600)
            t2 = kamer_a.locator(".zij [data-klok=A]").inner_text()
            assert t1 != t2 and ":" in t2, f"de klok tikt niet: {t1!r} en {t2!r}"
            expect(kamer_a.locator(".postit.leeg")).to_have_count(5)
            tonen = kamer_a.evaluate("window.__tonen")

            def stuur(tel, nr: int, antwoord: str, schot: str | None = None) -> float:
                tel.goto(f"{basis}/escape/puzzel/{nr}")
                tel.get_by_label("Antwoord").fill(antwoord)
                t0 = time.time()
                tel.get_by_role("button", name="Verstuur ▸").click()
                expect(tel.locator("#esc-zend")).to_be_visible()
                if schot:
                    tel.wait_for_timeout(800)
                    tel.screenshot(path=uit / schot)
                expect(tel.locator(".uitslag")).to_be_visible(timeout=5000)
                return time.time() - t0

            # Team A: wrong, then right.
            duur = stuur(tel_a, 1, "made by adults", "telefoon-2-versleutelen.png")
            expect(tel_a.get_by_text("Afgewezen")).to_be_visible()
            assert duur >= 1.4, f"het versturen duurde maar {duur:.2f} s"
            tel_a.screenshot(path=uit / "telefoon-3-afgewezen.png")
            kamer_a.wait_for_timeout(2600)
            assert kamer_a.evaluate("window.__tonen") > tonen, "geen zoemer in kamer A bij een fout antwoord"

            stuur(tel_a, 1, "Made by Kids")
            expect(tel_a.get_by_text("Ontvangen")).to_be_visible()
            tel_a.screenshot(path=uit / "telefoon-4-ontvangen.png")
            expect(kamer_a.locator(".postit.land")).to_have_count(1, timeout=5000)
            expect(kamer_a.locator("#esc-melding.band .m-tekst")).to_contain_text("gemaakt door kinderen")
            kamer_a.wait_for_timeout(500)
            kamer_a.screenshot(path=uit / "laptop-a-1-briefje-landt.png")

            # Team A takes a hint: big on its own laptop for about 15 s, and on the phone.
            tel_a.goto(f"{basis}/escape/puzzel/3")
            tel_a.get_by_role("link", name="Hint 1 van 3").click()
            tel_a.get_by_role("button", name="Ja, geef de hint").click()
            expect(tel_a.locator(".hintlijst li")).to_have_count(1)
            tel_a.screenshot(path=uit / "telefoon-5-hint.png")
            hint = tel_a.locator(".hintlijst li").inner_text().replace("💡", "").strip()
            expect(kamer_a.locator("#esc-melding.hint .m-tekst")).to_have_text(hint, timeout=12000)
            kamer_a.screenshot(path=uit / "laptop-a-2-hint.png")
            kamer_a.wait_for_timeout(10000)
            expect(kamer_a.locator("#esc-melding.hint")).to_be_visible()
            expect(kamer_b.locator("#esc-melding.hint")).to_be_hidden()              # the other room does not get team A's hint
            assert hint not in kamer_b.content(), "de hint van team A staat op het bord van team B"

            # More evidence: A finds 2 and 5 (the read order), B finds 4.
            stuur(tel_a, 2, "12")
            stuur(tel_a, 5, "7500")
            stuur(tel_b, 4, "alleen samen houden we de prijzen hoog")
            tel_b.screenshot(path=uit / "telefoon-6-ontvangen-b.png")

            expect(kamer_a.locator(".postit:not(.leeg)")).to_have_count(3, timeout=8000)
            expect(kamer_a.locator(".prikbord line")).to_have_count(3)
            expect(kamer_a.locator(".postit .pv .chip")).to_have_count(4)
            expect(kamer_a.locator(".hoek .briefjes i:not(.uit)")).to_have_count(1)
            expect(kamer_b.locator(".postit:not(.leeg)")).to_have_count(1)
            expect(kamer_b.locator(".hoek .briefjes i:not(.uit)")).to_have_count(3)
            expect(kamer_a.locator("#esc-melding")).to_be_hidden(timeout=30000)
            kamer_a.wait_for_timeout(1500)
            kamer_a.screenshot(path=uit / "laptop-a-3-prikbord.png")
            expect(kamer_b.locator("#esc-melding")).to_be_hidden(timeout=15000)
            kamer_b.screenshot(path=uit / "laptop-b-1-prikbord.png")

            expect(tv.locator("#esc-melding")).to_be_hidden(timeout=30000)
            expect(tv.locator("#team-A .vak.goed")).to_have_count(3)
            expect(tv.locator("#team-A .straf")).to_contain_text("−3 min")
            tv.screenshot(path=uit / "tv-leiding-beide-teams.png")

            tel_a.goto(f"{basis}/escape")
            tel_a.wait_for_timeout(400)
            tel_a.screenshot(path=uit / "telefoon-7-bewijzen.png", full_page=True)

            leiding.goto(f"{basis}/beheer/escape")
            expect(leiding.get_by_text("Slotcode voor beide kistjes")).to_be_visible()
            expect(leiding.get_by_text(f"{basis}/escape/bord")).to_be_visible()
            leiding.screenshot(path=uit / "beheer-1-bediening.png", full_page=True)

            # Pause stops every clock.
            leiding.get_by_role("button", name="⏸ Pauzeer beide klokken").click()
            kamer_a.wait_for_timeout(2600)
            p1 = kamer_a.locator(".zij [data-klok=A]").inner_text()
            kamer_a.wait_for_timeout(1500)
            assert kamer_a.locator(".zij [data-klok=A]").inner_text() == p1, "de klok loopt door tijdens de pauze"
            leiding.get_by_role("button", name="▶ Hervat beide klokken").click()

            tonen = (kamer_a.evaluate("window.__tonen"), kamer_b.evaluate("window.__tonen"), tv.evaluate("window.__tonen"))

            # Take team B's account out of its team: the phone and the laptop go back to waiting by themselves.
            leiding.locator("section.team-b").get_by_role("button", name="Uit team").click()
            expect(leiding.locator(".wachtend").get_by_text("teamtelefoon-b")).to_be_visible()
            expect(tel_b.get_by_text("Wacht op de recherche")).to_be_visible(timeout=8000)
            expect(kamer_b.get_by_text("Wacht op de recherche")).to_be_visible(timeout=8000)

            print(f"tonen gestart: laptop A {tonen[0]} | laptop B {tonen[1]} | tv {tonen[2]} | versturen duurde {duur:.2f} s")
            browser.close()
    finally:
        server.terminate()
        try:
            server.wait(5)
        except subprocess.TimeoutExpired:
            server.kill()
    if fouten:
        print("Console-fouten:", *fouten, sep="\n  ")
        return 1
    print(f"Alles goed. Screenshots in {uit}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
