# Simulatie van de matching

Gegenereerd door `python -m durfheilig.simulatie --seed 2026 --n 200`. Zelfde seed, zelfde rapport.

77 heiligen, 200 fictieve profielen per geslachtsvoorkeur. Profielen beantwoorden elke of-of-vraag 50/50 en kiezen 2 of 3 interesses; dat toetst de spreiding, niet of iemand zich herkent. "Eerste keuze" is plek 1 van de deterministische ranglijst.

**Eindoordeel: niet alle eisen gehaald.**

"Puur toeval" is wat een matching haalt die elke deelnemer een willekeurige heilige geeft, bij hetzelfde aantal profielen. Ligt een eis daaronder, dan is hij bij dit aantal profielen niet te halen door ruis alleen, ook niet met een perfecte matching.

## Eisen uit het plan

| Eis | Uitkomst | Gehaald |
| --- | --- | --- |
| man: geen heilige boven 4% van de eerste keuzes | hoogste: Paus Leo I, 12 van 200 (6.0%); gelijk verdeeld 2.2%, puur toeval haalt 4.5% | ❌ nee |
| man: minstens 60% van de heiligen ooit in een top-3 | 46 van 46 (100%) | ✅ ja |
| man: minstens 5 heiligen per interesse | te weinig: Natuur en dieren (4), Muziek en kunst (4) | ❌ nee |
| man: per as heiligen aan beide kanten | allemaal | ✅ ja |
| vrouw: geen heilige boven 4% van de eerste keuzes | hoogste: Jeanne d'Arc, 18 van 200 (9.0%); gelijk verdeeld 3.2%, puur toeval haalt 6.0% | ❌ nee |
| vrouw: minstens 60% van de heiligen ooit in een top-3 | 31 van 31 (100%) | ✅ ja |
| vrouw: minstens 5 heiligen per interesse | te weinig: Natuur en dieren (3), Techniek, bouwen en computers (0), Sport en buiten bewegen (1), Wetenschap en ontdekken (3) | ❌ nee |
| vrouw: per as heiligen aan beide kanten | allemaal | ✅ ja |
| maakt niet uit: geen heilige boven 4% van de eerste keuzes | hoogste: Bernadette Soubirous, 12 van 200 (6.0%); gelijk verdeeld 1.3%, puur toeval haalt 3.0% | ❌ nee |
| maakt niet uit: minstens 60% van de heiligen ooit in een top-3 | 76 van 77 (99%) | ✅ ja |
| maakt niet uit: minstens 5 heiligen per interesse | allemaal | ✅ ja |
| maakt niet uit: per as heiligen aan beide kanten | allemaal | ✅ ja |

## Heiligen die nooit in een top-3 komen

- **man** (0): geen
- **vrouw** (0): geen
- **maakt niet uit** (1): Columba van Iona

## Per heilige

Aantal keer eerste keuze en aantal keer in de top-3, per geslachtsvoorkeur. Gesorteerd op totaal aantal top-3-plekken.

| Heilige | Geslacht | Bekende assen | man: 1e / top-3 | vrouw: 1e / top-3 | maakt niet uit: 1e / top-3 |
| --- | --- | --- | --- | --- | --- |
| Bernadette Soubirous | vrouwelijk | 5 | – | 17 / 39 | 12 / 32 |
| Jeanne d'Arc | vrouwelijk | 6 | – | 18 / 34 | 5 / 15 |
| Paus Leo I | mannelijk | 4 | 12 / 26 | – | 12 / 23 |
| Margaretha-Maria Alacoque | vrouwelijk | 5 | – | 14 / 29 | 7 / 19 |
| Liduina van Schiedam | vrouwelijk | 4 | – | 10 / 33 | 9 / 14 |
| Kateri Tekakwitha | vrouwelijk | 6 | – | 7 / 24 | 12 / 22 |
| Alphonsa van de Onbevlekte Ontvangenis | vrouwelijk | 4 | – | 11 / 28 | 3 / 14 |
| Ladislaus I van Hongarije | mannelijk | 4 | 8 / 29 | – | 3 / 13 |
| Theresia van Lisieux | vrouwelijk | 6 | – | 4 / 24 | 6 / 17 |
| Petrus | mannelijk | 4 | 4 / 25 | – | 5 / 13 |
| Stefanus I van Hongarije | mannelijk | 4 | 10 / 25 | – | 4 / 13 |
| Monica van Tagaste | vrouwelijk | 4 | – | 10 / 22 | 5 / 15 |
| Beda | mannelijk | 5 | 11 / 26 | – | 2 / 10 |
| Rita van Cascia | vrouwelijk | 4 | – | 5 / 23 | 4 / 12 |
| Antonius van Egypte | mannelijk | 4 | 8 / 24 | – | 1 / 8 |
| Elisabeth van Aragón | vrouwelijk | 4 | – | 6 / 23 | 3 / 9 |
| Filippus Neri | mannelijk | 6 | 12 / 24 | – | 3 / 7 |
| Josephine Bakhita | vrouwelijk | 6 | – | 3 / 23 | 3 / 8 |
| Pater Pio | mannelijk | 5 | 8 / 21 | – | 4 / 10 |
| Jozefmaria Escrivá | mannelijk | 4 | 6 / 19 | – | 4 / 11 |
| Rosa van Lima | vrouwelijk | 4 | – | 7 / 23 | 1 / 7 |
| Marianne Cope | vrouwelijk | 4 | – | 9 / 21 | 2 / 7 |
| Augustinus van Canterbury | mannelijk | 4 | 2 / 11 | – | 4 / 16 |
| Franciscus Xaverius | mannelijk | 5 | 1 / 17 | – | 2 / 10 |
| Carlo Acutis | mannelijk | 6 | 9 / 19 | – | 1 / 7 |
| Clara van Assisi | vrouwelijk | 5 | – | 5 / 19 | 2 / 7 |
| Isidorus van Sevilla | mannelijk | 5 | 9 / 20 | – | 1 / 6 |
| Ursula van Keulen | vrouwelijk | 4 | – | 6 / 17 | 4 / 9 |
| Rochus van Montpellier | mannelijk | 4 | 5 / 16 | – | 2 / 9 |
| Theresia van Ávila | vrouwelijk | 6 | – | 7 / 21 | 1 / 4 |
| Elisabeth van Thüringen | vrouwelijk | 6 | – | 7 / 18 | 2 / 6 |
| Charles de Foucauld | mannelijk | 6 | 7 / 16 | – | 1 / 7 |
| Pier Giorgio Frassati | mannelijk | 6 | 6 / 15 | – | 2 / 8 |
| Angela Merici | vrouwelijk | 5 | – | 6 / 14 | 2 / 8 |
| Catharina van Bologna | vrouwelijk | 5 | – | 6 / 15 | 4 / 7 |
| Genoveva van Parijs | vrouwelijk | 5 | – | 7 / 18 | 2 / 4 |
| Willibrord | mannelijk | 6 | 4 / 12 | – | 1 / 10 |
| Birgitta van Zweden | vrouwelijk | 6 | – | 5 / 15 | 2 / 6 |
| Edith Stein | vrouwelijk | 6 | – | 2 / 13 | 3 / 8 |
| Franciscus van Assisi | mannelijk | 6 | 7 / 15 | – | 3 / 6 |
| Gertrudis van Helfta | vrouwelijk | 5 | – | 6 / 15 | 2 / 6 |
| Hildegard van Bingen | vrouwelijk | 6 | – | 4 / 17 | 1 / 2 |
| Ignatius van Loyola | mannelijk | 6 | 7 / 13 | – | 3 / 6 |
| Johanna van Valois | vrouwelijk | 4 | – | 4 / 13 | 1 / 6 |
| Maria Faustina Kowalska | vrouwelijk | 4 | – | 3 / 13 | 2 / 6 |
| Paus Johannes Paulus II | mannelijk | 6 | 3 / 13 | – | 4 / 6 |
| Alfonsus van Liguori | mannelijk | 6 | 8 / 14 | – | 0 / 4 |
| Ambrosius van Milaan | mannelijk | 5 | 6 / 13 | – | 0 / 5 |
| Giovanni Bosco | mannelijk | 6 | 4 / 13 | – | 3 / 5 |
| Keizer Hendrik II de Heilige | mannelijk | 4 | 4 / 11 | – | 3 / 7 |
| Maria MacKillop | vrouwelijk | 5 | – | 2 / 12 | 1 / 6 |
| Bonifatius | mannelijk | 5 | 0 / 8 | – | 3 / 9 |
| Johannes van het Kruis | mannelijk | 6 | 4 / 11 | – | 3 / 6 |
| Martinus van Tours | mannelijk | 5 | 3 / 14 | – | 1 / 3 |
| Moeder Teresa | vrouwelijk | 5 | – | 2 / 13 | 0 / 3 |
| Paus Johannes XXIII | mannelijk | 6 | 0 / 9 | – | 2 / 7 |
| Radegundis | vrouwelijk | 4 | – | 5 / 6 | 2 / 9 |
| Thomas More | mannelijk | 6 | 0 / 6 | – | 4 / 9 |
| Thomas van Aquino | mannelijk | 6 | 2 / 11 | – | 1 / 4 |
| Gregorius van Tours | mannelijk | 5 | 2 / 7 | – | 3 / 7 |
| Óscar Romero | mannelijk | 6 | 2 / 11 | – | 0 / 3 |
| Albertus Magnus | mannelijk | 6 | 5 / 11 | – | 1 / 2 |
| Maximiliaan Kolbe | mannelijk | 5 | 4 / 8 | – | 1 / 5 |
| Nicolaas van Myra | mannelijk | 4 | 3 / 10 | – | 0 / 3 |
| Titus Brandsma | mannelijk | 6 | 3 / 7 | – | 2 / 5 |
| Elizabeth Ann Seton | vrouwelijk | 4 | – | 0 / 7 | 0 / 4 |
| Hiëronymus van Stridon | mannelijk | 6 | 2 / 7 | – | 2 / 4 |
| Catharina van Siena | vrouwelijk | 6 | – | 2 / 8 | 0 / 2 |
| Paus Paulus VI | mannelijk | 6 | 4 / 6 | – | 2 / 4 |
| Anselmus van Canterbury | mannelijk | 6 | 0 / 5 | – | 0 / 3 |
| Augustinus van Hippo | mannelijk | 6 | 1 / 6 | – | 1 / 2 |
| Columba van Iona | mannelijk | 5 | 1 / 8 | – | 0 / 0 |
| Lodewijk IX van Frankrijk | mannelijk | 5 | 0 / 5 | – | 0 / 2 |
| Pater Damiaan | mannelijk | 5 | 0 / 4 | – | 1 / 3 |
| Paus Gregorius I | mannelijk | 5 | 1 / 4 | – | 2 / 3 |
| Thomas Becket | mannelijk | 6 | 1 / 4 | – | 0 / 1 |
| Liudger | mannelijk | 5 | 1 / 1 | – | 0 / 1 |

## De set, per geslachtsvoorkeur

| Interesse | man | vrouw | maakt niet uit |
| --- | --- | --- | --- |
| Mensen helpen | 19 | 14 | 33 |
| Kinderen en jongeren | 5 | 11 | 16 |
| Natuur en dieren | 4 | 3 | 7 |
| Muziek en kunst | 4 | 7 | 11 |
| Techniek, bouwen en computers | 5 | 0 | 5 |
| Lezen en schrijven | 17 | 12 | 29 |
| Sport en buiten bewegen | 6 | 1 | 7 |
| Reizen en andere culturen | 17 | 6 | 23 |
| Wetenschap en ontdekken | 7 | 3 | 10 |
| Opkomen voor wat eerlijk is | 10 | 6 | 16 |

Per as: aantal heiligen aan de min-kant / plus-kant.

| As | man | vrouw | maakt niet uit |
| --- | --- | --- | --- |
| samen_alleen | 6 / 21 | 11 / 13 | 17 / 34 |
| denken_doen | 13 / 22 | 5 / 14 | 18 / 36 |
| achter_voorop | 9 / 31 | 15 / 15 | 24 / 46 |
| plek_pad | 8 / 33 | 14 / 13 | 22 / 46 |
| diepgang_licht | 22 / 3 | 18 / 1 | 40 / 4 |
| vrede_strijd | 10 / 26 | 3 / 17 | 13 / 43 |
