# Simulatie van de matching

Gegenereerd door `python -m durfheilig.simulatie --seed 2026 --n 200`. Zelfde seed, zelfde rapport.

77 heiligen, 200 fictieve profielen per geslachtsvoorkeur. Profielen beantwoorden elke of-of-vraag 50/50 en kiezen 2 of 3 interesses; dat toetst de spreiding, niet of iemand zich herkent. "Eerste keuze" is plek 1 van de deterministische ranglijst.

**Eindoordeel: niet alle eisen gehaald.**

"Puur toeval" is wat een matching haalt die elke deelnemer een willekeurige heilige geeft, bij hetzelfde aantal profielen. Ligt een eis daaronder, dan is hij bij dit aantal profielen niet te halen door ruis alleen, ook niet met een perfecte matching.

## Eisen uit het plan

| Eis | Uitkomst | Gehaald |
| --- | --- | --- |
| man: geen heilige boven 4% van de eerste keuzes | hoogste: Paus Leo I, 23 van 200 (11.5%); gelijk verdeeld 2.2%, puur toeval haalt 4.5% | ❌ nee |
| man: minstens 60% van de heiligen ooit in een top-3 | 46 van 46 (100%) | ✅ ja |
| vrouw: geen heilige boven 4% van de eerste keuzes | hoogste: Bernadette Soubirous, 30 van 200 (15.0%); gelijk verdeeld 3.2%, puur toeval haalt 6.0% | ❌ nee |
| vrouw: minstens 60% van de heiligen ooit in een top-3 | 31 van 31 (100%) | ✅ ja |
| maakt niet uit: geen heilige boven 4% van de eerste keuzes | hoogste: Paus Leo I, 21 van 200 (10.5%); gelijk verdeeld 1.3%, puur toeval haalt 3.0% | ❌ nee |
| maakt niet uit: minstens 60% van de heiligen ooit in een top-3 | 70 van 77 (91%) | ✅ ja |
| minstens 5 heiligen per interesse | allemaal | ✅ ja |
| per as heiligen aan beide kanten | allemaal | ✅ ja |

## Heiligen die nooit in een top-3 komen

- **man** (0): geen
- **vrouw** (0): geen
- **maakt niet uit** (7): Albertus Magnus, Alfonsus van Liguori, Catharina van Siena, Columba van Iona, Liudger, Lodewijk IX van Frankrijk, Moeder Teresa

## Per heilige

Aantal keer eerste keuze en aantal keer in de top-3, per geslachtsvoorkeur. Gesorteerd op totaal aantal top-3-plekken.

| Heilige | Geslacht | Bekende assen | man: 1e / top-3 | vrouw: 1e / top-3 | maakt niet uit: 1e / top-3 |
| --- | --- | --- | --- | --- | --- |
| Bernadette Soubirous | vrouwelijk | 5 | – | 30 / 50 | 17 / 39 |
| Martinus van Tours | mannelijk | 5 | 16 / 40 | – | 10 / 29 |
| Paus Leo I | mannelijk | 4 | 23 / 34 | – | 21 / 35 |
| Theresia van Lisieux | vrouwelijk | 6 | – | 12 / 35 | 11 / 29 |
| Jeanne d'Arc | vrouwelijk | 6 | – | 20 / 37 | 6 / 20 |
| Margaretha-Maria Alacoque | vrouwelijk | 5 | – | 19 / 34 | 10 / 21 |
| Monica van Tagaste | vrouwelijk | 4 | – | 16 / 32 | 9 / 22 |
| Alphonsa van de Onbevlekte Ontvangenis | vrouwelijk | 4 | – | 15 / 34 | 8 / 17 |
| Clara van Assisi | vrouwelijk | 5 | – | 12 / 29 | 9 / 21 |
| Petrus | mannelijk | 4 | 10 / 33 | – | 6 / 17 |
| Franciscus Xaverius | mannelijk | 5 | 15 / 28 | – | 9 / 20 |
| Jozefmaria Escrivá | mannelijk | 4 | 17 / 34 | – | 5 / 14 |
| Ladislaus I van Hongarije | mannelijk | 4 | 9 / 30 | – | 5 / 18 |
| Willibrord | mannelijk | 6 | 10 / 25 | – | 4 / 19 |
| Kateri Tekakwitha | vrouwelijk | 6 | – | 4 / 21 | 9 / 21 |
| Stefanus I van Hongarije | mannelijk | 4 | 12 / 22 | – | 5 / 17 |
| Pater Pio | mannelijk | 5 | 13 / 23 | – | 6 / 14 |
| Theresia van Ávila | vrouwelijk | 6 | – | 9 / 27 | 2 / 10 |
| Carlo Acutis | mannelijk | 6 | 13 / 26 | – | 2 / 10 |
| Liduina van Schiedam | vrouwelijk | 4 | – | 9 / 26 | 3 / 10 |
| Augustinus van Canterbury | mannelijk | 4 | 1 / 16 | – | 5 / 17 |
| Antonius van Egypte | mannelijk | 4 | 6 / 22 | – | 1 / 7 |
| Elisabeth van Aragón | vrouwelijk | 4 | – | 4 / 20 | 0 / 7 |
| Franciscus van Assisi | mannelijk | 6 | 6 / 21 | – | 2 / 6 |
| Maria Faustina Kowalska | vrouwelijk | 4 | – | 4 / 17 | 3 / 9 |
| Marianne Cope | vrouwelijk | 4 | – | 7 / 21 | 0 / 4 |
| Beda | mannelijk | 5 | 6 / 19 | – | 0 / 5 |
| Catharina van Bologna | vrouwelijk | 5 | – | 3 / 19 | 3 / 5 |
| Ursula van Keulen | vrouwelijk | 4 | – | 7 / 17 | 2 / 6 |
| Ambrosius van Milaan | mannelijk | 5 | 4 / 13 | – | 1 / 9 |
| Angela Merici | vrouwelijk | 5 | – | 2 / 17 | 0 / 5 |
| Josephine Bakhita | vrouwelijk | 6 | – | 0 / 20 | 0 / 2 |
| Filippus Neri | mannelijk | 6 | 5 / 18 | – | 2 / 3 |
| Genoveva van Parijs | vrouwelijk | 5 | – | 4 / 19 | 0 / 2 |
| Rita van Cascia | vrouwelijk | 4 | – | 1 / 16 | 2 / 5 |
| Elisabeth van Thüringen | vrouwelijk | 6 | – | 6 / 17 | 1 / 3 |
| Gregorius van Tours | mannelijk | 5 | 2 / 11 | – | 1 / 8 |
| Keizer Hendrik II de Heilige | mannelijk | 4 | 5 / 12 | – | 2 / 7 |
| Thomas van Aquino | mannelijk | 6 | 4 / 13 | – | 1 / 4 |
| Elizabeth Ann Seton | vrouwelijk | 4 | – | 3 / 11 | 0 / 5 |
| Giovanni Bosco | mannelijk | 6 | 3 / 11 | – | 3 / 5 |
| Rosa van Lima | vrouwelijk | 4 | – | 0 / 13 | 0 / 2 |
| Bonifatius | mannelijk | 5 | 2 / 8 | – | 3 / 6 |
| Gertrudis van Helfta | vrouwelijk | 5 | – | 4 / 11 | 0 / 3 |
| Nicolaas van Myra | mannelijk | 4 | 2 / 9 | – | 0 / 5 |
| Óscar Romero | mannelijk | 6 | 0 / 10 | – | 1 / 4 |
| Edith Stein | vrouwelijk | 6 | – | 2 / 9 | 2 / 4 |
| Hildegard van Bingen | vrouwelijk | 6 | – | 2 / 12 | 0 / 1 |
| Isidorus van Sevilla | mannelijk | 5 | 2 / 12 | – | 1 / 1 |
| Johanna van Valois | vrouwelijk | 4 | – | 2 / 10 | 0 / 3 |
| Pier Giorgio Frassati | mannelijk | 6 | 2 / 11 | – | 0 / 2 |
| Ignatius van Loyola | mannelijk | 6 | 0 / 9 | – | 0 / 3 |
| Radegundis | vrouwelijk | 4 | – | 3 / 7 | 1 / 4 |
| Rochus van Montpellier | mannelijk | 4 | 0 / 8 | – | 1 / 3 |
| Albertus Magnus | mannelijk | 6 | 2 / 10 | – | 0 / 0 |
| Thomas More | mannelijk | 6 | 0 / 7 | – | 0 / 3 |
| Charles de Foucauld | mannelijk | 6 | 4 / 7 | – | 0 / 2 |
| Paus Johannes Paulus II | mannelijk | 6 | 1 / 6 | – | 0 / 3 |
| Paus Johannes XXIII | mannelijk | 6 | 0 / 4 | – | 1 / 5 |
| Maria MacKillop | vrouwelijk | 5 | – | 0 / 7 | 0 / 1 |
| Augustinus van Hippo | mannelijk | 6 | 3 / 5 | – | 0 / 2 |
| Alfonsus van Liguori | mannelijk | 6 | 0 / 6 | – | 0 / 0 |
| Anselmus van Canterbury | mannelijk | 6 | 0 / 5 | – | 0 / 1 |
| Birgitta van Zweden | vrouwelijk | 6 | – | 0 / 5 | 0 / 1 |
| Paus Paulus VI | mannelijk | 6 | 0 / 3 | – | 2 / 3 |
| Titus Brandsma | mannelijk | 6 | 1 / 4 | – | 0 / 2 |
| Hiëronymus van Stridon | mannelijk | 6 | 0 / 3 | – | 1 / 2 |
| Thomas Becket | mannelijk | 6 | 0 / 3 | – | 0 / 2 |
| Columba van Iona | mannelijk | 5 | 0 / 4 | – | 0 / 0 |
| Liudger | mannelijk | 5 | 1 / 4 | – | 0 / 0 |
| Moeder Teresa | vrouwelijk | 5 | – | 0 / 4 | 0 / 0 |
| Pater Damiaan | mannelijk | 5 | 0 / 2 | – | 0 / 2 |
| Paus Gregorius I | mannelijk | 5 | 0 / 3 | – | 1 / 1 |
| Catharina van Siena | vrouwelijk | 6 | – | 0 / 3 | 0 / 0 |
| Johannes van het Kruis | mannelijk | 6 | 0 / 2 | – | 0 / 1 |
| Maximiliaan Kolbe | mannelijk | 5 | 0 / 2 | – | 0 / 1 |
| Lodewijk IX van Frankrijk | mannelijk | 5 | 0 / 2 | – | 0 / 0 |

## De set

| Interesse | Heiligen |
| --- | --- |
| Mensen helpen | 33 |
| Kinderen en jongeren | 16 |
| Natuur en dieren | 7 |
| Muziek en kunst | 11 |
| Techniek, bouwen en computers | 5 |
| Lezen en schrijven | 29 |
| Sport en buiten bewegen | 7 |
| Reizen en andere culturen | 23 |
| Wetenschap en ontdekken | 10 |
| Opkomen voor wat eerlijk is | 16 |

| As | Min-kant | Plus-kant | Onbekend |
| --- | --- | --- | --- |
| samen_alleen | 17 | 34 | 13 |
| denken_doen | 18 | 36 | 14 |
| achter_voorop | 24 | 46 | 0 |
| plek_pad | 22 | 46 | 0 |
| diepgang_licht | 40 | 4 | 28 |
| vrede_strijd | 13 | 43 | 12 |
