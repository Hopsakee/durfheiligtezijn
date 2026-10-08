import copy
import json

import pytest

import shutil

from durfheilig.data import ASSEN, DATA_DIR, DataFout, data_dir, laad_heiligen, laad_vragen

# Example saints from docs/design/rubric.md: (axis, saint on the minus side, saint on the plus side).
RUBRIC_VOORBEELDEN = [
    ("samen_alleen", "Theresia van Lisieux", "Filippus Neri"),
    ("denken_doen", "Edith Stein", "Martinus van Tours"),
    ("achter_voorop", "Josephine Bakhita", "Giovanni Bosco"),
    ("plek_pad", "Clara van Assisi", "Willibrord"),
    ("diepgang_licht", "Edith Stein", "Filippus Neri"),
    ("vrede_strijd", "Franciscus van Assisi", "Jeanne d'Arc"),
]


@pytest.fixture(scope="module")
def heiligen():
    return laad_heiligen()


@pytest.fixture(scope="module")
def vragen():
    return laad_vragen()


def test_alle_heiligen_laden(heiligen, ruw):
    assert len(heiligen) == len(ruw["records"])


def test_vier_vragen_per_as(vragen):
    assert len(vragen.vragen) == 24
    for a in ASSEN:
        assert len(vragen.per_as(a)) == 4, a


def test_vraag_ids_uniek(vragen):
    ids = [v.id for v in vragen.vragen]
    assert len(ids) == len(set(ids))


def test_interessevraag_heeft_precies_de_tien_interesses(vragen):
    lijst = json.loads((DATA_DIR / "heiligen.json").read_text(encoding="utf-8"))["interesses_lijst"]
    assert list(vragen.interesses) == lijst
    assert len(lijst) == 10
    assert all(o["icoon"] for o in vragen.interessevraag["opties"])


@pytest.mark.parametrize("as_,min_naam,plus_naam", RUBRIC_VOORBEELDEN)
def test_tekenconventie_volgt_rubric(heiligen, as_, min_naam, plus_naam):
    per_naam = {h.naam: h for h in heiligen}
    assert per_naam[min_naam].assen[as_] < 0
    assert per_naam[plus_naam].assen[as_] > 0


def test_vragenbank_polen_volgen_rubric(vragen):
    # The minus pole of samen_alleen is "alleen", for the other axes the first word of the key.
    polen = {a["id"]: a["min"].split(":")[0] for a in vragen.assen}
    assert polen == {
        "samen_alleen": "alleen", "denken_doen": "denken", "achter_voorop": "achter de schermen",
        "plek_pad": "vaste plek", "diepgang_licht": "diepgang", "vrede_strijd": "vrede",
    }


def _schrijf(tmp_path, doc):
    pad = tmp_path / "heiligen.json"
    pad.write_text(json.dumps(doc), encoding="utf-8")
    return pad


@pytest.fixture(scope="module")
def ruw():
    return json.loads((DATA_DIR / "heiligen.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("bederf,melding", [
    (lambda r: r["assen"]["plek_pad"].__setitem__("score", 3), "plek_pad"),
    (lambda r: r.__setitem__("interesses", []), "interesses"),
    (lambda r: r.__setitem__("interesses", [{"interesse": "Koken"}]), "vaste lijst"),
    (lambda r: r.__setitem__("geslacht", "onbekend"), "geslacht"),
    (lambda r: r["assen"].pop("vrede_strijd"), "assen"),
])
def test_fout_record_faalt_luid_met_qid(tmp_path, ruw, bederf, melding):
    doc = copy.deepcopy(ruw)
    bederf(doc["records"][0])
    with pytest.raises(DataFout, match=rf"{doc['records'][0]['qid']}.*{melding}"):
        laad_heiligen(_schrijf(tmp_path, doc))


def test_heilige_met_te_weinig_assen_wordt_overgeslagen_met_waarschuwing(tmp_path, ruw):
    doc = copy.deepcopy(ruw)
    r = doc["records"][0]
    for a in ("samen_alleen", "denken_doen", "plek_pad"):
        r["assen"][a]["score"] = None
    with pytest.warns(UserWarning, match=rf"{r['qid']}.*3 van 6 assen"):
        heiligen = laad_heiligen(_schrijf(tmp_path, doc))
    assert len(heiligen) == len(ruw["records"]) - 1
    assert r["qid"] not in {h.qid for h in heiligen}


def test_datamap_via_omgevingsvariabele(tmp_path, monkeypatch):
    for f in ("heiligen.json", "vragen.json"):
        shutil.copy(DATA_DIR / f, tmp_path / f)
    monkeypatch.setenv("DURFHEILIG_DATA", str(tmp_path))
    assert data_dir() == tmp_path
    assert len(laad_heiligen()) == len(json.loads((DATA_DIR / "heiligen.json").read_text(encoding="utf-8"))["records"])
    assert len(laad_vragen().vragen) == 24


def test_iconen_zijn_uniek(vragen):
    iconen = [v.min["icoon"] for v in vragen.vragen] + [v.plus["icoon"] for v in vragen.vragen]
    iconen += [o["icoon"] for o in vragen.interessevraag["opties"]]
    assert len(iconen) == len(set(iconen))
