# Rubric

Status: vastgesteld door Jelle op 2026-10-06. Vervangt de rubric met 12 dimensies uit de eerste versie van het plan.

## Kern

**Van 12 losse dimensies naar twee lagen: 6 karakterassen met twee kanten, plus een handvol interesses.** Elke as heeft twee polen die allebei goed zijn ("liever samen" of "liever alleen"), zodat er geen flatteus antwoord bestaat. Dat past precies bij de of-of-vragen die we al gekozen hebben: één of-of-vraag meet één as.

## Waarom de eerste rubric niet werkte

Vier problemen, de eerste drie uit de RedTeam (`redteam-2026-10-06.md`, bevinding 5), de vierde daaruit afgeleid:

1. **Te weinig vragen per dimensie.** 8 basisvragen over 12 dimensies is minder dan één vraag per dimensie. Het profiel zegt dan vooral iets over welke vragen toevallig gekozen zijn.
2. **Sociaal wenselijk antwoorden.** "Leiden", "Moed", "Doorzetten" en "Zorgen voor anderen" zijn eigenschappen die iedereen wil hebben. Een tiener kiest ze vaker dan ze bij hem of haar passen, en dan winnen steeds dezelfde heiligen.
3. **Overlap.** "Opkomen voor wat eerlijk is", "Moed om anders te zijn" en "Doorzetten" meten grotendeels hetzelfde. Een tiener die daar hoog scoort, telt drie keer mee.
4. **Dimensies waarop elke heilige hoog scoort, onderscheiden niets.** Vrijwel elke heilige zette door en zorgde voor anderen. Zo'n dimensie voegt ruis toe en geen informatie.

Daarnaast: een heilige met een kort Wikipedia-artikel kreeg daar een 0 op alles wat er niet in staat. Dat is "niet bekend", niet "niet aanwezig".

## Laag 1: zes karakterassen

Elke as loopt van −2 tot +2. Een heilige mag op een as `onbekend` zijn; die as telt dan voor die heilige niet mee.

| As | Pool − | Pool + | Komt uit (oude dimensies) | Heilige aan de −kant | Heilige aan de +kant |
| --- | --- | --- | --- | --- | --- |
| **Samen ↔ alleen** | rust, eigen wereld, een paar goede vrienden | energie van mensen, midden in de groep | Mensen opzoeken, Rust en binnenwereld | Thérèse van Lisieux | Filippus Neri |
| **Denken ↔ doen** | eerst nadenken, leren, uitzoeken | meteen aanpakken, met je handen | Nadenken en leren | Edith Stein | Martinus |
| **Achter de schermen ↔ voorop** | zorgen dat het af komt, dienen | de leiding nemen, organiseren | Leiden en organiseren | Josephine Bakhita | Don Bosco |
| **Vaste plek ↔ op pad** | trouw aan één plek, wortels | reizen, nieuwe dingen proberen | Avontuur | Clara | Willibrord |
| **Diepgang ↔ lichtheid** | doorvragen, ernst, nadenken over grote vragen | humor, anderen aan het lachen maken | Humor en lichtheid | Edith Stein | Filippus Neri |
| **Vrede ↔ strijd** | verzoenen, geduld, het goedmaken | opkomen, er iets van zeggen, tegen de stroom in | Opkomen voor wat eerlijk is, Moed om anders te zijn | Franciscus | Jeanne d'Arc |

De voorbeeldheiligen zijn mijn eigen inschatting, ter illustratie. In de pijplijn komt elke score uit de bron, met onderbouwing, en jij leest ze na.

**Waarom beide polen goed zijn telt.** "Vaste plek" is geen gebrek aan avontuur: trouw aan één plek is een klassieke kloosterwaarde (Benedictus' *stabilitas*), en Clara bleef haar hele leven in San Damiano. "Vrede" is geen gebrek aan moed: Franciscus ging ongewapend naar de sultan. Zo kan elke tiener zich in elke pool herkennen zonder dat het minder klinkt.

## Laag 2: interesses

Concrete dingen die een tiener graag doet, en waarin een heilige herkenbaar is. Hier zit het "verrassen" uit het plan: Carlo Acutis bouwde websites, en dat herkent een gamer meteen. De jongere kiest er 2 of 3. Een heilige krijgt er 1 tot 3.

| Interesse | Bijvoorbeeld |
| --- | --- |
| Mensen helpen | Moeder Teresa, Martinus |
| Kinderen en jongeren | Don Bosco |
| Natuur en dieren | Franciscus, Kateri Tekakwitha |
| Muziek en kunst | Hildegard van Bingen |
| Techniek, bouwen en computers | Carlo Acutis |
| Lezen en schrijven | Titus Brandsma (journalist), Thérèse |
| Sport en buiten bewegen | Pier Giorgio Frassati (bergbeklimmer) |
| Reizen en andere culturen | Willibrord, Liudger |
| Wetenschap en ontdekken | Hildegard van Bingen |
| Opkomen voor wat eerlijk is | Óscar Romero, Thomas More |

"Zorgen voor anderen" en "Doorzetten" verdwijnen als dimensie. Zorg komt terug als de concrete interesse "Mensen helpen", en doorzetten hoort bij het veld `waarom_voorbeeld`: het is wat elke heilige deed, niet wat de ene van de andere onderscheidt.

## Vragen

**12 of-of-vragen, twee per as**, plus één interessevraag ("kies er 2 of 3"). Een of-of-vraag met twee icoontjes kost een paar seconden, dus 12 vragen passen ruim in het tijdsbudget van 7 minuten. Daarna volgen nog steeds de 3 vervolgvragen van de LLM, gericht op de assen waar de top-12 het meest verschilt.

Voorbeelden (concreet, je-vorm, beide antwoorden klinken goed):

| As | Vraag | Antwoord − | Antwoord + |
| --- | --- | --- | --- |
| Samen ↔ alleen | Na een drukke schooldag wil je… | even je eigen ding doen | afspreken met vrienden |
| Samen ↔ alleen | Op kamp ben jij… | met één of twee goede vrienden | midden in de groep |
| Denken ↔ doen | Een nieuwe kast in elkaar zetten: | eerst de handleiding | meteen beginnen |
| Achter de schermen ↔ voorop | Bij een toneelstuk sta je liever… | achter de schermen: licht, decor | op het podium |
| Vaste plek ↔ op pad | Vakantie: | terug naar je favoriete plek | elke keer ergens nieuw |
| Diepgang ↔ lichtheid | In een groep ben jij vaker… | degene die doorvraagt | degene die de grap maakt |
| Vrede ↔ strijd | Ruzie in de groep. Jij… | probeert het weer goed te maken | zegt eerlijk wat je ervan vindt |

Twee vragen per as geven een score van −2, 0 of +2. De vervolgvragen verfijnen dat.

## Matching

We gebruiken geen cosinusgelijkenis maar een gewone afstand per as, omdat die beter werkt met `onbekend` en met assen die door nul lopen:

- **Assen:** gemiddelde over de assen waarop de heilige bekend is van `1 − |jongere − heilige| / 4`. Uitkomst tussen 0 en 1.
- **Interesses:** aantal gedeelde interesses gedeeld door het aantal interesses van de heilige (maximaal 3).
- **Totaal:** 0,7 × assen + 0,3 × interesses. De gewichten stellen we bij in de simulatie.
- **Drempel:** een heilige doet alleen mee als hij of zij op minstens 4 van de 6 assen bekend is. Anders gaat het record terug voor aanvulling.

Het geslachtsfilter blijft vóór de matching.

**Bonus voor de onthulling:** omdat elke as een naam heeft, kan de uitleg concreet zijn: "jij en Clara houden allebei van een vaste plek en van rust; wat Clara bijzonder maakt is…". Dat sluit aan op het veld `waarom_voorbeeld`.

## Besluiten

- **Zes assen.** Ook "Diepgang ↔ lichtheid" blijft: humor is juist wat tieners in een heilige verrast.
- **Geen middenknop.** Een gedwongen keuze geeft meer informatie; twee vragen per as vangen het midden al op (score 0).
- **Tien interesses.** De lijst van negen kreeg op 2026-10-07 een tiende: "Opkomen voor wat eerlijk is". Die kwam naar voren bij het maken van de heiligenprofielen (fase 2), waar hij bij 16 van de 77 heiligen past.

## Gevolgen voor de rest van het plan

- **Heiligenrecord:** `assen` (zes velden, −2 tot +2 of `null`), per as een korte onderbouwing uit de bron, en `interesses` (1 tot 3 uit de vaste lijst). Vervangt de 12 rubricscores.
- **Vragenbank:** circa 24 of-of-vragen (vier per as), waaruit de app er twee per as kiest, plus de interessevraag.
- **Simulatie:** dezelfde eisen (geen heilige boven 4%, minstens 60% ooit in een top-3), plus per interesse minstens 5 heiligen in de set, en per as heiligen aan beide kanten.
- **Validatie met echte mensen:** de generale repetitie met familie en vrienden. Iedereen beoordeelt zijn top-3 met "klopt" of "klopt niet". Dat is de eerste echte toets; de simulatie toetst alleen de spreiding.
