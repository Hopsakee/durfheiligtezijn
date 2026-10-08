"""Spelstatus in SQLite (fastlite). Heiligen en vragen staan niet hier maar in JSON in de repo.

Per jongere bewaren we alleen de Authelia-gebruikersnaam, de nickname en de antwoorden.
Een heilige kan door maar één speler gekozen worden: dat dwingt de database af (unieke
`gekozen`), zodat twee jongeren die tegelijk dezelfde heilige kiezen niet allebei winnen.
"""

import json
import os
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
"""

JSON_VELDEN = {"vraag_ids", "antwoorden", "interesses", "open_antwoorden", "kandidaten", "vervolg",
               "vervolg_antwoorden", "top3", "niet_want", "afgewezen"}


KOLOMMEN = {"stap", "voorkeur", "vraag_ids", "antwoorden", "interesses", "open_antwoorden", "kandidaten", "vervolg",
            "vervolg_antwoorden", "extra_ronde"}


class AlGekozen(Exception):
    """Een andere speler heeft deze heilige al."""


def nu() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def db_pad() -> Path:
    return Path(os.environ.get("DURFHEILIG_DB", "data/spel.db"))


def open_db(pad: str | Path = ":memory:"):
    if pad != ":memory:":
        Path(pad).parent.mkdir(parents=True, exist_ok=True)
    db = database(str(pad))
    for stuk in SCHEMA.split(";"):
        if stuk.strip():
            db.execute(stuk)
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


def bewaar(db, speler_id: int, **velden) -> None:
    """Werk velden van de invulling bij; JSON-velden mogen Python-waarden zijn."""
    if not velden:
        return
    onbekend = set(velden) - KOLOMMEN
    if onbekend:
        raise ValueError(f"onbekende kolom: {sorted(onbekend)}")
    kolommen = [k for k in velden]
    waarden = [_in(v) if k in JSON_VELDEN else v for k, v in velden.items()]
    db.execute(f"update invulling set {', '.join(f'{k} = ?' for k in kolommen)}, bijgewerkt = ? where speler_id = ?",
               [*waarden, nu(), speler_id])


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


def bewaar_match(db, speler_id: int, top3: list[dict], via_llm: bool, markering: str | None, afgewezen: dict) -> None:
    inv = db.q("select id from invulling where speler_id = ?", [speler_id])[0]["id"]
    if db.q("select 1 from match where invulling_id = ?", [inv]):
        db.execute("update match set top3 = ?, via_llm = ?, markering = coalesce(?, markering), afgewezen = ? where invulling_id = ?",
                   [_in(top3), int(via_llm), markering, _in(afgewezen), inv])
    else:
        db.execute("insert into match(invulling_id, top3, via_llm, markering, afgewezen) values (?, ?, ?, ?, ?)",
                   [inv, _in(top3), int(via_llm), markering, _in(afgewezen)])


def match_van(db, speler_id: int) -> dict | None:
    rij = db.q("select m.* from match m join invulling i on i.id = m.invulling_id where i.speler_id = ?", [speler_id])
    return _uit(rij[0]) if rij else None


def kies(db, speler_id: int, qid: str, klopt_want: str, niet_want: dict[str, str]) -> None:
    """Leg de gekozen heilige vast; AlGekozen als een ander hem eerder koos."""
    try:
        db.execute(
            "update match set gekozen = ?, klopt_want = ?, niet_want = ? "
            "where invulling_id = (select id from invulling where speler_id = ?)",
            [qid, klopt_want, _in(niet_want), speler_id])
    except apsw.ConstraintError as e:
        raise AlGekozen(qid) from e


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
    }


def verwijder_alles(db) -> None:
    for tabel in ("match", "invulling", "speler"):
        db.execute(f"delete from {tabel}")
    # delete alone leaves the answers in free pages and in the write-ahead log: rewrite the file, then empty the log.
    db.execute("vacuum")
    db.execute("pragma wal_checkpoint(truncate)")
