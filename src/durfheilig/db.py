"""Spelstatus in SQLite (fastlite). Heiligen en vragen staan niet hier maar in JSON in de repo.

Per jongere bewaren we alleen de Authelia-gebruikersnaam, de nickname en de antwoorden.
Een heilige kan door maar één speler gekozen worden: dat dwingt de database af (unieke
`gekozen`), zodat twee jongeren die tegelijk dezelfde heilige kiezen niet allebei winnen.
"""

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

import apsw
from fastlite import database

SCHEMA = """
create table if not exists speler (
    id integer primary key,
    gebruikersnaam text not null unique,
    nickname text,
    aangemaakt text not null
);
create unique index if not exists speler_nickname on speler(lower(nickname));
create table if not exists invulling (
    id integer primary key,
    speler_id integer not null unique references speler(id),
    stap text not null default 'welkom',
    voorkeur text,
    vraag_ids text not null default '[]',
    antwoorden text not null default '{}',
    interesses text not null default '[]',
    open_antwoorden text not null default '[]',
    kandidaten text not null default '[]',
    vervolg text not null default '[]',
    vervolg_antwoorden text not null default '{}',
    extra_ronde integer not null default 0,
    bijgewerkt text not null
);
create table if not exists match (
    id integer primary key,
    invulling_id integer not null unique references invulling(id),
    top3 text not null,
    via_llm integer not null,
    markering text,
    gekozen text unique,
    klopt_want text,
    niet_want text not null default '{}',
    afgewezen text not null default '{}'
);
create table if not exists spel (
    id integer primary key check (id = 1),
    status text not null,
    huidige_ronde integer
);
create table if not exists bord (
    qid text primary key,
    gekozen integer not null,
    volgorde integer not null
);
create table if not exists spelronde (
    id integer primary key,
    speler_id integer not null unique references speler(id),
    volgorde integer not null,
    fase text not null default 'overleg1',
    punten integer,
    stemmers integer,
    goed1 integer,
    goed2 integer,
    max_punten integer
);
create table if not exists stem (
    id integer primary key,
    spelronde_id integer not null references spelronde(id),
    speler_id integer not null references speler(id),
    qid text not null,
    stemronde integer not null,
    unique (spelronde_id, speler_id, stemronde)
);
create table if not exists gelezen (
    speler_id integer not null references speler(id),
    lezer text not null,
    primary key (speler_id, lezer)
);
create table if not exists escape_klok (
    id integer primary key check (id = 1),
    duur integer not null,
    gestart real not null,
    gepauzeerd_op real,
    pauze_totaal real not null default 0
);
create table if not exists escape_team (
    team text primary key,
    extra integer not null default 0,
    klaar_speeltijd real
);
create table if not exists escape_account (
    gebruikersnaam text primary key,
    team text,
    aangemaakt real not null,
    laatst_gezien real
);
create table if not exists escape_opgelost (
    team text not null,
    puzzel integer not null,
    speeltijd real not null,
    primary key (team, puzzel)
);
create table if not exists escape_hint (
    team text not null,
    puzzel integer not null,
    nummer integer not null,
    speeltijd real not null,
    primary key (team, puzzel, nummer)
);
create table if not exists escape_gebeurtenis (
    id integer primary key autoincrement,
    team text not null,
    soort text not null,
    puzzel integer,
    nummer integer,
    tijd real not null
);
"""

JSON_VELDEN = {"vraag_ids", "antwoorden", "interesses", "open_antwoorden", "kandidaten", "vervolg",
               "vervolg_antwoorden", "top3", "niet_want", "afgewezen"}


KOLOMMEN = {"stap", "voorkeur", "vraag_ids", "antwoorden", "interesses", "open_antwoorden", "kandidaten", "vervolg",
            "vervolg_antwoorden", "extra_ronde"}


class AlGekozen(Exception):
    """Een andere speler heeft deze heilige al."""


class GeenMatch(Exception):
    """De speler heeft geen match (meer) om uit te kiezen."""


def nu() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def db_pad() -> Path:
    return Path(os.environ.get("DURFHEILIG_DB", "data/spel.db"))


def open_db(pad: str | Path = ":memory:"):
    if pad != ":memory:":
        Path(pad).parent.mkdir(parents=True, exist_ok=True)
    db = database(str(pad))
    # One SQLite connection serves every request thread, and apsw refuses overlapping use ("Connection is busy in another thread").
    # Phones and the tv poll every 2 seconds, so overlap is certain: every query and write waits its turn on one lock.
    db.lock = threading.RLock()
    for naam in ("q", "execute"):
        origineel = getattr(db, naam)
        def beurt(*a, _f=origineel, **k):
            with db.lock:
                return _f(*a, **k)
        setattr(db, naam, beurt)
    for stuk in SCHEMA.split(";"):
        if stuk.strip():
            db.execute(stuk)
    # A database made before the round result was stored at the reveal lacks these columns: add them (once; `create table if not exists` does not).
    bestaand = {r["name"] for r in db.q("pragma table_info(spelronde)")}
    for kolom in ("stemmers", "goed1", "goed2", "max_punten"):
        if kolom not in bestaand:
            db.execute(f"alter table spelronde add column {kolom} integer")
    return db


def _uit(rij: dict | None) -> dict | None:
    if rij is None:
        return None
    return {k: (json.loads(v) if k in JSON_VELDEN and isinstance(v, str) else v) for k, v in rij.items()}


def _in(waarde):
    return json.dumps(waarde, ensure_ascii=False)


def speler_voor(db, gebruikersnaam: str) -> dict:
    """De speler en zijn invulling; wordt bij het eerste bezoek aangemaakt."""
    rij = db.q("select * from speler where gebruikersnaam = ?", [gebruikersnaam])
    if not rij:
        db.execute("insert or ignore into speler(gebruikersnaam, aangemaakt) values (?, ?)", [gebruikersnaam, nu()])
        rij = db.q("select * from speler where gebruikersnaam = ?", [gebruikersnaam])
    sp = rij[0]
    if not db.q("select 1 from invulling where speler_id = ?", [sp["id"]]):
        db.execute("insert or ignore into invulling(speler_id, bijgewerkt) values (?, ?)", [sp["id"], nu()])
    return sp


def invulling(db, speler_id: int) -> dict:
    return _uit(db.q("select * from invulling where speler_id = ?", [speler_id])[0])


def bewaar(db, speler_id: int, *, alleen_bij_stap: str | None = None, **velden) -> bool:
    """Werk velden van de invulling bij; JSON-velden mogen Python-waarden zijn.

    Met `alleen_bij_stap` gebeurt het alleen als de speler nog in die stap staat. Zo schrijft een trage stap (die op Gemini wachtte)
    niet over een quiz heen die de speler intussen opnieuw begon. Geeft terug of er iets bijgewerkt is."""
    if not velden:
        return False
    onbekend = set(velden) - KOLOMMEN
    if onbekend:
        raise ValueError(f"onbekende kolom: {sorted(onbekend)}")
    kolommen = [k for k in velden]
    waarden = [_in(v) if k in JSON_VELDEN else v for k, v in velden.items()]
    with db.lock:
        db.execute(f"update invulling set {', '.join(f'{k} = ?' for k in kolommen)}, bijgewerkt = ? where speler_id = ?"
                   + (" and stap = ?" if alleen_bij_stap else ""),
                   [*waarden, nu(), speler_id, *([alleen_bij_stap] if alleen_bij_stap else [])])
        return db.conn.changes() > 0


class NicknameBezet(Exception):
    pass


def zet_nickname(db, speler_id: int, nickname: str) -> None:
    try:
        db.execute("update speler set nickname = ? where id = ?", [nickname, speler_id])
    except apsw.ConstraintError as e:
        raise NicknameBezet(nickname) from e


def gekozen_heiligen(db, behalve_speler: int | None = None) -> set[str]:
    rijen = db.q(
        "select m.gekozen from match m join invulling i on i.id = m.invulling_id "
        "where m.gekozen is not null and i.speler_id is not ?", [behalve_speler])
    return {r["gekozen"] for r in rijen}


def bewaar_match(db, speler_id: int, top3: list[dict], via_llm: bool, markering: str | None, afgewezen: dict, *,
                 verwacht_stap: str | None = None, stap_na: str | None = None) -> bool:
    """Bewaar de top-3. Met `verwacht_stap` alleen als de speler nog in die stap staat (anders is hij intussen opnieuw begonnen);
    `stap_na` zet de volgende stap in dezelfde transactie. Geeft terug of het bewaard is."""
    with db.lock, db.conn:
        rij = db.q("select id, stap from invulling where speler_id = ?", [speler_id])[0]
        if verwacht_stap and rij["stap"] != verwacht_stap:
            return False
        inv = rij["id"]
        if db.q("select 1 from match where invulling_id = ?", [inv]):
            db.execute("update match set top3 = ?, via_llm = ?, markering = coalesce(?, markering), afgewezen = ? where invulling_id = ?",
                       [_in(top3), int(via_llm), markering, _in(afgewezen), inv])
        else:
            db.execute("insert into match(invulling_id, top3, via_llm, markering, afgewezen) values (?, ?, ?, ?, ?)",
                       [inv, _in(top3), int(via_llm), markering, _in(afgewezen)])
        if stap_na:
            db.execute("update invulling set stap = ?, bijgewerkt = ? where id = ?", [stap_na, nu(), inv])
        return True


def match_van(db, speler_id: int) -> dict | None:
    rij = db.q("select m.* from match m join invulling i on i.id = m.invulling_id where i.speler_id = ?", [speler_id])
    return _uit(rij[0]) if rij else None


def kies(db, speler_id: int, qid: str, klopt_want: str, niet_want: dict[str, str]) -> None:
    """Leg de gekozen heilige vast; AlGekozen als een ander hem eerder koos, GeenMatch als er geen match meer is (de speler begon opnieuw)."""
    with db.lock:
        try:
            db.execute(
                "update match set gekozen = ?, klopt_want = ?, niet_want = ? "
                "where invulling_id = (select id from invulling where speler_id = ?)",
                [qid, klopt_want, _in(niet_want), speler_id])
        except apsw.ConstraintError as e:
            raise AlGekozen(qid) from e
        if db.conn.changes() == 0:
            raise GeenMatch(speler_id)


def profiel_van(db, gebruikersnaam: str) -> dict | None:
    """Zonder iets aan te maken: de stap van deze account en of er al een match is. None als de account nog niet bestaat."""
    rij = db.q("select i.stap, (select count(*) from match m where m.invulling_id = i.id) as match, (select count(*) from spel) as gestart "
               "from speler s join invulling i on i.speler_id = s.id where s.gebruikersnaam = ?", [gebruikersnaam])
    return {"stap": rij[0]["stap"], "heeft_match": bool(rij[0]["match"]), "spel_gestart": bool(rij[0]["gestart"])} if rij else None


# What a fresh `invulling` row holds (the same as the column defaults in SCHEMA; a test keeps the two equal).
INVULLING_BEGIN = {"stap": "welkom", "voorkeur": None, "vraag_ids": [], "antwoorden": {}, "interesses": [], "open_antwoorden": [],
                   "kandidaten": [], "vervolg": [], "vervolg_antwoorden": {}, "extra_ronde": 0}


def reset_invulling(db, speler_id: int) -> bool:
    """Fill in the quiz again: wipe the answers and the match (which frees the chosen saint). The nickname stays, and so does who read the
    explanation: a leader who read it already knows the saint the kid is likely to get again, so that rule must not be reset away.

    Not once the game has started: that is checked here, inside the same transaction as the wipe, so a start can never slip in between.
    Returns whether it was done."""
    with db.lock, db.conn:
        if spel_status(db):
            return False
        db.execute("delete from match where invulling_id = (select id from invulling where speler_id = ?)", [speler_id])
        kolommen = {**INVULLING_BEGIN, "bijgewerkt": nu()}
        db.execute(f"update invulling set {', '.join(f'{k} = ?' for k in kolommen)} where speler_id = ?",
                   [*[_in(v) if k in JSON_VELDEN else v for k, v in kolommen.items()], speler_id])
        return True


def overzicht(db) -> list[dict]:
    """Voor de begeleiders: wie is waar, en wat is gemarkeerd."""
    return [_uit(r) for r in db.q(
        "select s.id, s.gebruikersnaam, s.nickname, i.stap, m.gekozen, m.markering, m.via_llm "
        "from speler s join invulling i on i.speler_id = s.id left join match m on m.invulling_id = i.id "
        "order by s.nickname is null, s.nickname, s.gebruikersnaam")]


def exporteer(db) -> dict:
    """Alles wat de app over de groep bewaart, voor de begeleiders en de vergelijking in juni."""
    return {
        "spelers": db.q("select * from speler order by id"),
        "invullingen": [_uit(r) for r in db.q("select * from invulling order by id")],
        "matches": [_uit(r) for r in db.q("select * from match order by id")],
        "spel": db.q("select * from spel"),
        "bord": db.q("select * from bord order by volgorde"),
        "rondes": db.q("select * from spelronde order by volgorde"),
        # who voted what stays in the database (a vote is replaced per voter) but never leaves it, not even in the export
        "stemmen": db.q("select spelronde_id, qid, stemronde from stem order by id"),
        "gelezen": db.q("select * from gelezen"),
        "escape": {t: db.q(f"select * from {t}") for t in (*ESCAPE_TABELLEN, "escape_account")},
    }


def verwijder_alles(db) -> None:
    for tabel in ("stem", "spelronde", "bord", "spel", "gelezen", "match", "invulling", "speler", *ESCAPE_TABELLEN, "escape_account"):
        db.execute(f"delete from {tabel}")
    # delete alone leaves the answers in free pages and in the write-ahead log: rewrite the file, then empty the log.
    db.execute("vacuum")
    db.execute("pragma wal_checkpoint(truncate)")


# ---------------------------------------------------------------- het raadspel

def spelers_klaar(db) -> list[dict]:
    """Wie een heilige heeft gekozen en dus meedoet: id, bijnaam, account, gekozen qid en geslachtsvoorkeur."""
    return db.q(
        "select s.id, s.nickname, s.gebruikersnaam, m.gekozen, i.voorkeur from speler s "
        "join invulling i on i.speler_id = s.id join match m on m.invulling_id = i.id "
        "where i.stap = 'klaar' and m.gekozen is not null order by s.id")


def speler_door_id(db, speler_id: int) -> dict | None:
    rij = db.q("select id, nickname from speler where id = ?", [speler_id])
    return rij[0] if rij else None


def spel_status(db) -> dict | None:
    rij = db.q("select * from spel")
    return rij[0] if rij else None


def start_spel(db, bord: list[tuple[str, bool]], speler_ids: list[int]) -> None:
    """Leg het bord en de volgorde van de rondes vast. Eén keer; daarna ligt alles vast."""
    with db.lock, db.conn:   # one transaction: a polling screen never sees half a game
        db.execute("insert into spel(id, status, huidige_ronde) values (1, 'bord', null)")
        for volgorde, (qid, gekozen) in enumerate(bord):
            db.execute("insert into bord(qid, gekozen, volgorde) values (?, ?, ?)", [qid, int(gekozen), volgorde])
        for volgorde, sid in enumerate(speler_ids):
            db.execute("insert into spelronde(speler_id, volgorde) values (?, ?)", [sid, volgorde])


def reset_spel(db) -> None:
    with db.lock, db.conn:
        for tabel in ("stem", "spelronde", "bord", "spel"):
            db.execute(f"delete from {tabel}")


def bord_rijen(db) -> list[dict]:
    return db.q("select * from bord order by volgorde")


def rondes(db) -> list[dict]:
    return db.q("select r.*, s.nickname, s.gebruikersnaam from spelronde r join speler s on s.id = r.speler_id order by r.volgorde")


def zet_spelstatus(db, status: str, huidige_ronde: int | None = None) -> None:
    db.execute("update spel set status = ?, huidige_ronde = ? where id = 1", [status, huidige_ronde])


def zet_fase(db, ronde_id: int, fase: str, uitslag: dict | None = None) -> None:
    """Move a round to its next phase. The result of the round (at the reveal) goes in the same write, so no screen sees the phase without it and
    later changes (a leader opening someone's explanation) cannot alter what was scored."""
    u = uitslag or {}
    db.execute("update spelronde set fase = ?, punten = coalesce(?, punten), stemmers = coalesce(?, stemmers), goed1 = coalesce(?, goed1), "
               "goed2 = coalesce(?, goed2), max_punten = coalesce(?, max_punten) where id = ?",
               [fase, u.get("punten"), u.get("stemmers"), u.get("goed1"), u.get("goed2"), u.get("max"), ronde_id])


def stem_uit(db, ronde_id: int, speler_id: int, qid: str, stemronde: int) -> None:
    """Een stem per speler per stemronde; opnieuw stemmen vervangt de vorige."""
    db.execute(
        "insert into stem(spelronde_id, speler_id, qid, stemronde) values (?, ?, ?, ?) "
        "on conflict(spelronde_id, speler_id, stemronde) do update set qid = excluded.qid",
        [ronde_id, speler_id, qid, stemronde])


def stemmen(db, ronde_id: int, stemronde: int) -> list[dict]:
    return db.q("select speler_id, qid from stem where spelronde_id = ? and stemronde = ?", [ronde_id, stemronde])


def markeer_gelezen(db, speler_id: int, lezer: str) -> None:
    db.execute("insert or ignore into gelezen(speler_id, lezer) values (?, ?)", [speler_id, lezer])


def lezers(db, speler_id: int) -> set[str]:
    return {r["lezer"] for r in db.q("select lezer from gelezen where speler_id = ?", [speler_id])}


# ---------------------------------------------------------------- de escaperoom (escape.py)
# Times are epoch seconds from the server (`time.time()`), passed in by the caller so tests can fix them. `speeltijd` is the game's running
# time at that moment (pauses not counted), computed by escape.py.

ESCAPE_TABELLEN = ("escape_gebeurtenis", "escape_hint", "escape_opgelost", "escape_team", "escape_klok")   # a reset keeps escape_account (who is in which team)


def escape_klok(db) -> dict | None:
    rij = db.q("select * from escape_klok")
    return rij[0] if rij else None


def escape_start(db, duur: int, nu: float, teams) -> bool:
    """Start both clocks at once. Only once: a second tap (or a second leader) changes nothing. Returns whether it started now."""
    with db.lock, db.conn:
        if escape_klok(db):
            return False
        db.execute("insert into escape_klok(id, duur, gestart) values (1, ?, ?)", [duur, nu])
        for t in teams:
            db.execute("insert or ignore into escape_team(team) values (?)", [t])
        return True


def escape_pauze(db, pauze: bool, nu: float) -> None:
    """Pause or resume both clocks. Idempotent: pausing a paused game or resuming a running one does nothing."""
    with db.lock, db.conn:
        k = escape_klok(db)
        if not k:
            return
        if pauze and k["gepauzeerd_op"] is None:
            db.execute("update escape_klok set gepauzeerd_op = ? where id = 1", [nu])
        elif not pauze and k["gepauzeerd_op"] is not None:
            db.execute("update escape_klok set pauze_totaal = pauze_totaal + ?, gepauzeerd_op = null where id = 1", [max(0.0, nu - k["gepauzeerd_op"])])


def escape_teams(db) -> dict[str, dict]:
    return {r["team"]: r for r in db.q("select * from escape_team")}


def escape_zet_extra(db, team: str, extra: int) -> None:
    db.execute("update escape_team set extra = ? where team = ?", [extra, team])


def escape_account(db, gebruikersnaam: str) -> dict | None:
    rij = db.q("select * from escape_account where gebruikersnaam = ?", [gebruikersnaam])
    return rij[0] if rij else None


def escape_meld(db, gebruikersnaam: str, nu: float) -> None:
    """An account opened /escape: it now waits in the leader's list until the leader puts it in a team."""
    db.execute("insert or ignore into escape_account(gebruikersnaam, team, aangemaakt) values (?, null, ?)", [gebruikersnaam, nu])


def escape_accounts(db) -> list[dict]:
    """Every account that opened /escape, with its nickname from the saint quiz when it has one."""
    return db.q("select a.*, s.nickname from escape_account a left join speler s on s.gebruikersnaam = a.gebruikersnaam "
                "order by a.team is null, a.team, a.gebruikersnaam")


def escape_zet_account(db, gebruikersnaam: str, team: str | None) -> None:
    """Put a known account in a team, or take it out (None). An account that never opened /escape is left alone."""
    db.execute("update escape_account set team = ? where gebruikersnaam = ?", [team, gebruikersnaam])


def escape_gezien(db, gebruikersnaam: str, nu: float) -> None:
    """Note that the phone is alive; written at most every 10 seconds, though the phone polls every 2."""
    db.execute("update escape_account set laatst_gezien = ? where gebruikersnaam = ? and (laatst_gezien is null or laatst_gezien < ?)",
               [nu, gebruikersnaam, nu - 10])


def escape_opgelost(db) -> dict[str, dict[int, float]]:
    uit: dict[str, dict[int, float]] = {}
    for r in db.q("select * from escape_opgelost"):
        uit.setdefault(r["team"], {})[r["puzzel"]] = r["speeltijd"]
    return uit


def escape_hints(db) -> dict[str, dict[int, int]]:
    uit: dict[str, dict[int, int]] = {}
    for r in db.q("select team, puzzel, count(*) as n from escape_hint group by team, puzzel"):
        uit.setdefault(r["team"], {})[r["puzzel"]] = r["n"]
    return uit


def _gebeurtenis(db, team: str, soort: str, puzzel: int | None, nu: float, nummer: int | None = None) -> None:
    db.execute("insert into escape_gebeurtenis(team, soort, puzzel, nummer, tijd) values (?, ?, ?, ?, ?)", [team, soort, puzzel, nummer, nu])


def escape_los_op(db, team: str, puzzel: int, speeltijd: float, alle: set[int], nu: float) -> bool:
    """Record a right answer. In one transaction: the solve (once per team and puzzle, so two phones at once count once), the event for the
    screens, and the finish time when this was the last one missing. Returns whether it was new."""
    with db.lock, db.conn:
        db.execute("insert or ignore into escape_opgelost(team, puzzel, speeltijd) values (?, ?, ?)", [team, puzzel, speeltijd])
        if db.conn.changes() == 0:
            return False
        _gebeurtenis(db, team, "goed", puzzel, nu)
        klaar = {r["puzzel"] for r in db.q("select puzzel from escape_opgelost where team = ?", [team])}
        if alle <= klaar:
            db.execute("update escape_team set klaar_speeltijd = ? where team = ? and klaar_speeltijd is null", [speeltijd, team])
            _gebeurtenis(db, team, "klaar", None, nu)
        return True


def escape_fout(db, team: str, puzzel: int, nu: float) -> None:
    _gebeurtenis(db, team, "fout", puzzel, nu)


def escape_neem_hint(db, team: str, puzzel: int, maximum: int, speeltijd: float, nu: float) -> bool:
    """The team's next hint for this puzzle, if there is one left. Returns whether one was taken."""
    with db.lock, db.conn:
        n = db.q("select count(*) as n from escape_hint where team = ? and puzzel = ?", [team, puzzel])[0]["n"]
        if n >= maximum:
            return False
        db.execute("insert into escape_hint(team, puzzel, nummer, speeltijd) values (?, ?, ?, ?)", [team, puzzel, n + 1, speeltijd])
        _gebeurtenis(db, team, "hint", puzzel, nu, n + 1)
        return True


def escape_terug(db, team: str, puzzel: int) -> None:
    """Undo a wrongly accepted answer: the box goes grey again and the team is no longer finished."""
    with db.lock, db.conn:
        db.execute("delete from escape_opgelost where team = ? and puzzel = ?", [team, puzzel])
        db.execute("update escape_team set klaar_speeltijd = null where team = ?", [team])


def escape_gebeurtenissen(db, n: int = 20) -> list[dict]:
    return list(reversed(db.q("select id, team, soort, puzzel, nummer from escape_gebeurtenis order by id desc limit ?", [n])))


def escape_reset(db) -> None:
    """Back to before the start. The team accounts keep their team."""
    with db.lock, db.conn:
        for tabel in ESCAPE_TABELLEN:
            db.execute(f"delete from {tabel}")
