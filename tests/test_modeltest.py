import json
import random

from durfheilig.data import laad_heiligen, laad_vragen
from durfheilig.llm import LlmFout
from durfheilig.modeltest import (OPEN_ANTWOORDEN, controleer_uitleg, controleer_vraag, draai_model, rapport, samenvatting, verwijst_naar_kind,
                                  verzonnen_deelnemer, zinnen)

H, V = laad_heiligen(), laad_vragen()


def goede_llm(systeem, gegevens):
    data = json.loads(gegevens)
    qids = [k["qid"] for k in data["kandidaten"]]
    if "Bedenk" in systeem:
        return json.dumps({"vragen": [{"vraag": f"Vraag {i}?", "min": "Liever alleen", "plus": "Liever samen", "stijgt_bij_min": qids[:1], "stijgt_bij_plus": qids[1:2]} for i in range(3)]})
    eigen = (data["tekst_van_de_jongere"] or ["jou"])[0].split()[-1]
    return json.dumps({"keuzes": [{"qid": q, "uitleg": f"Jij houdt van {eigen}. Dat past bij hem. Mooi toch."} for q in qids[:3]], "markering": None})


def test_zinnen_tellen():
    assert zinnen("Een. Twee! Drie?") == 3 and zinnen("Eén zin zonder punt") == 1 and zinnen("") == 0


def test_een_goede_uitleg_geeft_geen_opmerkingen_en_een_slechte_veel():
    h = H[0]
    goed = "Jij houdt van tekenen, en hij vond mooie dingen belangrijk. Dat past bij jou."
    assert controleer_uitleg(goed, h, ["Ik ben goed in tekenen"]) == []
    slecht = "**You** are the one and this is your saint because he was kind. Als AI zeg ik dat u hem moet kiezen. In 1234 deed hij iets."
    p = " | ".join(controleer_uitleg(slecht, h, []))
    for woord in ("Engels", "markdown", "u-vorm", "AI", "jaartal niet in het record: 1234"):
        assert woord in p, woord
    assert any("zinnen" in x for x in controleer_uitleg("Alleen een.", h, []))


def test_een_jaartal_uit_het_record_telt_niet_als_verzonnen():
    h = next(x for x in H if any(j for j in __import__("re").findall(r"\b1[0-9]{3}\b", str(x.record.get("levensverhaal")))))
    jaar = __import__("re").search(r"\b1[0-9]{3}\b", h.record["levensverhaal"]).group(0)
    assert controleer_uitleg(f"Hij werd geboren rond {jaar}. Dat is lang geleden.", h, []) == []


def test_verwijzing_naar_de_eigen_woorden_van_het_kind():
    assert verwijst_naar_kind("Je tekenwerk past bij hem", ["Ik ben goed in tekenen"]) is True      # 'teken' shared
    assert verwijst_naar_kind("Hij hield van schapen", ["Ik ben goed in tekenen"]) is False
    assert verwijst_naar_kind("Alles", []) is False


def test_vragen_worden_gecontroleerd():
    from durfheilig.llm import Vervolgvraag
    assert controleer_vraag(Vervolgvraag("v1", "Wil je graag samen zijn?", "alleen", "samen", (), ())) == []
    assert "vraag eindigt niet op ?" in controleer_vraag(Vervolgvraag("v1", "Zeg het maar", "alleen", "samen", (), ()))
    assert "antwoord te kort" in controleer_vraag(Vervolgvraag("v1", "Is het zo?", "a", "samen", (), ()))


def test_de_verzonnen_deelnemers_zijn_herhaalbaar_en_verschillen_onderling():
    a = verzonnen_deelnemer(0, 7, H, V)
    assert verzonnen_deelnemer(0, 7, H, V)[1] == a[1] and len(a[4]) == 12
    assert len({tuple(sorted(verzonnen_deelnemer(i, 7, H, V)[1].items())) for i in range(len(OPEN_ANTWOORDEN))}) > 3


def test_een_hele_testrun_met_een_goed_model_telt_alles_als_bruikbaar_en_schrijft_een_leesbaar_rapport():
    per, ctx, duren = draai_model(goede_llm, 4, 7, gelijktijdig=5, heiligen=H, vragen=V)
    alle = [m for ms in per for m in ms]
    assert len(alle) == 8 and all(m.door_llm for m in alle) and len(duren) == 5
    tekst = rapport("model-x", per, ctx, duren)
    assert "# Modeltest: model-x" in tekst and "4 van 4 bruikbaar" in tekst and "5 tegelijk" in tekst and "Deelnemer 4" in tekst


def test_een_model_dat_faalt_valt_terug_en_dat_staat_in_de_samenvatting():
    def kapot(systeem, gegevens):
        raise LlmFout("uit")
    per, ctx, _ = draai_model(kapot, 3, 7, heiligen=H, vragen=V)
    s = samenvatting("kapot", per)
    assert "0 van 3 bruikbaar" in s and all(not m.door_llm for ms in per for m in ms)


def test_het_rapport_bevat_geen_sleutel_en_het_hulpprogramma_leest_de_omgeving_zoals_de_app(monkeypatch, tmp_path, capsys):
    from durfheilig import modeltest
    monkeypatch.setenv("LLM_BASE_URL", "https://api.example.test/v1")
    monkeypatch.setenv("LLM_API_KEY", "GEHEIMESLEUTEL")
    monkeypatch.setattr(modeltest, "draai_model", lambda llm, n, seed, g=0, **k: draai_model(goede_llm, 2, seed, g, heiligen=H, vragen=V))
    assert modeltest.main(["--model", "model-a", "--n", "2", "--uit", str(tmp_path)]) == 0
    uit = capsys.readouterr().out
    bestanden = list(tmp_path.glob("*model-a.md"))
    assert len(bestanden) == 1 and "model-a" in uit and "api.example.test" in uit
    assert "GEHEIMESLEUTEL" not in uit and "GEHEIMESLEUTEL" not in bestanden[0].read_text()


def test_zonder_aanbieder_stopt_het_met_een_duidelijke_melding(monkeypatch):
    import pytest
    from durfheilig import modeltest
    for k in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "LLM_PROVIDER", "GEMINI_API_KEY", "GEMINI_MODEL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(modeltest, "laad_env", lambda *a, **k: [])
    with pytest.raises(SystemExit, match="Geen aanbieder"):
        modeltest.main(["--model", "x"])


def test_een_voorvoegsel_kiest_de_aanbieder_per_model_en_een_kale_naam_houdt_de_aanbieder_uit_env():
    from durfheilig.modeltest import omgeving_voor
    basis = {"MISTRAL_API_KEY": "a", "SCALEWAY_API_KEY": "b"}
    env, naam = omgeving_voor("scaleway:mistral-small-3.2-24b-instruct-2506", basis)
    assert env["LLM_PROVIDER"] == "scaleway" and env["LLM_MODEL"] == "mistral-small-3.2-24b-instruct-2506" and naam == "mistral-small-3.2-24b-instruct-2506"
    env, _ = omgeving_voor("mistral:mistral-small-latest", {**basis, "LLM_PROVIDER": "scaleway"})
    assert env["LLM_PROVIDER"] == "mistral" and env["LLM_MODEL"] == "mistral-small-latest"
    env, _ = omgeving_voor("gemini:gem-y", basis)
    assert env["LLM_PROVIDER"] == "gemini" and env["GEMINI_MODEL"] == "gem-y"
    env, naam = omgeving_voor("llama-3.3-70b", {**basis, "LLM_PROVIDER": "scaleway"})
    assert env["LLM_MODEL"] == "llama-3.3-70b" and env["LLM_PROVIDER"] == "scaleway" and naam == "llama-3.3-70b"
    env, _ = omgeving_voor("gem-z", {"GEMINI_API_KEY": "k"})
    assert env["GEMINI_MODEL"] == "gem-z"
    env, _ = omgeving_voor("naam:met:dubbele-punten", basis)           # an unknown prefix is part of the model name
    assert "LLM_PROVIDER" not in env and env["GEMINI_MODEL"] == "naam:met:dubbele-punten"


def test_de_modellenlijst_opdracht_toont_alleen_namen(monkeypatch, capsys):
    from durfheilig import modeltest
    monkeypatch.setattr(modeltest, "laad_env", lambda *a, **k: [])
    monkeypatch.setattr(modeltest, "lijst_modellen", lambda aanbieder, env: ["m-1", "m-2"])
    assert modeltest.main(["--modellen", "scaleway"]) == 0
    assert capsys.readouterr().out.split() == ["m-1", "m-2"]
    import pytest
    with pytest.raises(SystemExit, match="minstens"):
        modeltest.main([])


def test_modeltest_draait_zonder_dev_module():
    """The image leaves dev.py out on purpose; the model test must still start there (it did not, once)."""
    import subprocess, sys, textwrap
    code = textwrap.dedent("""
        import sys
        sys.modules['durfheilig.dev'] = None          # importing it raises ImportError, like in the image
        import durfheilig.modeltest
    """)
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0
