"""Reading a `.env` file. Its own module so that both the dev launcher and the model test can use it inside the image, where dev.py is left out."""
import os
from pathlib import Path


def laad_env(pad: str | Path = ".env", env=os.environ) -> list[str]:
    """Lees KEY=waarde-regels uit een .env en zet ze in `env`, behalve wat al gezet is. Geeft de gezette namen terug."""
    pad = Path(pad)
    gezet = []
    if not pad.is_file():
        return gezet
    for regel in pad.read_text(encoding="utf-8").splitlines():
        regel = regel.strip()
        if not regel or regel.startswith("#") or "=" not in regel:
            continue
        naam, waarde = (x.strip() for x in regel.split("=", 1))
        waarde = waarde.strip("\"'")
        if naam and waarde and naam not in env:
            env[naam] = waarde
            gezet.append(naam)
    return gezet
