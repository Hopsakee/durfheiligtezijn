"""Nepdeelnemers voor lokaal testen van het raadspel: elk speelt de hele quiz door de echte app en kiest een heilige.

De LLM staat uit (vaste teksten), dus het kost niets. Alleen voor een lokale database: elke gekozen heilige is daarna bezet.
De echte app importeert dit bestand nooit (de image laat het weg, zie .dockerignore)."""
import random
import re

from starlette.testclient import TestClient

from .data import Vragenbank
from .scoring import VOORKEUR_GESLACHT

NAMEN = ["Aap", "Beer", "Cobra", "Dolfijn", "Ekster", "Fazant", "Gems", "Haai", "Ijsvogel", "Jaguar", "Kameel", "Lynx", "Mees", "Nijlpaard",
         "Otter", "Pauw", "Quokka", "Raaf", "Sneeuwuil", "Tapir", "Uil", "Vos", "Wolf", "Zebra"]
OPEN = ["tekenen", "voetballen", "eerlijkheid", "mensen helpen", "gamen", "muziek maken", "dieren", "bakken"]


def maak_dummies(app, vragen: Vragenbank, n: int, seed: int = 1) -> list[str]:
    """Add `n` players named dummy1..dummyN, each through the real quiz. Returns their usernames (log in as these with /dev/als/<naam>)."""
    rng = random.Random(seed)
    namen = []
    for i in range(1, n + 1):
        naam = f"dummy{i}"
        c = TestClient(app, headers={"remote-user": naam}, follow_redirects=True)
        c.post("/welkom", data={"nickname": f"{NAMEN[(i - 1) % len(NAMEN)]}{'' if i <= len(NAMEN) else i}"})
        c.post("/voorkeur", data={"voorkeur": rng.choice(list(VOORKEUR_GESLACHT))})
        for _ in range(12):
            vid = re.search(r'name="vid" value="(\w+)"', c.get("/quiz").text).group(1)
            c.post("/vraag", data={"vid": vid, "kant": rng.choice(["min", "plus"])})
        c.post("/interesses", data={"interesse": rng.sample(list(vragen.interesses), 2)})
        r = c.post("/open", data={"a1": rng.choice(OPEN), "a2": rng.choice(OPEN)})
        ids = list(dict.fromkeys(re.findall(r'name="(v\d)"', r.text)))
        r = c.post("/vervolg", data={v: rng.choice(["min", "plus"]) for v in ids})
        kandidaten = re.findall(r'name="gekozen" value="([^"]+)"', r.text)
        if len(kandidaten) != 3:
            raise RuntimeError(f"{naam}: geen drie heiligen om uit te kiezen")
        c.post("/keuze", data={"gekozen": rng.choice(kandidaten), "want": "dummy"})
        namen.append(naam)
    return namen


def laat_stemmen(app, db, namen: list[str], kans_juist: float = 0.7, seed: int | None = None) -> int:
    """In the current voting phase every dummy that may vote does: for the right saint with chance `kans_juist`, else a random one on the board.
    Returns how many votes the app accepted. Outside a voting phase nothing is accepted, so it is safe to call at any time."""
    from . import db as spel
    rng = random.Random(seed)
    status = spel.spel_status(db)
    ronde = next((r for r in spel.rondes(db) if r["id"] == status["huidige_ronde"]), None) if status and status["huidige_ronde"] else None
    if not ronde:
        return 0
    onderwerp = next((x for x in spel.spelers_klaar(db) if x["id"] == ronde["speler_id"]), None)
    if not onderwerp:
        return 0
    from .data import laad_heiligen
    from .raadspel import zichtbaar_bord
    juist = onderwerp["gekozen"]
    bord = [b["qid"] for b in zichtbaar_bord(spel.bord_rijen(db), {h.qid: h for h in laad_heiligen()}, onderwerp["voorkeur"], juist)]
    gedaan = 0
    for naam in namen:
        vorig = len(spel.stemmen(db, ronde["id"], 1)) + len(spel.stemmen(db, ronde["id"], 2))
        c = TestClient(app, headers={"remote-user": naam}, follow_redirects=True)
        c.post("/spel/stem", data={"qid": juist if juist and rng.random() < kans_juist else rng.choice(bord)})
        gedaan += (len(spel.stemmen(db, ronde["id"], 1)) + len(spel.stemmen(db, ronde["id"], 2))) > vorig
    return gedaan
