# ODD-Protokoll: klima-abm

Beschreibung nach dem ODD-Protokoll (Overview, Design concepts, Details) in der Fassung von Grimm et al. (2020, *JASSS* 23(2):7). Ampeln wie in den Vorpapieren: **grün** Primärquelle geöffnet, **gelb** übertragen oder interpoliert, **rot** eigene Annahme.

## 1 Zweck und Muster

**Zweck.** Das Modell rechnet die fünf Szenarien A bis E der Szenarioanalyse „Hamburg 2036 – 2051 – 2076: Klimaszenarien für den Bevölkerungsschutz" durch. Es fragt, wie Klimapfad und Bewältigungsfähigkeit gemeinsam die Last auf das Hamburger Hilfeleistungssystem verändern: Hitzetote, Überlast im Rettungsdienst, Sturmflutfolgen, Starkregenlagen, KRITIS-Ausfälle und verbundene Lagen. Es ist ein **Explorationsmodell**, kein Prognosemodell. Szenarien haben keine Eintrittswahrscheinlichkeit; die Monte-Carlo-Streuung beschreibt Wetterzufall und Parameterunsicherheit *innerhalb* eines Szenarios.

**Muster, an denen das Modell geprüft wird** (pattern-oriented modelling):

| Muster | Zielwert | Quelle | Rolle |
|---|---|---|---|
| Heiße Tage 1991–2020 | 6,6 pro Jahr | Klimareport Hamburg | Kalibrierung Wetter |
| Jahresmaximum Tmax, 30-jährlich | rund 37–38 °C | Stationsrekorde vor 2026 | Kalibrierung Wetter (gelb) |
| Hitzetote im Klima 1993–2015 | 0,81 % der Sterbefälle | Huber et al. 2020 | Kalibrierung β, T0 |
| Hitzetote in einem Sommer wie 2026 | rund 380 (RKI 16 000 × Bevölkerungsanteil) | RKI vorläufig | Kalibrierung β, T0 (gelb) |
| Hitzetote 2022 | rund 160 | Hitzeaktionsplan | Plausibilitätsprüfung |
| Heiße Tage 2036 / 2051 | 8–12 / 11 (moderat) bis 14 | Szenariopapier G2 (DWD) | unabhängige Validierung |
| Jahre mit Sturmflut > 5 m | rund 35 % | 19 Fluten 1962–2002 | Kalibrierung Gumbel |
| Rekordwasserstand 6,45 m | rund 65-jährlich | HPA | Kalibrierung Gumbel |
| Rettungsdienst-Einsätze | 809 pro Tag (295 314 im Jahr 2024) | Feuerwehr Hamburg | Eingang |

## 2 Entitäten, Zustandsgrößen und Skalen

| Entität | Anzahl | Zustandsgrößen | Ampel |
|---|---|---|---|
| `HitzeKohorte` (Bezirk × Gruppe) | 35 = 7 Bezirke × 5 Gruppen (unter 65, 65–79, 80+, häuslich Pflegebedürftige, Heimbewohner) | Personen, Grundsterberate, Wärmeinsel-Zuschlag, Anteil Alleinlebender, Befolgung, Warntage, Tote | Bevölkerung grün, Gruppenaufteilung gelb, Wärmeinsel rot |
| `FlutKohorte` (Zone × Altersgruppe) | 9 = 3 Zonen (Evakuierungsgebiet, übriges Flutgebiet 1962, vor der Deichlinie) × 3 Altersgruppen | Personen, evakuiert, betroffen, Tote | gelb |
| `Behoerde` | 1 | Hitzewarnungen (Vorhersagefehler 1 K), Lernsignale, Evakuierungsanordnung | rot (Schwellen) |
| `Pflegedienste` | 1 | Deckung der aufsuchenden Hitzehilfe je Warntag | rot |
| `Rettungsdienst` | 1 | Grundlast, Kapazität, Ermüdung, Überlasttage, unbediente Einsätze | Grundlast grün, Kapazität rot |
| `Kliniken` | 1 | Notaufnahme-Last, Übergabefaktor | rot |
| `Stromnetz` (KRITIS) | 1 | Ausfallereignisse (Hitze, Sabotage), betroffener Anteil, Dauer | rot |
| `Katastrophenschutz` | 1 | Kapazität technische Hilfe, Rückstand, Kräftepool Deichverteidigung | Personal grün, Pool rot |
| `Kuestenschutz` | 1 | Schutzhöhe St. Pauli, Bruchwahrscheinlichkeit | Bemessung grün, Versagenskurve rot |

**Umwelt.** Tagesreihe Tmax (Station Fuhlsbüttel), Jahreshöchstwasserstand St. Pauli mit Ereignistag, Starkregenlagen mit Einsatzzahl.

**Skalen.** Zeitschritt ein Tag, Laufzeit ein Jahr. Ein Lauf steht für ein typisches Jahr im Jahrzehnt um den Horizont (2026 Kalibrierjahr, 2036, 2051, 2076). Raum: sieben Bezirke für Hitze, drei Flutzonen für Sturmflut; keine Rasterauflösung.

## 3 Prozessübersicht und Ablauf

Vor dem ersten Tag werden alle exogenen Reihen gezogen (Wetter, Sturmflut, Starkregen, Stromausfälle) und die Behörde erstellt ihre Warnreihe aus einer fehlerbehafteten Vorhersage. Danach läuft je Tag eine feste Reihenfolge:

1. `Pflegedienste.planen` – an Warntagen Deckung der aufsuchenden Hilfe, gemindert durch hitzebedingten Personalausfall.
2. `HitzeKohorte.step_hitze` – nur wenn Tmax + Wärmeinsel über T0 liegt: Übersterblichkeit, Warnmüdigkeit.
3. `Behoerde.hitzewellen_bilanz` – mehr als 30 Hitzetote in sieben Tagen lösen ein Lernsignal aus, die Befolgung aller Kohorten steigt.
4. Sturmflut am Ereignistag: Vorhersage, Evakuierung, Deichverteidigung, Belastung der Deichlinie, Überflutung.
5. `Rettungsdienst.step` – Nachfrage gegen Kapazität, Überlast, Ermüdung, Verstärkung am Folgetag, Rückmeldung an die Kliniken.
6. `Katastrophenschutz.step` – Starkregen-Einsätze gegen Kapazität, Rückstand.
7. Lagezählung: Warnung, Stromausfall, Starkregen, Rettungsdienst-Überlast und Sturmflut zählen je als Lage; zwei oder mehr gleichzeitig ergeben einen Verbundtag.

Die feste Reihenfolge ist gewollt: Sie bildet die Meldekette ab (Warnung vor Wirkung, Wirkung vor Einsatz).

## 4 Designkonzepte

- **Grundprinzipien.** Risiko = Gefahr × Exposition × Verwundbarkeit, gemindert durch Bewältigung (BBK-Logik, wie im Szenariopapier). Hitzesterblichkeit als log-lineare Expositions-Wirkungs-Beziehung über einer Schwelle (wie Gasparrini-Modelle, vereinfacht ohne Verzögerung).
- **Emergenz.** Überlasttage, Verbundtage und die Zahl der Hitzetoten entstehen aus dem Zusammenspiel von Wetterfolge, Warnverhalten, Kapazität und Ermüdung, nicht aus einer Formel.
- **Anpassung.** Kohorten passen ihre Befolgung an: Lernen nach sichtbaren Folgen, Warnmüdigkeit nach mehr als 15 Warntagen. Der Rettungsdienst fordert nach einem Überlasttag Verstärkung an.
- **Ziele.** Implizit: Kohorten schützen sich, Institutionen halten Versorgung aufrecht.
- **Lernen.** Nur innerhalb eines Jahres; Erfahrung über Jahre ist in den Szenariosetzungen (Reichweite, Wirksamkeit) enthalten.
- **Vorhersage.** Behörde nutzt Tmax-Vorhersage mit 1 K Fehler und Wasserstandsvorhersage mit 0,25 m Fehler.
- **Wahrnehmung.** Alleinlebende werden schlechter erreicht (Reichweite minus 30 % ihres Anteils).
- **Interaktion.** Indirekt über gemeinsame Ressourcen: Rettungsdienst, Kliniken, Kräftepool, Betreuungsplätze. Ein gleichzeitiges Binnenhochwasser bindet 40 % des Pools und schwächt die Deichverteidigung.
- **Stochastik.** Wetter, Vorhersagefehler, Ereignistage, Ausfallereignisse, Deichbruch, Einsatzrauschen. Parameter je Lauf aus Spannen (scenarios.UNSICHER).
- **Kollektive.** Kohorten sind Kollektive; Einzelpersonen werden nicht abgebildet.
- **Beobachtung.** Je Lauf ein Ergebnissatz (model.ergebnis), je Szenario × Horizont Mittel, Median, 5- und 95-%-Quantil, Standardfehler und Ereigniswahrscheinlichkeiten.

## 5 Initialisierung

Bevölkerung je Bezirk aus der Regionalstatistik (Einwohner 2025, 65+ 2025, 80+ 2024, Einpersonenhaushalte 65+ 2024). Pflegebedürftige 96 606 (2023), 85 % häuslich; 78 % ab 65 Jahren (gelb); Aufteilung auf Bezirke nach Anteil 80+. Grundsterberaten so, dass die Kohorten die 18 591 Sterbefälle 2024 reproduzieren (Test `test_grundsterblichkeit_reproduziert_sterbefaelle`). Flutzonen aus dem Szenariopapier, Abschnitt 2.2. Demografie der Horizonte über Faktoren für 65+ (amtlich bis 2040) und 80+ (Annahme).

## 6 Eingangsdaten

Alle Werte mit Quelle und Ampel in `klima_abm/data.py`, Szenariosetzungen in `klima_abm/scenarios.py`.

## 7 Teilmodelle

**Wetter.** Tmax = Kosinus-Klimatologie (Juli 23,6 °C, Januar 4,1 °C) + Jahresanomalie (σ 0,9 K) + AR(1)-Tagesanomalie (φ 0,78, σ 4,65 K) + Klimaverschiebung. Verschiebung = 2,34 + f × (global − 1,4) − 1,72 K, f ∈ [1,5; 1,9], im Sommer um den Faktor 1,0–1,25 verstärkt.

**Hitzesterblichkeit.** Übertote = N × m/365 × (exp(β·s·(T + UHI − T0)) − 1) × Strom-Faktor × (1 − Wirksamkeit × Schutzanteil). β und T0 kalibriert; s je Gruppe 0,5 bis 1,5.

**Rettungsdienst.** Grundlast = 809 × (1 − a + a × f65) mit a = Anteil 65+ an den Einsätzen; Hitzeeffekt +5 bis 10 % je 5 K über 25 °C (Xu et al. 2023), +10 % in extremen Hitzewellen (≥ 3 Tage ≥ 33 °C); Kapazität = Grundlast × (1 + Reserve) × Personal × (1 − Ermüdung) × (1 − Hitzeausfall) × Übergabefaktor. Nicht zeitgerecht bediente Einsätze tragen ein Sterberisiko von 0,1 bis 0,5 % (rot).

**Sturmflut.** Jahresmaximum Gumbel(μ, β) + Meeresspiegelanstieg; Anker P(> 5 m) = 0,35 und 6,45 m als 65-jährlicher Wert. Bruchwahrscheinlichkeit = Φ((W − Schutzhöhe − 0,5 m + Verteidigungsdefizit) / σ). Bei Bruch wird ein Anteil des Flutgebiets 1962 überflutet; Sterberate der nicht Evakuierten 0,2 bis 0,6 % mit Altersfaktor 1/2/4 (1962 als Anker).

**Starkregen.** Poisson-Lagen (≥ 300 Einsätze), Häufigkeit +7 bis 20 % je K Sommererwärmung, Einsatzzahl lognormal (Median 450).

**Stromnetz.** Ausfälle an heißen Tagen mit Wahrscheinlichkeit proportional zu (Tmax − 30), gemindert durch Resilienz; Sabotage als Poisson-Prozess (0,02–0,15 je Jahr).

## 8 Grenzen

Siehe Ergebnisseite, Abschnitt „Grenzen". Kurz: keine Hitzeverzögerung und kein Ernteeffekt, keine räumliche Auflösung unter Bezirksebene, keine Dürre und kein Sturm, Bewältigungsfähigkeit als Setzung, Kapazitäten des Rettungsdienstes und Versagenskurve der Deiche ohne Primärquelle.
