"""06 — İş gerekçesi: yalın paket mi, yeni makine mi? (NPV + Monte Carlo risk analizi)

Seçenekler (hepsi "hiçbir şey yapmama" durumuyla kıyaslanır)
    A  Yalın paket: SMED + TPM + kampanya planlama + gece standart işi + Power BI izleme
    B  Yeni CNC işleme merkezi (FRZ-2): darboğaz kapasitesini iki katına çıkarır
    C  Aşamalı: yalın paket hemen; talep tahminin %8 üstüne çıktığı yıl yeni makine (reel opsiyon)

Fayda motoru
    Plan maliyeti (fazla mesai, gecikme, kayıp satış, ayar, stok) 05_optimizasyon.py modelleriyle
    talep seviyesinin bir fonksiyonu olarak hesaplanır (0,90 – 1,45 × tahmin; 12 nokta). Monte Carlo
    her yıl için talep seviyesini çekip bu eğrilerden enterpolasyon yapar.

Belirsizlikler (10.000 senaryo)
    talep tahmin hatası, yıllık büyüme, yalın kazanımların kalıcılık oranı, hurda tasarrufu,
    yatırım tutarı (makine Euro bazlı → kur riski), işletme gideri, fazla mesai ücreti, makine teslim süresi.
Değerlendirme: 5 yıl, sabit 2026 fiyatları, reel iskonto %12; makinenin 5. yıl hurda değeri yatırımın %35'i.
"""
from __future__ import annotations

import importlib

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from grafik_stili import (IKINCIL, MAVI, MUREKKEP, SARI, SERI, SU_YESILI, SUNUM, baslik, kaydet, kaynak_notu,
                          stil_uygula)
from ortak import PILOT_BASLANGIC, TABLO, TOHUM, milyon_tl, ozet_yaz, sayi, yuzde
from veri_yukle import oku

opt = importlib.import_module("05_optimizasyon")
stil_uygula()
N = 10_000
YIL = 5
ISKONTO = 0.12
IZGARA = np.round(np.arange(0.90, 1.4501, 0.05), 2)
TETIK = 1.08            # C seçeneği: talep çarpanı bu eşiği aşınca makine siparişi verilir
SECENEK_AD = {"A": "A: Yalın paket", "B": "B: Yeni işleme merkezi", "C": "C: Aşamalı (yalın + tetikli makine)"}


def maliyet_egrileri() -> pd.DataFrame:
    """Talep seviyesine göre 6 aylık plan maliyeti (toplam ve fazla mesai payı), üç durum için."""
    v = opt.verim_parametreleri()
    mevcut = {"M04": v[("Baz", "M04")], "M06": v[("Baz", "M06")]}
    pilot = {"M04": v[("Pilot", "M04")], "M06": v[("Pilot", "M06")]}
    s1000 = v[("Baz", "M04")]["setup_1000"]
    satir = []
    for m in IZGARA:
        baz = opt.mevcut_yontem(mevcut, s1000, talep_carpani=m)
        yalin = opt.optimal_plan(pilot, ad=f"yalin_{m}", talep_carpani=m)
        makine = opt.mevcut_yontem(mevcut, s1000, talep_carpani=m, frz_kapasite=2.0)
        ikisi = opt.optimal_plan(pilot, ad=f"ikisi_{m}", talep_carpani=m, frz_kapasite=2.0)
        satir.append({"TalepCarpani": m,
                      "Baz": baz["toplam"], "BazMesai": baz["kalemler"]["Fazla mesai"],
                      "Yalin": yalin["toplam"], "YalinMesai": yalin["kalemler"]["Fazla mesai"],
                      "Makine": makine["toplam"], "MakineMesai": makine["kalemler"]["Fazla mesai"],
                      "YalinMakine": ikisi["toplam"], "YalinMakineMesai": ikisi["kalemler"]["Fazla mesai"]})
    df = pd.DataFrame(satir)
    df.to_csv(TABLO / "finans_maliyet_egrileri.csv", index=False, encoding="utf-8")
    return df


def hurda_tasarrufu_yillik() -> float:
    """Pilotta Hat-1 birim hurda maliyetindeki düşüş × yıllık üretim (12 aylık baz)."""
    u = oku("uretim", ("Tarih",))
    u = u[u.MakineID.isin(["M01", "M02", "M03", "M04", "M05", "M06"])]
    u["Donem"] = np.where(u.Tarih >= PILOT_BASLANGIC, "Pilot", "Baz")
    son = u[u.MakineID == "M06"]
    birim = u.groupby("Donem").HurdaMaliyetiTL.sum() / son.groupby("Donem").SaglamAdet.sum()
    yillik_adet = son[son.Donem == "Baz"].SaglamAdet.sum()
    return float((birim["Baz"] - birim["Pilot"]) * yillik_adet)


def ucgen(rng, a, m, b, n):
    return rng.triangular(a, m, b, n)


def monte_carlo(egri: pd.DataFrame, hurda: float) -> dict:
    rng = np.random.default_rng(TOHUM)
    m1 = rng.normal(1.0, 0.05, N)                      # tahmin hatası (MAPE ≈ %5)
    buyume = rng.normal(0.045, 0.025, N)              # yıllık talep büyümesi
    gerceklesme = ucgen(rng, 0.55, 0.85, 1.0, N)      # pilot kazanımlarının kalıcılığı
    hurda_k = ucgen(rng, 0.4, 0.8, 1.0, N)
    capex_a = ucgen(rng, 1.60e6, 1.75e6, 2.30e6, N)
    capex_b = ucgen(rng, 8.2e6, 8.5e6, 9.8e6, N)      # Euro bazlı fiyat → kur riski
    opex_a = ucgen(rng, 0.25e6, 0.30e6, 0.40e6, N)
    opex_b = ucgen(rng, 2.4e6, 2.68e6, 3.0e6, N)      # 3 operatör + bakım + enerji
    mesai_k = rng.uniform(0.9, 1.15, N)               # fazla mesai ücret belirsizliği
    teslim_ay = rng.integers(5, 9, N)                 # makine teslim + devreye alma (ay)

    def maliyet(kolon, carpan):
        toplam = np.interp(carpan, egri.TalepCarpani, egri[kolon])
        mesai = np.interp(carpan, egri.TalepCarpani, egri[kolon + "Mesai"])
        return 2 * ((toplam - mesai) + mesai_k * mesai)  # 6 aylık → yıllık

    nakit_a = np.zeros((N, YIL))
    nakit_b = np.zeros((N, YIL))
    nakit_c = np.zeros((N, YIL))
    yatirim_c = np.zeros((N, YIL))          # C: makine ödemesi hangi yılın başında yapıldı
    siparis_yili = np.full(N, -1)
    for y in range(YIL):
        carpan = np.clip(m1 * (1 + buyume) ** y, IZGARA[0], IZGARA[-1])
        baz = maliyet("Baz", carpan)
        yalin = baz - gerceklesme * (baz - maliyet("Yalin", carpan))
        makine = maliyet("Makine", carpan)
        ikisi = makine - gerceklesme * (makine - maliyet("YalinMakine", carpan))
        hurda_y = hurda * hurda_k * carpan
        nakit_a[:, y] = (baz - yalin) + hurda_y - opex_a
        oran = np.clip((12 - teslim_ay) / 12, 0, 1) if y == 0 else 1.0
        nakit_b[:, y] = (baz - makine) * oran - opex_b * oran
        # C: yıl başında talep eşiği aşılmışsa makine siparişi; teslim süresi kadar gecikmeyle devreye girer
        yeni = (siparis_yili < 0) & (carpan > TETIK)
        siparis_yili[yeni] = y
        yatirim_c[yeni, y] = capex_b[yeni]
        aktif = np.where(siparis_yili == y, np.clip((12 - teslim_ay) / 12, 0, 1),
                         np.where((siparis_yili >= 0) & (siparis_yili < y), 1.0, 0.0))
        nakit_c[:, y] = (baz - yalin) * (1 - aktif) + (baz - ikisi) * aktif + hurda_y - opex_a - opex_b * aktif
    iskonto = 1 / (1 + ISKONTO) ** np.arange(1, YIL + 1)
    iskonto_bas = 1 / (1 + ISKONTO) ** np.arange(0, YIL)
    npv_a = -capex_a + nakit_a @ iskonto
    npv_b = -capex_b + nakit_b @ iskonto + 0.35 * capex_b / (1 + ISKONTO) ** YIL
    kalinti_c = np.where(siparis_yili >= 0, capex_b * np.minimum(0.35 + 0.13 * siparis_yili, 0.8), 0.0)
    npv_c = -capex_a - yatirim_c @ iskonto_bas + nakit_c @ iskonto + kalinti_c / (1 + ISKONTO) ** YIL

    def geri_odeme(capex, nakit):
        aylik = np.repeat(nakit / 12, 12, axis=1)
        kum = np.cumsum(aylik, axis=1)
        odendi = kum >= capex[:, None]
        return np.where(odendi.any(axis=1), odendi.argmax(axis=1) + 1, np.nan)

    def kumulatif(capex, nakit, kalinti=None):
        aylik = np.repeat(nakit / 12, 12, axis=1) / (1 + ISKONTO) ** (np.arange(1, 12 * YIL + 1) / 12)
        kum = -capex[:, None] + np.cumsum(aylik, axis=1)
        if kalinti is not None:
            kum[:, -1] += kalinti / (1 + ISKONTO) ** YIL
        return kum

    kum_c = kumulatif(capex_a, nakit_c, kalinti_c)
    for y in range(1, YIL):  # C'de sonraki yıllardaki makine ödemesini kendi ayında düş
        kum_c[:, 12 * y:] -= (yatirim_c[:, y] / (1 + ISKONTO) ** y)[:, None]
    return {
        "npv_a": npv_a, "npv_b": npv_b, "npv_c": npv_c,
        "geri_a": geri_odeme(capex_a, nakit_a), "geri_b": geri_odeme(capex_b, nakit_b),
        "kum_a": kumulatif(capex_a, nakit_a), "kum_b": kumulatif(capex_b, nakit_b, 0.35 * capex_b), "kum_c": kum_c,
        "yil1_fayda_a": nakit_a[:, 0] + opex_a, "yil1_fayda_b": nakit_b[:, 0],
        "capex_a": capex_a, "capex_b": capex_b, "siparis_yili_c": siparis_yili,
    }


def main() -> None:
    egri = maliyet_egrileri()
    hurda = hurda_tasarrufu_yillik()
    s = monte_carlo(egri, hurda)
    npv_a, npv_b, npv_c = s["npv_a"], s["npv_b"], s["npv_c"]
    p = lambda x, q: float(np.nanpercentile(x, q))  # noqa: E731
    siparis = s["siparis_yili_c"]
    ozet = {
        "C": {"npv_p10": p(npv_c, 10), "npv_p50": p(npv_c, 50), "npv_p90": p(npv_c, 90),
              "pozitif_olasilik": float((npv_c > 0).mean()),
              "makine_alinma_olasilik": float((siparis >= 0).mean()),
              "makine_alim_yili_p50": float(np.median(siparis[siparis >= 0]) + 1) if (siparis >= 0).any() else None},
        "en_iyi_secenek_olasilik": {
            ad: float(v) for ad, v in zip("ABC", np.bincount(np.argmax(np.vstack([npv_a, npv_b, npv_c]), axis=0),
                                                              minlength=3) / N)},
        "C_A_dan_iyi": float((npv_c > npv_a).mean()), "C_B_den_iyi": float((npv_c > npv_b).mean()),
        "hurda_tasarrufu_yillik_tl": hurda,
        "A": {"npv_p10": p(npv_a, 10), "npv_p50": p(npv_a, 50), "npv_p90": p(npv_a, 90),
              "pozitif_olasilik": float((npv_a > 0).mean()), "geri_odeme_ay_p50": p(s["geri_a"], 50),
              "yil1_fayda_p50": p(s["yil1_fayda_a"], 50), "capex_p50": p(s["capex_a"], 50)},
        "B": {"npv_p10": p(npv_b, 10), "npv_p50": p(npv_b, 50), "npv_p90": p(npv_b, 90),
              "pozitif_olasilik": float((npv_b > 0).mean()), "geri_odeme_ay_p50": p(s["geri_b"], 50),
              "geri_odeme_yok_olasilik": float(np.isnan(s["geri_b"]).mean()),
              "yil1_fayda_p50": p(s["yil1_fayda_b"], 50), "capex_p50": p(s["capex_b"], 50)},
        "A_daha_iyi_olasilik": float((npv_a > npv_b).mean()),
        "N": N, "iskonto": ISKONTO, "ufuk_yil": YIL,
    }
    ozet_yaz("finans", ozet)
    pd.DataFrame([{"Secenek": SECENEK_AD[k], **{a: b for a, b in ozet[k].items() if a.startswith("npv") or
                                                 a == "pozitif_olasilik"}} for k in "ABC"]) \
        .to_csv(TABLO / "finans_ozet.csv", index=False, encoding="utf-8")
    npvler = {"A": npv_a, "B": npv_b, "C": npv_c}
    kutular = np.linspace(min(x.min() for x in npvler.values()), max(x.max() for x in npvler.values()), 61)
    hist = []
    for k, x in npvler.items():
        f, _ = np.histogram(x, bins=kutular)
        hist += [(SECENEK_AD[k], (kutular[j] + kutular[j + 1]) / 2, int(f[j])) for j in range(len(f))]
    pd.DataFrame(hist, columns=["Secenek", "NPVOrta", "Frekans"]).to_csv(
        TABLO / "monte_carlo_npv_dagilimi.csv", index=False, encoding="utf-8")
    for k in "ABC":
        print(k, {a: (round(b / 1e6, 2) if ("npv" in a or "fayda" in a or "capex" in a) else b)
                  for a, b in ozet[k].items()})
    print("En iyi seçenek olasılığı:", ozet["en_iyi_secenek_olasilik"])

    # ---- Grafik 20: NPV dağılımları (P5–P95 kutu grafiği) ----
    renkler = {"A": MAVI, "B": SARI, "C": SU_YESILI}
    fig, ax = plt.subplots(figsize=(8.6, 4.4) if SUNUM else (11, 4.8))  # slaytta yazılar okunur kalsın
    sira = ["B", "C", "A"]
    bp = ax.boxplot([npvler[k] / 1e6 for k in sira], orientation="horizontal", widths=0.5, whis=(5, 95),
                    showfliers=False,
                    patch_artist=True, medianprops={"color": MUREKKEP, "lw": 2},
                    whiskerprops={"color": IKINCIL, "lw": 1.2}, capprops={"color": IKINCIL, "lw": 1.2},
                    boxprops={"lw": 0})
    for kutu, k in zip(bp["boxes"], sira):
        kutu.set_facecolor(renkler[k])
    ax.axvline(0, color=MUREKKEP, lw=1.2)
    for yi, k in enumerate(sira, start=1):
        o = ozet[k]
        ax.text(np.percentile(npvler[k], 95) / 1e6 + 1.5, yi,
                f"medyan {sayi(o['npv_p50'] / 1e6, 1)} M · P10 {sayi(o['npv_p10'] / 1e6, 1)} M\n"
                f"P(NPV > 0) = {yuzde(o['pozitif_olasilik'], 0)}", va="center", fontsize=8.8, color=MUREKKEP)
    ax.set_yticks(range(1, 4))
    ax.set_yticklabels([SECENEK_AD[k] for k in sira])
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.set_xlim(min(np.percentile(x, 5) for x in npvler.values()) / 1e6 - 3,
                max(np.percentile(x, 95) for x in npvler.values()) / 1e6 + 22)
    ax.set_xlabel("5 yıllık net bugünkü değer, milyon TL (sabit 2026 fiyatları, reel iskonto %12) · kutu P25–P75, bıyık P5–P95")
    en_iyi = max(ozet["en_iyi_secenek_olasilik"], key=ozet["en_iyi_secenek_olasilik"].get)
    baslik(ax, f"Aşamalı yol (C) senaryoların {yuzde(ozet['en_iyi_secenek_olasilik']['C'], 0)}'ünde en yüksek değeri veriyor; "
               f"kötü senaryoda bile A kadar güvenli",
           "Monte Carlo (N = 10.000): talep, büyüme, kazanımların kalıcılığı, yatırım tutarı (kur), işletme gideri, "
           "mesai ücreti, teslim süresi")
    kaynak_notu(fig, "Kaynak: Optimizasyon tabanlı maliyet eğrileri (05) + Monte Carlo")
    kaydet(fig, "20_monte_carlo_npv.png")
    ozet_yaz("finans", {**ozet, "en_iyi": en_iyi})

    # ---- Grafik 21: kümülatif indirgenmiş nakit akışı ----
    fig, ax = plt.subplots(figsize=(11, 5.2))
    aylar = np.arange(1, 12 * YIL + 1)
    for k in ("B", "C", "A"):
        x = s[f"kum_{k.lower()}"] / 1e6
        if k != "C":  # bantlar üst üste binip okunmasın diye yalnızca A ve B için
            ax.fill_between(aylar, np.percentile(x, 10, axis=0), np.percentile(x, 90, axis=0), color=renkler[k],
                            alpha=0.16, lw=0)
        ax.plot(aylar, np.median(x, axis=0), color=renkler[k], lw=2.4, label=f"{SECENEK_AD[k]} · medyan")
    ax.axhline(0, color=MUREKKEP, lw=1)
    ax.set_xticks(np.arange(0, 12 * YIL + 1, 6))
    ax.set_xlabel("Ay · bantlar: A ve B için P10–P90 aralığı")
    ax.set_ylabel("Kümülatif indirgenmiş nakit (milyon TL)")
    ax.legend(loc="upper left")
    baslik(ax, f"Yalın paket kendini ~{sayi(ozet['A']['geri_odeme_ay_p50'])} ayda, yeni makine "
               f"~{sayi(ozet['B']['geri_odeme_ay_p50'])} ayda geri ödüyor",
           "Kümülatif indirgenmiş nakit akışı · makine için 5. yıl sonunda hurda değeri dahil · C'de makine ödemesi "
           "tetiklendiği yılın başında")
    kaynak_notu(fig, "Kaynak: Monte Carlo (N = 10.000)")
    kaydet(fig, "21_kumulatif_nakit_akisi.png")


if __name__ == "__main__":
    main()
