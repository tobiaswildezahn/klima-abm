"""Kalibrierung: Wettergenerator, Hitze-Expositions-Wirkung, Sturmflut-Anker.

Aufruf: python -m klima_abm.calibration  → schreibt results/kalibrierung.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from concurrent.futures import ProcessPoolExecutor

from . import data, hazards
from .model import HamburgModell
from .scenarios import draw_config

# Schutzniveau vor dem Hitzeaktionsplan (Kalibrierzeitraum Huber et al. 1993–2015; Annahme)
VOR_HAP = dict(reach=0.30, eff=0.35, outreach=0.10, heim_kuehl=0.20, notstrom=0.20)


def kalibriere_wetter(n=4000, seed=1) -> dict:
    rng = np.random.default_rng(seed)
    T = np.array([hazards.tmax_reihe(rng, 0.0) for _ in range(n)])
    mx = T.max(1)
    return dict(
        heisse_tage_mittel=float((T >= 30).sum(1).mean()), ziel_heisse_tage=data.HEISSE_TAGE_1991_2020.wert,
        tage35_mittel=float((T >= 35).sum(1).mean()),
        jahresmax_30j=float(np.quantile(mx, 1 - 1 / 30)),
        juli_tmax=float(T[:, 181:212].mean()), januar_tmax=float(T[:, :31].mean()),
    )


def _jahre(szenario, n, seed, fixed):
    rng = np.random.default_rng(seed)
    cfgs = [draw_config(szenario, 2026, rng, fixed=fixed) for _ in range(n)]
    return cfgs


def hitzetote(cfgs, beta, t0, seeds):
    out = []
    for c, s in zip(cfgs, seeds):
        m = HamburgModell(c, seed=int(s), beta=beta, t0=t0)
        r = m.run_year()
        out.append((r["hitzetote"], r["heisse_tage"], r["tage35"]))
    return np.array(out)


def _punkt(args):
    cfg1, cfg2, seeds1, seeds2, b, t0 = args
    return hitzetote(cfg1, b, t0, seeds1), hitzetote(cfg2, b, t0, seeds2)


def kalibriere_hitze(n=300, seed=7, betas=None, t0s=None) -> dict:
    """Gitter über (beta, T0) mit zwei Zielen.

    Ziel 1: Klima 1991–2020, Schutz vor HAP → mittlere Hitzetote = 0,81 % der Sterbefälle
            (Huber et al. 2020).
    Ziel 2: Ist 2026 mit HAP, Jahre wie Sommer 2026 (≥ 11 heiße Tage, ≥ 3 Tage ≥ 35 °C)
            → RKI-Schätzung 2026 anteilig für Hamburg.
    Fehlermaß: Summe der quadrierten relativen Abweichungen.
    """
    betas = betas if betas is not None else np.round(np.arange(0.02, 0.101, 0.01), 3)
    t0s = t0s if t0s is not None else np.arange(24.0, 28.1, 1.0)
    ziel1 = data.HITZETOTE_ANTEIL_1993_2015.wert * data.STERBEFAELLE_2024.wert
    ziel2 = data.HITZETOTE_DE_2026.wert * data.ANTEIL_HH_AN_DE.wert
    fix_basis = dict(global_t=1.4 - 0.62 / 1.7, reg_faktor=1.7, sommer_amp=1.0, beta_scale=1.0, eff_scale=1.0,
                     **VOR_HAP)  # global_t so, dass shift = 0 (Klima 1991–2020)
    cfg1 = _jahre("IST", n, seed, fix_basis)
    cfg2 = _jahre("IST", n * 3, seed + 1, dict(beta_scale=1.0, eff_scale=1.0, sommer_amp=1.0))
    seeds1 = np.arange(n) + 10_000
    seeds2 = np.arange(n * 3) + 20_000
    gitter = []
    punkte = [(float(b), float(t0)) for b in betas for t0 in t0s]
    with ProcessPoolExecutor() as ex:
        erg = list(ex.map(_punkt, [(cfg1, cfg2, seeds1, seeds2, b, t0) for b, t0 in punkte]))
    for (b, t0), (r1, r2) in zip(punkte, erg):
            wie26 = (r2[:, 1] >= 11) & (r2[:, 2] >= 3)
            m1 = r1[:, 0].mean()
            m2 = r2[wie26, 0].mean() if wie26.any() else np.nan
            fehler = ((m1 - ziel1) / ziel1) ** 2 + ((m2 - ziel2) / ziel2) ** 2
            gitter.append(dict(beta=float(b), t0=float(t0), mittel_1991_2020=float(m1),
                               wie_2026=float(m2), n_wie_2026=int(wie26.sum()),
                               ist_mittel=float(r2[:, 0].mean()), fehler=float(fehler)))
    best = min(gitter, key=lambda g: g["fehler"])
    return dict(ziel_1991_2020=ziel1, ziel_wie_2026=ziel2, bestes=best, gitter=gitter)


def gumbel_check() -> dict:
    b = hazards.GUMBEL_BETA_REF
    mu = hazards.gumbel_mu(b)
    p5 = 1 - np.exp(-np.exp(-(5.0 - mu) / b))
    rp = lambda x: 1 / (1 - np.exp(-np.exp(-(x - mu) / b)))
    return dict(mu=mu, beta=b, p_ueber_5m=float(p5), wiederkehr_645=float(rp(6.45)),
                wiederkehr_730=float(rp(7.30)), wiederkehr_810=float(rp(8.10)))


def gev_check(xi=0.1, schutz=(7.66, 8.10, 8.70), slr=(0.0, 0.4, 1.0)) -> dict:
    """Prüft, wie stark das Bruchrisiko an der Annahme eines dünnen Gumbel-Rands hängt.

    GEV mit Formparameter xi > 0 (schwerer Rand), angepasst an dieselben zwei Anker.
    Ausgegeben wird die Wiederkehrzeit eines Wasserstands Schutzhöhe + 0,5 m
    (Mitte der Versagenskurve) bei verschiedenen Meeresspiegelständen.
    """
    from scipy.optimize import brentq
    from scipy.stats import genextreme, gumbel_r

    def fit(xi):
        c = -xi  # scipy-Konvention
        def gl(s):
            mu = 5.0 - genextreme.ppf(0.65, c, loc=0, scale=s)
            return genextreme.ppf(1 - 1 / 65, c, loc=mu, scale=s) - 6.45
        s = brentq(gl, 0.05, 2.0)
        return c, 5.0 - genextreme.ppf(0.65, c, loc=0, scale=s), s

    c, mu, s = fit(xi)
    gmu, gb = hazards.gumbel_mu(hazards.GUMBEL_BETA_REF), hazards.GUMBEL_BETA_REF
    zeilen = []
    for h in schutz:
        for d in slr:
            x = h + 0.5 - d
            zeilen.append(dict(schutzhoehe=h, slr=d,
                               wiederkehr_gumbel=float(1 / gumbel_r.sf(x, gmu, gb)),
                               wiederkehr_gev=float(1 / genextreme.sf(x, c, mu, s))))
    return dict(xi=xi, gev_mu=float(mu), gev_scale=float(s), tabelle=zeilen)


if __name__ == "__main__":
    out = dict(wetter=kalibriere_wetter(), sturmflut=gumbel_check(), gev=gev_check(), hitze=kalibriere_hitze())
    Path("results").mkdir(exist_ok=True)
    Path("results/kalibrierung.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps({k: (v if k != "hitze" else v["bestes"]) for k, v in out.items()}, indent=2, ensure_ascii=False))
