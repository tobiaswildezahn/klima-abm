"""Monte-Carlo-Experimente je Szenario und Horizont.

Jeder Lauf zieht Parameter (draw_config) und Wetter neu. Gleiche Seeds über die
Szenarien (common random numbers) machen Szenariovergleiche schärfer.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from .model import simuliere_jahr
from .scenarios import HORIZONTE, SZENARIEN, draw_config

KENNZAHLEN = [
    "hitzetote", "indirekte_tote", "flut_tote", "tote_gesamt", "heisse_tage", "tage35", "warntage",
    "rd_ueberlasttage", "rd_ohne_reserve", "rd_max_folge", "kliniken_ueberlast",
    "strom_ausfaelle", "hitze_strom_tage", "starkregen_lagen", "th_rueckstandstage",
    "w_max", "p_bruch_jahr", "evakuiert", "flut_betroffen", "vordeich_betroffen", "betreuung_fehl",
    "verbundtage", "hitzetote_u65", "hitzetote_65_79", "hitzetote_80plus", "hitzetote_pflege_haus",
    "hitzetote_heim",
]
WAHRSCHEINLICHKEITEN = {
    "P_hitzetote_ueber_500": lambda d: d["hitzetote"] > 500,
    "P_sehr_schwere_sturmflut": lambda d: d["sehr_schwere_sturmflut"],
    "P_deichbruch_gezogen": lambda d: d["deichbruch"],
    "P_rd_ueberlast_7_tage": lambda d: d["rd_max_folge"] >= 7,
    "P_hitze_mit_stromausfall": lambda d: d["hitze_strom_tage"] > 0,
}


def _zelle(args):
    szenario, horizont, seeds, fixed = args
    out = []
    for s in seeds:
        rng = np.random.default_rng([int(s), 1])
        cfg = draw_config(szenario, horizont, rng, fixed=fixed)
        out.append(simuliere_jahr(cfg, seed=int(s)))
    return out


def lauf(szenario, horizont, n, seed0=0, fixed=None, prozesse=None, chunk=50) -> pd.DataFrame:
    seeds = np.arange(seed0, seed0 + n)
    teile = [(szenario, horizont, seeds[i:i + chunk], fixed) for i in range(0, n, chunk)]
    with ProcessPoolExecutor(prozesse) as ex:
        res = [r for teil in ex.map(_zelle, teile) for r in teil]
    df = pd.DataFrame(res)
    df["seed"] = seeds
    return df


def alle_laeufe(n=1000) -> pd.DataFrame:
    teile = [lauf("IST", 2026, n)]
    for h in HORIZONTE[1:]:
        for s in SZENARIEN:
            teile.append(lauf(s, h, n))
    return pd.concat(teile, ignore_index=True)


def zusammenfassen(df: pd.DataFrame) -> pd.DataFrame:
    zeilen = []
    for (s, h), g in df.groupby(["szenario", "horizont"], sort=False):
        z = {"szenario": s, "horizont": h, "n": len(g)}
        for k in KENNZAHLEN:
            x = g[k].astype(float)
            z[f"{k}_mittel"] = x.mean()
            z[f"{k}_se"] = x.std(ddof=1) / np.sqrt(len(x))
            z[f"{k}_p05"] = x.quantile(0.05)
            z[f"{k}_median"] = x.median()
            z[f"{k}_p95"] = x.quantile(0.95)
        for name, f in WAHRSCHEINLICHKEITEN.items():
            z[name] = float(f(g).mean())
        # Deichbruch: über die Wasserstandsverteilung integriert, gemittelt über die Parameter
        z["P_deichbruch"] = float(g["p_bruch_jahr"].mean())
        z["deichbruch_wiederkehr_jahre"] = 1 / z["P_deichbruch"] if z["P_deichbruch"] > 0 else np.inf
        zeilen.append(z)
    return pd.DataFrame(zeilen)


def achsenzerlegung(zus: pd.DataFrame, kennzahlen=("hitzetote_mittel", "rd_ueberlasttage_mittel",
                                                      "tote_gesamt_mittel", "P_deichbruch",
                                                      "verbundtage_mittel")) -> pd.DataFrame:
    """2×2-Zerlegung der Szenarien A–D: Haupteffekt Klimapfad und Haupteffekt Bewältigung.

    Pfad-Effekt = Mittel(B, D) − Mittel(A, C); Bewältigungs-Effekt = Mittel(C, D) − Mittel(A, B).
    Prüft die These des Szenariopapiers: bis 2036 dominiert die Vorsorge, ab 2051 der Pfad.
    """
    zeilen = []
    for h, g in zus[zus.szenario.isin(list("ABCD"))].groupby("horizont"):
        v = g.set_index("szenario")
        for k in kennzahlen:
            pfad = (v.loc["B", k] + v.loc["D", k] - v.loc["A", k] - v.loc["C", k]) / 2
            bew = (v.loc["C", k] + v.loc["D", k] - v.loc["A", k] - v.loc["B", k]) / 2
            wechsel = (v.loc["D", k] - v.loc["C", k] - v.loc["B", k] + v.loc["A", k]) / 2
            summe = abs(pfad) + abs(bew) + abs(wechsel)
            zeilen.append(dict(horizont=h, kennzahl=k, effekt_pfad=pfad, effekt_bewaeltigung=bew,
                               wechselwirkung=wechsel,
                               anteil_pfad=abs(pfad) / summe if summe else np.nan,
                               anteil_bewaeltigung=abs(bew) / summe if summe else np.nan))
    return pd.DataFrame(zeilen)


def konvergenz(df: pd.DataFrame, kennzahl="hitzetote") -> pd.DataFrame:
    """Laufender Mittelwert und relativer Standardfehler je Zelle bei wachsendem n."""
    zeilen = []
    for (s, h), g in df.groupby(["szenario", "horizont"], sort=False):
        x = g[kennzahl].to_numpy(float)
        for n in (50, 100, 200, 400, 700, len(x)):
            if n <= len(x):
                y = x[:n]
                zeilen.append(dict(szenario=s, horizont=h, n=n, mittel=y.mean(),
                                   rel_se=y.std(ddof=1) / np.sqrt(n) / max(y.mean(), 1e-9)))
    return pd.DataFrame(zeilen)
