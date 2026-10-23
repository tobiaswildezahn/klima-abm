"""Gefahrengeneratoren: Hitze (Tageshöchsttemperatur), Sturmflut, Starkregen.

Die Generatoren erzeugen für ein simuliertes Jahr die exogenen Gefahrenreihen.
Ihre Parameter sind in `calibration.py` auf Hamburger Beobachtungen kalibriert;
die Zielwerte stehen in `data.py`.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

TAGE = 365
SOMMER = slice(120, 273)  # 1. Mai bis 30. September
WINTER_TAGE = np.r_[0:90, 273:365]  # Sturmflutsaison Oktober bis März


@dataclass(frozen=True)
class WetterParameter:
    """Stochastischer Wettergenerator für Tmax am Flughafen Fuhlsbüttel.

    Klimatologie 1991–2020: Kosinus mit Maximum Mitte Juli (Juli-Mittel Tmax rund
    23 °C, Januar rund 4 °C). Anomalien: Jahresanomalie plus AR(1)-Tagesrauschen,
    rechtsschief transformiert, damit Hitzeperioden und Spitzen realistisch sind.
    sd und kappa sind auf 6,6 heiße Tage pro Jahr (Klimareport) und ein 30-jährliches
    Jahresmaximum um 38 °C kalibriert (calibration.kalibriere_wetter); die Schiefe-
    Option kappa wird dafür nicht gebraucht (0).
    """
    mittel: float = 13.8
    amplitude: float = 9.9
    peak_tag: int = 200
    phi: float = 0.78
    sd: float = 4.65
    kappa: float = 0.0
    sd_jahr: float = 0.9


WETTER = WetterParameter()


def tmax_reihe(rng: np.random.Generator, shift: float, sommer_amp: float = 1.0,
               p: WetterParameter = WETTER) -> np.ndarray:
    d = np.arange(TAGE)
    saison = np.cos(2 * np.pi * (d - p.peak_tag) / TAGE)
    klima = p.mittel + p.amplitude * saison
    # Erwärmung: im Sommer um sommer_amp verstärkt
    gewicht = 1.0 + (sommer_amp - 1.0) * np.clip(saison, 0, 1)
    z = rng.normal(size=TAGE)
    e = np.empty(TAGE)
    e[0] = z[0] * p.sd
    innov = p.sd * np.sqrt(1 - p.phi ** 2)
    for t in range(1, TAGE):
        e[t] = p.phi * e[t - 1] + innov * z[t]
    # Rechtsschiefe nur im Sommerhalbjahr (Hitzeperioden), nicht im Winter
    sommer_w = np.clip(saison, 0, 1)
    e = e + sommer_w * p.kappa * np.maximum(e, 0) ** 2
    jahr = rng.normal(0, p.sd_jahr)
    return klima + shift * gewicht + jahr + e


# --- Sturmflut --------------------------------------------------------------------
# Jahreshöchstwasserstand St. Pauli als Gumbel-Verteilung. Kalibriert auf zwei Anker:
# P(Jahresmaximum > 5,0 m) ≈ 0,35 (19 Fluten > 5 m in 1962–2002) und 65-jährlicher
# Wert 6,45 m (Rekord 1976 in 65 Jahren seit 1962). Bezugszeit rund 1995–2014,
# also dieselbe Basis wie die IPCC-Meeresspiegelwerte.
GUMBEL_MU = 4.633
GUMBEL_BETA_REF = 0.436
GUMBEL_ANKER_P5 = 0.842  # -ln(-ln(0.65))


def gumbel_mu(beta: float) -> float:
    """Lageparameter so, dass der Anker P(>5 m) = 0,35 bei jeder Streuung hält."""
    return 5.0 - GUMBEL_ANKER_P5 * beta


def sturmflut(rng: np.random.Generator, slr: float, beta: float) -> tuple[float, int]:
    """Jahreshöchstwasserstand (m NHN) und Tag des Ereignisses."""
    w = gumbel_mu(beta) + slr - beta * np.log(-np.log(rng.random()))
    tag = int(rng.choice(WINTER_TAGE))
    return float(w), tag


# --- Starkregen ----------------------------------------------------------------
def starkregen(rng: np.random.Generator, rate: float, skalierung: float,
               shift_sommer: float) -> list[tuple[int, float]]:
    """Starkregenlagen (≥ 300 Einsätze in 24 h) im Sommerhalbjahr.

    Häufigkeit steigt je K regionaler Sommererwärmung um `skalierung`
    (7 %/K Clausius-Clapeyron bis rund 20 %/K bei stündlichen Extremen).
    Einsatzzahl lognormal, Median 450, Hamburger Größenordnung (Annahme).
    """
    lam = rate * (1 + skalierung) ** max(shift_sommer, 0.0)
    n = rng.poisson(lam)
    tage = rng.integers(120, 273, size=n)
    # Größe der Lage wächst halb so schnell wie die Häufigkeit (Annahme)
    eins = rng.lognormal(np.log(450), 0.7, size=n) * (1 + skalierung) ** (0.5 * max(shift_sommer, 0.0))
    return sorted(zip(tage.tolist(), eins.tolist()))
