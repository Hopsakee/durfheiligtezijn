# Prompt voor claude.ai: heiligen aanvullen

Gebruik: open in claude.ai het gesprek waarin de heiligenprofielen gemaakt zijn (of een nieuw gesprek), voeg `data/heiligen.json` en `data/heiligen-uitgevallen.json` uit deze repo toe als bijlage, en plak de tekst hieronder. De uitkomst gaat als JSON terug naar de repo en wordt daar gecontroleerd door `uv run pytest` en `uv run python -m durfheilig.simulatie`.

Waarom: de simulatie (`docs/simulatie/rapport.md`) laat zien dat de set per geslacht te weinig heiligen heeft bij een paar interesses. Wie "vrouw" kiest en techniek of sport leuk vindt, krijgt nu nooit een heilige die daar iets mee heeft.

---

Je helpt mij de set heiligen voor een welkomstspel voor 13-jarigen aan te vullen. In de bijlage staan `heiligen.json` (77 heiligen) en `heiligen-uitgevallen.json` (22 heiligen die afvielen omdat ze op minder dan 4 van de 6 karakterassen bekend waren). Volg de `stijlregels` uit `heiligen.json` precies, en gebruik exact hetzelfde recordformaat, met alle velden.

**Wat er tekortkomt** (minimaal 5 heiligen per interesse, per geslacht):

| Interesse | Vrouwen nu | Mannen nu |
| --- | --- | --- |
| Techniek, bouwen en computers | 0 | 5 |
| Sport en buiten bewegen | 1 | 6 |
| Natuur en dieren | 3 | 4 |
| Wetenschap en ontdekken | 3 | 7 |
| Muziek en kunst | 7 | 4 |

**Opdracht:**

1. **Nieuwe heiligen.** Zoek heiligverklaarde vrouwen (en voor natuur en muziek ook mannen) bij wie de interesse echt uit het nl- of en-Wikipedia-artikel blijkt, niet uit een patronaat alleen. Ideeën om te controleren, niet om aan te nemen: Gianna Beretta Molla (arts, skiën, bergbeklimmen), Teresa van de Andes (paardrijden, zwemmen), Frances Xavier Cabrini (bouwde ziekenhuizen en scholen), Katharine Drexel (bouwde scholen), Isidorus de Landbouwer, Hubertus. Maak voor elke nieuwe heilige een volledig record, inclusief een afbeelding van Commons met maker en licentie (`afbeelding.soort`: `heilige`, of `tijd_en_streek` als er geen afbeelding van de heilige zelf is).
2. **Bestaande heiligen.** Controleer bij de heiligen in `heiligen.json` of een van de tekort-interesses ontbreekt terwijl de bron het duidelijk steunt. Een heilige heeft maximaal 3 interesses.
3. **Uitgevallen heiligen.** Barbara van Nicomedië, Theodelinde en Maria Mazzarello hebben al "Techniek, bouwen en computers". Kijk of de bron genoeg zegt om ze op minstens 4 van de 6 assen te scoren. Zo ja, vul de assen aan met onderbouwing en zet ze in de nieuwe set. Zo nee, laat ze uitgevallen.
4. **Scores.** Elke asscore van −2 tot +2 krijgt een onderbouwing uit de bron; als de bron er niets over zegt, is de score `null`. Let op de tekenconventie: bij `samen_alleen` is −2 "alleen" en +2 "samen"; bij de andere assen is −2 het eerste woord (denken, achter de schermen, vaste plek, diepgang, vrede).

**Lever op:** één bestand `heiligen-aanvulling.json` met drie lijsten: `nieuw` (volledige nieuwe records), `interesses_aangepast` (qid, naam, nieuwe interesses, onderbouwing per toegevoegde interesse) en `uit_uitgevallen` (volledige records). Geef daarnaast een korte lijst van wat je niet hebt kunnen onderbouwen.
