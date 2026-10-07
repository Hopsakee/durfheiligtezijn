from durfheilig.data import laad_heiligen, laad_vragen
from durfheilig.simulatie import rapport


def test_zelfde_seed_zelfde_rapport():
    h, v = laad_heiligen(), laad_vragen()
    assert rapport(7, 40, h, v) == rapport(7, 40, h, v)


def test_rapport_noemt_elke_eis():
    tekst, _ = rapport(7, 40, laad_heiligen(), laad_vragen())
    for eis in ("man: geen heilige boven", "vrouw: geen heilige boven", "maakt niet uit: geen heilige boven",
                "man: minstens 60%", "vrouw: minstens 60%", "maakt niet uit: minstens 60%",
                "heiligen per interesse", "beide kanten"):
        assert eis in tekst, eis
