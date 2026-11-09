"""04 — Kesikli olay simülasyonu (SimPy): Hat-1 için "ne olursa?" analizi.

Model
    Kesim (TST) → CNC Torna (2 paralel) → CNC Freze (FRZ) → Isıl İşlem (ISL) → Taşlama (TSL)
    Lot (iş emri) bazlı akış; her istasyonun önünde FIFO kuyruk.
    Ayar süresi ürün ailesi değişimine bağlı, arızalar çalışma süresine bağlı (MTBF/MTTR),
    performans kaybı ve hurda istasyon bazında. Tüm parametreler MES verisinden kestirilir
    (02_analiz.py → ciktilar/tablolar/sim_parametreleri.json).
    Zaman birimi: çalışma dakikası (3 vardiya × 450 dk = 1.350 dk/gün, 6 gün = 1 hafta).

Deneyler
    1) Kapasite testi: CONWIP ile hat sürekli dolu tutulur → azami haftalık çıktı ve darboğaz.
    2) Talep testi: önümüzdeki 6 ayın tahmini talep hızında Poisson iş emri gelişi →
       tedarik süresi, yarı mamul (WIP), 5 gün içinde tamamlanan iş emri oranı.

Senaryo iyileşme oranları pilot ayında (Ekim 2026) ölçülen değerlerden alınır.
"""
from __future__ import annotations

import json
import math
import textwrap
from collections import defaultdict
from dataclasses import dataclass, field

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import simpy
from matplotlib.colors import LinearSegmentedColormap
from scipy import stats

from grafik_stili import (DARBOGAZ_RENK, DURUM, EKSEN, GRI_SERI, IKINCIL, MAVI, MAVI_RAMPA, MUREKKEP, SARI, SUNUM,
                          YUZEY, baslik, kaydet, kaynak_notu, sayi_ekseni, stil_uygula)
from ortak import (PILOT_BASLANGIC, TABLO, TOHUM, URUNLER, calisma_gunu_sayisi, ozet_yaz, sayi, yuzde)
from veri_yukle import oku

stil_uygula()
PARAM = json.loads((TABLO / "sim_parametreleri.json").read_text(encoding="utf-8"))
AILE = URUNLER.set_index("UrunID")["UrunAilesi"].to_dict()
GUN_DK, HAFTA_DK = 1350, 6 * 1350
ISINMA_HAFTA, OLCUM_HAFTA, TEKRAR = 2, 12, 25
WIP_TAVAN_ADET = 5000
TRANSFER_ADET = 200  # iş emri, istasyonlar arasında 4 kasalık (4 × 50) transfer partileriyle akar
HEDEF_TEDARIK_GUN = 5
ROTA = [("Kesim", ["M01"]), ("Torna", ["M02", "M03"]), ("Freze", ["M04"]), ("Isıl işlem", ["M05"]),
        ("Taşlama", ["M06"])]
KAMPANYA_SIRASI = ["P01", "P02", "P04", "P03"]


# --------------------------------------------------------------------------
# Senaryolar
# --------------------------------------------------------------------------
@dataclass
class Senaryo:
    kod: str
    ad: str
    setup: dict = field(default_factory=dict)   # makine → ayar süresi çarpanı
    onay: dict = field(default_factory=dict)    # makine → ilk parça onayı çarpanı
    mtbf: dict = field(default_factory=dict)    # makine → MTBF çarpanı
    mttr: dict = field(default_factory=dict)    # makine → MTTR çarpanı
    perf: dict = field(default_factory=dict)    # makine → performans artışı (puan)
    pm_dk: dict = field(default_factory=dict)   # makine → haftalık planlı bakım (dk)
    politika: str = "acil"                      # "acil" (yangın söndürme) / "kampanya"
    ek_frz: bool = False                        # ikinci işleme merkezi yatırımı


def pilot_olcumleri() -> dict:
    """Pilot ayında H1-FRZ'de ölçülen iyileşme oranları."""
    d, u = oku("durus", ("Tarih",)), oku("uretim", ("Tarih",))
    d["Donem"] = np.where(d.Tarih >= PILOT_BASLANGIC, "Pilot", "Baz")
    u["Donem"] = np.where(u.Tarih >= PILOT_BASLANGIC, "Pilot", "Baz")
    fd, fu = d[d.MakineID == "M04"], u[u.MakineID == "M04"]
    setup = fd[fd.NedenID == "D01"].groupby("Donem").SureDk.mean()
    onay = fd[fd.NedenID == "D02"].groupby("Donem").SureDk.mean()
    ariza = fd[fd.NedenID.isin(["D03", "D04"])]
    saat = fu.groupby("Donem").CalismaSuresiDk.sum() / 60
    mtbf = saat / ariza.groupby("Donem").size()
    mttr = ariza.groupby("Donem").SureDk.mean()
    perf = fu.groupby("Donem").IdealSureDk.sum() / fu.groupby("Donem").CalismaSuresiDk.sum()
    # Baz dönemde kesilen (yarım kalan) lotlar yüzünden ürün değişimi sıklığı, tamamlanan lot
    # başına değil üretilen adet başına kalibre edilir: değişim olasılığı = setup / (çıktı ÷ ort. lot)
    n_setup_baz = int(((fd.NedenID == "D01") & (fd.Donem == "Baz")).sum())
    cikti_baz = fu[fu.Donem == "Baz"].UretilenAdet.sum()
    p_degisim = min(0.95, n_setup_baz / (cikti_baz / PARAM["talep"]["ort_lot_baz"]))
    return {"setup": setup["Pilot"] / setup["Baz"], "onay": onay["Pilot"] / onay["Baz"],
            "mtbf": mtbf["Pilot"] / mtbf["Baz"], "mttr": mttr["Pilot"] / mttr["Baz"],
            "perf": perf["Pilot"] - perf["Baz"], "p_degisim_baz": p_degisim,
            "setup_hafta_baz_gercek": n_setup_baz / 52}


def senaryolar(p: dict) -> list[Senaryo]:
    smed = {"setup": {"M04": p["setup"]}, "onay": {"M04": p["onay"]}}
    tpm = {"mtbf": {"M04": p["mtbf"]}, "mttr": {"M04": p["mttr"]}, "perf": {"M04": p["perf"]},
           "pm_dk": {"M04": 90}}
    return [
        Senaryo("S0", "Mevcut durum"),
        Senaryo("S1", "SMED (hızlı ürün değişimi)", **smed),
        Senaryo("S2", "TPM (önleyici bakım)", **tpm),
        Senaryo("S3", "SMED + TPM", **smed, **tpm),
        Senaryo("S4", "SMED + TPM + kampanya planlama", **smed, **tpm, politika="kampanya"),
        Senaryo("S5", "Yeni işleme merkezi (FRZ-2)", ek_frz=True),
        # Kısıtlar Teorisi kontrolü: aynı iyileştirme darboğaz olmayan istasyona yapılırsa?
        Senaryo("S6", "SMED + TPM yalnızca Taşlama'da", setup={"M06": p["setup"]}, onay={"M06": p["onay"]},
                mtbf={"M06": p["mtbf"]}, mttr={"M06": p["mttr"]}, perf={"M06": p["perf"]}, pm_dk={"M06": 90}),
    ]


# --------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------
class Lot:
    __slots__ = ("no", "urun", "adet", "giris")

    def __init__(self, no, urun, adet, giris):
        self.no, self.urun, self.adet, self.giris = no, urun, adet, giris


class Makine:
    def __init__(self, env, mid, sen: Senaryo, rng):
        p = PARAM[mid]
        self.env, self.mid, self.rng = env, mid, rng
        self.ct = p["ideal_cevrim_sn"]
        self.perf = p["performans"] + sen.perf.get(mid, 0.0)
        self.hurda = p["hurda_orani"]
        c = sen.setup.get(mid, 1.0)
        self.setup_ayni = (p["setup_ayni_aile"]["ort"] * c, p["setup_ayni_aile"]["cv"])
        self.setup_farkli = (p["setup_farkli_aile"]["ort"] * c, p["setup_farkli_aile"]["cv"])
        self.onay = (p["ilk_parca_onayi"]["ort"] * sen.onay.get(mid, 1.0), p["ilk_parca_onayi"]["cv"])
        self.mtbf = p["mtbf_saat"] * 60 * sen.mtbf.get(mid, 1.0)
        self.tamir = (p["tamir"]["ort"] * sen.mttr.get(mid, 1.0), p["tamir"]["cv"])
        self.diger_ara = p["diger_durus_saat_arasi"] * 60
        self.diger = (p["diger_durus"]["ort"], p["diger_durus"]["cv"])
        self.pm_dk = sen.pm_dk.get(mid, 0)
        self.sonraki_pm = HAFTA_DK
        self.urun = None
        self.ariza_saati = rng.exponential(self.mtbf)
        self.diger_saati = rng.exponential(self.diger_ara)
        self.sure = defaultdict(float)
        self.setup_sayisi = 0
        self.ideal_saglam_dk = 0.0

    def lognormal(self, ort, cv):
        s2 = math.log(1 + cv * cv)
        return float(self.rng.lognormal(math.log(max(ort, 0.1)) - s2 / 2, math.sqrt(s2)))

    def calis(self, sure):
        while sure > 1e-9:
            adim = min(self.ariza_saati, self.diger_saati, sure)
            yield self.env.timeout(adim)
            self.sure["isleme"] += adim
            sure -= adim
            self.ariza_saati -= adim
            self.diger_saati -= adim
            if self.ariza_saati <= 1e-9:
                t = self.lognormal(*self.tamir)
                yield self.env.timeout(t)
                self.sure["ariza"] += t
                self.ariza_saati = self.rng.exponential(self.mtbf)
            if self.diger_saati <= 1e-9:
                t = self.lognormal(*self.diger)
                yield self.env.timeout(t)
                self.sure["diger"] += t
                self.diger_saati = self.rng.exponential(self.diger_ara)

    def isle(self, lot: Lot):
        if self.pm_dk and self.env.now >= self.sonraki_pm:
            yield self.env.timeout(self.pm_dk)
            self.sure["planli_bakim"] += self.pm_dk
            self.sonraki_pm += HAFTA_DK
        if self.urun != lot.urun:
            ayni = self.urun is not None and AILE[self.urun] == AILE[lot.urun]
            t = self.lognormal(*(self.setup_ayni if ayni else self.setup_farkli)) + self.lognormal(*self.onay)
            yield self.env.timeout(t)
            self.sure["setup"] += t
            self.setup_sayisi += 1
            self.urun = lot.urun
        yield from self.calis(lot.adet * self.ct[lot.urun] / 60 / self.perf)
        hurda = int(self.rng.binomial(lot.adet, self.hurda))
        lot.adet -= hurda
        self.ideal_saglam_dk += lot.adet * self.ct[lot.urun] / 60
        return hurda


class LotUretici:
    """Planlama politikası: hangi ürün, kaç adet?"""

    def __init__(self, rng, politika, pay, p_degisim):
        self.rng, self.politika, self.pay, self.p_degisim = rng, politika, pay, p_degisim
        self.onceki, self.idx = None, -1
        self.lot_baz = PARAM["talep"]["ort_lot_baz"]
        self.lot_kampanya = PARAM["talep"]["ort_lot_pilot"]

    def sonraki(self):
        if self.politika == "kampanya":
            self.idx = (self.idx + 1) % len(KAMPANYA_SIRASI)
            u = KAMPANYA_SIRASI[self.idx]
            adet = max(300, round(len(KAMPANYA_SIRASI) * self.lot_kampanya * self.pay[u] / 50) * 50)
        else:
            if self.onceki is None or self.rng.random() < self.p_degisim:
                adaylar = [x for x in self.pay if x != self.onceki]
                p = np.array([self.pay[x] for x in adaylar])
                u = str(self.rng.choice(adaylar, p=p / p.sum()))
            else:
                u = self.onceki
            adet = max(150, round(self.rng.lognormal(math.log(self.lot_baz) - 0.06, 0.35) / 50) * 50)
        self.onceki = u
        return u, adet


def calistir(sen: Senaryo, mod: str, tohum: int, pay: dict, haftalik_talep: float, p_degisim: float) -> dict:
    rng = np.random.default_rng(tohum)
    env = simpy.Environment()
    rota = [(ad, list(m)) for ad, m in ROTA]
    if sen.ek_frz:
        rota[2][1].append("M04")  # aynı özellikte ikinci işleme merkezi
    kuyruklar = [simpy.Store(env) for _ in rota]
    makineler = [[Makine(env, m, sen, rng) for m in grup] for _, grup in rota]
    uretici = LotUretici(rng, sen.politika, pay, p_degisim)
    durum = {"wip": 0, "alan": 0.0, "son": 0.0, "no": 0}
    bitenler = []

    def wip_degis(delta):
        durum["alan"] += durum["wip"] * (env.now - durum["son"])
        durum["son"] = env.now
        durum["wip"] += delta

    def serbest_birak():
        u, adet = uretici.sonraki()
        durum["no"] += 1
        while adet > 0:
            parti = min(TRANSFER_ADET, adet)
            wip_degis(parti)
            kuyruklar[0].put(Lot(durum["no"], u, parti, env.now))
            adet -= parti

    def conwip_doldur():
        while durum["wip"] < WIP_TAVAN_ADET:
            serbest_birak()

    def sure(mk: Makine, i: int):
        while True:
            lot = yield kuyruklar[i].get()
            hurda = yield from mk.isle(lot)
            if hurda:
                wip_degis(-hurda)
            if i + 1 < len(rota):
                kuyruklar[i + 1].put(lot)
            else:
                wip_degis(-lot.adet)
                bitenler.append((env.now, lot.adet, (env.now - lot.giris) / GUN_DK))
                if mod == "kapasite":
                    conwip_doldur()

    for i, grup in enumerate(makineler):
        for mk in grup:
            env.process(sure(mk, i))

    if mod == "kapasite":
        conwip_doldur()
    else:
        ort_lot = (PARAM["talep"]["ort_lot_pilot"] if sen.politika == "kampanya" else PARAM["talep"]["ort_lot_baz"])
        # Hat boyunca hurda kaybı telafi edilecek kadar brüt iş emri açılır
        verim = float(np.prod([1 - np.mean([PARAM[m]["hurda_orani"] for m in grup]) for _, grup in ROTA]))
        brut_talep = haftalik_talep / verim

        def poisson_gelis():
            while True:
                yield env.timeout(rng.exponential(ort_lot / brut_talep * HAFTA_DK))
                serbest_birak()
        env.process(poisson_gelis())

    isinma = ISINMA_HAFTA * HAFTA_DK
    anlik = {}

    def isinma_kaydi():
        yield env.timeout(isinma)
        wip_degis(0)
        anlik["alan"] = durum["alan"]
        for grup in makineler:
            for mk in grup:
                anlik[id(mk)] = (dict(mk.sure), mk.setup_sayisi, mk.ideal_saglam_dk)
    env.process(isinma_kaydi())
    bitis = isinma + OLCUM_HAFTA * HAFTA_DK
    env.run(until=bitis)
    wip_degis(0)

    sure_olcum = bitis - isinma
    b = [x for x in bitenler if x[0] >= isinma]
    sonuc = {
        "HaftalikCikti": sum(x[1] for x in b) / OLCUM_HAFTA,
        "OrtTedarikGun": float(np.mean([x[2] for x in b])) if b else np.nan,
        "HizmetDuzeyi": float(np.mean([x[2] <= HEDEF_TEDARIK_GUN for x in b])) if b else np.nan,
        "OrtWIPAdet": (durum["alan"] - anlik["alan"]) / sure_olcum,
    }
    for (ad, _), grup in zip(rota, makineler):
        kullanim, setup, ideal = [], 0, 0.0
        for mk in grup:
            once, s0, i0 = anlik[id(mk)]
            mesgul = sum(mk.sure.values()) - sum(once.values())
            kullanim.append(mesgul / sure_olcum)
            setup += mk.setup_sayisi - s0
            ideal += mk.ideal_saglam_dk - i0
        sonuc[f"Kullanim_{ad}"] = float(np.mean(kullanim))
        if ad == "Freze":
            sonuc["FRZ_OEE"] = ideal / (sure_olcum * len(grup))
            sonuc["FRZ_SetupHafta"] = setup / OLCUM_HAFTA
    return sonuc


def guven_araligi(x: np.ndarray) -> tuple[float, float]:
    x = x[~np.isnan(x)]
    if len(x) < 2:
        return float(np.mean(x)) if len(x) else np.nan, 0.0
    return float(x.mean()), float(stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / math.sqrt(len(x)))


# --------------------------------------------------------------------------
# Deneyler ve grafikler
# --------------------------------------------------------------------------
def main() -> None:
    pilot = pilot_olcumleri()
    print("Pilot ölçümleri:", {k: round(v, 3) for k, v in pilot.items()})
    tahmin = pd.read_csv(TABLO / "talep_tahmini.csv", parse_dates=["Ay"])
    t1 = tahmin[tahmin.UrunID.isin(["P01", "P02", "P03", "P04"])]
    gun = sum(calisma_gunu_sayisi(a) for a in t1.Ay.unique())
    haftalik_talep = t1.Tahmin.sum() / gun * 6
    aylik = t1.groupby("Ay").Tahmin.sum()
    zirve_ay = aylik.idxmax()
    zirve_haftalik = aylik.max() / calisma_gunu_sayisi(zirve_ay) * 6
    pay = (t1.groupby("UrunID").Tahmin.sum() / t1.Tahmin.sum()).to_dict()
    sen_listesi = senaryolar(pilot)

    kayit = []
    for sen in sen_listesi:
        for mod in ("kapasite", "talep"):
            for r in range(TEKRAR):
                s = calistir(sen, mod, TOHUM + 1000 * r + 7, pay, haftalik_talep, pilot["p_degisim_baz"])
                kayit.append({"Senaryo": sen.kod, "SenaryoAdi": sen.ad, "Mod": mod, "Tekrar": r + 1, **s})
        print(f"{sen.kod} tamam")
    ham = pd.DataFrame(kayit)
    ham.to_csv(TABLO / "sim_tekrarlar.csv", index=False, encoding="utf-8")

    # Özet: ortalama ± %95 güven aralığı
    metrikler = [c for c in ham.columns if c not in ("Senaryo", "SenaryoAdi", "Mod", "Tekrar")]
    ozet_satir = []
    for (kod, ad, mod), g in ham.groupby(["Senaryo", "SenaryoAdi", "Mod"], sort=False):
        for m in metrikler:
            ort, yari = guven_araligi(g[m].to_numpy(float))
            ozet_satir.append((kod, ad, mod, m, ort, ort - yari, ort + yari))
    ozet = pd.DataFrame(ozet_satir, columns=["Senaryo", "SenaryoAdi", "Mod", "Metrik", "Ortalama", "AltCI", "UstCI"])
    ozet.to_csv(TABLO / "sim_sonuclari.csv", index=False, encoding="utf-8")

    kap = ozet[ozet.Mod == "kapasite"].pivot(index="Senaryo", columns="Metrik", values="Ortalama")
    kap_ci = ozet[ozet.Mod == "kapasite"].assign(Yari=lambda d: d.UstCI - d.Ortalama).pivot(
        index="Senaryo", columns="Metrik", values="Yari")
    tal = ozet[ozet.Mod == "talep"].pivot(index="Senaryo", columns="Metrik", values="Ortalama")
    tal_ci = ozet[ozet.Mod == "talep"].assign(Yari=lambda d: d.UstCI - d.Ortalama).pivot(
        index="Senaryo", columns="Metrik", values="Yari")
    adlar = {s.kod: s.ad for s in sen_listesi}
    istasyonlar = [ad for ad, _ in ROTA]
    kullanim = kap[[f"Kullanim_{i}" for i in istasyonlar]]
    kullanim.columns = istasyonlar
    darbogaz = kullanim.idxmax(axis=1)
    taban = kap.at["S0", "HaftalikCikti"]

    # Doğrulama: simülasyon (S0) vs gerçek veri
    gercek_hafta = PARAM["dogrulama"]["hat1_haftalik_cikti_6gun"]
    dogrulama = {"gercek_haftalik_cikti": gercek_hafta, "sim_haftalik_cikti_S0": taban,
                 "fark": taban / gercek_hafta - 1, "sim_frz_oee_S0": kap.at["S0", "FRZ_OEE"],
                 "gercek_frz_oee": json.loads((TABLO.parent / "ozet_metrikler.json").read_text(
                     encoding="utf-8"))["analiz"]["frz_oee_baz"],
                 "sim_frz_setup_hafta_S0": kap.at["S0", "FRZ_SetupHafta"],
                 "gercek_frz_setup_hafta": pilot["setup_hafta_baz_gercek"],
                 "haftalik_talep": haftalik_talep}
    print("Doğrulama:", {k: round(v, 3) for k, v in dogrulama.items()})

    # ---- Grafik 15: azami haftalık çıktı ----
    fig, ax = plt.subplots(figsize=(11, 5.6))
    sira = list(kap.index)[::-1]
    renk = {k: (GRI_SERI if k == "S0" else SARI if k == "S5" else MAVI) for k in sira}
    y = np.arange(len(sira))
    ax.barh(y, [kap.at[k, "HaftalikCikti"] for k in sira], xerr=[kap_ci.at[k, "HaftalikCikti"] for k in sira],
            color=[renk[k] for k in sira], height=0.62, error_kw={"ecolor": MUREKKEP, "elinewidth": 1, "capsize": 3})
    for yi, k in zip(y, sira):
        v = kap.at[k, "HaftalikCikti"]
        etiket = sayi(v) + ("" if k == "S0" else f"  ({'+' if v >= taban else '−'}{yuzde(abs(v / taban - 1), 0)})")
        ax.text(v + kap_ci.at[k, "HaftalikCikti"] + 80, yi, etiket, va="center", fontsize=9, color=MUREKKEP)
    ax.axvline(haftalik_talep, color=IKINCIL, lw=1.4)
    ax.axvline(zirve_haftalik, color=DURUM["kritik"], lw=1.4)
    ax.text(haftalik_talep - 60, len(sira) - 0.35, f"Ort. talep\n{sayi(haftalik_talep)}", ha="right", va="bottom",
            fontsize=8.5, color=IKINCIL)
    ax.text(zirve_haftalik + 60, len(sira) - 0.35, f"Zirve ay\n{sayi(zirve_haftalik)}", ha="left", va="bottom",
            fontsize=8.5, color=MUREKKEP)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{k}  {adlar[k]}" for k in sira])
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.set_xlim(0, kap.HaftalikCikti.max() * 1.25)
    ax.set_ylim(-0.6, len(sira) + 0.5)
    sayi_ekseni(ax, "x")
    ax.set_xlabel("Azami haftalık sağlam çıktı (adet) · 25 tekrar ortalaması, %95 güven aralığı")
    s4, s5 = kap.at["S4", "HaftalikCikti"] / taban - 1, kap.at["S5", "HaftalikCikti"] / taban - 1
    baslik(ax, f"Yalın paket (S4) kapasiteyi {yuzde(s4, 0)} artırıyor; yeni makine (S5) {yuzde(s5, 0)}",
           "Kapasite testi: hat sürekli dolu (CONWIP) · dikey çizgiler: Kas 26 – Nis 27 tahmini talep")
    kaynak_notu(fig, "Kaynak: SimPy kesikli olay simülasyonu, parametreler MES verisinden · Senaryo oranları pilot ölçümlerinden")
    kaydet(fig, "15_sim_kapasite_senaryolari.png")

    # ---- Grafik 16: darboğaz haritası (senaryo × istasyon kullanım) ----
    fig, ax = plt.subplots(figsize=(10, 5.4))
    cmap = LinearSegmentedColormap.from_list("mavi", MAVI_RAMPA[0:12])
    veri = kullanim.loc[list(kap.index)]
    ax.imshow(veri.values, cmap=cmap, vmin=0.3, vmax=1.0, aspect="auto")
    for i, k in enumerate(veri.index):
        for j, ist in enumerate(istasyonlar):
            v = veri.iat[i, j]
            dar = ist == darbogaz[k]
            ax.text(j, i, yuzde(v, 0) + (" ◆" if dar else ""), ha="center", va="center", fontsize=9.5,
                    color="#ffffff" if v > 0.72 else MUREKKEP, fontweight="semibold" if dar else "normal")
    ax.set_xticks(range(len(istasyonlar)))
    ax.set_xticklabels(istasyonlar)
    ax.set_yticks(range(len(veri)))
    ax.set_yticklabels([f"{k}  {adlar[k]}" for k in veri.index])
    ax.tick_params(length=0)
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks(np.arange(-0.5, len(istasyonlar), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(veri), 1), minor=True)
    ax.grid(which="minor", color=YUZEY, linewidth=2)
    ax.tick_params(which="minor", length=0)
    baslik(ax, f"Yeni makine darboğazı {darbogaz['S5']}'ya kaydırıyor; yalın pakette Freze darboğaz kalıyor ama rahatlıyor",
           "İstasyon kullanımı (işleme + ayar + arıza + bakım) · kapasite testi · ◆ = darboğaz")
    kaynak_notu(fig, "Kaynak: SimPy kesikli olay simülasyonu · 25 tekrar ortalaması")
    kaydet(fig, "16_sim_darbogaz_haritasi.png")

    # ---- Grafik 17: talep altında tedarik süresi ----
    fig, ax = plt.subplots(figsize=(11, 5.4))
    sira2 = list(tal.index)
    x = np.arange(len(sira2))
    kararsiz = {k: kap.at[k, "HaftalikCikti"] < haftalik_talep for k in sira2}
    degerler = [tal.at[k, "OrtTedarikGun"] for k in sira2]
    ax.bar(x, degerler, yerr=[tal_ci.at[k, "OrtTedarikGun"] for k in sira2], width=0.62,
           color=[DURUM["kritik"] if kararsiz[k] else (SARI if k == "S5" else MAVI) for k in sira2],
           error_kw={"ecolor": MUREKKEP, "elinewidth": 1, "capsize": 3})
    for xi, k, v in zip(x, sira2, degerler):
        if kararsiz[k]:
            acik = haftalik_talep - kap.at[k, "HaftalikCikti"]
            metin = f"kararsız\nkuyruk haftada\n+{sayi(acik)} adet"
        else:
            metin = f"{sayi(v, 1)} gün\n%{sayi(tal.at[k, 'HizmetDuzeyi'] * 100)} ≤ {HEDEF_TEDARIK_GUN} gün"
        ax.text(xi, v + tal_ci.at[k, "OrtTedarikGun"] + 0.25, metin, ha="center", va="bottom", fontsize=8.5,
                color=MUREKKEP)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{k}\n" + "\n".join(textwrap.wrap(adlar[k], 17)) for k in sira2], fontsize=8)
    ax.set_ylabel("Ortalama tedarik süresi (iş günü)")
    ax.set_ylim(0, max(np.array(degerler) + np.array([tal_ci.at[k, "OrtTedarikGun"] for k in sira2])) * 1.45)
    dengede = [k for k in sira2 if not kararsiz[k]]
    baslik(ax, f"Tahmini talepte yalnızca {', '.join(dengede[:-1])} ve {dengede[-1]} dengede kalıyor; "
               "diğerlerinde kuyruk her hafta büyüyor",
           f"Talep testi: haftada {sayi(haftalik_talep)} sağlam adet (Kas 26 – Nis 27 ort.), Poisson iş emri gelişi · "
           "kırmızı = azami kapasite talebin altında")
    kaynak_notu(fig, "Kaynak: SimPy kesikli olay simülasyonu · fazla mesai varsayılmadı")
    kaydet(fig, "17_sim_tedarik_suresi.png")

    sonuc_ozet = {
        "pilot_olcumleri": pilot,
        "haftalik_talep_tahmini": haftalik_talep,
        "zirve_haftalik_talep": zirve_haftalik,
        "dogrulama": dogrulama,
        "kapasite": {k: {"ad": adlar[k], "haftalik_cikti": kap.at[k, "HaftalikCikti"],
                         "ci_yari": kap_ci.at[k, "HaftalikCikti"], "artis": kap.at[k, "HaftalikCikti"] / taban - 1,
                         "frz_oee": kap.at[k, "FRZ_OEE"], "darbogaz": darbogaz[k],
                         "frz_setup_hafta": kap.at[k, "FRZ_SetupHafta"],
                         "kullanim": {i: round(kullanim.at[k, i], 3) for i in istasyonlar}} for k in kap.index},
        "talep": {k: {"tedarik_gun": tal.at[k, "OrtTedarikGun"], "hizmet": tal.at[k, "HizmetDuzeyi"],
                      "wip": tal.at[k, "OrtWIPAdet"], "kararsiz": bool(kararsiz[k])} for k in tal.index},
    }
    ozet_yaz("simulasyon", sonuc_ozet)
    tablo = pd.DataFrame({
        "Senaryo": [f"{k} {adlar[k]}" for k in kap.index],
        "Haftalık çıktı": kap.HaftalikCikti.round(0).values,
        "Artış": [(v / taban - 1) for v in kap.HaftalikCikti],
        "FRZ OEE": kap.FRZ_OEE.values,
        "Darboğaz": darbogaz.values,
        "Tedarik (gün)": tal.loc[kap.index, "OrtTedarikGun"].values,
    })
    print(tablo.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
