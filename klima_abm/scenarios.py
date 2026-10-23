"""Szenarien A–E, Horizonte und Parameterunsicherheit.

Ein Lauf des Modells ist ein simuliertes Jahr im Horizont (Mittel eines Jahrzehnts
um 2036, 2051, 2076). `draw_config` zieht für jeden Lauf die unsicheren Parameter;
so trägt die Monte-Carlo-Streuung beides: Wetterzufall und Parameterunsicherheit.
"""
from __future__ import annotations

import numpy as np

HORIZONTE = (2026, 2036, 2051, 2076)
SZENARIEN = ("A", "B", "C", "D", "E")

SZENARIO_NAMEN = {
    "IST": "Ist 2026 (Kalibrierjahr)",
    "A": "A Vorsorge trägt",
    "B": "B Anpassung im Dauerlauf",
    "C": "C Glück ohne Vorsorge",
    "D": "D Überlastung",
    "E": "E Rand des Trichters",
}

# Klimapfad und Bewältigung je Szenario (Szenariopapier, Tabelle Kurzfassung)
ACHSEN = {
    "A": ("2.1", "hoch"),
    "B": ("2.6-2.8", "hoch"),
    "C": ("2.1", "niedrig"),
    "D": ("2.6-2.8", "niedrig"),
    "E": (">3.4", "beliebig"),
}

# Globale Erwärmung ggü. 1850–1900 je Pfad und Horizont (Szenariopapier 2.3, eigene
# Interpolation dort, gelb). Spannen als (min, max), gleichverteilt gezogen.
GLOBAL_T = {
    "2.1":     {2026: (1.35, 1.45), 2036: (1.6, 1.8), 2051: (1.8, 2.0), 2076: (2.0, 2.2)},
    "2.6":     {2026: (1.35, 1.45), 2036: (1.6, 1.8), 2051: (1.9, 2.1), 2076: (2.3, 2.5)},
    "2.8":     {2026: (1.35, 1.45), 2036: (1.6, 1.8), 2051: (2.0, 2.2), 2076: (2.4, 2.6)},
    ">3.4":    {2026: (1.35, 1.45), 2036: (1.7, 1.9), 2051: (2.2, 2.4), 2076: (2.8, 3.1)},
}

# Meeresspiegel ggü. 1995–2014 in m (IPCC AR6, Median und wahrscheinliche Spanne;
# 2036 und 2076 linear interpoliert wie im Szenariopapier 2.3). (median, unten, oben)
SLR = {
    "2.1":  {2026: (0.07, 0.05, 0.09), 2036: (0.12, 0.10, 0.15), 2051: (0.19, 0.16, 0.25), 2076: (0.32, 0.24, 0.44)},
    "2.6":  {2026: (0.07, 0.05, 0.09), 2036: (0.13, 0.10, 0.15), 2051: (0.20, 0.17, 0.26), 2076: (0.39, 0.31, 0.52)},
    "2.8":  {2026: (0.07, 0.05, 0.09), 2036: (0.13, 0.10, 0.15), 2051: (0.21, 0.17, 0.27), 2076: (0.42, 0.33, 0.57)},
    ">3.4": {2026: (0.07, 0.05, 0.09), 2036: (0.14, 0.11, 0.17), 2051: (0.24, 0.20, 0.40), 2076: (0.56, 0.42, 1.00)},
}

# Bewältigungsfähigkeit als Setzung je Horizont (Szenariodefinition, nicht Prognose).
# reach: Anteil, den die Hitzewarnung erreicht; eff: Minderung des Übersterblichkeitsrisikos
# bei Schutzverhalten; outreach: Besuchskapazität ambulanter Dienste je Pflegebedürftigem
# an Warntagen; headroom: Reserve des Rettungsdienstes über dem Jahresmittel;
# staff: Personalfaktor; vol: Ehrenamt; dike: wirksame Schutzhöhe St. Pauli (m NHN);
# res: KRITIS-Resilienz (0–1); notstrom: Anteil Heime mit Notstrom und Kühlung;
# heim_kuehl: Anteil Heime mit gekühlten Aufenthaltsräumen;
# betreuung: Betreuungsplätze; reinforce: Verstärkung bei Überlast (Anteil der Kapazität).
# Rettungsdienst: Kapazität/Grundlast = (1 + headroom) × staff. Ist 1,12; hoch 1,16–1,18;
# niedrig sinkt von 1,07 (2036) auf 1,03 (2076), d. h. die Vorhaltung wächst langsamer
# als die alternde Nachfrage und die Spitzenreserve schrumpft.
BEWAELTIGUNG = {
    "ist": {
        2026: dict(reach=0.55, eff=0.35, outreach=0.30, headroom=0.12, staff=1.00, vol=1.00,
                   dike=7.66, res=0.40, notstrom=0.30, heim_kuehl=0.30, betreuung=15_000, reinforce=0.05),
    },
    "hoch": {
        2036: dict(reach=0.80, eff=0.45, outreach=0.60, headroom=0.16, staff=1.00, vol=1.05,
                   dike=7.94, res=0.60, notstrom=0.70, heim_kuehl=0.60, betreuung=25_000, reinforce=0.10),
        2051: dict(reach=0.88, eff=0.50, outreach=0.75, headroom=0.18, staff=1.00, vol=1.10,
                   dike=8.10, res=0.75, notstrom=0.90, heim_kuehl=0.85, betreuung=30_000, reinforce=0.12),
        2076: dict(reach=0.90, eff=0.55, outreach=0.80, headroom=0.18, staff=1.00, vol=1.10,
                   dike=8.10, res=0.80, notstrom=0.95, heim_kuehl=0.95, betreuung=30_000, reinforce=0.12),
    },
    "niedrig": {
        2036: dict(reach=0.55, eff=0.32, outreach=0.25, headroom=0.10, staff=0.97, vol=0.90,
                   dike=7.78, res=0.35, notstrom=0.35, heim_kuehl=0.35, betreuung=12_000, reinforce=0.04),
        2051: dict(reach=0.50, eff=0.30, outreach=0.20, headroom=0.09, staff=0.96, vol=0.75,
                   dike=7.90, res=0.30, notstrom=0.40, heim_kuehl=0.40, betreuung=10_000, reinforce=0.03),
        2076: dict(reach=0.50, eff=0.30, outreach=0.20, headroom=0.08, staff=0.95, vol=0.70,
                   dike=8.10, res=0.30, notstrom=0.45, heim_kuehl=0.45, betreuung=10_000, reinforce=0.03),
    },
}

# Nächste Küstenschutzgeneration bis 2076 (Szenariopapier 4.2/6.2: Beschluss um 2040).
# Bei hoher Bewältigung pfadabhängig: kräftiger bei 2,6–2,8 °C und am Rand.
NAECHSTE_GENERATION = {"2.1": 0.3, "2.6": 0.6, "2.8": 0.6, ">3.4": 0.6}

# Demografie: Faktoren ggü. 2024/25 (65+ bis 2040 amtlich, danach Annahme)
DEMOGRAFIE = {
    2026: dict(f65=(1.00, 1.02), f80=(1.00, 1.03)),
    2036: dict(f65=(1.18, 1.18), f80=(1.00, 1.15)),
    2051: dict(f65=(1.22, 1.33), f80=(1.30, 1.55)),
    2076: dict(f65=(1.10, 1.40), f80=(1.20, 1.60)),
}

# Unsichere Modellparameter (für Monte Carlo und Morris-Sensitivität).
# name: (min, max, Ampel, Herkunft)
UNSICHER = {
    "reg_faktor":     (1.5, 1.9, "gelb", "Verhältnis regionale/globale Erwärmung, Ist-Zustand 5.2"),
    "sommer_amp":     (1.0, 1.25, "rot", "Sommerliche Verstärkung der Erwärmung von Tmax"),
    "beta_scale":     (0.8, 1.2, "gelb", "Unsicherheit der kalibrierten Hitze-Expositions-Wirkung"),
    "eff_scale":      (0.7, 1.3, "rot", "Wirksamkeit des Schutzverhaltens"),
    "rd_hitze":       (0.05, 0.10, "gelb", "RD-Mehreinsätze je +5 K, Xu et al. 2023 (95-%-KI)"),
    "rd_anteil65":    (0.40, 0.50, "rot", "Anteil der RD-Einsätze bei 65+"),
    "p_tod_verzug":   (0.001, 0.005, "rot", "Sterberisiko je nicht zeitgerecht bedientem Einsatz"),
    "gumbel_beta":    (0.39, 0.48, "gelb", "Streuung der Jahreshöchstwasserstände St. Pauli"),
    "deich_sigma":    (0.15, 0.35, "rot", "Unschärfe der Deich-Versagenskurve (m)"),
    "flut_mort":      (0.002, 0.006, "gelb", "Sterberate nicht evakuierter Betroffener, 1962 als Anker"),
    "flut_anteil":    (0.15, 0.45, "rot", "überfluteter Anteil des Flutgebiets 1962 bei Deichbruch"),
    "evak_compliance": (0.6, 0.9, "rot", "Befolgung der Evakuierungsanordnung"),
    "sr_rate":        (0.6, 1.4, "rot", "Starkregenlagen (≥ 300 Einsätze/24 h) je Jahr im Klima 1991–2020"),
    "sr_skalierung":  (0.07, 0.20, "gelb", "Zunahme der Starkregenhäufigkeit je K (Clausius-Clapeyron bis super-CC)"),
    "strom_hitze":    (0.5, 2.0, "rot", "Hitzeabhängigkeit großflächiger Stromausfälle"),
    "sabotage_rate":  (0.02, 0.15, "rot", "Sabotage an Stromversorgung je Jahr (U1)"),
}


def _u(rng, lo, hi):
    return float(rng.uniform(lo, hi))


def _slr(rng, med, lo, hi):
    """Schiefe Verteilung aus Median und 17–83-%-Spanne (zwei Halbnormalen)."""
    z = rng.normal()
    return float(med + (z * (hi - med) if z > 0 else z * (med - lo)))


def draw_config(szenario: str, horizont: int, rng: np.random.Generator,
                fixed: dict | None = None) -> dict:
    """Zieht eine Parameterkonfiguration für ein simuliertes Jahr.

    szenario: "IST" (Kalibrierjahr 2026) oder "A"–"E".
    fixed: überschreibt einzelne Parameter (für Sensitivitätsanalyse und Tests).
    """
    fixed = fixed or {}
    if szenario == "IST":
        pfad, bew = "2.8", "ist"
        horizont = 2026
    else:
        pfad, bew = ACHSEN[szenario]
        if pfad == "2.6-2.8":
            pfad = "2.6" if rng.random() < 0.5 else "2.8"
        if bew == "beliebig":
            bew = "hoch" if rng.random() < 0.5 else "niedrig"

    cfg = {"szenario": szenario, "horizont": horizont, "pfad": pfad, "bewaeltigung": bew}

    for k, (lo, hi, _, _) in UNSICHER.items():
        cfg[k] = _u(rng, lo, hi)

    g_lo, g_hi = GLOBAL_T[pfad][horizont]
    cfg["global_t"] = _u(rng, g_lo, g_hi)
    cfg["slr"] = _slr(rng, *SLR[pfad][horizont])

    b = dict(BEWAELTIGUNG[bew][horizont])
    # Setzungen mit ±10 % Unschärfe, damit Ergebnisse nicht an Einzelwerten kleben
    for k in ("reach", "eff", "outreach", "res", "notstrom", "heim_kuehl"):
        b[k] = float(np.clip(b[k] * rng.uniform(0.9, 1.1), 0, 1))
    for k in ("headroom", "reinforce"):
        b[k] = float(b[k] * rng.uniform(0.9, 1.1))
    for k in ("staff", "vol"):
        b[k] = float(b[k] * rng.uniform(0.97, 1.03))
    if horizont == 2076 and bew == "hoch":
        b["dike"] = b["dike"] + NAECHSTE_GENERATION[pfad]
    cfg.update(b)

    d = DEMOGRAFIE[horizont]
    cfg["f65"] = _u(rng, *d["f65"])
    cfg["f80"] = _u(rng, *d["f80"])
    cfg["f_pflege"] = cfg["f80"] * (_u(rng, 1.0, 1.15) if horizont > 2026 else 1.0)

    cfg.update(fixed)
    return cfg


def regional_shift(cfg: dict) -> float:
    """Verschiebung der Tmax-Klimatologie ggü. 1991–2020 in K.

    Regionale Anomalie 2016–2025 = 2,34 K bei global 1,4 °C (Ist-Zustand); 1991–2020
    lag rund 0,6 K darunter (0,39 K/Jahrzehnt × 1,6 Jahrzehnte).
    """
    reg = 2.34 + cfg["reg_faktor"] * (cfg["global_t"] - 1.4)
    return reg - 1.72
