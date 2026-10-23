"""Sensitivitätsanalyse nach Morris (Elementareffekte) mit SALib.

Zwei Fragen:
  1. Unsicherheit: Welche unsicheren Modellparameter (scenarios.UNSICHER) treiben die
     Ergebnisse? Zeigt, wo Kalibrierung und Daten am meisten bringen.
  2. Hebel: Welche gestaltbaren Größen des Bevölkerungsschutzes wirken am stärksten?
     Zeigt, wo Vorsorge am meisten bringt.

Jeder Morris-Punkt wird über K Jahre mit festen Seeds gemittelt (common random numbers),
damit der Wetterzufall die Elementareffekte nicht überdeckt.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
from SALib.analyze import morris as morris_an
from SALib.sample import morris as morris_sa

from .model import simuliere_jahr
from .scenarios import UNSICHER, draw_config

HEBEL = {
    "reach":      (0.40, 0.95, "Reichweite der Hitzewarnung"),
    "eff":        (0.25, 0.60, "Wirksamkeit des Schutzverhaltens"),
    "outreach":   (0.10, 0.85, "Aufsuchende Hilfe für häuslich Pflegebedürftige"),
    "heim_kuehl": (0.20, 1.00, "Gekühlte Räume in Pflegeheimen"),
    "headroom":   (0.00, 0.25, "Reserve des Rettungsdienstes"),
    "staff":      (0.80, 1.05, "Personalfaktor Rettungsdienst und Pflege"),
    "vol":        (0.60, 1.15, "Ehrenamt und Hilfsorganisationen"),
    "reinforce":  (0.00, 0.15, "Verstärkung bei Überlast"),
    "res":        (0.20, 0.90, "KRITIS-Resilienz Strom"),
    "notstrom":   (0.20, 1.00, "Notstrom in Pflegeheimen"),
    "dike":       (7.66, 8.70, "Schutzhöhe St. Pauli (m NHN)"),
    "betreuung":  (5_000, 40_000, "Betreuungsplätze"),
}

AUSGABEN = ["hitzetote", "rd_ueberlasttage", "tote_gesamt", "p_bruch_jahr", "verbundtage"]


def _bewerten(args):
    szenario, horizont, fixed, seeds = args
    werte = []
    for s in seeds:
        rng = np.random.default_rng([int(s), 2])
        cfg = draw_config(szenario, horizont, rng, fixed=fixed)
        r = simuliere_jahr(cfg, seed=int(s))
        werte.append([r[a] for a in AUSGABEN])
    return np.mean(werte, axis=0)


def morris(parameter: dict, szenario="D", horizont=2051, r=20, k_jahre=30, seed=3,
           basis_fix: dict | None = None) -> pd.DataFrame:
    names = list(parameter)
    problem = {"num_vars": len(names), "names": names,
               "bounds": [[parameter[n][0], parameter[n][1]] for n in names]}
    X = morris_sa.sample(problem, N=r, num_levels=4, seed=seed)
    seeds = np.arange(50_000, 50_000 + k_jahre)
    basis_fix = basis_fix or {}
    jobs = [(szenario, horizont, {**basis_fix, **dict(zip(names, map(float, x)))}, seeds) for x in X]
    with ProcessPoolExecutor() as ex:
        Y = np.array(list(ex.map(_bewerten, jobs, chunksize=4)))
    zeilen = []
    for j, a in enumerate(AUSGABEN):
        y = Y[:, j]
        if a == "p_bruch_jahr":  # Bruchwahrscheinlichkeiten spannen Größenordnungen: log10
            y = np.log10(y + 1e-15)
            a = "log10_p_bruch"
        si = morris_an.analyze(problem, X, y, num_levels=4, seed=seed)
        for i, n in enumerate(names):
            zeilen.append(dict(ausgabe=a, parameter=n, mu_star=si["mu_star"][i],
                               mu=si["mu"][i], sigma=si["sigma"][i],
                               mu_star_conf=si["mu_star_conf"][i]))
    df = pd.DataFrame(zeilen)
    # normiert je Ausgabe, damit Rangfolgen vergleichbar sind
    df["mu_star_rel"] = df.groupby("ausgabe")["mu_star"].transform(lambda s: s / s.max() if s.max() > 0 else s)
    return df


def unsicherheit(**kw):
    return morris({k: v[:2] for k, v in UNSICHER.items()}, **kw)


def hebel(**kw):
    # Unsichere Parameter auf Bereichsmitte, damit nur die Hebel variieren
    mitte = {k: (v[0] + v[1]) / 2 for k, v in UNSICHER.items()}
    return morris({k: v[:2] for k, v in HEBEL.items()}, basis_fix=mitte, **kw)
