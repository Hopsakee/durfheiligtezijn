"""Load and validate the saints and the question bank.

Both live as JSON in git (`data/heiligen.json`, `data/vragen.json`) and are read into memory.
A record that breaks the rubric's rules fails loudly with its qid, instead of silently
scoring as zero.
"""

import json
import os
import warnings
from dataclasses import dataclass, field
from pathlib import Path

_REPO_DATA = Path(__file__).resolve().parents[2] / "data"


def data_dir() -> Path:
    """`DURFHEILIG_DATA` if set (the Docker image sets it), else the repo's `data/`, else `./data`."""
    if os.environ.get("DURFHEILIG_DATA"):
        return Path(os.environ["DURFHEILIG_DATA"])
    return _REPO_DATA if _REPO_DATA.is_dir() else Path.cwd() / "data"


DATA_DIR = _REPO_DATA

# Order matters only for display. The sign convention comes from docs/design/rubric.md:
# for samen_alleen the minus pole is "alleen"; for the other axes minus is the first word.
ASSEN = ("samen_alleen", "denken_doen", "achter_voorop", "plek_pad", "diepgang_licht", "vrede_strijd")
GESLACHTEN = ("mannelijk", "vrouwelijk")
MIN_BEKENDE_ASSEN = 4


class DataFout(ValueError):
    """A saint or question that breaks the rubric's rules."""


class TeWeinigAssen(DataFout):
    """A saint known on fewer than MIN_BEKENDE_ASSEN axes: excluded until the record is completed."""


@dataclass(frozen=True)
class Heilige:
    qid: str
    naam: str
    geslacht: str
    assen: dict[str, int | None]
    interesses: tuple[str, ...]
    record: dict = field(repr=False, compare=False, hash=False)

    @property
    def bekende_assen(self) -> dict[str, int]:
        return {a: s for a, s in self.assen.items() if s is not None}


@dataclass(frozen=True)
class Vraag:
    id: str
    as_: str
    vraag: str
    min: dict
    plus: dict


@dataclass(frozen=True)
class Vragenbank:
    assen: tuple[dict, ...]
    vragen: tuple[Vraag, ...]
    interessevraag: dict

    @property
    def interesses(self) -> tuple[str, ...]:
        return tuple(o["interesse"] for o in self.interessevraag["opties"])

    def per_as(self, as_: str) -> list[Vraag]:
        return [v for v in self.vragen if v.as_ == as_]


def _heilige(r: dict, interesse_lijst: set[str]) -> Heilige:
    qid = r.get("qid", "?")
    fout = lambda msg: DataFout(f"{qid} ({r.get('naam', '?')}): {msg}")
    if r.get("geslacht") not in GESLACHTEN:
        raise fout(f"geslacht {r.get('geslacht')!r} niet in {GESLACHTEN}")
    ruw = r.get("assen") or {}
    if set(ruw) != set(ASSEN):
        raise fout(f"assen {sorted(ruw)} wijken af van {sorted(ASSEN)}")
    assen: dict[str, int | None] = {}
    for a in ASSEN:
        s = ruw[a].get("score") if isinstance(ruw[a], dict) else ruw[a]
        if s is not None and (not isinstance(s, int) or isinstance(s, bool) or not -2 <= s <= 2):
            raise fout(f"as {a} heeft score {s!r}, verwacht -2..2 of null")
        assen[a] = s
    bekend = sum(s is not None for s in assen.values())
    if bekend < MIN_BEKENDE_ASSEN:
        raise TeWeinigAssen(f"{qid} ({r.get('naam', '?')}): "
                            f"maar {bekend} van 6 assen bekend, minimaal {MIN_BEKENDE_ASSEN}")
    interesses = tuple(i["interesse"] if isinstance(i, dict) else i for i in r.get("interesses") or [])
    if not 1 <= len(interesses) <= 3:
        raise fout(f"{len(interesses)} interesses, verwacht 1 tot 3")
    onbekend = [i for i in interesses if i not in interesse_lijst]
    if onbekend:
        raise fout(f"interesses buiten de vaste lijst: {onbekend}")
    return Heilige(qid, r["naam"], r["geslacht"], assen, interesses, r)


def laad_heiligen(pad: Path | None = None) -> list[Heilige]:
    """Every other rule violation fails loudly. A record with too few known axes is left out
    with a warning, per rubric.md ("gaat terug voor aanvulling"), so one edited record cannot
    stop the quiz from starting."""
    doc = json.loads((pad or data_dir() / "heiligen.json").read_text(encoding="utf-8"))
    lijst = set(doc["interesses_lijst"])
    heiligen = []
    for r in doc["records"]:
        try:
            heiligen.append(_heilige(r, lijst))
        except TeWeinigAssen as e:
            warnings.warn(f"heilige overgeslagen: {e}", stacklevel=2)
    dubbel = {h.qid for h in heiligen if sum(x.qid == h.qid for x in heiligen) > 1}
    if dubbel:
        raise DataFout(f"dubbele qid's: {sorted(dubbel)}")
    return heiligen


def laad_vragen(pad: Path | None = None) -> Vragenbank:
    doc = json.loads((pad or data_dir() / "vragen.json").read_text(encoding="utf-8"))
    vragen = []
    for v in doc["vragen"]:
        if v["as"] not in ASSEN:
            raise DataFout(f"vraag {v['id']}: onbekende as {v['as']!r}")
        for kant in ("min", "plus"):
            if not v[kant].get("tekst") or not v[kant].get("icoon"):
                raise DataFout(f"vraag {v['id']}: antwoord {kant} mist tekst of icoon")
        vragen.append(Vraag(v["id"], v["as"], v["vraag"], v["min"], v["plus"]))
    return Vragenbank(tuple(doc["assen"]), tuple(vragen), doc["interessevraag"])
