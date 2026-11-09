"""03 — Talep tahmini ve darboğaz kapasite ihtiyacı.

* 37 aylık ERP satış geçmişi, ürün bazında ETS(M,Ad,M) (Holt-Winters ailesi) ile modellenir.
* Model seçimi geriye dönük testle yapılır: son 6 ay ayrılır, ETS / mevsimsel naif / 3 aylık
  hareketli ortalama MAPE ile karşılaştırılır.
* Satış ekibinden gelen bilinen olay (OEM-Gama yeni model: RB-140 Ocak 2027'den itibaren +%20)
  istatistiksel tahmine yargısal düzeltme olarak eklenir.
* Tahmin, H1-FRZ'nin aylık yük oranına çevrilir: mevcut OEE ile kapasite yetiyor mu?
"""
from __future__ import annotations

import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.tsa.exponential_smoothing.ets import ETSModel

from grafik_stili import (DARBOGAZ_RENK, EKSEN, GRI_SERI, IKINCIL, MAVI, MAVI_RAMPA, MUREKKEP, YUZEY, baslik,
                          kaydet, kaynak_notu, sayi_ekseni, stil_uygula, yuzde_ekseni)
from ortak import (IDEAL_CEVRIM, TABLO, TAHMIN_UFKU_AY, URUNLER, ay_etiketi, calisma_gunu_sayisi, ozet_oku,
                   ozet_yaz, sayi, yuzde)
from veri_yukle import oku

warnings.filterwarnings("ignore")
stil_uygula()

HAT1 = ["P01", "P02", "P03", "P04"]
TEST_AY = 6
SATIS_GIRDISI = {"P04": (pd.Timestamp("2027-01-01"), 1.20)}  # OEM-Gama yeni model
GUNLUK_DK = 3 * 450


def ets(y: pd.Series):
    model = ETSModel(y.astype(float), error="mul", trend="add", damped_trend=True,
                     seasonal="mul", seasonal_periods=12)
    return model.fit(disp=False, maxiter=3000)


def mevsimsel_naif(y: np.ndarray, h: int) -> np.ndarray:
    buyume = y[-12:].sum() / y[-24:-12].sum()
    return np.array([y[-12 + (k % 12)] * buyume for k in range(h)])


def mape(gercek, tahmin) -> float:
    gercek, tahmin = np.asarray(gercek, float), np.asarray(tahmin, float)
    return float(np.mean(np.abs(gercek - tahmin) / gercek))


def main() -> None:
    talep = oku("talep_aylik", ("Ay",))
    talep = talep.pivot(index="Ay", columns="UrunID", values="Talep").asfreq("MS")

    # ---- 1) Geriye dönük test ----
    satirlar = []
    for u in talep.columns:
        y = talep[u]
        egitim, test = y.iloc[:-TEST_AY], y.iloc[-TEST_AY:]
        tahminler = {
            "ETS (Holt-Winters)": ets(egitim).forecast(TEST_AY).values,
            "Mevsimsel naif": mevsimsel_naif(egitim.values, TEST_AY),
            "3 aylık hareketli ort.": np.repeat(egitim.values[-3:].mean(), TEST_AY),
        }
        for yontem, t in tahminler.items():
            satirlar.append((u, yontem, mape(test.values, t)))
    bt = pd.DataFrame(satirlar, columns=["UrunID", "Yontem", "MAPE"])
    ozet_bt = bt.pivot(index="UrunID", columns="Yontem", values="MAPE")
    ozet_bt.loc["Ortalama"] = ozet_bt.mean()
    ozet_bt.round(4).to_csv(TABLO / "tahmin_geriye_donuk_test.csv", encoding="utf-8")
    secilen = ozet_bt.loc["Ortalama"].idxmin()
    print("Geriye dönük test (MAPE):\n", (ozet_bt * 100).round(1).to_string())

    # ---- 2) Tüm veriyle yeniden kur, 6 ay ileri tahmin + %80 tahmin aralığı ----
    ufuk = pd.date_range(talep.index[-1] + pd.offsets.MonthBegin(1), periods=TAHMIN_UFKU_AY, freq="MS")
    kayit = []
    for u in talep.columns:
        y = talep[u]
        sonuc = ets(y)
        tablo = sonuc.get_prediction(start=len(y), end=len(y) + TAHMIN_UFKU_AY - 1).summary_frame(alpha=0.2)
        for ay, r in zip(ufuk, tablo.itertuples()):
            carpan = 1.0
            if u in SATIS_GIRDISI and ay >= SATIS_GIRDISI[u][0]:
                carpan = SATIS_GIRDISI[u][1]
            kayit.append((ay, u, r.mean * carpan, r.pi_lower * carpan, r.pi_upper * carpan, carpan))
    tahmin = pd.DataFrame(kayit, columns=["Ay", "UrunID", "Tahmin", "Alt80", "Ust80", "SatisDuzeltmesi"])
    tahmin[["Tahmin", "Alt80", "Ust80"]] = (tahmin[["Tahmin", "Alt80", "Ust80"]] / 50).round() * 50
    tahmin.to_csv(TABLO / "talep_tahmini.csv", index=False, encoding="utf-8")

    # ---- 3) Hat-1 toplamı ve H1-FRZ yük oranı ----
    gecmis_h1 = talep[HAT1].sum(axis=1)
    t1 = tahmin[tahmin.UrunID.isin(HAT1)]
    toplam = t1.groupby("Ay").Tahmin.sum()
    yari = t1.assign(y=(t1.Ust80 - t1.Alt80) / 2).groupby("Ay").y.apply(lambda s: np.sqrt((s ** 2).sum()))
    ozet = ozet_oku().get("analiz", {})
    oee_baz, oee_pilot = ozet.get("frz_oee_baz", 0.60), ozet.get("frz_oee_pilot", 0.70)
    cevrim = IDEAL_CEVRIM["M04"]
    yuk = []
    for ay, g in t1.groupby("Ay"):
        ideal_saat = sum(r.Tahmin * cevrim[r.UrunID] for r in g.itertuples()) / 3600
        gun = calisma_gunu_sayisi(ay)
        mevcut_saat = gun * GUNLUK_DK / 60
        yuk.append((ay, gun, mevcut_saat, ideal_saat, ideal_saat / oee_baz / mevcut_saat,
                    ideal_saat / oee_pilot / mevcut_saat))
    yuk = pd.DataFrame(yuk, columns=["Ay", "CalismaGunu", "MevcutSaat", "IdealSaat", "YukMevcutOEE", "YukPilotOEE"])
    yuk.to_csv(TABLO / "frz_kapasite_ihtiyaci.csv", index=False, encoding="utf-8")

    # ---- Grafik: geçmiş + tahmin ----
    fig, ax = plt.subplots(figsize=(11, 5.2))
    ax.fill_between(toplam.index, toplam - 1.0 * yari, toplam + 1.0 * yari, color=MAVI_RAMPA[1], lw=0,
                    label="%80 tahmin aralığı")
    ax.plot(gecmis_h1.index, gecmis_h1.values, color=IKINCIL, lw=2, label="Gerçekleşen talep")
    ax.plot([gecmis_h1.index[-1], *toplam.index], [gecmis_h1.iloc[-1], *toplam.values], color=MAVI, lw=2.4,
            marker="o", ms=4.5, markeredgecolor=YUZEY, label="Tahmin (ETS + satış girdisi)")
    ax.axvline(gecmis_h1.index[-1] + pd.Timedelta(days=15), color=EKSEN, lw=1)
    zirve = toplam.idxmax()
    ax.annotate(f"{ay_etiketi(zirve)}: {sayi(toplam.max())} adet", (zirve, toplam.max()), xytext=(-10, 16),
                textcoords="offset points", ha="right", fontsize=9, color=MUREKKEP,
                arrowprops={"arrowstyle": "-", "color": EKSEN, "lw": 0.8})
    sayi_ekseni(ax)
    ax.set_ylabel("Adet / ay")
    ax.legend(loc="upper left", ncols=3)
    ax.set_ylim(gecmis_h1.min() * 0.92, max(toplam.max() + yari.max(), gecmis_h1.max()) * 1.10)
    isaretler = pd.date_range(gecmis_h1.index[0], toplam.index[-1], freq="6MS")
    ax.set_xticks(isaretler)
    ax.set_xticklabels([ay_etiketi(a) for a in isaretler])
    artis = toplam.mean() / gecmis_h1.loc["2025-11-01":"2026-04-01"].mean() - 1
    baslik(ax, f"Hat-1 talebi önümüzdeki 6 ayda geçen yılın aynı dönemine göre {yuzde(artis, 0)} yüksek",
           f"Aylık talep, adet · Ekim 2023 – Nisan 2027 · model: ETS(M,Ad,M), geriye dönük test MAPE "
           f"{yuzde(ozet_bt.at['Ortalama', 'ETS (Holt-Winters)'], 1)}")
    kaynak_notu(fig, "Kaynak: Demirkanat ERP (sentetik veri) · OEM-Gama yeni model girdisi: satış ekibi")
    kaydet(fig, "13_talep_tahmini.png")

    # ---- Grafik: H1-FRZ yük oranı ----
    fig, ax = plt.subplots(figsize=(11, 5.0))
    x = np.arange(len(yuk))
    ax.bar(x - 0.19, yuk.YukMevcutOEE, width=0.36, color=GRI_SERI, label=f"Mevcut OEE ({yuzde(oee_baz, 0)})")
    ax.bar(x + 0.19, yuk.YukPilotOEE, width=0.36, color=MAVI, label=f"Pilot OEE ({yuzde(oee_pilot, 0)})")
    ax.axhline(1.0, color=DARBOGAZ_RENK, lw=1.6, label="Normal vardiya kapasitesi (%100)")
    for i, r in yuk.iterrows():
        ax.text(i - 0.19, r.YukMevcutOEE + 0.015, yuzde(r.YukMevcutOEE, 0), ha="center", fontsize=8.5, color=MUREKKEP)
        ax.text(i + 0.19, r.YukPilotOEE + 0.015, yuzde(r.YukPilotOEE, 0), ha="center", fontsize=8.5, color=MUREKKEP)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{ay_etiketi(a)}\n{g} iş günü" for a, g in zip(yuk.Ay, yuk.CalismaGunu)])
    ax.set_ylim(0, max(yuk.YukMevcutOEE.max() * 1.22, 1.2))
    yuzde_ekseni(ax)
    ax.legend(loc="upper left", ncols=3)
    asim = int((yuk.YukMevcutOEE > 1).sum())
    baslik(ax, f"Mevcut OEE ile H1-FRZ önümüzdeki 6 ayın {asim}'{'ında' if asim in (1, 2, 5, 6) else 'ünde'} "
               f"kapasitenin üstünde yüklü",
           "H1-FRZ yük oranı = gereken süre (tahmin × ideal çevrim ÷ OEE) ÷ normal vardiya süresi")
    kaynak_notu(fig)
    kaydet(fig, "14_frz_yuk_orani.png")

    ozet_yaz("tahmin", {
        "secilen_model": secilen,
        "mape": {k: round(v, 4) for k, v in ozet_bt.loc["Ortalama"].items()},
        "hat1_aylik_tahmin": {ay_etiketi(a): round(v) for a, v in toplam.items()},
        "hat1_tahmin_ortalama": toplam.mean(),
        "hat1_gecen_yil_ayni_donem": gecmis_h1.loc["2025-11-01":"2026-04-01"].mean(),
        "artis_orani": artis,
        "zirve_ay": ay_etiketi(zirve),
        "frz_yuk_mevcut": {ay_etiketi(a): round(v, 3) for a, v in zip(yuk.Ay, yuk.YukMevcutOEE)},
        "frz_yuk_pilot": {ay_etiketi(a): round(v, 3) for a, v in zip(yuk.Ay, yuk.YukPilotOEE)},
        "kapasite_asan_ay_sayisi": asim,
    })
    print("Hat-1 tahmin:", {ay_etiketi(a): int(v) for a, v in toplam.items()})
    print("FRZ yük (mevcut OEE):", yuk.YukMevcutOEE.round(3).tolist())
    print("FRZ yük (pilot OEE):", yuk.YukPilotOEE.round(3).tolist())


if __name__ == "__main__":
    main()
