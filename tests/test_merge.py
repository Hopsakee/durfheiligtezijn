import copy
import importlib.util
import json
import shutil

import pytest

from durfheilig.data import DATA_DIR

_spec = importlib.util.spec_from_file_location("merge_aanvulling", DATA_DIR.parent / "pipeline" / "merge_aanvulling.py")
merge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(merge)


@pytest.fixture
def kopie(tmp_path, monkeypatch):
    for f in ("heiligen.json", "heiligen-uitgevallen.json"):
        shutil.copy(DATA_DIR / f, tmp_path / f)
    monkeypatch.setattr(merge, "H", tmp_path / "heiligen.json")
    monkeypatch.setattr(merge, "U", tmp_path / "heiligen-uitgevallen.json")
    return tmp_path


def _aanvulling(tmp_path, **delen):
    p = tmp_path / "a.json"
    p.write_text(json.dumps(delen), encoding="utf-8")
    return str(p)


def _record(kopie):
    r = copy.deepcopy(json.loads((kopie / "heiligen.json").read_text(encoding="utf-8"))["records"][0])
    r["lees_zelf"] = []     # the first old record links to an external site, which new records may not
    return r


def test_nieuw_record_wordt_toegevoegd_en_een_tweede_run_doet_niets(kopie):
    r = _record(kopie)
    r["qid"], r["naam"] = "Q1", "Test"
    pad = _aanvulling(kopie, nieuw=[r])
    merge.main(pad)
    na = (kopie / "heiligen.json").read_bytes()
    assert b'"Q1"' in na
    merge.main(pad)
    assert (kopie / "heiligen.json").read_bytes() == na


def test_record_met_te_weinig_assen_stopt_het_schrijven(kopie):
    voor = (kopie / "heiligen.json").read_bytes()
    r = _record(kopie)
    r["qid"], r["naam"] = "Q1", "Test"
    for a in ("samen_alleen", "denken_doen", "plek_pad"):
        r["assen"][a]["score"] = None
    with pytest.raises(Exception):
        merge.main(_aanvulling(kopie, nieuw=[r]))
    assert (kopie / "heiligen.json").read_bytes() == voor


def test_tekst_aangepast_mag_geen_scores_of_afbeeldingen_wijzigen(kopie):
    r = _record(kopie)
    with pytest.raises(SystemExit, match="assen"):
        merge.main(_aanvulling(kopie, tekst_aangepast=[{"qid": r["qid"], "naam": r["naam"], "velden": {"assen": {}}}]))


def test_nieuw_record_met_vreemde_host_wordt_geweigerd(kopie):
    r = _record(kopie)
    r["qid"], r["naam"] = "Q1", "Test"
    r["afbeelding"]["url"] = "https://evil.example/x.jpg"
    with pytest.raises(SystemExit, match="onverwachte url"):
        merge.main(_aanvulling(kopie, nieuw=[r]))


def test_uit_uitgevallen_moet_in_de_uitgevallen_lijst_staan(kopie):
    r = _record(kopie)
    r["qid"], r["naam"] = "Q1", "Test"
    with pytest.raises(SystemExit, match="staat niet in"):
        merge.main(_aanvulling(kopie, uit_uitgevallen=[r]))
