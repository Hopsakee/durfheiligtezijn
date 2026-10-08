# Simulatie van de matching

Gegenereerd door `python -m durfheilig.simulatie --seed 2026 --n 200`. Zelfde seed, zelfde rapport.

89 heiligen, 200 fictieve profielen per geslachtsvoorkeur. Profielen beantwoorden elke of-of-vraag 50/50 en kiezen 2 of 3 interesses; dat toetst de spreiding, niet of iemand zich herkent. "Eerste keuze" is plek 1 van de deterministische ranglijst.

**Eindoordeel: niet alle eisen gehaald.**

"Puur toeval" is wat een matching haalt die elke deelnemer een willekeurige heilige geeft, bij hetzelfde aantal profielen. Ligt een eis daaronder, dan is hij bij dit aantal profielen niet te halen door ruis alleen, ook niet met een perfecte matching.

## Eisen uit het plan

| Eis | Uitkomst | Gehaald |
| --- | --- | --- |
| man: geen heilige boven 4% van de eerste keuzes | hoogste: Isidorus van Madrid, 12 van 200 (6.0%); gelijk verdeeld 2.0%, puur toeval haalt 4.5% | ❌ nee |
| man: minstens 60% van de heiligen ooit in een top-3 | 49 van 49 (100%) | ✅ ja |
| man: minstens 5 heiligen per interesse | allemaal | ✅ ja |
| man: per as heiligen aan beide kanten | allemaal | ✅ ja |
| vrouw: geen heilige boven 4% van de eerste keuzes | hoogste: Germaine Cousin, 13 van 200 (6.5%); gelijk verdeeld 2.5%, puur toeval haalt 5.5% | ❌ nee |
| vrouw: minstens 60% van de heiligen ooit in een top-3 | 40 van 40 (100%) | ✅ ja |
| vrouw: minstens 5 heiligen per interesse | te weinig: Sport en buiten bewegen (4) | ❌ nee |
| vrouw: per as heiligen aan beide kanten | allemaal | ✅ ja |
| maakt niet uit: geen heilige boven 4% van de eerste keuzes | hoogste: Paus Leo I, 12 van 200 (6.0%); gelijk verdeeld 1.1%, puur toeval haalt 3.0% | ❌ nee |
| maakt niet uit: minstens 60% van de heiligen ooit in een top-3 | 88 van 89 (99%) | ✅ ja |
| maakt niet uit: minstens 5 heiligen per interesse | allemaal | ✅ ja |
| maakt niet uit: per as heiligen aan beide kanten | allemaal | ✅ ja |

## Heiligen die nooit in een top-3 komen

- **man** (0): geen
- **vrouw** (0): geen
- **maakt niet uit** (1): Francisca Xaveria Cabrini

## Per heilige

Aantal keer eerste keuze en aantal keer in de top-3, per geslachtsvoorkeur. Gesorteerd op totaal aantal top-3-plekken.

| Heilige | Geslacht | Bekende assen | man: 1e / top-3 | vrouw: 1e / top-3 | maakt niet uit: 1e / top-3 |
| --- | --- | --- | --- | --- | --- |
| Bernadette Soubirous | vrouwelijk | 5 | – | 9 / 28 | 11 / 23 |
| Paus Leo I | mannelijk | 4 | 11 / 25 | – | 12 / 21 |
| Margaretha-Maria Alacoque | vrouwelijk | 5 | – | 9 / 25 | 6 / 15 |
| Alphonsa van de Onbevlekte Ontvangenis | vrouwelijk | 4 | – | 9 / 26 | 3 / 12 |
| Theresia van Lisieux | vrouwelijk | 6 | – | 4 / 21 | 6 / 17 |
| Isidorus van Madrid | mannelijk | 4 | 12 / 26 | – | 3 / 11 |
| Teresa van Los Andes | vrouwelijk | 4 | – | 12 / 26 | 2 / 11 |
| Kateri Tekakwitha | vrouwelijk | 6 | – | 7 / 17 | 12 / 19 |
| Petrus | mannelijk | 4 | 2 / 24 | – | 4 / 10 |
| Stefanus I van Hongarije | mannelijk | 4 | 10 / 24 | – | 1 / 10 |
| Ladislaus I van Hongarije | mannelijk | 4 | 7 / 25 | – | 0 / 8 |
| Liduina van Schiedam | vrouwelijk | 4 | – | 4 / 20 | 8 / 12 |
| Monica van Tagaste | vrouwelijk | 4 | – | 9 / 18 | 5 / 14 |
| Beda | mannelijk | 5 | 10 / 20 | – | 2 / 11 |
| Jeanne d'Arc | vrouwelijk | 6 | – | 12 / 22 | 4 / 9 |
| Pater Pio | mannelijk | 5 | 6 / 19 | – | 4 / 9 |
| Jozefmaria Escrivá | mannelijk | 4 | 6 / 18 | – | 3 / 9 |
| Elisabeth van Aragón | vrouwelijk | 4 | – | 5 / 18 | 3 / 8 |
| Rita van Cascia | vrouwelijk | 4 | – | 3 / 15 | 3 / 11 |
| Augustinus van Canterbury | mannelijk | 4 | 2 / 10 | – | 4 / 15 |
| Franciscus Xaverius | mannelijk | 5 | 1 / 16 | – | 1 / 9 |
| Maria Faustina Kowalska | vrouwelijk | 4 | – | 0 / 12 | 4 / 13 |
| Theresia van Ávila | vrouwelijk | 6 | – | 6 / 21 | 0 / 4 |
| Clara van Assisi | vrouwelijk | 5 | – | 5 / 17 | 2 / 7 |
| Genoveva van Parijs | vrouwelijk | 5 | – | 5 / 18 | 0 / 6 |
| Germaine Cousin | vrouwelijk | 5 | – | 13 / 17 | 1 / 7 |
| Marianne Cope | vrouwelijk | 4 | – | 4 / 16 | 4 / 8 |
| Antonius van Egypte | mannelijk | 4 | 5 / 17 | – | 1 / 6 |
| Filippus Neri | mannelijk | 6 | 11 / 18 | – | 3 / 5 |
| Isidorus van Sevilla | mannelijk | 5 | 7 / 20 | – | 1 / 3 |
| Pier Giorgio Frassati | mannelijk | 6 | 6 / 14 | – | 1 / 9 |
| Rosa van Lima | vrouwelijk | 4 | – | 1 / 15 | 1 / 7 |
| Ursula van Keulen | vrouwelijk | 4 | – | 3 / 13 | 4 / 9 |
| Willibrord | mannelijk | 6 | 4 / 12 | – | 1 / 10 |
| Carlo Acutis | mannelijk | 6 | 8 / 16 | – | 1 / 5 |
| Clothilde | vrouwelijk | 6 | – | 9 / 18 | 0 / 3 |
| Gianna Beretta Molla | vrouwelijk | 4 | – | 7 / 16 | 3 / 5 |
| Rochus van Montpellier | mannelijk | 4 | 4 / 11 | – | 2 / 10 |
| Charles de Foucauld | mannelijk | 6 | 7 / 15 | – | 1 / 5 |
| Elisabeth van Thüringen | vrouwelijk | 6 | – | 3 / 14 | 3 / 6 |
| Josephine Bakhita | vrouwelijk | 6 | – | 3 / 14 | 3 / 6 |
| Edith Stein | vrouwelijk | 6 | – | 1 / 12 | 3 / 7 |
| Franciscus van Assisi | mannelijk | 6 | 6 / 15 | – | 3 / 4 |
| Hubertus van Luik | mannelijk | 4 | 5 / 13 | – | 4 / 6 |
| Catharina van Bologna | vrouwelijk | 5 | – | 6 / 12 | 3 / 6 |
| Francisca Xaveria Cabrini | vrouwelijk | 5 | – | 8 / 18 | 0 / 0 |
| Giovanni Bosco | mannelijk | 6 | 4 / 13 | – | 2 / 5 |
| Ignatius van Loyola | mannelijk | 6 | 7 / 12 | – | 3 / 6 |
| Keizer Hendrik II de Heilige | mannelijk | 4 | 4 / 11 | – | 2 / 7 |
| Paus Johannes Paulus II | mannelijk | 6 | 3 / 12 | – | 3 / 6 |
| Ambrosius van Milaan | mannelijk | 5 | 5 / 12 | – | 0 / 5 |
| Birgitta van Zweden | vrouwelijk | 6 | – | 5 / 14 | 0 / 3 |
| Gertrudis van Helfta | vrouwelijk | 5 | – | 4 / 11 | 2 / 6 |
| Gregorius van Tours | mannelijk | 5 | 3 / 10 | – | 2 / 7 |
| Johanna van Valois | vrouwelijk | 4 | – | 4 / 12 | 1 / 5 |
| Martinus van Tours | mannelijk | 5 | 2 / 14 | – | 1 / 3 |
| Angela Merici | vrouwelijk | 5 | – | 4 / 9 | 1 / 7 |
| Bonifatius | mannelijk | 5 | 0 / 7 | – | 3 / 9 |
| Dunstan | mannelijk | 5 | 2 / 11 | – | 3 / 5 |
| Margaretha van Schotland | vrouwelijk | 6 | – | 1 / 9 | 0 / 7 |
| Elizabeth Ann Seton | vrouwelijk | 4 | – | 3 / 9 | 3 / 6 |
| Johannes van het Kruis | mannelijk | 6 | 4 / 9 | – | 3 / 6 |
| Maria MacKillop | vrouwelijk | 5 | – | 4 / 10 | 3 / 5 |
| Maria Mazzarello | vrouwelijk | 4 | – | 3 / 10 | 3 / 5 |
| Paus Johannes XXIII | mannelijk | 6 | 0 / 8 | – | 1 / 7 |
| Alfonsus van Liguori | mannelijk | 6 | 8 / 12 | – | 0 / 2 |
| Hedwig van Polen | vrouwelijk | 5 | – | 7 / 11 | 3 / 3 |
| Thomas More | mannelijk | 6 | 0 / 5 | – | 4 / 8 |
| Óscar Romero | mannelijk | 6 | 2 / 10 | – | 0 / 3 |
| Albertus Magnus | mannelijk | 6 | 4 / 10 | – | 0 / 2 |
| Catharina van Alexandrië | vrouwelijk | 4 | – | 1 / 9 | 1 / 3 |
| Hildegard van Bingen | vrouwelijk | 6 | – | 2 / 11 | 1 / 1 |
| Maximiliaan Kolbe | mannelijk | 5 | 3 / 7 | – | 2 / 5 |
| Radegundis | vrouwelijk | 4 | – | 4 / 5 | 1 / 7 |
| Thomas van Aquino | mannelijk | 6 | 3 / 8 | – | 0 / 4 |
| Augustinus van Hippo | mannelijk | 6 | 1 / 8 | – | 1 / 3 |
| Hiëronymus van Stridon | mannelijk | 6 | 2 / 7 | – | 2 / 4 |
| Nicolaas van Myra | mannelijk | 4 | 2 / 10 | – | 0 / 1 |
| Titus Brandsma | mannelijk | 6 | 2 / 7 | – | 0 / 4 |
| Anselmus van Canterbury | mannelijk | 6 | 1 / 8 | – | 0 / 2 |
| Catharina van Siena | vrouwelijk | 6 | – | 1 / 7 | 0 / 2 |
| Columba van Iona | mannelijk | 5 | 1 / 8 | – | 0 / 1 |
| Paus Paulus VI | mannelijk | 6 | 4 / 6 | – | 2 / 3 |
| Lodewijk IX van Frankrijk | mannelijk | 5 | 0 / 5 | – | 0 / 3 |
| Moeder Teresa | vrouwelijk | 5 | – | 0 / 4 | 0 / 3 |
| Paus Gregorius I | mannelijk | 5 | 1 / 4 | – | 1 / 2 |
| Pater Damiaan | mannelijk | 5 | 0 / 4 | – | 0 / 1 |
| Thomas Becket | mannelijk | 6 | 1 / 3 | – | 0 / 1 |
| Liudger | mannelijk | 5 | 1 / 1 | – | 0 / 1 |

## De set, per geslachtsvoorkeur

| Interesse | man | vrouw | maakt niet uit |
| --- | --- | --- | --- |
| Mensen helpen | 20 | 20 | 40 |
| Kinderen en jongeren | 5 | 14 | 19 |
| Natuur en dieren | 6 | 5 | 11 |
| Muziek en kunst | 6 | 8 | 14 |
| Techniek, bouwen en computers | 6 | 6 | 12 |
| Lezen en schrijven | 17 | 14 | 31 |
| Sport en buiten bewegen | 7 | 4 | 11 |
| Reizen en andere culturen | 17 | 8 | 25 |
| Wetenschap en ontdekken | 7 | 7 | 14 |
| Opkomen voor wat eerlijk is | 11 | 7 | 18 |

Per as: aantal heiligen aan de min-kant / plus-kant.

| As | man | vrouw | maakt niet uit |
| --- | --- | --- | --- |
| samen_alleen | 6 / 22 | 13 / 16 | 19 / 38 |
| denken_doen | 13 / 24 | 6 / 18 | 19 / 42 |
| achter_voorop | 10 / 33 | 16 / 21 | 26 / 54 |
| plek_pad | 9 / 34 | 17 / 17 | 26 / 51 |
| diepgang_licht | 22 / 3 | 23 / 2 | 45 / 5 |
| vrede_strijd | 10 / 27 | 6 / 21 | 16 / 48 |
