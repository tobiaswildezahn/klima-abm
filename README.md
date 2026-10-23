# klima-abm

Agentenbasiertes Modell, das die Klimaszenarien A–E für den Hamburger Bevölkerungsschutz
durchrechnet (Horizonte 2036, 2051, 2076). Es baut auf drei Papieren auf:

1. [Steuert die Erde auf 2,8 °C zu? Ein kritischer Faktencheck](https://claude.ai/artifact/TX65HRUwx3p4MNpcwn2bnH) – Endpunkte 2,1 / 2,6 / 2,8 / > 3,4 °C
2. [Wie warm ist es heute?](https://claude.ai/artifact/U5uZwekhtyXaaFzCkx644Z) – Ist-Zustand Welt, Deutschland, Hamburg
3. [Hamburg 2036 – 2051 – 2076: Klimaszenarien für den Bevölkerungsschutz](https://claude.ai/artifact/M9uw394FFgcuY2CSWr1myC) – zwölf Schlüsselfaktoren, Szenarien A–E

Das Modell ist ein Explorationsmodell, kein Prognosemodell. Szenarien haben keine
Eintrittswahrscheinlichkeit; die Streuung der Ergebnisse beschreibt Wetterzufall und
Parameterunsicherheit innerhalb eines Szenarios.

## Aufbau

| Datei | Inhalt |
|---|---|
| `klima_abm/data.py` | Eingangsdaten mit Quelle und Ampel (grün/gelb/rot) |
| `klima_abm/scenarios.py` | Klimapfade, Meeresspiegel, Bewältigungssetzungen, Demografie, unsichere Parameter |
| `klima_abm/hazards.py` | Wettergenerator (Tmax), Sturmflut (Gumbel), Starkregen |
| `klima_abm/agents.py` | Agenten: Bevölkerungskohorten, Behörde, Pflegedienste, Rettungsdienst, Kliniken, Stromnetz, Katastrophenschutz, Küstenschutz |
| `klima_abm/model.py` | `HamburgModell` (Mesa), ein Lauf = ein Jahr im Tagesschritt |
| `klima_abm/calibration.py` | Kalibrierung Wetter, Hitzesterblichkeit, Sturmflut |
| `klima_abm/experiments.py` | Monte Carlo, Zusammenfassung, 2×2-Achsenzerlegung, Konvergenz |
| `klima_abm/sensitivity.py` | Morris-Elementareffekte für Unsicherheit und Hebel |
| `docs/ODD.md` | Modellbeschreibung nach ODD-Protokoll |
| `results/` | Ergebnisse (CSV, JSON, Abbildungen) |

## Nutzung

```bash
pip install -r requirements.txt
python -m pytest tests            # 14 Tests
python -m klima_abm.calibration   # Kalibrierung, schreibt results/kalibrierung.json
python scripts/run_all.py --n 1000  # Monte Carlo (16 000 Jahre) und Morris, rund 3 Minuten auf 4 Kernen
```

## Ampeln

Jeder Eingangswert trägt eine Ampel: **grün** Primärquelle geöffnet, **gelb** übertragen,
interpoliert oder sekundär belegt, **rot** eigene Annahme. Alle roten Werte stehen in der
Sensitivitätsanalyse (`scenarios.UNSICHER`, `sensitivity.HEBEL`).
