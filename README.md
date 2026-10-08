# Durf heilig te zijn

Een welkomstspel voor een katholieke jongerengroep: elke deelnemer doet thuis een quiz en kiest een heilige die bij hem of haar past, en op de middag raadt de groep samen wie bij welke heilige hoort.

Het ontwerp staat in `docs/design/plan-heiligen-welkomstspel.md`, de rubric in `docs/design/rubric.md`, en de stand van het werk in `ISA.md`.

## Fase 3: vragen, scoring en simulatie

```bash
uv sync
uv run pytest                          # tests
uv run python -m durfheilig.speel      # speel de quiz zelf in de terminal
uv run python -m durfheilig.simulatie  # schrijft docs/simulatie/rapport.md
```

## Lokaal proberen met de webapp

```bash
uv sync                      # op de Mac maakt uv de lock zelf tegen PyPI
uv run python -m durfheilig.dev
```

Open http://127.0.0.1:8000/dev en kies wie je bent: `kind1` tot `kind4`, of `leiding1` (ziet `/beheer`).
Het kiezen is een cookie, dus gebruik per kind een eigen privévenster of browser. Dit startje
luistert alleen op je eigen computer en staat niet in de Docker-image: in productie komt de
identiteit van Authelia.

Zonder sleutel gebruikt de app de vaste terugval (geen persoonlijke uitleg). Gemini proberen:

```bash
export GEMINI_API_KEY=...    # je eigen sleutel, nooit in een bestand in de repo
export GEMINI_MODEL=...
uv run python -m durfheilig.dev
```

De spelstatus staat in `data/spel-dev.db` (genegeerd door git). Weg ermee voor een schone start.
