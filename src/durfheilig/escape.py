"""De escaperoom X-ploitation: twee teams zoeken in twee kamers tegelijk vijf bewijzen, de schermen tonen de race.

Puzzels, geaccepteerde antwoorden, hints en dossierregels staan in `data/escape.json` (inhoud in git, gecontroleerd bij het laden); wat er
gebeurt staat in SQLite (de `escape_*` tabellen in db.py). Elk team heeft één teamtelefoon met een eigen gewoon account (geen leiding);
wie `/escape` opent wacht tot de leiding het account op `/beheer/escape` in team A of B zet, en voert daarna bewijzen in en koopt hints. Elke kamer
heeft een laptop met het prikbord van het team (`/beheer/escape/tv?team=A`); `/beheer/escape/tv` toont beide teams voor de leiding, en
`/beheer/escape` is de bediening.

De klok rekent de server uit (start, pauzes, hintstraf, extra minuten), zodat een herladen scherm de juiste tijd toont; tussen twee polls telt
de pagina zelf af. De schermen pollen met een eigen klein script (geen htmx): de tv moet na elke verversing toch klok en geluid bijwerken,
en zo werkt het ook zonder CDN.
"""

import functools
import json
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from fasthtml.common import A, B, Button, Div, Form, H2, I, Input, Label, Li, P, Response, Script, Section, Span, Ul
from fasthtml.svg import Line, Svg

from . import db as spel
from .data import DataFout, data_dir
from .ui import is_leiding, naar, pagina

TEAMS = ("A", "B")
HINTS_PER_PUZZEL = 3
SLOT_CIJFERS = 3   # the padlocks have three dials: the order-puzzle names three of the digit-bearing puzzles
MAX_ANTWOORD = 80


# ---------------------------------------------------------------- de inhoud, uit data/escape.json

@dataclass(frozen=True)
class Puzzel:
    nr: int
    naam: str          # always on screen (gives nothing away)
    icoon: str
    bewijs: str        # short title, shown once found
    dossier: str       # one line, shown big on the tv once found
    antwoorden: tuple[str, ...]
    hints: tuple[str, ...]
    cijfer: dict[str, int] | None = None       # per team one digit of its lock, written on the post-it (the locks differ)
    volgorde: tuple[int, ...] | None = None    # the order in which to read the digits (puzzle numbers)

    def cijfer_van(self, team: str) -> int | None:
        return self.cijfer[team] if self.cijfer else None

    @functools.cached_property
    def geaccepteerd(self) -> frozenset[str]:
        return frozenset(normaliseer(a) for a in self.antwoorden)


@dataclass(frozen=True)
class Escape:
    titel: str
    speeltijd_minuten: int
    hintstraf_minuten: int
    puzzels: tuple[Puzzel, ...]

    @property
    def per_nr(self) -> dict[int, Puzzel]:
        return {p.nr: p for p in self.puzzels}


def laad_escape(pad: Path | None = None) -> Escape:
    """Read and check the escape room. Anything wrong fails loudly with the puzzle number, so a typo never reaches the afternoon."""
    doc = json.loads((pad or data_dir() / "escape.json").read_text(encoding="utf-8"))
    for veld in ("speeltijd_minuten", "hintstraf_minuten"):
        if not isinstance(doc.get(veld), int) or isinstance(doc.get(veld), bool) or doc[veld] < 0 or (veld == "speeltijd_minuten" and doc[veld] == 0):
            raise DataFout(f"escape: {veld} {doc.get(veld)!r} moet een positief geheel getal zijn")
    puzzels, gezien = [], {}
    for i, r in enumerate(doc.get("puzzels") or [], 1):
        fout = lambda msg: DataFout(f"escape puzzel {r.get('nr', i)}: {msg}")   # noqa: E731
        if r.get("nr") != i:
            raise fout(f"nummer {r.get('nr')!r}, verwacht {i} (genummerd 1, 2, 3, ... op volgorde)")
        for veld in ("naam", "icoon", "bewijs", "dossier"):
            if not isinstance(r.get(veld), str) or not r[veld].strip():
                raise fout(f"{veld} ontbreekt of is leeg")
        antwoorden = r.get("antwoorden")
        if not isinstance(antwoorden, list) or not antwoorden or not all(isinstance(a, str) and normaliseer(a) for a in antwoorden):
            raise fout("antwoorden moet een lijst van teksten zijn, elk met minstens één letter of cijfer")
        for a in antwoorden:
            ander = gezien.setdefault(normaliseer(a), i)
            if ander != i:
                raise fout(f"antwoord {a!r} hoort ook bij puzzel {ander}")
        hints = r.get("hints")
        if not isinstance(hints, list) or len(hints) != HINTS_PER_PUZZEL or not all(isinstance(h, str) and h.strip() for h in hints):
            raise fout(f"precies {HINTS_PER_PUZZEL} hints nodig, elk een tekst")
        cijfer = r.get("cijfer")
        if cijfer is not None:   # one digit for both teams, or {"A": 5, "B": 3} when the locks differ
            per_team = cijfer if isinstance(cijfer, dict) else dict.fromkeys(TEAMS, cijfer)
            if sorted(per_team) != sorted(TEAMS):
                raise fout(f"cijfer {cijfer!r} moet één cijfer zijn of één per team: {list(TEAMS)}")
            for c in per_team.values():
                if not isinstance(c, int) or isinstance(c, bool) or not 0 <= c <= 9:
                    raise fout(f"cijfer {cijfer!r} moet een cijfer van 0 tot 9 zijn")
            cijfer = per_team
        volgorde = r.get("volgorde")
        if volgorde is not None and (not isinstance(volgorde, list) or not all(isinstance(x, int) and not isinstance(x, bool) for x in volgorde)):
            raise fout(f"volgorde {volgorde!r} moet een lijst puzzelnummers zijn")
        if cijfer is not None and volgorde is not None:
            raise fout("een puzzel geeft een cijfer of de volgorde, niet allebei")
        puzzels.append(Puzzel(i, r["naam"], r["icoon"], r["bewijs"], r["dossier"], tuple(antwoorden), tuple(hints), cijfer,
                              tuple(volgorde) if volgorde is not None else None))
    if not puzzels:
        raise DataFout("escape: geen puzzels")
    met_cijfer = sorted(p.nr for p in puzzels if p.cijfer is not None)
    met_volgorde = [p for p in puzzels if p.volgorde is not None]
    if len(met_volgorde) > 1:
        raise DataFout(f"escape: alleen één puzzel geeft de volgorde, nu {[p.nr for p in met_volgorde]}")
    if met_volgorde:
        v = met_volgorde[0].volgorde
        if len(v) != SLOT_CIJFERS or len(set(v)) != len(v) or not set(v) <= set(met_cijfer):
            raise DataFout(f"escape puzzel {met_volgorde[0].nr}: volgorde {list(v)} moet precies {SLOT_CIJFERS} verschillende puzzelnummers "
                           f"noemen, elk van een puzzel met een cijfer: {met_cijfer}")
    return Escape(doc.get("titel") or "Escaperoom", doc["speeltijd_minuten"], doc["hintstraf_minuten"], tuple(puzzels))


# ---------------------------------------------------------------- de regels, zonder database

def normaliseer(tekst: str) -> str:
    """Lowercase letters and digits only: spaces, punctuation and accents go. 'Made by Kids!' and 'madebykids' are the same; '7.500' is '7500'."""
    t = unicodedata.normalize("NFKD", tekst).lower()
    return "".join(c for c in t if c.isascii() and c.isalnum())


def klopt(antwoord: str, puzzel: Puzzel) -> bool:
    n = normaliseer(antwoord)
    return bool(n) and n in puzzel.geaccepteerd


@dataclass(frozen=True)
class Klok:
    """The shared game clock. Times are epoch seconds; `pauze_totaal` is the paused time already over."""
    duur: int
    gestart: float
    gepauzeerd_op: float | None = None
    pauze_totaal: float = 0.0


def speeltijd(klok: Klok | None, nu: float) -> float:
    """Seconds the game has been running at `nu`, pauses left out. A paused clock stands still at the moment of the pause."""
    if klok is None:
        return 0.0
    eind = klok.gepauzeerd_op if klok.gepauzeerd_op is not None else nu
    return max(0.0, eind - klok.gestart - klok.pauze_totaal)


@dataclass(frozen=True)
class TeamStand:
    gestart: bool
    pauze: bool
    gespeeld: float      # running time of the game for this team (frozen at the finish)
    rest_ruw: float      # time left; negative once the time is up
    straf: int           # seconds of hint penalty
    extra: int           # seconds the leader added (negative: took away)
    klaar: bool          # all evidence found
    eindtijd: float | None   # used time at the finish, penalty included

    @property
    def rest(self) -> float:
        return max(0.0, self.rest_ruw)

    @property
    def op(self) -> bool:
        return self.gestart and not self.klaar and self.rest_ruw <= 0

    @property
    def loopt(self) -> bool:
        """The clock ticks on screen, and the team may answer and take hints."""
        return self.gestart and not self.pauze and not self.klaar and self.rest_ruw > 0


def team_stand(klok: Klok | None, nu: float, *, duur: int, straf: int, extra: int, klaar_speeltijd: float | None) -> TeamStand:
    """Time left = play time + extra minutes - hint penalty - time played. `duur` is used before the start, when there is no clock yet."""
    gespeeld = klaar_speeltijd if klaar_speeltijd is not None else speeltijd(klok, nu)
    totaal = klok.duur if klok else duur
    rest = totaal + extra - straf - gespeeld
    return TeamStand(gestart=klok is not None, pauze=bool(klok and klok.gepauzeerd_op is not None), gespeeld=gespeeld, rest_ruw=rest,
                     straf=straf, extra=extra, klaar=klaar_speeltijd is not None,
                     eindtijd=(gespeeld + straf - extra) if klaar_speeltijd is not None else None)


def nieuwe_extra(extra: int, rest_ruw: float, delta: int) -> int:
    """The leader gives (or takes) `delta` seconds. For a team whose time is already up that counts from now: the time that ran on after
    0:00 is forgiven first, so '+2 minuten' always means two more minutes of play."""
    if rest_ruw < 0:
        extra += int(-rest_ruw) + 1
    return extra + delta


def alles_gevonden(opgelost, puzzels) -> bool:
    return {p.nr for p in puzzels} <= set(opgelost)


def winnaar(standen: dict[str, TeamStand]) -> str | None:
    """Once every team is finished or out of time: the finished team with the shortest time (penalties included). None while it is open."""
    if not standen or not all(s.klaar or s.op for s in standen.values()):
        return None
    klaar = sorted((s.eindtijd, t) for t, s in standen.items() if s.klaar)
    if not klaar or (len(klaar) > 1 and klaar[0][0] == klaar[1][0]):
        return None
    return klaar[0][1]


def slotcode(esc: Escape, team: str) -> str | None:
    """The team's lock code: its digits of the puzzles the order-puzzle names, in that order (without an order-puzzle: every digit by
    puzzle number). None without digits."""
    per_nr = esc.per_nr
    volgorde = next((p.volgorde for p in esc.puzzels if p.volgorde), None) or tuple(p.nr for p in esc.puzzels if p.cijfer is not None)
    return "".join(str(per_nr[n].cijfer_van(team)) for n in volgorde) or None


def mmss(seconden: float) -> str:
    s = max(0, int(-(-seconden // 1)))   # round up, like the countdown on the page
    return f"{s // 60}:{s % 60:02d}"


# ---------------------------------------------------------------- het prikbord: waar de briefjes hangen

# Centre of each post-it on the room screen's board (in % of the board) and its tilt; the case card hangs at KAART. Six or more puzzles
# would need more places here.
KAART = (50.0, 40.0)
PLEKKEN = [(17, 22, -4.0), (83, 22, 3.0), (15, 74, 2.5), (85, 74, -3.0), (50, 84, 1.5)]
KLEUREN = ["#ffe066", "#ff9ecb", "#8fd3ff", "#a6f0a0", "#ffb870"]
HAND = '"Segoe Print","Bradley Hand","Chalkboard SE","Marker Felt","Comic Sans MS","Comic Neue",cursive'   # system fonts only, no CDN
MONO = 'ui-monospace,"SF Mono",Menlo,Consolas,"DejaVu Sans Mono",monospace'


def plek(nr: int) -> tuple[float, float, float]:
    return PLEKKEN[(nr - 1) % len(PLEKKEN)]


def kleur(nr: int) -> str:
    return KLEUREN[(nr - 1) % len(KLEUREN)]


# ---------------------------------------------------------------- stijl en script

ESCAPE_CSS = """
.esc{--team-a:#ff7a52;--team-b:#4fc3f7;--groen:#2fbf71;--groen-zacht:#173d2a}
.esc-teams{display:grid;gap:1rem}
.esc .team{position:relative;border-radius:24px;padding:.9rem 1rem 1rem;background:var(--kaart);border:3px solid var(--rand);box-shadow:var(--schaduw)}
.esc .team-a{border-top:12px solid var(--team-a)}.esc .team-b{border-top:12px solid var(--team-b)}
.esc .kop{display:flex;justify-content:space-between;align-items:baseline;gap:1rem;flex-wrap:wrap}
.esc .tnaam{font-weight:900;font-size:1.5rem;letter-spacing:.06em}.team-a .tnaam,.team-a.tnaam{color:var(--team-a,#ff7a52)}.team-b .tnaam,.team-b.tnaam{color:var(--team-b,#4fc3f7)}
.esc .status{font-weight:800;font-size:1.15rem}
.esc .klok{font-variant-numeric:tabular-nums;font-weight:900;line-height:1;font-size:3.6rem;text-align:center;margin:.4rem 0 .6rem;letter-spacing:-.02em;min-height:1em}
.esc .klok.bijna{color:var(--geel)}.esc .op .klok{color:var(--fout)}.esc .klaar .klok{color:var(--groen)}
.esc .vakken{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.5rem}
.esc .vak{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:.15rem;min-height:6.5rem;border-radius:16px;background:var(--bg);border:3px solid var(--rand);color:var(--zacht);text-align:center;padding:.4rem .2rem;font-weight:800;line-height:1.15;text-decoration:none}
.esc .vak .vi{font-size:2rem;filter:grayscale(1);opacity:.55}.esc .vak .vnr{font-size:1.1rem}.esc .vak .vt{font-size:.8rem;overflow-wrap:break-word;max-width:100%}
.esc .vak .vc{white-space:nowrap;font-size:.85rem;background:rgba(0,0,0,.35);border-radius:999px;padding:0 .5rem}
.esc .vak.goed{background:var(--groen-zacht);border-color:var(--groen);color:#eafff2}.esc .vak.goed .vi{filter:none;opacity:1}
.esc .straf{margin:.6rem 0 0;font-weight:700;color:var(--zacht);text-align:center}
.esc .flits-fout{animation:schud .5s;border-color:var(--fout)!important}.esc .flits-hint{border-color:var(--geel)!important}
@keyframes schud{20%,60%{translate:-10px 0}40%,80%{translate:10px 0}}
.esc.los::before{content:"geen verbinding, probeert opnieuw…";position:fixed;bottom:.6rem;right:.8rem;z-index:25;font-size:.9rem;background:#5a1d1d;color:#fff;padding:.3rem .8rem;border-radius:999px}
body:has(.esc-tv) main>h1{display:none}
.esc-tv .titelbalk{display:flex;justify-content:space-between;align-items:center;font-weight:900;letter-spacing:.12em;text-transform:uppercase;color:var(--zacht);font-size:1rem;margin-bottom:.8rem}
.esc-tv .esc-teams.twee{grid-template-columns:1fr 1fr}
.esc-tv .klok{font-size:clamp(4rem,23vh,15rem)}.esc-tv .tnaam{font-size:clamp(1.6rem,4vh,2.6rem)}.esc-tv .status{font-size:clamp(1.2rem,3vh,2rem)}
.esc-tv .vak{min-height:clamp(7rem,26vh,16rem)}.esc-tv .vak .vi{font-size:clamp(2.2rem,8vh,5rem)}.esc-tv .vak .vnr{font-size:clamp(1.1rem,2.8vh,1.8rem)}.esc-tv .vak .vt{font-size:min(clamp(.9rem,2.3vh,1.5rem),.95vw)}.esc-tv .vak .vc{font-size:clamp(.9rem,2.3vh,1.5rem)}
.esc-tv .straf{font-size:clamp(1.1rem,2.8vh,1.8rem)}
/* the room screen: detective board plus clock */
body:has(.esc-kamer){background:#0b0c13}body:has(.esc-kamer) main{max-width:none;padding:0}
.esc-kamer{color:#f4f1ea;--zacht:#a5a9bc;--fout:#ff6b6b;--geel:#ffd35c}
.kamer{display:grid;grid-template-columns:1fr minmax(16rem,29vw);gap:1.2vw;height:100vh;padding:1.2vw;box-sizing:border-box}
.prikbord{position:relative;min-height:0;border-radius:10px;border:clamp(8px,1.1vw,16px) solid #5b3a1e;background-color:#b98a5e;
 background-image:radial-gradient(rgba(60,30,10,.35) 1px,transparent 1.6px),radial-gradient(rgba(255,235,200,.18) 1px,transparent 1.6px),radial-gradient(ellipse at 30% 20%,rgba(255,255,255,.14),transparent 60%);
 background-size:6px 6px,9px 9px,100% 100%;background-position:0 0,3px 4px,0 0;box-shadow:inset 0 0 50px rgba(0,0,0,.5),0 10px 30px rgba(0,0,0,.5);overflow:hidden}
.prikbord .touw{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
.touw line{stroke:#c0262d;stroke-width:4;stroke-linecap:round;filter:drop-shadow(0 2px 1px rgba(0,0,0,.45))}
.touw line.land{animation:verschijn 1s .7s both}@keyframes verschijn{from{opacity:0}to{opacity:1}}
.dossierkaart{position:absolute;left:50%;top:40%;transform:translate(-50%,-50%) rotate(-1.5deg);width:36%;padding:1.1vw 1.3vw;background:#efe2c0;color:#2b2112;font-family:"Courier New",Courier,monospace;box-shadow:0 8px 18px rgba(0,0,0,.45);text-align:center}
.dossierkaart .dk-klein{font-size:clamp(.65rem,1.4vh,1rem);letter-spacing:.2em;text-transform:uppercase}
.dossierkaart .dk-naam{font-size:clamp(1.1rem,min(4.4vh,2.3vw),3rem);font-weight:900;letter-spacing:.02em;margin:.25em 0;white-space:nowrap}
.dossierkaart .dk-stempel{display:inline-block;border:3px solid #b3122a;color:#b3122a;font-weight:900;padding:.05em .5em;transform:rotate(-8deg);font-size:clamp(.9rem,2.4vh,1.6rem);letter-spacing:.15em}
.dossierkaart::before,.postit::before{content:"";position:absolute;top:-.5em;left:50%;width:1.1em;height:1.1em;margin-left:-.55em;border-radius:50%;background:radial-gradient(circle at 35% 35%,#ff8a8a,#a30d15 70%);box-shadow:0 2px 3px rgba(0,0,0,.5);font-size:clamp(14px,2.2vh,24px)}
.postit{--x:50%;--y:50%;--r:0deg;--kleur:#ffe066;position:absolute;left:var(--x);top:var(--y);width:19%;aspect-ratio:1;transform:translate(-50%,-50%) rotate(var(--r));background:var(--kleur);color:#2a2410;box-shadow:0 10px 16px rgba(0,0,0,.4);
 padding:.5em .6em;display:flex;flex-direction:column;align-items:center;justify-content:space-between;text-align:center;font-family:""" + HAND + """;font-size:clamp(10px,min(1.9vh,1.25vw),22px);line-height:1.1;overflow:hidden}
.postit .pk{font-size:.8em;letter-spacing:.12em;text-transform:uppercase;opacity:.7;font-weight:700}
.postit .pt{font-size:1.25em;font-weight:700}
.postit .pc{font-size:4.6em;font-weight:900;line-height:.9}
.postit .pv{display:flex;flex-wrap:wrap;align-items:center;justify-content:center;gap:.15em;font-size:1.5em;font-weight:900}
.postit .pv .slot{flex-basis:100%;font-size:.8em;line-height:1}
.postit .chip{display:inline-grid;place-items:center;width:1.35em;height:1.35em;border-radius:.25em;border:2px solid rgba(0,0,0,.35)}
.postit.leeg{background:transparent;border:3px dashed rgba(255,240,220,.35);box-shadow:none;color:rgba(255,240,220,.45);justify-content:center}.postit.leeg::before{display:none}.postit.leeg span{font-size:4em}
.postit.land{animation:land 1.2s cubic-bezier(.2,.9,.3,1.15) both}
@keyframes land{0%{transform:translate(-50%,-50%) rotate(calc(var(--r) - 25deg)) scale(3.2);opacity:0}50%{opacity:1}100%{transform:translate(-50%,-50%) rotate(var(--r)) scale(1);opacity:1}}
.zij{display:flex;flex-direction:column;gap:.5rem;min-width:0;min-height:0}
.zij .tnaam{font-size:clamp(1.6rem,4.5vh,3rem);font-weight:900;letter-spacing:.08em}
.esc-kamer .zij .klok{font-size:min(8.6vw,22vh);text-align:left;margin:0;letter-spacing:-.03em}
.zij .status{font-size:clamp(1.1rem,3.2vh,2.1rem);font-weight:800}
.esc-kamer .zij .straf{font-size:clamp(1rem,2.6vh,1.6rem);text-align:left;margin:0}
.zij .vulling{flex:1}
.hoek{background:#1f2230;border:2px solid #32364a;border-radius:16px;padding:.7rem 1rem;display:flex;flex-direction:column;gap:.25rem}
.hoek .tnaam{font-size:clamp(1rem,2.6vh,1.5rem);letter-spacing:.06em}.esc-kamer .hoek .klok{font-size:clamp(1.8rem,6vh,3.4rem);text-align:left;margin:0}
.hoek .klein{color:#a5a9bc;font-size:clamp(.85rem,2vh,1.1rem)}
.briefjes{display:flex;gap:.35em;font-size:clamp(14px,2.4vh,26px)}.briefjes i{width:1.1em;height:1.1em;background:#ffe066;transform:rotate(-5deg);box-shadow:0 2px 3px rgba(0,0,0,.4)}.briefjes i.uit{background:#32364a;box-shadow:none;transform:none}
/* messages on the screens */
.melding{position:fixed;inset:0;z-index:30;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:1rem;text-align:center;padding:2rem;background:rgba(6,36,20,.96);color:#fff;font-family:system-ui,sans-serif}
.melding[hidden]{display:none}
.melding .m-icoon{font-size:clamp(5rem,20vh,12rem);line-height:1}.melding .m-kop{font-size:clamp(1.6rem,5vh,3.2rem);font-weight:900;letter-spacing:.06em;text-transform:uppercase;color:#7dffb0}
.melding .m-tekst{font-size:clamp(1.8rem,6vh,4rem);font-weight:800;max-width:28ch;line-height:1.2}
/* on a room screen the messages cover the board, never the clock column */
.melding.band,.melding.hint{right:calc(max(16rem,29vw) + 1.2vw)}
.melding.band{top:auto;display:grid;grid-template-columns:auto 1fr;column-gap:1.4rem;row-gap:.2rem;align-items:center;justify-items:start;padding:1rem 2rem;text-align:left}
.melding.band[hidden]{display:none}
.melding.band .m-icoon{grid-row:span 2;font-size:clamp(3rem,10vh,6rem)}.melding.band .m-kop{font-size:clamp(1rem,2.6vh,1.6rem)}.melding.band .m-tekst{font-size:clamp(1.3rem,4vh,2.6rem);max-width:none}
.melding.hint{background:rgba(10,8,0,.72)}.melding.hint .m-kop{color:#ffe066}
.melding.hint .m-tekst{background:#ffe066;color:#2a2410;font-family:""" + HAND + """;padding:1em 1.2em;transform:rotate(-1.5deg);box-shadow:0 14px 34px rgba(0,0,0,.55);max-width:24ch;font-size:clamp(1.8rem,6vh,4rem)}
.toast{position:fixed;top:1rem;left:50%;transform:translateX(-50%);z-index:28;background:#0e2a44;color:#fff;border:3px solid #4fc3f7;padding:.6rem 1.4rem;border-radius:999px;font-weight:800;font-size:clamp(1.1rem,3vh,1.8rem);font-family:system-ui,sans-serif}.toast[hidden]{display:none}
#esc-geluid{position:fixed;inset:0;z-index:40;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:1rem;background:rgba(8,9,15,.92);color:#fff;font:800 clamp(1.4rem,4vh,2.4rem) system-ui,sans-serif;cursor:pointer;border:0;width:100%;margin:0;border-radius:0;text-align:center}
#esc-geluid span{font-size:clamp(4rem,14vh,8rem)}#esc-geluid[hidden]{display:none}
/* the team phone: a secure police line */
body:has(.esc-lijn){--bg:#06110c;--kaart:#0c1d15;--ink:#d9ffe9;--zacht:#7aa892;--rand:#1d3a2c;--accent:#38e07b;--accent-ink:#03140a;--accent-zacht:#123222;--geel:#ffd35c;--fout:#ff6b6b;--schaduw:none;background:#06110c;color:#d9ffe9}
body:has(.esc-lijn) main{font-family:""" + MONO + """}body:has(.esc-lijn) main>h1{display:none}
.lijnkop{display:flex;justify-content:space-between;align-items:center;font-size:.85rem;letter-spacing:.14em;color:var(--accent);text-transform:uppercase;border-bottom:1px solid var(--rand);padding:.6rem 0 .5rem;margin-bottom:.8rem}
.led{display:inline-block;width:.65rem;height:.65rem;border-radius:50%;background:var(--accent);box-shadow:0 0 8px var(--accent);margin-right:.5rem;animation:knipper 1.6s infinite}@keyframes knipper{50%{opacity:.3}}
.esc-kamer .wachten{min-height:100vh;justify-content:center}.esc-kamer .wachttekst{color:#38e07b;font-size:clamp(1.4rem,4vh,2.4rem)}.esc-kamer .wachten .draai{border-color:#1d3a2c;border-top-color:#38e07b}
.wachten{display:flex;flex-direction:column;align-items:center;gap:1.2rem;padding:4rem 0}.wachten .draai{border-color:var(--rand);border-top-color:var(--accent)}.wachttekst{font-size:1.3rem;letter-spacing:.06em;color:var(--accent)}
.lijntitel{font-size:1.5rem;font-weight:800;margin:.2rem 0 .8rem}
.esc-tel .team{border-top-width:6px}
.esc-tel .vakken{grid-template-columns:1fr;gap:.6rem}
.esc-tel .vak{flex-direction:row;justify-content:flex-start;gap:.9rem;min-height:4.2rem;padding:.6rem 1rem;text-align:left;font-size:1.1rem;color:var(--ink);background:var(--kaart)}
.esc-tel .vak .vi{font-size:2rem;filter:none;opacity:1}.esc-tel .vak .vnr{font-size:1.4rem;min-width:1.4rem}.esc-tel .vak .vt{font-size:1rem}.esc-tel .vak .vc{margin-left:auto}
.esc-tel .vak.goed{color:#eafff2}
.groot-knoppen{display:grid;grid-template-columns:1fr 1fr;gap:.8rem}.groot-knoppen button{min-height:9rem;justify-content:center;flex-direction:column;font-size:1.3rem;text-align:center}
.groot-knoppen .team-a{border-color:#ff7a52;border-width:4px}.groot-knoppen .team-b{border-color:#4fc3f7;border-width:4px}
.uitslag{padding:1rem 1.2rem;border-radius:16px;font-weight:800;font-size:1.3rem;margin:.6rem 0;text-align:center;letter-spacing:.04em}
.uitslag.goed{background:#173d2a;color:#eafff2;border:2px solid #2fbf71}.uitslag.fout{background:#4a1515;color:#fff;border:2px solid #ff6b6b;animation:schud .5s}.uitslag.info{background:var(--accent-zacht);border:2px solid var(--rand)}
.uitslag .groot{font-size:3rem;line-height:1.1}
.mini-postit{display:inline-flex;flex-direction:column;align-items:center;margin:.6rem auto 0;padding:.5rem 1rem;color:#2a2410;transform:rotate(-3deg);font-family:""" + HAND + """;box-shadow:0 6px 12px rgba(0,0,0,.4)}.mini-postit b{font-size:2.6rem;line-height:1}
.hintlijst{list-style:none;padding:0}.hintlijst li{background:#ffe066;color:#2a2410;border-radius:4px;padding:.7rem 1rem;margin:.6rem 0;font-weight:700;font-family:""" + HAND + """;transform:rotate(-.6deg)}
input.antwoord{font:inherit;font-size:1.3rem;padding:1rem;text-align:center;letter-spacing:.06em}
#esc-zend{position:fixed;inset:0;z-index:30;background:#020806;color:#38e07b;display:flex;flex-direction:column;justify-content:center;padding:2rem;gap:.9rem;font-family:""" + MONO + """;font-size:1.15rem}
#esc-zend[hidden]{display:none}#esc-zend .r{opacity:.12;transition:opacity .2s}#esc-zend .r.aan{opacity:1}
#esc-zend .code{font-size:.95rem;color:#7aa892;word-break:break-all;min-height:2.6em}
#esc-zend .zbalk{height:.5rem;background:#123222;border-radius:999px;overflow:hidden}#esc-zend .zbalk i{display:block;height:100%;width:0;background:#38e07b}
/* the two buttons on the start page of a team account */
.teamknoppen{display:grid;grid-template-columns:minmax(0,1fr);gap:.8rem;margin:.4rem 0 1rem}
@media (min-width:34rem){.teamknoppen{grid-template-columns:repeat(2,minmax(0,1fr))}}
.knop.teamknop{min-height:5.5rem;overflow-wrap:break-word;margin:0;justify-content:center;text-align:center;font-size:1.35rem;font-weight:800;border-width:3px;border-color:var(--accent);background:var(--accent-zacht)}
/* the alarm on a room board: red flashing for five seconds */
.alarm{position:fixed;inset:0;z-index:45;display:grid;place-items:center;color:#fff;font:900 clamp(5rem,26vh,16rem) system-ui,sans-serif;letter-spacing:.12em;animation:alarm .5s steps(1) infinite}
.alarm[hidden]{display:none}
@keyframes alarm{0%{background:rgba(220,0,0,.92)}50%{background:rgba(70,0,0,.85)}}
@media (prefers-reduced-motion:reduce){.alarm{animation:none!important;background:rgba(220,0,0,.9)}}
button.alarmknop{border-color:#c62828;color:#c62828}
/* leader page */
.esc-start input[type=number]{width:7rem;padding:.7rem .9rem;font:inherit;color:var(--ink);background:var(--kaart);border:2px solid var(--rand);border-radius:14px;margin-left:.6rem}
.knoprij{display:flex;flex-wrap:wrap;gap:.4rem;align-items:center}.knoprij form{margin:0}
.knoprij button,button.klein{width:auto;min-height:2.6rem;margin:.2rem 0;padding:.4rem .9rem;font-size:.95rem}
.leden{list-style:none;padding:0;margin:.4rem 0}.leden li{display:flex;justify-content:space-between;align-items:center;gap:.5rem;padding:.2rem 0;border-bottom:1px solid var(--rand);flex-wrap:wrap}
.beheer-esc .vak{min-height:4.6rem;padding:.35rem .1rem}.beheer-esc .vak .vt{font-size:.58rem;letter-spacing:-.01em}.beheer-esc .vak .vc{font-size:.68rem;padding:0 .3rem}.beheer-esc .vak form{margin-top:.2rem}.beheer-esc .vak button{white-space:nowrap;padding:.3rem .6rem;min-height:2.2rem}
"""

ESCAPESCRIPT = """
(function () {
  // Asks the server for a fresh copy of the live block every 2 seconds and swaps it in only when something changed (so a post-it that
  // just landed is not redrawn), counts the clocks down in between, and (on a screen whose sound was switched on) plays a sound and shows
  // what happened. The server decides everything; this only shows it.
  var live = document.getElementById('esc-live');
  if (!live) return;
  var focus = live.getAttribute('data-team') || '';
  var ctx = null, gezien = null, klokken = {}, vorige = {}, wachtrij = [], bezig = false, vorm = null, geland = null;
  var elk = function (wortel, sel, f) { Array.prototype.forEach.call(wortel.querySelectorAll(sel), f); };

  function toon(freq, start, duur, vorm, vol) {
    var o = ctx.createOscillator(), g = ctx.createGain(), t = ctx.currentTime + start;
    o.type = vorm; o.frequency.value = freq;
    g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, t + duur);
    o.connect(g); g.connect(ctx.destination); o.start(t); o.stop(t + duur + 0.05);
  }
  var GELUID = {
    goed: function () { [523, 659, 784, 1047].forEach(function (f, i) { toon(f, i * 0.12, 0.4, 'triangle', 0.35); }); },
    klaar: function () { [523, 659, 784, 1047, 784, 1047].forEach(function (f, i) { toon(f, i * 0.16, i === 5 ? 1.2 : 0.3, 'triangle', 0.4); }); },
    fout: function () { toon(98, 0, 0.8, 'sawtooth', 0.35); toon(104, 0, 0.8, 'square', 0.18); },
    hint: function () { toon(880, 0, 0.3, 'sine', 0.3); toon(660, 0.25, 0.5, 'sine', 0.3); },
    op: function () { toon(220, 0, 1.2, 'sawtooth', 0.3); toon(147, 0.7, 1.8, 'sawtooth', 0.3); },
    ander: function () { toon(1318, 0, 0.18, 'sine', 0.25); toon(1760, 0.12, 0.25, 'sine', 0.2); },
    alarm: function () {   // a police siren: two tones, high-low, for about five seconds
      for (var i = 0; i < 12; i++) { var f = i % 2 ? 660 : 880; toon(f, i * 0.42, 0.4, 'square', 0.3); toon(f / 2, i * 0.42, 0.4, 'sawtooth', 0.2); }
    }
  };
  function speel(naam) { if (ctx && GELUID[naam]) { try { GELUID[naam](); } catch (e) {} } }
  function mmss(s) { s = Math.max(0, Math.ceil(s)); var m = Math.floor(s / 60), r = s % 60; return m + ':' + (r < 10 ? '0' : '') + r; }

  function tik() {
    var nu = Date.now();
    elk(live, '[data-klok]', function (el) {
      var t = el.getAttribute('data-klok'), k = klokken[t];
      if (!k) return;
      var s = k.loopt ? (k.eind - nu) / 1000 : k.rest;
      el.textContent = mmss(s);
      el.classList.toggle('bijna', !!k.loopt && s > 0 && s <= 300);
      if (el.hasAttribute('data-hoofd')) {   // a team's main clock: sound once when it reaches zero while we watch
        if (k.loopt && s <= 0 && vorige[t] > 0 && (!focus || t === focus)) speel('op');
        vorige[t] = s;
      }
    });
  }
  function landen() {   // whatever is new on the board since the last picture flies in
    var nu = {};
    elk(live, '[data-land]', function (el) {
      var k = el.getAttribute('data-land'); nu[k] = true;
      if (geland && !geland[k]) el.classList.add('land');
    });
    geland = nu;
  }
  function flits(team, soort) {
    var el = document.getElementById('team-' + team);
    if (!el) return;
    el.classList.add('flits-' + soort);
    setTimeout(function () { var x = document.getElementById('team-' + team); if (x) x.classList.remove('flits-' + soort); }, 1500);
  }
  function toast(e) {
    var t = document.getElementById('esc-toast');
    if (!t) return;
    t.textContent = e.kop; t.hidden = false;
    clearTimeout(t._weg); t._weg = setTimeout(function () { t.hidden = true; }, 5000);
  }
  function volgende() {   // one message at a time, each for a while
    var m = document.getElementById('esc-melding');
    if (bezig || !wachtrij.length || !m) return;
    bezig = true;
    var e = wachtrij.shift();
    speel(e.soort);
    m.className = 'melding ' + e.soort + (focus && e.soort === 'goed' ? ' band' : '');
    m.querySelector('.m-icoon').textContent = e.icoon;
    m.querySelector('.m-kop').textContent = e.kop;
    m.querySelector('.m-tekst').textContent = e.tekst;
    m.hidden = false;
    setTimeout(function () { m.hidden = true; bezig = false; volgende(); }, e.soort === 'hint' ? 15000 : e.soort === 'klaar' ? 8000 : 6000);
  }
  var alarmTot = 0;
  function alarm() {   // red flashing over the whole screen for five seconds, then back to normal
    var a = document.getElementById('esc-alarm');
    if (!a || Date.now() < alarmTot) return;
    alarmTot = Date.now() + 5000;
    speel('alarm'); a.hidden = false;
    setTimeout(function () { a.hidden = true; }, 5000);
  }
  if (focus) {   // on a room board a leader sets it off by pressing Q twice quickly, unless typing in a field
    var vorigeQ = 0;
    document.addEventListener('keydown', function (e) {
      var t = e.target, veld = t && (/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.isContentEditable);
      if (veld || e.repeat || e.ctrlKey || e.metaKey || e.altKey || (e.key !== 'q' && e.key !== 'Q')) return;
      var nu = Date.now();
      if (nu - vorigeQ < 600) { vorigeQ = 0; alarm(); } else { vorigeQ = nu; }
    });
  }
  function nieuws(e) {
    if (e.soort === 'alarm') { if (focus && e.team === focus) alarm(); else if (!focus) toast(e); return; }
    var eigen = !focus || e.team === focus;
    if (eigen && (e.soort === 'goed' || e.soort === 'klaar' || (e.soort === 'hint' && focus))) { wachtrij.push(e); volgende(); }
    else if (eigen && e.soort === 'hint') { speel('hint'); toast(e); flits(e.team, 'hint'); }
    else if (eigen && e.soort === 'fout') { speel('fout'); flits(e.team, 'fout'); }
    else if (!eigen && (e.soort === 'goed' || e.soort === 'klaar')) { speel('ander'); toast(e); }
  }
  function lees(wortel) {   // the clocks and the events travel as attributes of the block, so its inside only changes when something happened
    var t0 = Date.now(), k = JSON.parse(wortel.getAttribute('data-klokken') || '{}');
    klokken = {};
    Object.keys(k).forEach(function (t) { klokken[t] = { eind: t0 + k[t].rest * 1000, rest: k[t].rest, loopt: k[t].loopt }; });
    var ev = JSON.parse(wortel.getAttribute('data-events') || '[]');
    var hoogste = ev.reduce(function (m, e) { return Math.max(m, e.id); }, 0);
    if (gezien === null || hoogste < gezien) { gezien = hoogste; return; }   // first look (or a fresh database): history is not news
    ev.forEach(function (e) { if (e.id > gezien) nieuws(e); });
    gezien = hoogste;
  }
  function opnieuw() { setTimeout(poll, 2000); }
  function poll() {
    fetch(live.getAttribute('data-poll'), { headers: { 'HX-Request': 'true' }, cache: 'no-store', credentials: 'same-origin', redirect: 'error' })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
      .then(function (html) {
        var tpl = document.createElement('template');
        tpl.innerHTML = html;
        var wortel = tpl.content.querySelector('#esc-frag');
        if (!wortel) throw new Error('geen fragment');   // a login page or an error: keep the last picture
        var eerder = live.querySelector('#esc-frag');
        if (eerder && eerder.hasAttribute('data-wacht') !== wortel.hasAttribute('data-wacht')) { location.reload(); return; }   // put in or out of a team
        if (wortel.innerHTML !== vorm) { vorm = wortel.innerHTML; live.innerHTML = ''; live.appendChild(wortel); landen(); }
        live.classList.remove('los'); lees(wortel); tik();
      })
      .then(opnieuw, function () { live.classList.add('los'); opnieuw(); });
  }

  var knop = document.getElementById('esc-geluid');
  if (knop) knop.addEventListener('click', function () {
    try { ctx = new (window.AudioContext || window.webkitAudioContext)(); ctx.resume(); speel('hint'); } catch (e) { ctx = null; }
    knop.hidden = true;
  });
  var eerste = live.querySelector('#esc-frag');
  if (eerste) { vorm = eerste.innerHTML; lees(eerste); }
  landen(); tik(); setInterval(tik, 250); opnieuw();
})();
"""

# Sending an answer feels like a secure transmission: about 1.5 seconds of "connecting, encrypting, sent", then the form really goes.
ZENDSCRIPT = """
(function () {
  var f = document.querySelector('form[data-versleutel]'), o = document.getElementById('esc-zend');
  if (!f || !o) return;
  var bezig = false;
  window.addEventListener('pageshow', function () { o.hidden = true; bezig = false; });
  f.addEventListener('submit', function (e) {
    var veld = f.querySelector('input[name=antwoord]');
    if (bezig || !veld.value.trim()) { e.preventDefault(); return; }
    e.preventDefault(); bezig = true; o.hidden = false;
    var regels = o.querySelectorAll('.r'), code = o.querySelector('.code'), balk = o.querySelector('.zbalk i'), t0 = Date.now(), H = '0123456789ABCDEF';
    var iv = setInterval(function () {
      var p = Math.min(1, (Date.now() - t0) / 1500), s = '';
      for (var i = 0; i < 32; i++) s += H.charAt(Math.floor(Math.random() * 16));
      code.textContent = p < 1 ? s : '';
      balk.style.width = Math.round(p * 100) + '%';
      for (var j = 0; j < regels.length; j++) regels[j].classList.toggle('aan', p >= j / regels.length);
      if (p >= 1) { clearInterval(iv); f.submit(); }
    }, 60);
  });
})();
"""

TRILSCRIPT = "if (navigator.vibrate) { try { navigator.vibrate([250, 120, 250]); } catch (e) {} }"

# ---------------------------------------------------------------- routes en schermen

def registreer(app, db, esc: Escape, *, tijd=time.time) -> None:
    """Hang the escape room's routes on `app`. Who may open /beheer/... and what a POST may do is decided once, in the app's login check."""
    route = functools.partial(app.route, methods=["get"])   # a route that changes something says methods=["post"]
    per_nr = esc.per_nr
    straf_per_hint = esc.hintstraf_minuten * 60
    codes = {t: slotcode(esc, t) for t in TEAMS}

    def klok_nu() -> Klok | None:
        k = spel.escape_klok(db)
        return Klok(k["duur"], k["gestart"], k["gepauzeerd_op"], k["pauze_totaal"]) if k else None

    def stand(nu: float | None = None) -> dict:
        """Everything a screen needs, read once."""
        nu = tijd() if nu is None else nu
        klok, teams, opgelost, hints = klok_nu(), spel.escape_teams(db), spel.escape_opgelost(db), spel.escape_hints(db)
        standen = {t: team_stand(klok, nu, duur=esc.speeltijd_minuten * 60, straf=straf_per_hint * sum(hints.get(t, {}).values()),
                                 extra=(teams.get(t) or {}).get("extra", 0), klaar_speeltijd=(teams.get(t) or {}).get("klaar_speeltijd"))
                   for t in TEAMS}
        return {"klok": klok, "nu": nu, "teams": standen, "opgelost": {t: opgelost.get(t, {}) for t in TEAMS},
                "hints": {t: hints.get(t, {}) for t in TEAMS}, "winnaar": winnaar(standen)}

    def ander_team(t: str) -> str:
        return next(x for x in TEAMS if x != t)

    def status_tekst(st: dict, t: str) -> str:
        s = st["teams"][t]
        if not s.gestart:
            return "Wacht op de start"
        if s.klaar:
            return ("🏆 " if st["winnaar"] == t else "🎉 ") + f"Klaar in {mmss(s.eindtijd)}"
        if s.op:
            return "⏰ Tijd is op"
        if s.pauze:
            return "⏸ Pauze"
        return f"{len(st['opgelost'][t])} van {len(esc.puzzels)} bewijzen"

    def strafregel(st: dict, t: str) -> str:
        s, n = st["teams"][t], sum(st["hints"][t].values())
        delen = [f"💡 {n} {'hint' if n == 1 else 'hints'}: −{s.straf // 60} min" if n else "💡 geen hints"]
        if s.extra:
            delen.append(f"{'+' if s.extra > 0 else '−'}{abs(s.extra) // 60} min van de leiding")
        return " · ".join(delen)

    def toestand(s: TeamStand) -> str:
        return (" klaar" if s.klaar else "") + (" op" if s.op else "")

    def klok_el(team: str, hoofd: bool = False):
        """Empty on purpose: the page fills it every quarter second from the block's `data-klokken`."""
        return Div(cls="klok", **{"data-klok": team, **({"data-hoofd": "1"} if hoofd else {})})

    def klokken_json(st: dict) -> str:
        return json.dumps({t: {"rest": round(s.rest, 1), "loopt": 1 if s.loopt else 0} for t, s in st["teams"].items()})

    def blok(*inhoud, st: dict, events: str | None = None, cls: str = ""):
        """The block a screen polls. Clocks and events ride along as attributes, so its inside only changes when something happened.
        `events` is None for no events, "" for every team's (the leader's view), or the team whose room the screen stands in."""
        attrs = {"data-klokken": klokken_json(st), **({"data-events": gebeurtenissen(events)} if events is not None else {})}
        return Div(*inhoud, id="esc-frag", **({"cls": cls} if cls else {}), **attrs)

    def live(url: str, inhoud, *, team: str = "", cls: str = "esc"):
        return Div(inhoud, id="esc-live", cls=cls, **{"data-poll": url, "data-team": team})

    def slot_tekst(p: Puzzel, team: str) -> str | None:
        if p.cijfer is not None:
            return f"🔒 {p.cijfer_van(team)}"
        if p.volgorde:
            return "🔒 " + "→".join(map(str, p.volgorde))
        return None

    def vak(p: Puzzel, team: str, goed: bool, href: str | None = None, extra=()):
        inhoud = [Span(p.icoon, cls="vi"), Span(str(p.nr), cls="vnr"), Span(f"✔ {p.bewijs}" if goed else p.naam, cls="vt")]
        if goed and slot_tekst(p, team):
            inhoud.append(Span(slot_tekst(p, team), cls="vc"))
        inhoud += list(extra)
        cls = "vak goed" if goed else "vak"
        return A(*inhoud, href=href, cls=cls) if href else Div(*inhoud, cls=cls)

    def team_paneel(st: dict, t: str):
        s = st["teams"][t]
        return Section(Div(Span(f"TEAM {t}", cls="tnaam"), Span(status_tekst(st, t), cls="status"), cls="kop"),
                       klok_el(t, hoofd=True), Div(*[vak(p, t, p.nr in st["opgelost"][t]) for p in esc.puzzels], cls="vakken"),
                       P(strafregel(st, t), cls="straf"), cls=f"team team-{t.lower()}{toestand(s)}", id=f"team-{t}")

    def gebeurtenissen(kamer: str = "") -> str:
        """The latest events, ready to show: the page never needs to know the texts. A room screen (`kamer`) gets the other team's progress
        only as "found one" or "found all": never its hints, wrong answers, evidence titles or dossier lines, which would give answers away."""
        uit = []
        for e in spel.escape_gebeurtenissen(db):
            if kamer and e["team"] != kamer:
                if e["soort"] in ("goed", "klaar"):
                    kop = f"Team {e['team']} vond een bewijs!" if e["soort"] == "goed" else f"Team {e['team']} heeft alle bewijzen!"
                    uit.append({"id": e["id"], "team": e["team"], "soort": e["soort"], "kop": kop, "tekst": "", "icoon": ""})
                continue
            p = per_nr.get(e["puzzel"]) if e["puzzel"] else None
            kop, tekst, icoon = f"Team {e['team']}", "", ""
            if e["soort"] == "goed" and p:
                kop, tekst, icoon = f"Team {e['team']} · bewijs {p.nr}: {p.bewijs}", p.dossier, p.icoon
            elif e["soort"] == "klaar":
                kop, tekst, icoon = f"Team {e['team']}: alle bewijzen!", "De zaak tegen X-ploitation is rond.", "🏆"
            elif e["soort"] == "alarm":
                kop, icoon = f"🚨 Alarm bij team {e['team']}", "🚨"
            elif e["soort"] == "hint" and p and e["nummer"] and e["nummer"] <= len(p.hints):
                kop, tekst, icoon = f"Team {e['team']} · hint voor bewijs {p.nr}", p.hints[e["nummer"] - 1], "💡"
            uit.append({"id": e["id"], "team": e["team"], "soort": e["soort"], "kop": kop, "tekst": tekst, "icoon": icoon})
        return json.dumps(uit, ensure_ascii=False)

    # -------- het prikbord in de kamer van een team

    def volgorde_chips(volgorde) -> list:
        uit = [Span("🔒", cls="slot")]   # on a line of its own, so the three chips stay on one row
        for i, n in enumerate(volgorde):
            uit += [*([Span("→")] if i else []), Span(str(n), cls="chip", style=f"background:{kleur(n)}")]
        return uit

    def postit(p: Puzzel, team: str):
        x, y, r = plek(p.nr)
        inhoud = [Div(f"Bewijs {p.nr}", cls="pk"), Div(p.bewijs, cls="pt")]
        if p.cijfer is not None:
            inhoud.append(Div(str(p.cijfer_van(team)), cls="pc"))
        if p.volgorde:
            inhoud.append(Div(*volgorde_chips(p.volgorde), cls="pv"))
        return Div(*inhoud, cls="postit", style=f"--x:{x}%;--y:{y}%;--r:{r}deg;--kleur:{kleur(p.nr)}", **{"data-land": f"{team}{p.nr}"})

    def lege_plek(p: Puzzel):
        x, y, r = plek(p.nr)
        return Div(Span("?"), cls="postit leeg", style=f"--x:{x}%;--y:{y}%;--r:{r}deg")

    def prikbord(st: dict, team: str):
        gevonden = st["opgelost"][team]
        kx, ky = KAART
        touw = [Line(x1=kx, y1=ky, x2=plek(p.nr)[0], y2=plek(p.nr)[1] - 11, vector_effect="non-scaling-stroke", **{"data-land": f"touw{team}{p.nr}"})
                for p in esc.puzzels if p.nr in gevonden]
        kaart = Div(Div("Politie · dossier", cls="dk-klein"), Div(esc.titel.upper().replace("-", "\u2011"), cls="dk-naam"), Div("Verdacht", cls="dk-stempel"),
                    cls="dossierkaart")
        briefjes = [postit(p, team) if p.nr in gevonden else lege_plek(p) for p in esc.puzzels]
        return Div(Svg(*touw, viewBox="0 0 100 100", preserveAspectRatio="none", cls="touw"), kaart, *briefjes, cls="prikbord", id=f"team-{team}")

    def hoek(st: dict, t: str):
        n = len(st["opgelost"][t])
        return Div(Span(f"Team {t}", cls=f"tnaam team-{t.lower()}"), klok_el(t),
                   Div(*[I(cls="" if i < n else "uit") for i in range(len(esc.puzzels))], cls="briefjes"),
                   Span(status_tekst(st, t), cls="klein"), cls="hoek")

    def zijkant(st: dict, team: str):
        s = st["teams"][team]
        return Div(Div(f"TEAM {team}", cls=f"tnaam team-{team.lower()}"), klok_el(team, hoofd=True), Div(status_tekst(st, team), cls="status"),
                   P(strafregel(st, team), cls="straf"), Div(cls="vulling"), hoek(st, ander_team(team)), cls=f"zij{toestand(s)}")

    # -------- tv en kamerschermen

    def focus_van(team: str) -> str:
        return team if team in TEAMS else ""

    def tv_inhoud(team: str = ""):
        st, focus = stand(), focus_van(team)
        if focus:
            return blok(prikbord(st, focus), zijkant(st, focus), st=st, events=focus, cls="kamer")
        pauze = st["klok"] is not None and st["klok"].gepauzeerd_op is not None
        kop = Div(Span(f"Politieportaal · {esc.titel}"), Span("⏸ Pauze" if pauze else ""), cls="titelbalk")
        return blok(kop, Div(*[team_paneel(st, t) for t in TEAMS], cls="esc-teams twee"), st=st, events="")

    def scherm(url: str, focus: str):
        return pagina(f"Escaperoom{' team ' + focus if focus else ''}",
                      live(url, tv_inhoud(focus), team=focus, cls="esc esc-tv " + ("esc-kamer" if focus else "tv")),
                      Div(Div(cls="m-icoon"), Div(cls="m-kop"), Div(cls="m-tekst"), id="esc-melding", cls="melding", hidden=True),
                      Div(id="esc-toast", cls="toast", hidden=True),
                      Div("ALARM", id="esc-alarm", cls="alarm", hidden=True, role="alert"),
                      Button(Span("🔊"), "Klik om te beginnen (geluid aan)", id="esc-geluid", type="button"),
                      Script(ESCAPESCRIPT), toon_menu=False)

    @route("/beheer/escape/tv")
    def tv_pagina(team: str = ""):
        focus = focus_van(team)
        return scherm("/beheer/escape/tv/inhoud" + (f"?team={focus}" if focus else ""), focus)

    @route("/beheer/escape/tv/inhoud")
    def tv_fragment(team: str = ""):
        return tv_inhoud(team)

    # -------- het prikbord op de laptop in de kamer, ingelogd met het teamaccount

    @route("/escape/bord")
    def bord_pagina(req):
        """The room laptop, logged in with the team's own account (no leader login in a room with the kids). The team comes from the account,
        never from the address, so a team can only ever see its own board."""
        if is_leiding(req.headers):
            return naar("/beheer/escape/tv")
        meld(req)
        team = mijn_team(req)
        if team is None:
            return pagina("Escaperoom", live("/escape/bord/inhoud", wacht_inhoud(), cls="esc esc-tv esc-kamer"), Script(ESCAPESCRIPT), toon_menu=False)
        return scherm("/escape/bord/inhoud", team)

    @route("/escape/bord/inhoud")
    def bord_fragment(req):
        team = mijn_team(req)
        return wacht_inhoud() if team is None else tv_inhoud(team)

    # -------- de teamtelefoon

    def mijn_team(req) -> str | None:
        """The team of this account, if the leader put it in one. A leader is never in a team: a leader's phone cannot play by accident."""
        if is_leiding(req.headers):
            return None
        a = spel.escape_account(db, req.scope["gebruiker"])
        return a["team"] if a and a["team"] in TEAMS else None

    def lijnpagina(titel: str, *inhoud, team: str | None = None):
        """A page of the secure police line. No menu: a team phone should not invite anyone to wander off."""
        kop = Div(Span(Span(cls="led"), "Beveiligde lijn"), Span(f"Team {team}" if team else "Geen team"), cls="lijnkop")
        return pagina(titel, Div(kop, Div(titel, cls="lijntitel"), *inhoud, cls="esc-lijn"), toon_menu=False)

    def meld(req) -> None:
        """Put this account on the leader's waiting list. A GET with an effect, so only from our own pages, never started by another site."""
        if req.headers.get("sec-fetch-site", "same-origin") in ("same-origin", "none"):
            spel.escape_meld(db, req.scope["gebruiker"], tijd())

    def wacht_inhoud():
        """For an account not (or no longer) in a team. `data-wacht` tells the page to reload once that changes."""
        return Div(Div(Div(cls="draai"), P("Wacht op de recherche…", cls="wachttekst"), cls="wachten"), id="esc-frag", **{"data-wacht": "1"})

    def tel_inhoud(team: str):
        st = stand()
        s = st["teams"][team]
        return blok(Section(Div(Span(f"TEAM {team}", cls="tnaam"), Span(status_tekst(st, team), cls="status"), cls="kop"), klok_el(team),
                            Div(*[vak(p, team, p.nr in st["opgelost"][team], href=f"/escape/puzzel/{p.nr}") for p in esc.puzzels], cls="vakken"),
                            P(strafregel(st, team), cls="straf"), cls=f"team team-{team.lower()}{toestand(s)}", id=f"team-{team}"), st=st)

    @route("/escape")
    def tel_pagina(req, goed: str = ""):
        if is_leiding(req.headers):
            return pagina("Teamtelefoon", P("Hier voeren de teams bewijzen in, op een telefoon met een eigen teamaccount (geen begeleider). "
                                            "Begeleiders spelen niet mee en kunnen hier niets insturen."),
                          A("Escaperoom bedienen", href="/beheer/escape", cls="knop"),
                          *[A(f"Prikbord van team {t}", href=f"/beheer/escape/tv?team={t}", cls="knop") for t in TEAMS])
        meld(req)
        spel.escape_gezien(db, req.scope["gebruiker"], tijd())
        team = mijn_team(req)
        if team is None:
            return lijnpagina("Verbinding maken", live("/escape/inhoud", wacht_inhoud(), cls="esc esc-tel"), Script(ESCAPESCRIPT))
        melding = []
        p = puzzel_van(goed)
        if p:
            melding = [Div(Div("✅", cls="groot"), "Ontvangen", P(p.bewijs, style="font-size:1.1rem"), *mini_postit(p, team), cls="uitslag goed")]
        return lijnpagina("Bewijzen", *melding, live("/escape/inhoud", tel_inhoud(team), cls="esc esc-tel"), Script(ESCAPESCRIPT), team=team)

    def mini_postit(p: Puzzel, team: str) -> list:
        if p.cijfer is not None:
            return [Div(Span("cijfer"), B(str(p.cijfer_van(team))), cls="mini-postit", style=f"background:{kleur(p.nr)}")]
        if p.volgorde:
            return [Div(Span("lees het slot zo"), B(" → ".join(map(str, p.volgorde)), style="font-size:1.8rem"), cls="mini-postit",
                        style=f"background:{kleur(p.nr)}")]
        return []

    @route("/escape/inhoud")
    def tel_fragment(req):
        if not is_leiding(req.headers):
            spel.escape_gezien(db, req.scope["gebruiker"], tijd())   # so the leader sees which phone is on, waiting or in a team
        team = mijn_team(req)
        return wacht_inhoud() if team is None else tel_inhoud(team)

    def puzzel_van(nr: str) -> Puzzel | None:
        return per_nr.get(int(nr)) if nr.isascii() and nr.isdigit() and len(nr) < 4 else None

    @route("/escape/puzzel/{nr}")
    def tel_puzzel(req, nr: str, uitslag: str = ""):
        team, p = mijn_team(req), puzzel_van(nr)
        if team is None:
            return naar("/escape")
        if not p:
            return Response("Niet gevonden.", status_code=404)
        st = stand()
        s = st["teams"][team]
        genomen = st["hints"][team].get(p.nr, 0)
        terug = A("← Alle bewijzen", href="/escape", cls="knop sec")
        titel = f"{p.icoon} Bewijs {p.nr}: {p.naam}"
        hints = [Ul(*[Li(f"💡 {h}") for h in p.hints[:genomen]], cls="hintlijst")] if genomen else []
        if p.nr in st["opgelost"][team]:
            return lijnpagina(titel, Div(Div("✅", cls="groot"), p.bewijs, *mini_postit(p, team), cls="uitslag goed"), terug, team=team)
        if not s.loopt:
            return lijnpagina(titel, Div(status_tekst(st, team), cls="uitslag info"), *hints, terug, team=team)
        fout = [Div(Div("❌", cls="groot"), "Afgewezen", P("Probeer opnieuw.", style="font-size:1rem"), cls="uitslag fout"), Script(TRILSCRIPT)] \
            if uitslag == "fout" else []
        hintknop = ([A(f"💡 Hint {genomen + 1} van {HINTS_PER_PUZZEL} (kost {esc.hintstraf_minuten} min)", href=f"/escape/hint/{p.nr}", cls="knop sec")]
                    if genomen < HINTS_PER_PUZZEL else [])
        zend = Div(Div("▸ beveiligde verbinding", cls="r"), Div("▸ versleutelen", cls="r"), Div("▸ verzonden", cls="r"),
                   Div(cls="code"), Div(I(), cls="zbalk"), id="esc-zend", hidden=True, role="status")
        return lijnpagina(titel, *fout,
                          Form(Input(type="text", name="antwoord", maxlength=MAX_ANTWOORD, autocomplete="off", autocapitalize="off", spellcheck="false",
                                     autofocus=True, required=True, placeholder="bewijs", cls="antwoord", **{"aria-label": "Antwoord"}),
                               Input(type="hidden", name="nr", value=str(p.nr)), Button("Verstuur ▸", cls="hoofd", type="submit"),
                               method="post", action="/escape/antwoord", **{"data-versleutel": "1"}),
                          *hints, *hintknop, terug, zend, Script(ZENDSCRIPT), team=team)

    @route("/escape/antwoord", methods=["post"])
    def tel_antwoord(req, nr: str = "", antwoord: str = ""):
        team, p = mijn_team(req), puzzel_van(nr)
        if team is None or not p:
            return naar("/escape")
        nu = tijd()
        st = stand(nu)
        s = st["teams"][team]
        if p.nr in st["opgelost"][team]:
            return naar(f"/escape?goed={p.nr}")
        if not s.loopt or not antwoord.strip():
            return naar(f"/escape/puzzel/{p.nr}")
        if klopt(antwoord[:MAX_ANTWOORD], p):
            spel.escape_los_op(db, team, p.nr, s.gespeeld, {x.nr for x in esc.puzzels}, nu)
            return naar(f"/escape?goed={p.nr}")
        spel.escape_fout(db, team, p.nr, nu)
        return naar(f"/escape/puzzel/{p.nr}?uitslag=fout")

    @route("/escape/hint/{nr}")
    def tel_hint_vraag(req, nr: str):
        team, p = mijn_team(req), puzzel_van(nr)
        if team is None or not p:
            return naar("/escape")
        return lijnpagina(f"💡 Hint voor bewijs {p.nr}?",
                          Div(Div("⏱️", cls="groot"), f"Kost {esc.hintstraf_minuten} minuten.", cls="uitslag info"),
                          Form(Input(type="hidden", name="nr", value=str(p.nr)), Button(f"Ja, geef de hint (−{esc.hintstraf_minuten} min)", cls="hoofd", type="submit"),
                               method="post", action="/escape/hint"),
                          A("Nee, terug", href=f"/escape/puzzel/{p.nr}", cls="knop sec"), team=team)

    @route("/escape/hint", methods=["post"])
    def tel_hint(req, nr: str = ""):
        team, p = mijn_team(req), puzzel_van(nr)
        if team is None or not p:
            return naar("/escape")
        nu = tijd()
        st = stand(nu)
        if st["teams"][team].loopt and p.nr not in st["opgelost"][team]:
            spel.escape_neem_hint(db, team, p.nr, HINTS_PER_PUZZEL, st["teams"][team].gespeeld, nu)
        return naar(f"/escape/puzzel/{p.nr}")

    # -------- bediening door de leiding

    def knop(doel: str, tekst: str, cls: str = "klein", bevestig: str | None = None, **velden):
        """A one-button form; `velden` become hidden fields."""
        extra = {"onsubmit": f"return confirm({json.dumps(bevestig)})"} if bevestig else {}
        return Form(*[Input(type="hidden", name=k, value=str(v)) for k, v in velden.items()], Button(tekst, type="submit", cls=cls),
                    method="post", action=doel, **extra)

    def actief(x: dict, nu: float) -> str:
        return "🟢 actief" if x["laatst_gezien"] and nu - x["laatst_gezien"] < 30 else "⚪ niet actief"

    def account_rij(x: dict, nu: float):
        naam = x["gebruikersnaam"] + (f" ({x['nickname']})" if x["nickname"] else "")
        knoppen = [knop("/beheer/escape/account", f"→ team {t}", gebruikersnaam=x["gebruikersnaam"], team=t) for t in TEAMS if t != x["team"]]
        if x["team"]:
            knoppen.append(knop("/beheer/escape/account", "Uit team", bevestig=f"{x['gebruikersnaam']} uit team {x['team']} halen?",
                                gebruikersnaam=x["gebruikersnaam"], team=""))
        return Li(Span(f"📱 {naam}: {actief(x, nu)}"), Div(*knoppen, cls="knoprij"))

    def team_accounts(t: str, accounts: list[dict], nu: float):
        mijn = [x for x in accounts if x["team"] == t]
        return Ul(*[account_rij(x, nu) for x in mijn], cls="leden") if mijn else P("Nog geen account in dit team.", cls="klein")

    def beheer_inhoud():
        st = stand()
        klok, accounts = st["klok"], spel.escape_accounts(db)
        if klok is None:
            regel, spelknop = P("Nog niet gestart."), ""
        elif klok.gepauzeerd_op is not None:
            regel, spelknop = P("⏸ Gepauzeerd: beide klokken staan stil."), knop("/beheer/escape/pauze", "▶ Hervat beide klokken", "hoofd", actie="hervat")
        else:
            regel, spelknop = P(f"De klokken lopen ({klok.duur // 60} minuten)."), knop("/beheer/escape/pauze", "⏸ Pauzeer beide klokken", "", actie="pauze")
        slot = P("🔒 Slotcodes: " + " · ".join(f"team {t} {c}" for t, c in codes.items()), style="font-weight:800") if any(codes.values()) else ""
        panelen = []
        for t in TEAMS:
            s = st["teams"][t]
            vakken = [vak(p, t, p.nr in st["opgelost"][t],
                          extra=[knop("/beheer/escape/terug", "↩ terug", bevestig=f"Bewijs {p.nr} van team {t} weer op grijs zetten?", team=t, nr=p.nr)]
                          if p.nr in st["opgelost"][t] else []) for p in esc.puzzels]
            panelen.append(Section(
                Div(Span(f"TEAM {t}", cls="tnaam"), Span(status_tekst(st, t), cls="status"), cls="kop"), klok_el(t),
                Div(*vakken, cls="vakken"), P(strafregel(st, t), cls="straf"),
                Div(*[knop("/beheer/escape/tijd", f"{m:+d} min".replace("-", "−"), team=t, minuten=m) for m in (-1, 1, 5)],
                    knop("/beheer/escape/alarm", "🚨 Alarm", "klein alarmknop", team=t), cls="knoprij"),
                H2("Teamtelefoon"), team_accounts(t, accounts, st["nu"]),
                cls=f"team team-{t.lower()}{toestand(s)}"))
        wachtend = [x for x in accounts if not x["team"]]
        wachtrij = Div(H2("Wachten op een team"), Ul(*[account_rij(x, st["nu"]) for x in wachtend], cls="leden") if wachtend else
                       P("Niemand. Een teamaccount verschijnt hier zodra het /escape opent.", cls="klein"), cls="wachtend")
        return blok(regel, spelknop, slot, wachtrij, Div(*panelen, cls="esc-teams"), st=st)

    @route("/beheer/escape")
    def beheer_pagina(req):
        host = req.headers.get("x-forwarded-host") or req.headers.get("host") or ""
        basis = f"{'http' if host.startswith(('127.0.0.1', 'localhost')) else 'https'}://{host}"
        start = [] if spel.escape_klok(db) else [
            Form(Label("Speeltijd in minuten", Input(type="number", name="minuten", value=str(esc.speeltijd_minuten), min="1", max="180"), cls="veld"),
                 Button("▶ Start beide klokken", type="submit", cls="hoofd"), method="post", action="/beheer/escape/start", cls="esc-start")]
        return pagina("Escaperoom bedienen", *start, live("/beheer/escape/inhoud", beheer_inhoud(), cls="esc beheer-esc"),
                      H2("Laptops en telefoons in de kamers"),
                      P("Log op de telefoon én op de laptop van een team in met hetzelfde teamaccount (geen begeleider). Open op de telefoon ",
                        B(f"{basis}/escape"), " en op de laptop ", B(f"{basis}/escape/bord"),
                        ". Zet het account hierboven in een team; de laptop toont dan vanzelf het prikbord van dat team."),
                      H2("Schermen voor de leiding"),
                      A("Tv: beide teams", href="/beheer/escape/tv", cls="knop"),
                      *[A(f"Meekijken: prikbord van team {t}", href=f"/beheer/escape/tv?team={t}", cls="knop") for t in TEAMS],
                      Form(Label("Typ OPNIEUW om klokken, bewijzen en hints te wissen (de teams blijven)", Input(type="text", name="bevestig", autocomplete="off")),
                           Button("Escaperoom opnieuw beginnen", type="submit"), method="post", action="/beheer/escape/reset"),
                      Script(ESCAPESCRIPT))

    @route("/beheer/escape/inhoud")
    def beheer_fragment():
        return beheer_inhoud()

    @route("/beheer/escape/start", methods=["post"])
    def beheer_start(minuten: str = ""):
        m = int(minuten) if minuten.isascii() and minuten.isdigit() and len(minuten) < 4 else esc.speeltijd_minuten
        spel.escape_start(db, min(max(m, 1), 180) * 60, tijd(), TEAMS)
        return naar("/beheer/escape")

    @route("/beheer/escape/pauze", methods=["post"])
    def beheer_pauze(actie: str = ""):
        if actie in ("pauze", "hervat"):
            spel.escape_pauze(db, actie == "pauze", tijd())
        return naar("/beheer/escape")

    @route("/beheer/escape/tijd", methods=["post"])
    def beheer_tijd(team: str = "", minuten: str = ""):
        try:
            m = int(minuten)
        except ValueError:
            m = 0
        st = stand()
        if team in TEAMS and st["klok"] is not None and m and abs(m) <= 30:
            s = st["teams"][team]
            spel.escape_zet_extra(db, team, nieuwe_extra(s.extra, s.rest_ruw, m * 60))
        return naar("/beheer/escape")

    @route("/beheer/escape/alarm", methods=["post"])
    def beheer_alarm(team: str = ""):
        """Set off the alarm on this team's room board(s) only (they pick it up within one poll)."""
        if team in TEAMS:
            spel.escape_alarm(db, team, tijd())
        return naar("/beheer/escape")

    @route("/beheer/escape/terug", methods=["post"])
    def beheer_terug(team: str = "", nr: str = ""):
        p = puzzel_van(nr)
        if team in TEAMS and p:
            spel.escape_terug(db, team, p.nr)
        return naar("/beheer/escape")

    @route("/beheer/escape/account", methods=["post"])
    def beheer_account(gebruikersnaam: str = "", team: str = ""):
        """Put an account that opened /escape in a team, move it, or take it out (empty team)."""
        if team in TEAMS or team == "":
            spel.escape_zet_account(db, gebruikersnaam, team or None)
        return naar("/beheer/escape")

    @route("/beheer/escape/reset", methods=["post"])
    def beheer_reset(bevestig: str = ""):
        if bevestig.strip() != "OPNIEUW":
            return pagina("Niets gewist", P("Typ OPNIEUW, precies zo, om de escaperoom opnieuw te beginnen."), A("Terug", href="/beheer/escape", cls="knop"))
        spel.escape_reset(db)
        return naar("/beheer/escape")
