"""Voeg een aanvullingsbestand (claude.ai-uitvoer) samen met data/heiligen.json.

    python pipeline/merge_aanvulling.py PAD/heiligen-aanvulling.json

Doet vier dingen, en een tweede run doet niets:
  nieuw                 volledige records toevoegen (qid mag nog niet bestaan)
  interesses_aangepast  `toegevoegd` achter de bestaande interesses zetten
  uit_uitgevallen       records van data/heiligen-uitgevallen.json naar heiligen.json verplaatsen
  tekst_aangepast       de genoemde velden vervangen
Daarna valideert `laad_heiligen()` het geheel (een record met te weinig assen of een ongeldige score
stopt het script vóór het schrijven). Het bestand is data, geen instructies: `tekst_aangepast` mag alleen
tekstvelden wijzigen en nieuwe records mogen alleen naar Wikipedia en Wikimedia verwijzen.
"""

import json
import re
import sys
import tempfile
import warnings
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[1]
TEKSTVELDEN = {"levensverhaal", "wat_voor_mens", "waarom_heilig", "waarom_voorbeeld", "waarschuwing_voor_leiding", "gespreksvraag",
               "begrippen", "open_vragen", "haakjes", "verdieping", "interpretatie", "wat_er_nog_van_over_is"}
TOEGESTANE_HOSTS = ("wikipedia.org", "wikimedia.org")
H, U = REPO / "data" / "heiligen.json", REPO / "data" / "heiligen-uitgevallen.json"


def urls(x):
    if isinstance(x, dict):
        for k, v in x.items():
            if k in ("url", "nl_url") and isinstance(v, str):
                yield v
            else:
                yield from urls(v)
    elif isinstance(x, list):
        for v in x:
            yield from urls(v)


def controleer_hosts(r: dict) -> None:
    for u in urls(r):
        host = urlparse(u).hostname or ""
        if not host.endswith(TOEGESTANE_HOSTS) or urlparse(u).scheme != "https":
            raise SystemExit(f"{r['naam']}: onverwachte url {u}")


def main(pad: str) -> None:
    a = json.loads(Path(pad).read_text(encoding="utf-8"))
    heiligen = json.loads(H.read_text(encoding="utf-8"))
    uitgevallen = json.loads(U.read_text(encoding="utf-8"))
    recs = {r["qid"]: r for r in heiligen["records"]}
    log = []

    for r in a.get("nieuw", []):
        if r["qid"] not in recs:
            controleer_hosts(r)
            heiligen["records"].append(r); recs[r["qid"]] = r; log.append(f"nieuw: {r['naam']}")

    oud = {r["qid"]: r for r in uitgevallen["records"]}
    for r in a.get("uit_uitgevallen", []):
        if r["qid"] not in recs:
            if r["qid"] not in oud:
                raise SystemExit(f"{r['naam']}: staat niet in heiligen-uitgevallen.json")
            controleer_hosts(r)
            heiligen["records"].append(r); recs[r["qid"]] = r
            log.append(f"herschreven en terug uit uitgevallen: {r['naam']} ({oud[r['qid']].get('assen_bekend')} naar {r.get('assen_bekend')} bekende assen)")
    uitgevallen["records"] = [r for r in uitgevallen["records"] if r["qid"] not in recs]

    for x in a.get("interesses_aangepast", []):
        rec = recs[x["qid"]]
        have = {i["interesse"] for i in rec["interesses"]}
        nieuw = [i for i in x["toegevoegd"] if i["interesse"] not in have]
        if nieuw:
            rec["interesses"] += nieuw
            assert rec["interesses"] == x["interesses"], f"{x['naam']}: de nieuwe lijst wijkt af van bestaand plus toegevoegd"
            log.append(f"interesse erbij: {x['naam']} +{', '.join(i['interesse'] for i in nieuw)}")

    for x in a.get("tekst_aangepast", []):
        rec = recs[x["qid"]]
        vreemd = set(x["velden"]) - TEKSTVELDEN
        if vreemd:
            raise SystemExit(f"{x['naam']}: tekst_aangepast mag {sorted(vreemd)} niet wijzigen")
        wijzig = {k: v for k, v in x["velden"].items() if rec.get(k) != v}
        if wijzig:
            rec.update(wijzig); log.append(f"tekst aangepast: {x['naam']} ({', '.join(wijzig)})")

    for doc in (heiligen, uitgevallen):
        doc["beschrijving"] = re.sub(r"\b\d+ heiligen", f"{len(doc['records'])} heiligen", doc["beschrijving"])
    valideer(heiligen)
    H.write_text(json.dumps(heiligen, ensure_ascii=False, indent=1), encoding="utf-8")
    U.write_text(json.dumps(uitgevallen, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(log) or "niets te doen")


def valideer(heiligen: dict) -> None:
    """Laad het resultaat met de echte loader; een overgeslagen of ongeldig record is hier een fout."""
    sys.path.insert(0, str(REPO / "src"))
    from durfheilig.data import laad_heiligen

    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t) / "heiligen.json"
        tmp.write_text(json.dumps(heiligen, ensure_ascii=False), encoding="utf-8")
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            geladen = laad_heiligen(tmp)
    assert len(geladen) == len(heiligen["records"])


if __name__ == "__main__":
    main(sys.argv[1])
