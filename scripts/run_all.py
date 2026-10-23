"""Alle Experimente: Monte Carlo, Achsenzerlegung, Konvergenz, Sensitivität, Abbildungen.

Aufruf: python scripts/run_all.py [--n 1000] [--morris-r 20]
Ergebnisse landen in results/.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from klima_abm import experiments, sensitivity  # noqa: E402
from klima_abm.scenarios import SZENARIO_NAMEN  # noqa: E402

RES = ROOT / "results"
FIG = RES / "figures"
FARBEN = {"A": "#2a9d8f", "B": "#e9c46a", "C": "#8ab17d", "D": "#e76f51", "E": "#6d597a", "IST": "#555555"}


def trichter(zus, kennzahl, titel, datei, ylabel):
    fig, ax = plt.subplots(figsize=(7, 4.2), dpi=150)
    ist = zus[zus.szenario == "IST"].iloc[0]
    for s in "ABCDE":
        g = zus[zus.szenario == s].sort_values("horizont")
        x = [2026] + g.horizont.tolist()
        m = [ist[f"{kennzahl}_median"]] + g[f"{kennzahl}_median"].tolist()
        lo = [ist[f"{kennzahl}_p05"]] + g[f"{kennzahl}_p05"].tolist()
        hi = [ist[f"{kennzahl}_p95"]] + g[f"{kennzahl}_p95"].tolist()
        ax.plot(x, m, color=FARBEN[s], lw=2, label=SZENARIO_NAMEN[s])
        ax.fill_between(x, lo, hi, color=FARBEN[s], alpha=0.12)
    ax.set_xticks([2026, 2036, 2051, 2076])
    ax.set_title(titel, loc="left", fontsize=11)
    ax.set_ylabel(ylabel)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(FIG / datei)
    plt.close(fig)


def morris_bild(df, ausgabe, titel, datei, labels=None):
    g = df[df.ausgabe == ausgabe].sort_values("mu_star")
    fig, ax = plt.subplots(figsize=(6.5, 4.5), dpi=150)
    namen = [labels.get(p, p) if labels else p for p in g.parameter]
    ax.barh(namen, g.mu_star, xerr=g.mu_star_conf, color="#4c6a92")
    ax.set_title(titel, loc="left", fontsize=11)
    ax.set_xlabel("μ* (mittlerer absoluter Elementareffekt)")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIG / datei)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--morris-r", type=int, default=20)
    ap.add_argument("--morris-k", type=int, default=30)
    a = ap.parse_args()
    FIG.mkdir(parents=True, exist_ok=True)

    t = time.time()
    df = experiments.alle_laeufe(a.n)
    df.to_csv(RES / "mc_laeufe.csv.gz", index=False)
    zus = experiments.zusammenfassen(df)
    zus.to_csv(RES / "zusammenfassung.csv", index=False)
    achsen = experiments.achsenzerlegung(zus)
    achsen.to_csv(RES / "achsenzerlegung.csv", index=False)
    konv = experiments.konvergenz(df)
    konv.to_csv(RES / "konvergenz.csv", index=False)
    print(f"Monte Carlo: {len(df)} Jahre in {time.time() - t:.0f} s")

    trichter(zus, "hitzetote", "Hitzebedingte Übersterblichkeit je Jahr (Median, 5–95 %)", "trichter_hitzetote.png", "Todesfälle")
    trichter(zus, "rd_ueberlasttage", "Tage mit Überlast im Rettungsdienst je Jahr", "trichter_rd_ueberlast.png", "Tage")
    trichter(zus, "verbundtage", "Tage mit zwei oder mehr gleichzeitigen Lagen", "trichter_verbundtage.png", "Tage")

    t = time.time()
    un = sensitivity.unsicherheit(r=a.morris_r, k_jahre=a.morris_k)
    un.to_csv(RES / "morris_unsicherheit.csv", index=False)
    he = sensitivity.hebel(r=a.morris_r, k_jahre=a.morris_k)
    he.to_csv(RES / "morris_hebel.csv", index=False)
    print(f"Morris: {time.time() - t:.0f} s")
    morris_bild(un, "tote_gesamt", "Unsicherheit: Treiber der Todesfälle (D, 2051)", "morris_unsicherheit_tote.png")
    labels = {k: v[2] for k, v in sensitivity.HEBEL.items()}
    morris_bild(he, "hitzetote", "Hebel: Wirkung auf Hitzetote (D, 2051)", "morris_hebel_hitzetote.png", labels)
    morris_bild(un, "log10_p_bruch", "Unsicherheit: Treiber des Deichbruchrisikos (log10, D, 2051)", "morris_unsicherheit_bruch.png")
    morris_bild(he, "rd_ueberlasttage", "Hebel: Wirkung auf RD-Überlasttage (D, 2051)", "morris_hebel_rd.png", labels)

    meta = dict(n_je_zelle=a.n, morris_r=a.morris_r, morris_k=a.morris_k)
    (RES / "lauf_meta.json").write_text(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
