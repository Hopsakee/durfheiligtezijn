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
