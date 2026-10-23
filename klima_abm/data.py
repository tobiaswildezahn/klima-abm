"""Empirische Eingangsdaten mit Quelle und Ampel.

Jeder Wert trägt seine Herkunft. Ampel:
  gruen  – amtliche oder begutachtete Primärquelle geöffnet
  gelb   – Quelle vorhanden, aber übertragen, interpoliert oder nur sekundär belegt
  rot    – eigene Annahme ohne direkte Quelle (immer in der Sensitivitätsanalyse)
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Datum:
    wert: float
    quelle: str
    ampel: str
    notiz: str = ""


# --- Bevölkerung nach Bezirk -------------------------------------------------
# Regio-Gateway (Statistikamt Nord / UDP, dl-de/by-2.0), abgefragt 23.10.2026.
# einwohner: 2025, ab65: 2025, ab80: 2024
BEZIRKE = {
    #               einwohner  ab65    ab80   uhi_tmax (K, Annahme)
    "Hamburg-Mitte": (315_320, 45_713, 12_690, 1.0),
    "Altona":        (283_232, 51_745, 18_215, 0.6),
    "Eimsbüttel":    (278_426, 51_996, 18_155, 0.8),
    "Hamburg-Nord":  (332_153, 53_178, 17_100, 0.7),
    "Wandsbek":      (457_027, 97_633, 35_930, 0.3),
    "Bergedorf":     (134_434, 26_676,  8_640, 0.1),
    "Harburg":       (179_693, 30_958, 10_710, 0.3),
}
# Einpersonenhaushalte der 65-Jährigen und Älteren (2024), rs:hau_einpersonenhaushalte_ab65
ALLEIN_AB65 = {
    "Hamburg-Mitte": 20_375, "Altona": 21_930, "Eimsbüttel": 23_155, "Hamburg-Nord": 26_015,
    "Wandsbek": 37_345, "Bergedorf": 9_055, "Harburg": 11_585,
}
QUELLE_BEZIRKE =Datum(0, "Statistikamt Nord, Regionalstatistik Bezirke (Regio-Gateway rs:bev_insgesamt, rs:bev_ab65, rs:bev_ab80)", "gruen")
QUELLE_UHI = Datum(0, "Annahme; Klimainformationssystem nennt 2–3 K Jahresmittel und bis 7,4 K Spitze, aber keine Tmax-Werte je Bezirk", "rot")

# --- Sterblichkeit -------------------------------------------------------------
STERBEFAELLE_2024 = Datum(18_591, "Statistikamt Nord, rs:bevb_sterbefaelle_anz (2024)", "gruen")
STERBEFAELLE_2022 = Datum(19_877, "Statistikamt Nord, rs:bevb_sterbefaelle_anz (2022)", "gruen")
# Altersverteilung der Gestorbenen: Standardtabelle 12613-02-02 (Statistikamt Nord), Stand 2015
ANTEIL_TOTE_U65 = Datum(0.16, "Statistikamt Nord 12613-02-02, eigene Rechnung (Stand 2015)", "gelb", "Altersstruktur 2015 auf 2024 übertragen")
ANTEIL_TOTE_65_79 = Datum(0.32, "ebd.", "gelb")
ANTEIL_TOTE_80 = Datum(0.52, "ebd.", "gelb")

PFLEGEBEDUERFTIGE_2023 = Datum(96_606, "Statistikamt Nord, Meine Region mr:17_14 (2023); Hitzeaktionsplan HH S. 22", "gruen")
ANTEIL_HAEUSLICH = Datum(0.85, "Hamburger Hitzeaktionsplan (85 % häuslich versorgt)", "gruen")
ANTEIL_PFLEGE_AB65 = Datum(0.78, "Annahme in Anlehnung an Bundespflegestatistik", "gelb")
MORT_HEIM = Datum(0.28, "Annahme (Größenordnung Literatur zur Heimsterblichkeit)", "rot")
MORT_PFLEGE_HAUS = Datum(0.10, "Annahme", "rot")
MORT_U65 = Datum(0.0018, "abgeleitet: 16 % der Sterbefälle / Bevölkerung unter 65", "gelb")

# --- Hitze und Gesundheit -------------------------------------------------------
HITZETOTE_ANTEIL_1993_2015 = Datum(0.0081, "Huber et al. 2020, Environ. Res. 186:109447, 12 deutsche Städte, hitzebedingter Anteil 0,81 % (0,72–0,89)", "gelb", "Städtemittel, nicht Hamburg allein")
HITZETOTE_HH_2022 = Datum(160, "Hamburger Hitzeaktionsplan S. 22 (Modellschätzung nach Huber et al.)", "gelb")
HITZETOTE_DE_2026 = Datum(16_000, "RKI, vorläufig, laut Ist-Zustands-Papier Abschnitt 3.3", "gelb")
ANTEIL_HH_AN_DE = Datum(0.0236, "1,98 Mio. / 83,6 Mio. Einwohner", "gruen")
RTW_PRO_5K = Datum(0.07, "Xu et al. 2023, Int. J. Biometeorol., Metaanalyse: +7 % (5–10 %) Rettungsdiensteinsätze je +5 °C", "gelb", "international, nicht Hamburg")
RTW_EXTREME_HITZEWELLE = Datum(0.18, "ebd.: +18 % (12–23 %) bei extremen Hitzewellen", "gelb")

# --- Klima Hamburg ------------------------------------------------------------
HEISSE_TAGE_1991_2020 = Datum(6.6, "Klimareport Hamburg (DWD), heiße Tage 1991–2020", "gruen")
HEISSE_TAGE_2026 = Datum(11, "BUKEA 1.9.2026, Station Flughafen", "gruen")
TAGE_35_2026 = Datum(3, "ebd.", "gruen")
TMAX_REKORD_2026 = Datum(39.1, "BUKEA/DWD, Station Flughafen 27.6.2026", "gruen")
REG_ANOMALIE_2016_2025 = Datum(2.34, "Ist-Zustand 4.1, eigene Nachrechnung DWD-Gebietsmittel Ni/HH/HB", "gruen")
REG_TREND_SEIT_1971 = Datum(0.39, "ebd., K pro Jahrzehnt", "gruen")
REG_FAKTOR = Datum(1.7, "Ist-Zustand 5.2, Verhältnis regional/global 1,5–1,9", "gelb")

# --- Rettungsdienst und Einsatzkräfte -----------------------------------------
RD_EINSAETZE_2024 = Datum(295_314, "Feuerwehr Hamburg, Jahresbericht 2024", "gruen")
TH_EINSAETZE_2024 = Datum(24_541, "ebd., technische Hilfeleistungen", "gruen")
BF_PERSONAL = Datum(3_652, "ebd., Beschäftigte Berufsfeuerwehr", "gruen")
FF_AKTIVE = Datum(2_742, "ebd., aktive Mitglieder Freiwillige Feuerwehr", "gruen")
ANTEIL_RD_65PLUS = Datum(0.45, "Annahme; Literatur nennt 40–50 % der Notfalleinsätze bei 65+", "rot")

# --- Sturmflut und Küstenschutz -------------------------------------------------
BHW_ALT = Datum(7.30, "LSBG Bericht Nr. 7, Anleitung Deichverteidigung (Bemessung + 7,30 m NHN St. Pauli)", "gruen")
BHW_NEU = Datum(8.10, "LSBG Bericht Nr. 16/2014: im August 2013 neu festgelegter Bemessungswasserstand NN + 8,10 m", "gruen")
REKORD_STPAULI = Datum(6.45, "HPA Gewässerkundliche Information 2026 (3.1.1976)", "gruen")
FLUTEN_UEBER_5M_1962_2002 = Datum(19, "Kasang/von Storch 2010, laut Ist-Zustand 4.5", "gelb")
HAFENCITY_BETROFFEN_AB = Datum(5.0, "LSBG Merkblatt Flutschutz HafenCity: tiefliegende Flächen ca. NHN + 5,00 m", "gruen")
TOTE_1962_HH = Datum(315, "allgemein dokumentiert (Sturmflut 16./17.2.1962)", "gelb", "bibliografisch, nicht erneut geöffnet")
BETROFFENE_1962_HH = Datum(60_000, "Größenordnung obdachlos gewordener Menschen 1962", "rot")

# Exposition aus dem Szenariopapier, Abschnitt 2.2 (Regio-Gateway, Zensus-Raster, 31.12.2024)
FLUTZONEN = {
    #                 gesamt   ab65    ab80
    "Evakuierungsgebiet": (23_130, 3_910, 1_230),
    "Flutgebiet1962_rest": (135_200 - 23_130, 18_960 - 3_910, 5_030 - 1_230),
    "Vordeichs": (9_530, 1_130, 340),
}
QUELLE_FLUTZONEN = Datum(0, "Szenariopapier 2.2; Evakuierungsgebiete als Teilmenge des Flutgebiets 1962 angenommen", "gelb")

# Bevölkerungsvorausberechnung (prog_land)
AB65_2024 = Datum(353_800, "Statistikamt Nord prog_land", "gruen")
AB65_2036 = Datum(422_315, "Statistikamt Nord prog_land", "gruen")
AB65_2040 = Datum(431_535, "Statistikamt Nord prog_land", "gruen")
