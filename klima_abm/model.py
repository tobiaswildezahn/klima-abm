"""HamburgModell: ein simuliertes Jahr Bevölkerungsschutz unter Klimagefahren."""
from __future__ import annotations

import mesa
import numpy as np

from . import data, hazards
from .agents import (Behoerde, FlutKohorte, HitzeKohorte, Katastrophenschutz, Kliniken,
                     Kuestenschutz, Pflegedienste, Rettungsdienst, Stromnetz)
from .scenarios import regional_shift

# Kalibrierte Hitze-Expositions-Wirkung (calibration.kalibriere_hitze: Grobgitter in
# results/kalibrierung.json, Feinschritt in results/kalibrierung_fein.json)
BETA = 0.034
T0 = 27.0

SCHWELLE_SEHR_SCHWER = 5.69  # MHW St. Pauli 2,19 m + 3,5 m (BSH-Klasse sehr schwere Sturmflut)
SCHWELLE_EVAK = 6.0  # Annahme: Evakuierung der Evakuierungsgebiete ab vorhergesagt 6,0 m NHN


def kohorten_hitze(cfg):
    """Bezirk × Gruppe mit Personenzahl und Grundsterberate (Daten: data.py)."""
    pflege65 = data.PFLEGEBEDUERFTIGE_2023.wert * data.ANTEIL_PFLEGE_AB65.wert
    heim_ges = data.PFLEGEBEDUERFTIGE_2023.wert * (1 - data.ANTEIL_HAEUSLICH.wert)
    haus_ges = pflege65 - heim_ges
    n80_ges = sum(v[2] for v in data.BEZIRKE.values())

    zeilen = []
    for bez, (ew, n65, n80, uhi) in data.BEZIRKE.items():
        a = n80 / n80_ges
        heim, haus = heim_ges * a, haus_ges * a
        g = {
            "u65": ew - n65,
            "65_79": (n65 - n80) - 0.2 * heim - 0.4 * haus,
            "80plus": n80 - 0.8 * heim - 0.6 * haus,
            "pflege_haus": haus,
            "heim": heim,
        }
        zeilen.append((bez, uhi, data.ALLEIN_AB65[bez] / n65, g))

    # Grundsterberaten aus Sterbefällen 2024 und Altersanteilen
    tote = data.STERBEFAELLE_2024.wert
    n_u65 = sum(z[3]["u65"] for z in zeilen)
    n_6579 = sum(z[3]["65_79"] for z in zeilen)
    n_80 = sum(z[3]["80plus"] for z in zeilen)
    rest = tote * (1 - data.ANTEIL_TOTE_U65.wert) - data.MORT_HEIM.wert * heim_ges \
        - data.MORT_PFLEGE_HAUS.wert * haus_ges
    r = rest / (n_6579 + 4 * n_80)
    mort = {"u65": tote * data.ANTEIL_TOTE_U65.wert / n_u65, "65_79": r, "80plus": 4 * r,
            "pflege_haus": data.MORT_PFLEGE_HAUS.wert, "heim": data.MORT_HEIM.wert}

    # Demografie des Horizonts
    n65_ges = sum(v[1] for v in data.BEZIRKE.values())
    f6579 = (cfg["f65"] * n65_ges - cfg["f80"] * n80_ges) / (n65_ges - n80_ges)
    faktor = {"u65": 1.0, "65_79": f6579, "80plus": cfg["f80"],
              "pflege_haus": cfg["f_pflege"], "heim": cfg["f_pflege"]}
    out = []
    for bez, uhi, allein, g in zeilen:
        for grp, n in g.items():
            al = allein if grp in ("65_79", "80plus", "pflege_haus") else 0.0
            out.append((bez, grp, n * faktor[grp], mort[grp], uhi, al))
    return out


class HamburgModell(mesa.Model):
    """Ein Jahr im Horizont eines Szenarios, Tagesschritt.

    Ablauf je Tag (feste Reihenfolge, siehe docs/ODD.md, Abschnitt Scheduling):
    Behörde warnt → Pflegedienste planen → Kohorten erleiden Hitze → Behörde bilanziert →
    Sturmflut (am Ereignistag) → Rettungsdienst → Katastrophenschutz.
    """

    def __init__(self, cfg: dict, seed: int | None = None, beta: float = BETA, t0: float = T0):
        super().__init__(rng=seed)
        self.cfg = cfg
        self.beta = beta * cfg.get("beta_scale", 1.0)
        self.t0 = t0
        shift = regional_shift(cfg)
        self.shift = shift
        self.tmax = hazards.tmax_reihe(self.rng, shift, cfg["sommer_amp"])
        n = len(self.tmax)
        heiss33 = self.tmax >= 33
        lauf = np.zeros(n, dtype=int)
        for i in range(n):
            lauf[i] = lauf[i - 1] + 1 if (heiss33[i] and i > 0) else int(heiss33[i])
        self.hitzewelle_extrem = lauf >= 3
        self.hitzetote_tag = np.zeros(n)
        self.rd_last = np.zeros(n)
        self.zusatz_rd = np.zeros(n)
        self.starkregen_tag = np.zeros(n)
        self.lagen = np.zeros(n, dtype=int)

        for tag, eins in hazards.starkregen(self.rng, cfg["sr_rate"], cfg["sr_skalierung"],
                                            shift * cfg["sommer_amp"]):
            self.starkregen_tag[tag] += eins
        self.w_max, self.flut_tag = hazards.sturmflut(self.rng, cfg["slr"], cfg["gumbel_beta"])

        # Institutionen
        self.strom = Stromnetz(self)
        self.behoerde = Behoerde(self)
        self.pflegedienst = Pflegedienste(self)
        self.kliniken = Kliniken(self)
        a65 = cfg["rd_anteil65"]
        rd_basis = data.RD_EINSAETZE_2024.wert / 365 * ((1 - a65) + a65 * cfg["f65"])
        self.rettungsdienst = Rettungsdienst(self, rd_basis)
        self.kats = Katastrophenschutz(self)
        self.kueste = Kuestenschutz(self)

        # Bevölkerung
        self.hitzekohorten = [HitzeKohorte(self, *z) for z in kohorten_hitze(cfg)]
        self.max_uhi = max(k.uhi for k in self.hitzekohorten)
        self.flutkohorten = []
        f6579 = cfg["f65"]
        for zone, (ges, n65, n80) in data.FLUTZONEN.items():
            for grp, nn in (("u65", ges - n65), ("65_79", (n65 - n80) * f6579), ("80plus", n80 * cfg["f80"])):
                self.flutkohorten.append(FlutKohorte(self, zone, grp, nn))

        self.flut = dict(evakuiert=0.0, betroffen=0.0, tote=0.0, vordeich=0.0, betreuung_fehl=0.0,
                         sehr_schwer=False, bruch=False, p_bruch=0.0, verteidigt=True, binnen=False)

    # ------------------------------------------------------------------
    def _sturmflut(self, tag):
        cfg, rng = self.cfg, self.rng
        w = self.w_max
        fc = w + rng.normal(0, 0.25)
        f = self.flut
        f["vordeich"] = sum(k.n for k in self.flutkohorten if k.zone == "Vordeichs") if w >= data.HAFENCITY_BETROFFEN_AB.wert else 0.0
        f["sehr_schwer"] = fc >= SCHWELLE_SEHR_SCHWER
        if not f["sehr_schwer"]:
            return
        self.lagen[tag] += 1
        gebunden = 0.0
        if rng.random() < 0.15:  # Binnenhochwasser/Starkregen gleichzeitig (verbundenes Ereignis)
            f["binnen"] = True
            self.starkregen_tag[tag] += 500
            gebunden = 0.4
        zonen = []
        if fc >= SCHWELLE_EVAK:
            zonen.append("Evakuierungsgebiet")
        if fc >= self.kueste.schutzhoehe - 0.3:
            zonen.append("Flutgebiet1962_rest")
        bedarf80 = sum(k.n for k in self.flutkohorten if k.zone in zonen and k.gruppe == "80plus")
        quote = min(1.0, 3_000 * cfg["vol"] / bedarf80) if bedarf80 > 0 else 1.0
        for k in self.flutkohorten:
            if k.zone in zonen:
                k.evakuieren(quote)
        f["verteidigt"] = self.kats.deichverteidigung(gebunden)
        f["bruch"] = self.kueste.belasten(w, f["verteidigt"])
        f["p_bruch"] = self.kueste.p_bruch
        if f["bruch"]:
            self.lagen[tag] += 1
            for k in self.flutkohorten:
                if k.zone == "Evakuierungsgebiet":
                    k.ueberflutet(min(1.0, 2 * cfg["flut_anteil"]))
                elif k.zone == "Flutgebiet1962_rest":
                    k.ueberflutet(cfg["flut_anteil"])
        f["evakuiert"] = sum(k.evakuiert for k in self.flutkohorten)
        f["betroffen"] = sum(k.betroffen for k in self.flutkohorten)
        f["tote"] = sum(k.tote for k in self.flutkohorten)
        bedarf = 0.5 * f["evakuiert"] + 0.25 * f["betroffen"]
        f["betreuung_fehl"] = max(0.0, bedarf - cfg["betreuung"])
        self.zusatz_rd[tag] += 0.002 * f["betroffen"] + 0.0005 * f["evakuiert"]

    def step_tag(self, tag):
        self.pflegedienst.planen(tag)
        if self.tmax[tag] + self.max_uhi > self.t0:
            for k in self.hitzekohorten:
                k.step_hitze(tag, self.tmax[tag])
            self.behoerde.hitzewellen_bilanz(tag)
        if tag == self.flut_tag:
            self._sturmflut(tag)
        self.rettungsdienst.step(tag)
        self.kats.step(tag)
        self.lagen[tag] += int(self.behoerde.warnung[tag]) + int(self.strom.ausfall_anteil[tag] > 0) \
            + int(self.starkregen_tag[tag] > 0) + int(self.rd_last[tag] > 1.0)

    def run_year(self) -> dict:
        for tag in range(len(self.tmax)):
            self.step_tag(tag)
        return self.ergebnis()

    def ergebnis(self) -> dict:
        T, cfg, rd, f = self.tmax, self.cfg, self.rettungsdienst, self.flut
        hitzetote = float(self.hitzetote_tag.sum())
        nach_gruppe = {}
        for k in self.hitzekohorten:
            nach_gruppe[k.gruppe] = nach_gruppe.get(k.gruppe, 0.0) + k.tote
        hitze_strom = int(((self.strom.ausfall_anteil > 0) & (T >= 30)).sum())
        res = dict(
            szenario=cfg["szenario"], horizont=cfg["horizont"], pfad=cfg["pfad"],
            bewaeltigung=cfg["bewaeltigung"], shift=self.shift, global_t=cfg["global_t"], slr=cfg["slr"],
            heisse_tage=int((T >= 30).sum()), tage35=int((T >= 35).sum()), tmax_max=float(T.max()),
            warntage=int(self.behoerde.warnung.sum()),
            hitzetote=hitzetote,
            **{f"hitzetote_{g}": v for g, v in nach_gruppe.items()},
            rd_ueberlasttage=rd.ueberlasttage, rd_ohne_reserve=rd.ohne_reserve,
            rd_unbedient=rd.unbedient, rd_max_folge=rd.max_folge, indirekte_tote=rd.indirekte_tote,
            kliniken_ueberlast=self.kliniken.ueberlast,
            strom_ausfaelle=len(self.strom.ereignisse), hitze_strom_tage=hitze_strom,
            starkregen_lagen=int((self.starkregen_tag > 0).sum()),
            th_rueckstandstage=self.kats.rueckstandstage, th_max_rueckstand=self.kats.max_rueckstand,
            w_max=self.w_max, sehr_schwere_sturmflut=bool(f["sehr_schwer"]), deichbruch=bool(f["bruch"]),
            p_bruch=f["p_bruch"], p_bruch_jahr=self.kueste.jahresrisiko(cfg["slr"], cfg["gumbel_beta"]),
            deich_verteidigt=bool(f["verteidigt"]), binnenhochwasser=bool(f["binnen"]),
            evakuiert=f["evakuiert"], flut_betroffen=f["betroffen"], flut_tote=f["tote"],
            vordeich_betroffen=f["vordeich"], betreuung_fehl=f["betreuung_fehl"],
            verbundtage=int((self.lagen >= 2).sum()),
            tote_gesamt=hitzetote + rd.indirekte_tote + f["tote"],
        )
        return res


def simuliere_jahr(cfg: dict, seed: int, **kw) -> dict:
    return HamburgModell(cfg, seed=seed, **kw).run_year()
