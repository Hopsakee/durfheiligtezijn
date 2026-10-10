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
cp .env.example .env         # vul GEMINI_API_KEY en GEMINI_MODEL in; .env staat in .gitignore
uv run python -m durfheilig.dev
```

De spelstatus staat in `data/spel-dev.db` (genegeerd door git). Weg ermee voor een schone start.

### Het raadspel proberen met telefoons en een tv

```bash
uv run python -m durfheilig.dev --schoon --dummies 12 --lan
```

`--dummies 12` maakt 12 nepdeelnemers die de quiz al gedaan hebben (zonder taalmodel). `--lan` laat de app op je
netwerk luisteren; de terminal toont het adres en de firewallopdrachten. Daarna:

1. Leider en tv in je gewone browser: kies `leiding1`, start het spel op `/beheer/spel`, open `/beheer/tv` op de tv.
2. Telefoon: open het adres uit de terminal, tik een `dummy…` aan (niet de deelnemer van de ronde) en stem door op een heilige te tikken.
3. Zonder telefoon: de knop "Laat de dummies stemmen" op `/dev`.
4. Time-out op de telefoon? Dan blokkeert de firewall van je computer de poort. Open hem tijdelijk (`sudo ufw allow from <netwerk>/24 to any port 8000 proto tcp`, de terminal toont de exacte regel) en sluit hem als je klaar bent (zelfde opdracht met `delete`).
5. Alleen spelers stemmen: een leider is geen speler, en de deelnemer van de ronde stemt niet.

Met `--lan` kan iedereen op het netwerk zich als elke persoon voordoen, ook als begeleider. Gebruik het alleen thuis.

## Een taalmodel kiezen

```bash
uv run python -m durfheilig.modeltest --model <modelnaam> --model <nog een> --n 6 --gelijktijdig 12
```

Speelt de echte prompts op verzonnen deelnemers (geen kinderen), meet de snelheid en controleert het grofste (ongeldige JSON, Engels,
markdown, verzonnen jaartallen). De aanbieder komt uit `.env` (zie `.env.example`). De volledige teksten komen in `modeltest/`; lees ze,
want warm en kloppend klinken beoordeel je met je ogen.
