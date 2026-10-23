"""Agenten des Hamburger Bevölkerungsschutz-Modells.

Bevölkerung ist als Kohorten-Agenten abgebildet (Bezirk × Gruppe bzw. Flutzone ×
Altersgruppe). Ein Kohorten-Agent steht für viele Menschen mit gleicher Exposition
und gleichem Verhalten; sein Zustand (Befolgung, Lernen, Warnmüdigkeit) ist
dynamisch. Institutionen sind Einzelagenten mit Kapazitäten und Entscheidungsregeln.
"""
from __future__ import annotations

import math

import mesa
import numpy as np
from scipy.stats import norm

# Relative Hitzeempfindlichkeit je Gruppe (Literatur: Risiko steigt mit Alter und
# Pflegebedarf; Werte sind Setzung, gemeinsam mit beta kalibriert)
EMPFINDLICHKEIT = {"u65": 0.5, "65_79": 1.0, "80plus": 1.3, "pflege_haus": 1.5, "heim": 1.3}
# Ausgangsbefolgung von Hitzeschutzempfehlungen (Annahme)
BEFOLGUNG0 = {"u65": 0.50, "65_79": 0.60, "80plus": 0.55, "pflege_haus": 0.45, "heim": 0.0}


class HitzeKohorte(mesa.Agent):
    """Bevölkerungsgruppe eines Bezirks unter Hitzebelastung."""

    def __init__(self, model, bezirk, gruppe, n, mort, uhi, allein):
        super().__init__(model)
        self.bezirk, self.gruppe, self.n = bezirk, gruppe, n
        self.mort = mort  # jährliche Grundsterberate
        self.uhi = uhi
        self.allein = allein  # Anteil Alleinlebender (Erreichbarkeit)
        self.befolgung = BEFOLGUNG0[gruppe]
        self.warntage = 0
        self.tote = 0.0

    def schutzanteil(self, tag) -> float:
        m, cfg = self.model, self.model.cfg
        if not m.behoerde.warnung[tag]:
            return 0.0
        reach = cfg["reach"] * (1 - 0.3 * self.allein)
        if self.gruppe == "heim":
            kuehl = cfg["heim_kuehl"]
            ausfall = m.strom.ausfall_anteil[tag]
            if ausfall > 0:
                kuehl *= 1 - ausfall * (1 - cfg["notstrom"])
            return kuehl
        eigen = reach * self.befolgung
        if self.gruppe == "pflege_haus":
            dek = m.pflegedienst.deckung[tag]
            return dek + (1 - dek) * 0.5 * eigen
        return eigen

    def step_hitze(self, tag, t_station):
        m, cfg = self.model, self.model.cfg
        t_eff = t_station + self.uhi
        if t_eff <= m.t0:
            return
        if m.behoerde.warnung[tag]:
            self.warntage += 1
            if self.warntage > 15:  # Warnmüdigkeit
                self.befolgung = max(0.2, self.befolgung - 0.01)
        rr = math.exp(m.beta * EMPFINDLICHKEIT[self.gruppe] * (t_eff - m.t0))
        mult = 1.0
        ausfall = m.strom.ausfall_anteil[tag]
        if ausfall > 0 and self.gruppe != "heim":
            mult += ausfall * 0.5  # ohne Strom keine Ventilatoren, Kühlung, Aufzüge
        wirk = min(0.9, cfg["eff"] * cfg["eff_scale"])
        ueber = self.n * self.mort / 365 * (rr - 1) * mult * (1 - wirk * self.schutzanteil(tag))
        self.tote += ueber
        m.hitzetote_tag[tag] += ueber

    def lernen(self):
        """Nach einer Hitzewelle mit sichtbaren Folgen steigt die Befolgung."""
        if self.gruppe != "heim":
            self.befolgung = min(0.95, self.befolgung + 0.05)


class FlutKohorte(mesa.Agent):
    """Bevölkerungsgruppe in einer sturmflutgefährdeten Zone."""

    ALTERSFAKTOR = {"u65": 1.0, "65_79": 2.0, "80plus": 4.0}

    def __init__(self, model, zone, gruppe, n):
        super().__init__(model)
        self.zone, self.gruppe, self.n = zone, gruppe, n
        self.evakuiert = 0.0
        self.betroffen = 0.0
        self.tote = 0.0

    def evakuieren(self, transportquote):
        p = self.model.cfg["evak_compliance"]
        if self.gruppe == "80plus":
            p *= transportquote
        self.evakuiert = self.n * p

    def ueberflutet(self, anteil):
        cfg = self.model.cfg
        self.betroffen = self.n * anteil
        verbleibend = self.betroffen * (1 - self.evakuiert / self.n)
        self.tote = verbleibend * cfg["flut_mort"] * self.ALTERSFAKTOR[self.gruppe]


class Behoerde(mesa.Agent):
    """Katastrophenschutzbehörde und Gesundheitsbehörde: Warnung, Anordnung, Lage."""

    def __init__(self, model):
        super().__init__(model)
        n = len(model.tmax)
        fc = model.tmax + model.rng.normal(0, 1.0, n)  # Vorhersagefehler 1 K
        nxt = np.r_[fc[1:], fc[-1]]
        self.warnung = ((fc >= 30) & (nxt >= 30)) | (fc >= 32)
        self.lernsignal_gegeben = set()

    def hitzewellen_bilanz(self, tag):
        """Rückkopplung: nach einer Welle mit hoher Sterblichkeit lernen die Kohorten."""
        start = max(0, tag - 6)
        tote_woche = float(self.model.hitzetote_tag[start:tag + 1].sum())
        if tote_woche > 30 and (tag // 14) not in self.lernsignal_gegeben:
            self.lernsignal_gegeben.add(tag // 14)
            for k in self.model.hitzekohorten:
                k.lernen()


class Pflegedienste(mesa.Agent):
    """Ambulante Pflege: aufsuchende Hitzehilfe für häuslich Pflegebedürftige."""

    def __init__(self, model):
        super().__init__(model)
        self.deckung = np.zeros(len(model.tmax))

    def planen(self, tag):
        m, cfg = self.model, self.model.cfg
        if not m.behoerde.warnung[tag]:
            return
        ausfall = 0.01 * max(0.0, m.tmax[tag] - 30)  # hitzebedingter Personalausfall
        self.deckung[tag] = min(1.0, cfg["outreach"] * cfg["staff"] * (1 - ausfall))


class Rettungsdienst(mesa.Agent):
    """Rettungsdienst der Feuerwehr Hamburg und Hilfsorganisationen."""

    def __init__(self, model, basis):
        super().__init__(model)
        self.basis = basis
        self.ermuedung = 0.0
        self.ueberlast_vortag = False
        self.ueberlasttage = 0
        self.ohne_reserve = 0
        self.unbedient = 0.0
        self.max_folge = 0
        self._folge = 0
        self.indirekte_tote = 0.0

    def step(self, tag):
        m, cfg = self.model, self.model.cfg
        t = m.tmax[tag]
        nachfrage = self.basis * (1 + m.rng.normal(0, 0.03))
        nachfrage *= math.exp(math.log(1 + cfg["rd_hitze"]) / 5 * max(0.0, t - 25))
        if m.hitzewelle_extrem[tag]:
            nachfrage *= 1.10
        nachfrage *= 1 + 0.10 * m.strom.ausfall_anteil[tag]
        if m.starkregen_tag[tag] > 0:
            nachfrage *= 1.03
        nachfrage += m.zusatz_rd[tag]

        abwesend = 0.01 * max(0.0, t - 30)
        kap = self.basis * (1 + cfg["headroom"]) * cfg["staff"] * (1 - self.ermuedung) * (1 - abwesend)
        kap *= m.kliniken.uebergabe_faktor
        if self.ueberlast_vortag:
            kap += self.basis * cfg["reinforce"] * cfg["vol"]

        last = nachfrage / kap
        ueber = max(0.0, nachfrage - kap)
        self.unbedient += ueber
        self.indirekte_tote += ueber * cfg["p_tod_verzug"]
        m.rd_last[tag] = last
        if ueber > 0:
            self.ueberlasttage += 1
            self._folge += 1
            self.max_folge = max(self.max_folge, self._folge)
            if last > 1.05:  # nur deutliche Überlast ermüdet (Annahme)
                self.ermuedung = min(0.05, self.ermuedung + 0.01)
        else:
            self._folge = 0
            self.ermuedung *= 0.7
        if last > 0.95:
            self.ohne_reserve += 1
        self.ueberlast_vortag = ueber > 0
        m.kliniken.melden(nachfrage / self.basis)


class Kliniken(mesa.Agent):
    """Notaufnahmen: hohe Last verlängert Übergabezeiten und bindet Rettungsmittel."""

    def __init__(self, model):
        super().__init__(model)
        self.uebergabe_faktor = 1.0
        self.ueberlast = 0
        self._hoch = 0

    def melden(self, rel_last):
        self._hoch = self._hoch + 1 if rel_last > 1.12 else 0
        if self._hoch >= 2:
            self.ueberlast += 1
            self.uebergabe_faktor = 0.95
        else:
            self.uebergabe_faktor = 1.0


class Stromnetz(mesa.Agent):
    """KRITIS Strom: großflächige Ausfälle durch Hitze-Last und Sabotage (U1)."""

    def __init__(self, model):
        super().__init__(model)
        cfg, rng, T = model.cfg, model.rng, model.tmax
        n = len(T)
        self.ausfall_anteil = np.zeros(n)
        self.ereignisse = []
        res = cfg["res"]
        p = 0.004 * cfg["strom_hitze"] * np.clip(T - 30, 0, None) * (1 - 0.7 * res)
        heiss = np.nonzero(rng.random(n) < p)[0]
        for d in heiss:
            self._ausfall(d, rng.uniform(0.03, 0.15), "Hitze", res)
        for d in rng.integers(0, n, rng.poisson(cfg["sabotage_rate"])):
            self._ausfall(int(d), rng.uniform(0.05, 0.30), "Sabotage", res)

    def _ausfall(self, d, anteil, ursache, res):
        dauer = 1 if self.model.rng.random() < 0.4 + 0.5 * res else 2
        for k in range(dauer):
            if d + k < len(self.ausfall_anteil):
                self.ausfall_anteil[d + k] = max(self.ausfall_anteil[d + k], anteil)
        self.ereignisse.append((d, ursache, anteil, dauer))


class Katastrophenschutz(mesa.Agent):
    """Feuerwehr (BF/FF), THW und Hilfsorganisationen: technische Hilfe und Deichverteidigung."""

    def __init__(self, model):
        super().__init__(model)
        cfg = model.cfg
        self.th_kapazitaet = 350 * cfg["vol"] * cfg["staff"]  # Sondereinsätze je Tag (Annahme)
        self.rueckstand = 0.0
        self.rueckstandstage = 0
        self.max_rueckstand = 0.0
        # Kräftepool für Deichverteidigung (BF anteilig, FF, THW/HiOrg; Annahme)
        self.pool = 3_652 * 0.35 * cfg["staff"] + 2_742 * 0.6 * cfg["vol"] + 2_000 * cfg["vol"]

    def step(self, tag):
        neu = self.model.starkregen_tag[tag]
        self.rueckstand = max(0.0, self.rueckstand + neu - self.th_kapazitaet)
        if self.rueckstand > 0:
            self.rueckstandstage += 1
        self.max_rueckstand = max(self.max_rueckstand, self.rueckstand)

    def deichverteidigung(self, gebunden_anteil) -> bool:
        """True, wenn die benötigten 1 500 Kräfte verfügbar sind."""
        return self.pool * (1 - gebunden_anteil) >= 1_500


class Kuestenschutz(mesa.Agent):
    """Öffentlicher Hochwasserschutz: Schutzhöhe und Versagensrisiko der Deichlinie."""

    def __init__(self, model):
        super().__init__(model)
        self.schutzhoehe = model.cfg["dike"]
        self.bruch = False
        self.p_bruch = 0.0

    def jahresrisiko(self, slr: float, beta: float) -> float:
        """Jährliche Bruchwahrscheinlichkeit, integriert über die Verteilung des
        Jahreshöchstwasserstands (verteidigte Deichlinie). Glatter Schätzer, weil seltene
        Brüche mit einigen tausend gezogenen Jahren nicht auflösbar sind."""
        from .hazards import gumbel_mu
        cfg = self.model.cfg
        mu = gumbel_mu(beta) + slr
        w = np.linspace(mu - 2, mu + 40 * beta, 4000)
        z = (w - mu) / beta
        pdf = np.exp(-z - np.exp(-z)) / beta
        p = norm.cdf((w - (self.schutzhoehe + 0.5)) / cfg["deich_sigma"])
        return float(np.trapezoid(pdf * p, w))

    def belasten(self, w, verteidigt: bool):
        cfg = self.model.cfg
        reserve = 0.5 - (0 if verteidigt else 0.15)
        self.p_bruch = float(norm.cdf((w - (self.schutzhoehe + reserve)) / cfg["deich_sigma"]))
        self.bruch = self.model.rng.random() < self.p_bruch
        return self.bruch
