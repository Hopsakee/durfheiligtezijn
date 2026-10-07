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
