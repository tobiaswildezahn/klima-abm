import numpy as np
import pytest

from klima_abm import data, hazards
from klima_abm.model import HamburgModell, kohorten_hitze, simuliere_jahr
from klima_abm.scenarios import SZENARIEN, draw_config, regional_shift


def cfg(s="IST", h=2026, seed=0, **fixed):
    return draw_config(s, h, np.random.default_rng(seed), fixed=fixed)


def test_kohorten_summen_stimmen_mit_daten():
    k = kohorten_hitze(cfg(f65=1.0, f80=1.0, f_pflege=1.0))
    ew = sum(z[2] for z in k)
    assert ew == pytest.approx(sum(v[0] for v in data.BEZIRKE.values()), rel=1e-6)
    assert all(z[2] > 0 for z in k)


def test_grundsterblichkeit_reproduziert_sterbefaelle():
    k = kohorten_hitze(cfg(f65=1.0, f80=1.0, f_pflege=1.0))
    tote = sum(z[2] * z[3] for z in k)
    assert tote == pytest.approx(data.STERBEFAELLE_2024.wert, rel=0.01)


def test_wettergenerator_heisse_tage():
    rng = np.random.default_rng(1)
    T = np.array([hazards.tmax_reihe(rng, 0.0) for _ in range(1500)])
    assert (T >= 30).sum(1).mean() == pytest.approx(data.HEISSE_TAGE_1991_2020.wert, abs=0.8)


def test_gumbel_anker():
    b = hazards.GUMBEL_BETA_REF
    mu = hazards.gumbel_mu(b)
    p5 = 1 - np.exp(-np.exp(-(5.0 - mu) / b))
    assert p5 == pytest.approx(0.35, abs=0.01)
    rp645 = 1 / (1 - np.exp(-np.exp(-(6.45 - mu) / b)))
    assert 50 < rp645 < 80


def test_regionale_verschiebung_null_im_referenzklima():
    c = cfg(global_t=1.4 - 0.62 / 1.7, reg_faktor=1.7)
    assert regional_shift(c) == pytest.approx(0.0, abs=1e-9)


def test_reproduzierbar():
    c = cfg(seed=3)
    assert simuliere_jahr(c, seed=11) == simuliere_jahr(c, seed=11)


@pytest.mark.parametrize("s", SZENARIEN)
def test_alle_szenarien_laufen(s):
    for h in (2036, 2051, 2076):
        r = simuliere_jahr(cfg(s, h, seed=5), seed=5)
        assert r["hitzetote"] >= 0 and 0 <= r["p_bruch"] <= 1


def test_mehr_hitze_mehr_tote():
    """Monotonie: wärmeres Klima erhöht bei gleichem Zufall die Hitzetoten."""
    kalt = np.mean([simuliere_jahr(cfg(seed=i, global_t=1.4), seed=i)["hitzetote"] for i in range(40)])
    warm = np.mean([simuliere_jahr(cfg(seed=i, global_t=2.4), seed=i)["hitzetote"] for i in range(40)])
    assert warm > kalt


def test_vorsorge_senkt_hitzetote():
    hoch = dict(reach=0.95, eff=0.6, outreach=0.9, heim_kuehl=1.0)
    niedrig = dict(reach=0.3, eff=0.2, outreach=0.1, heim_kuehl=0.1)
    a = np.mean([simuliere_jahr(cfg(seed=i, **hoch), seed=i)["hitzetote"] for i in range(40)])
    b = np.mean([simuliere_jahr(cfg(seed=i, **niedrig), seed=i)["hitzetote"] for i in range(40)])
    assert a < b


def test_hoeherer_deich_senkt_bruchrisiko():
    p = lambda d: simuliere_jahr(cfg(seed=1, dike=d, slr=0.5), seed=1)["p_bruch_jahr"]
    assert p(8.6) < p(7.4)


def test_jahresrisiko_passt_zu_gumbel_ohne_unschaerfe():
    """Bei sehr scharfer Versagenskurve entspricht das Bruchrisiko der Überschreitung von Schutzhöhe + 0,5 m."""
    from scipy.stats import gumbel_r
    c = cfg(seed=2, dike=8.10, slr=0.0, deich_sigma=0.01, gumbel_beta=hazards.GUMBEL_BETA_REF)
    p = simuliere_jahr(c, seed=2)["p_bruch_jahr"]
    soll = gumbel_r.sf(8.60, hazards.gumbel_mu(hazards.GUMBEL_BETA_REF), hazards.GUMBEL_BETA_REF)
    assert p == pytest.approx(soll, rel=0.05)
