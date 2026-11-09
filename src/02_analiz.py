"""02 — Ölç & Analiz Et: KPI'lar, kayıp analizi, istatistiksel testler ve SPC.

Cevaplanan sorular
1. Hangi makine darboğaz?                → kapasite kullanımı
2. Darboğaz neden düşük OEE'de?          → kayıp şelalesi, duruş Pareto'su, MTBF/MTTR
3. Vardiya farkı gerçek mi, tesadüf mü?  → ANOVA / Kruskal-Wallis, ki-kare
4. Süreç müşteri toleransını tutuyor mu? → X̄-R kontrol kartı, Cpk / Ppk
5. Teslimata ve maliyete etkisi ne?      → OTD, ceza, ekspres nakliye, fazla mesai
6. Simülasyon modeli için parametreler   → ciktilar/tablolar/sim_parametreleri.json
"""
from __future__ import annotations

import json
import textwrap

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from matplotlib.colors import LinearSegmentedColormap
from scipy import stats

from grafik_stili import (DARBOGAZ_RENK, DURUM, EKSEN, GOLGE, GRI_SERI, HAT_RENK, IKINCIL, MAVI, MAVI_RAMPA, MUREKKEP,
                          SARI, SERI, SOLUK, SU_YESILI, SUNUM, YUZEY, baslik, kaydet, kaynak_notu, sayi_ekseni,
                          stil_uygula, ust_baslik, yuzde_ekseni)
from ortak import (AY_KISA, DURUS_NEDENLERI, HATA_TURLERI, IDEAL_CEVRIM, MAKINELER, PILOT_BASLANGIC, SPC_LSL,
                   SPC_USL, TABLO, URUNLER, ay_etiketi, milyon_tl, ozet_yaz, sayi, yuzde)
from veri_yukle import oee_tablosu, yukle

stil_uygula()
V = yukle()
U, D, K, O, S, M = V["uretim"], V["durus"], V["kalite"], V["olcum"], V["siparis"], V["mesai"]
BAZ = U[U.Donem == "Baz"]
FRZ = "M04"
GECE_RENK = SERI[6]  # mor: gece vardiyası kimliği
NEDEN = DURUS_NEDENLERI.set_index("NedenID")
KOD = MAKINELER.set_index("MakineID")["MakineKodu"].to_dict()
AILE = URUNLER.set_index("UrunID")["UrunAilesi"].to_dict()
OZET: dict = {}


def ay_eksenini_ayarla(ax, aylar) -> None:
    """Ay ekseni; slayt sürümünde etiketler sığsın diye iki ayda bir yazılır."""
    ax.set_xticks(aylar)
    ax.set_xticklabels([ay_etiketi(a) if (i % 2 == 0 or not SUNUM) else "" for i, a in enumerate(aylar)])


def pilot_golgesi(ax, ymax_metin: float) -> None:
    sol = PILOT_BASLANGIC - pd.Timedelta(days=15)
    ax.axvspan(sol, sol + pd.Timedelta(days=31), color=GOLGE, zorder=0, lw=0)
    ax.text(PILOT_BASLANGIC, ymax_metin, "Pilot", ha="center", va="bottom", fontsize=8.5, color=IKINCIL)


# --------------------------------------------------------------------------
# 1) KPI özeti
# --------------------------------------------------------------------------
def kpi_ozeti() -> None:
    makine = oee_tablosu(U, ["MakineID", "Donem"])
    hat = oee_tablosu(U, ["Hat", "Donem"])
    s_baz = S[S.Donem == "Baz"]
    OZET.update({
        "frz_oee_baz": makine.loc[(FRZ, "Baz"), "OEE"],
        "frz_oee_pilot": makine.loc[(FRZ, "Pilot"), "OEE"],
        "frz_kullanilabilirlik_baz": makine.loc[(FRZ, "Baz"), "Kullanilabilirlik"],
        "frz_performans_baz": makine.loc[(FRZ, "Baz"), "Performans"],
        "frz_kalite_baz": makine.loc[(FRZ, "Baz"), "Kalite"],
        "frz_kullanilabilirlik_pilot": makine.loc[(FRZ, "Pilot"), "Kullanilabilirlik"],
        "frz_performans_pilot": makine.loc[(FRZ, "Pilot"), "Performans"],
        "frz_kapasite_kullanimi_baz": makine.loc[(FRZ, "Baz"), "KapasiteKullanimi"],
        "hat1_oee_baz": hat.loc[("Hat-1", "Baz"), "OEE"],
        "hat2_oee_baz": hat.loc[("Hat-2", "Baz"), "OEE"],
        "otd_hat1_baz": s_baz[s_baz.Hat == "Hat-1"].ZamanindaMi.mean(),
        "otd_hat2_baz": s_baz[s_baz.Hat == "Hat-2"].ZamanindaMi.mean(),
        "otd_toplam_baz": s_baz.ZamanindaMi.mean(),
        "otd_hat1_pilot": S[(S.Donem == "Pilot") & (S.Hat == "Hat-1")].ZamanindaMi.mean(),
        "otd_hat1_pilot_2_4_hafta": S[(S.TerminTarihi >= "2026-10-05") & (S.Hat == "Hat-1")].ZamanindaMi.mean(),
        "otd_hat1_haziran": S[(S.Ay == "2026-06-01") & (S.Hat == "Hat-1")].ZamanindaMi.mean(),
        "ceza_baz_tl": s_baz.CezaTutariTL.sum(),
        "ekspres_baz_tl": s_baz.EkspresNakliyeTL.sum(),
        "fazla_mesai_baz_tl": M[M.Donem == "Baz"].MaliyetTL.sum(),
        "fazla_mesai_baz_pazar": int((M.Donem == "Baz").sum()),
        "fazla_mesai_baz_vardiya": int(M[M.Donem == "Baz"].VardiyaSayisi.sum()),
        "hurda_maliyeti_baz_tl": BAZ.HurdaMaliyetiTL.sum(),
        "hurda_orani_hat1_baz": BAZ[BAZ.Hat == "Hat-1"].HurdaAdet.sum() / BAZ[BAZ.Hat == "Hat-1"].UretilenAdet.sum(),
        "ciro_baz_tl": s_baz.Tutar.sum(),
        "siparis_sayisi_baz": int(len(s_baz)),
        "geciken_siparis_baz": int((s_baz.ZamanindaMi == 0).sum()),
        "ort_gecikme_gun_baz": s_baz[s_baz.ZamanindaMi == 0].GecikmeGun.mean(),
    })
    tablo = makine[["Kullanilabilirlik", "Performans", "Kalite", "OEE", "KapasiteKullanimi"]].round(4)
    tablo.to_csv(TABLO / "makine_oee_baz_pilot.csv", encoding="utf-8")


# --------------------------------------------------------------------------
# 2) Grafikler: OEE trendi ve darboğaz
# --------------------------------------------------------------------------
def grafik_oee_trend() -> None:
    hat = oee_tablosu(U, ["Ay", "Hat"]).OEE.unstack("Hat")
    frz = oee_tablosu(U[U.MakineID == FRZ], "Ay").OEE
    fig, ax = plt.subplots(figsize=(11, 5.2))
    pilot_golgesi(ax, 0.905)
    ax.axhline(0.75, color=EKSEN, lw=1.2, zorder=1)
    ax.text(frz.index[0] - pd.Timedelta(days=12), 0.755, "Hedef %75", fontsize=8.5, color=IKINCIL, va="bottom")
    seriler = [("Hat-2 ortalaması", hat["Hat-2"], HAT_RENK["Hat-2"], 2),
               ("Hat-1 ortalaması", hat["Hat-1"], HAT_RENK["Hat-1"], 2),
               ("H1-FRZ (darboğaz)", frz, DARBOGAZ_RENK, 2.6)]
    for ad, seri, renk, kalinlik in seriler:
        ax.plot(seri.index, seri.values, color=renk, lw=kalinlik, marker="o", ms=4.5, label=ad, zorder=3,
                markeredgecolor=YUZEY, markeredgewidth=1.2)
        ax.annotate(yuzde(seri.iloc[-1], 0), (seri.index[-1], seri.iloc[-1]), xytext=(8, 0),
                    textcoords="offset points", va="center", fontsize=9, color=MUREKKEP, fontweight="semibold")
    ay_eksenini_ayarla(ax, frz.index)
    ax.set_ylim(0.45, 0.92)
    ax.set_xlim(frz.index[0] - pd.Timedelta(days=20), frz.index[-1] + pd.Timedelta(days=28))
    yuzde_ekseni(ax)
    ax.legend(loc="upper left", ncols=3, bbox_to_anchor=(0, 1.0))
    baslik(ax, f"Darboğaz H1-FRZ'nin OEE'si bir yıl boyunca {yuzde(OZET['frz_oee_baz'], 0)} civarında kaldı",
           "Aylık OEE (Kullanılabilirlik × Performans × Kalite) · Ekim 2025 – Ekim 2026")
    kaynak_notu(fig)
    kaydet(fig, "01_oee_aylik_trend.png")


def grafik_kapasite_kullanimi() -> None:
    t = oee_tablosu(BAZ, "MakineID")
    t["Etiket"] = [f"{KOD[m]}  {MAKINELER.set_index('MakineID').at[m, 'Makine']}" for m in t.index]
    t = t.sort_values("KapasiteKullanimi")
    fig, ax = plt.subplots(figsize=(11, 5.0))
    renkler = [DARBOGAZ_RENK if m == FRZ else GRI_SERI for m in t.index]
    ax.barh(t.Etiket, t.KapasiteKullanimi, color=renkler, height=0.62)
    for y, (m, v) in enumerate(t.KapasiteKullanimi.items()):
        ax.text(v + 0.01, y, yuzde(v, 0), va="center", fontsize=9,
                color=MUREKKEP, fontweight="semibold" if m == FRZ else "normal")
    ax.set_xlim(0, 1.12)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.tick_params(axis="y", length=0)
    yuzde_ekseni(ax, "x")
    baslik(ax, f"H1-FRZ planlı sürenin {yuzde(OZET['frz_kapasite_kullanimi_baz'], 0)}'ünde dolu: hattın darboğazı",
           "Kapasite kullanımı = makinenin iş yüklenen süresi / vardiya takvimi · Baz dönem (Eki 25 – Eyl 26)")
    kaynak_notu(fig)
    kaydet(fig, "02_kapasite_kullanimi.png")
    OZET["kapasite_kullanimi_baz"] = {KOD[m]: round(v, 3) for m, v in t.KapasiteKullanimi.items()}


def frz_kayiplari() -> dict:
    u = BAZ[BAZ.MakineID == FRZ]
    d = D[(D.MakineID == FRZ) & (D.Donem == "Baz") & (D.NedenID != "D09")].copy()
    d["Kategori"] = d.NedenID.map(NEDEN["Kategori"])
    planlanan, calisma, ideal = u.PlanlananSureDk.sum(), u.CalismaSuresiDk.sum(), u.IdealSureDk.sum()
    q = u.SaglamAdet.sum() / u.UretilenAdet.sum()
    durus_toplam = planlanan - calisma
    pay = d.groupby("Kategori").SureDk.sum()
    pay = pay / pay.sum() * durus_toplam  # olay toplamını kesin süre farkına ölçekle
    return {
        "Planlanan süre": planlanan,
        "Ayar & değişim": pay.get("Ayar & Değişim", 0),
        "Arıza": pay.get("Arıza", 0),
        "Diğer duruşlar": durus_toplam - pay.get("Ayar & Değişim", 0) - pay.get("Arıza", 0),
        "Hız kaybı ve küçük duruşlar": calisma - ideal,
        "Kalite kaybı": ideal * (1 - q),
        "OEE (değer katan süre)": ideal * q,
    }


def grafik_kayip_selalesi() -> None:
    k = frz_kayiplari()
    toplam = k["Planlanan süre"]
    adlar = list(k)
    fig, ax = plt.subplots(figsize=(11, 5.4))
    seviye = toplam
    for i, ad in enumerate(adlar):
        v = k[ad] / toplam
        if i == 0 or i == len(adlar) - 1:
            ax.bar(i, v, color=MAVI if i == 0 else DARBOGAZ_RENK, width=0.62)
            ax.text(i, v + 0.015, yuzde(v, 0), ha="center", fontsize=10, color=MUREKKEP, fontweight="semibold")
        else:
            ust = seviye / toplam
            ax.bar(i, -v, bottom=ust, color=DURUM["kritik"], width=0.62)
            ax.text(i, ust + 0.015, "−" + yuzde(v, 1), ha="center", fontsize=9.5, color=MUREKKEP)
            seviye -= k[ad]
    ax.set_xticks(range(len(adlar)))
    ax.set_xticklabels([textwrap.fill(a, 13) for a in adlar], fontsize=9)
    ax.set_ylim(0, 1.1)
    yuzde_ekseni(ax)
    saat = toplam / 60 / 12
    baslik(ax, f"H1-FRZ'nin planlı süresinin yalnızca {yuzde(k['OEE (değer katan süre)'] / toplam, 0)}'ı sağlam ürüne dönüşüyor",
           f"OEE kayıp şelalesi, planlanan sürenin yüzdesi · Baz dönem, ayda ortalama {sayi(saat)} saat planlı süre")
    kaynak_notu(fig)
    kaydet(fig, "03_frz_kayip_selalesi.png")
    OZET["frz_kayip_payi"] = {a: round(v / toplam, 4) for a, v in k.items()}


def pareto_ciz(ax, seri: pd.Series, renk: str) -> pd.Series:
    pay = seri.sort_values(ascending=False) / seri.sum()
    kum = pay.cumsum()
    x = np.arange(len(pay))
    ax.bar(x, pay.values, color=renk, width=0.62, label="Pay")
    ax.plot(x, kum.values, color=IKINCIL, lw=2, marker="o", ms=5, markeredgecolor=YUZEY, label="Kümülatif pay")
    ax.axhline(0.8, color=EKSEN, lw=1)
    ax.text(len(pay) - 0.6, 0.81, "%80", fontsize=8, color=IKINCIL, ha="right", va="bottom")
    for i, p in enumerate(pay.values):
        if p > 0.12:  # uzun çubukta etiket içeride, kümülatif çizgiyle çakışmasın
            ax.text(i, p - 0.02, yuzde(p, 0), ha="center", va="top", fontsize=9, color="#ffffff",
                    fontweight="semibold")
        else:
            ax.text(i, p + 0.015, yuzde(p, 0), ha="center", fontsize=8.5, color=MUREKKEP)
    ax.set_xticks(x)
    ax.set_ylim(0, 1.08)
    yuzde_ekseni(ax)
    return pay


def grafik_durus_pareto() -> None:
    d = D[(D.MakineID == FRZ) & (D.Donem == "Baz") & (D.NedenID != "D09")]
    seri = d.groupby("NedenID").SureDk.sum()
    fig, ax = plt.subplots(figsize=(11, 5.4))
    pay = pareto_ciz(ax, seri, MAVI)
    ax.set_xticklabels([textwrap.fill(NEDEN.at[n, "Neden"], 10 if SUNUM else 15) for n in pay.index],
                       fontsize=8 if SUNUM else 8.5)
    ax.legend(loc="center right")
    ilk_iki = pay.iloc[:2].sum()
    baslik(ax, f"H1-FRZ duruşlarının {yuzde(ilk_iki, 0)}'u iki kaynaktan: mekanik arıza ve ürün değişimi",
           f"Duruş süresinin nedenlere dağılımı (Pareto) · Baz dönem, toplam {sayi(seri.sum() / 60)} saat plansız duruş")
    kaynak_notu(fig)
    kaydet(fig, "04_frz_durus_pareto.png")
    OZET["frz_durus_pareto"] = {NEDEN.at[n, "Neden"]: round(v, 4) for n, v in pay.items()}
    OZET["frz_plansiz_durus_saat_baz"] = seri.sum() / 60


def grafik_vardiya_isi_haritasi() -> None:
    t = oee_tablosu(BAZ, ["MakineID", "VardiyaID"]).OEE.unstack("VardiyaID")
    t.index = [KOD[m] for m in t.index]
    cmap = LinearSegmentedColormap.from_list("mavi", MAVI_RAMPA[1:11])
    fig, ax = plt.subplots(figsize=(8.6, 5.6))
    vmin, vmax = 0.5, 0.9
    ax.imshow(t.values, cmap=cmap, vmin=vmin, vmax=vmax, aspect="auto")
    for i in range(t.shape[0]):
        for j in range(t.shape[1]):
            v = t.values[i, j]
            koyu = (v - vmin) / (vmax - vmin) > 0.55
            ax.text(j, i, yuzde(v, 0), ha="center", va="center", fontsize=10,
                    color="#ffffff" if koyu else MUREKKEP, fontweight="semibold" if t.index[i] == "H1-FRZ" else "normal")
    ax.set_xticks(range(3))
    ax.set_xticklabels(["A  07–15", "B  15–23", "C  23–07 (gece)"])
    ax.set_yticks(range(len(t)))
    ax.set_yticklabels(t.index)
    ax.tick_params(length=0)
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks(np.arange(-0.5, 3, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(t), 1), minor=True)
    ax.grid(which="minor", color=YUZEY, linewidth=2)
    ax.tick_params(which="minor", length=0)
    fark = (t["A"] - t["C"]).mean()
    baslik(ax, f"Gece vardiyası tüm makinelerde ortalama {sayi(fark * 100, 1)} puan geride",
           "OEE, makine × vardiya · Baz dönem · koyu = yüksek")
    kaynak_notu(fig)
    kaydet(fig, "05_vardiya_oee_isi_haritasi.png")
    OZET["vardiya_oee_farki_A_C_puan"] = fark * 100


def grafik_kalite() -> None:
    k = K[(K.Donem == "Baz") & (K.Hat == "Hat-1")]
    seri = k.groupby("HataID").Adet.sum()
    hata = HATA_TURLERI.set_index("HataID")["HataTuru"]
    vardiya = BAZ[BAZ.Hat == "Hat-1"].groupby("VardiyaID")[["HurdaAdet", "UretilenAdet"]].sum()
    oran = vardiya.HurdaAdet / vardiya.UretilenAdet
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5.2), gridspec_kw={"width_ratios": [2.3, 1]})
    pay = pareto_ciz(ax1, seri, MAVI)
    ax1.set_xticklabels([textwrap.fill(hata[h], 11) for h in pay.index], fontsize=8.5)
    ax1.legend(loc="center right")
    ax1.set_title("Hata türlerine göre hurda (Hat-1)", fontsize=10.5, loc="left")
    renk = [GRI_SERI, GRI_SERI, GECE_RENK]
    ax2.bar(["A", "B", "C (gece)"], oran.values, color=renk, width=0.6)
    for i, v in enumerate(oran.values):
        ax2.text(i, v + 0.0006, yuzde(v, 2), ha="center", fontsize=9.5, color=MUREKKEP)
    ax2.set_ylim(0, oran.max() * 1.25)
    ax2.yaxis.set_major_locator(plt.MultipleLocator(0.005))
    yuzde_ekseni(ax2, ondalik=1)
    ax2.set_title("Hurda oranı, vardiya", fontsize=10.5, loc="left")
    kat = oran["C"] / oran[["A", "B"]].mean()
    grup = HATA_TURLERI.set_index("HataID")["HataGrubu"]
    boyutsal = seri[grup.reindex(seri.index) == "Boyutsal"].sum() / seri.sum()
    ust_baslik(fig, f"Hurdanın {yuzde(boyutsal, 0)}'ü boyutsal (ölçü dışı, salgı); gece vardiyasında hurda oranı "
                    f"{sayi(kat, 1)} kat", "Hat-1 tüm operasyonlar · Baz dönem")
    OZET["hurda_boyutsal_pay"] = boyutsal
    kaynak_notu(fig)
    kaydet(fig, "06_kalite_pareto_vardiya.png")
    OZET["hurda_gece_kat"] = kat
    OZET["hata_pareto_hat1"] = {hata[h]: round(v, 4) for h, v in pay.items()}


# --------------------------------------------------------------------------
# 3) İstatistiksel testler
# --------------------------------------------------------------------------
def istatistik_testleri() -> pd.DataFrame:
    sonuc = []
    # (a) Vardiya → H1-FRZ OEE (vardiya bazlı gözlemler)
    v = BAZ[BAZ.MakineID == FRZ].groupby(["Tarih", "VardiyaID"]).agg(
        P=("PlanlananSureDk", "sum"), I=("IdealSureDk", "sum"), S=("SaglamAdet", "sum"), Ur=("UretilenAdet", "sum"))
    v = v[v.P > 200]
    v["OEE"] = v.I / v.P * v.S / v.Ur.clip(lower=1)
    gruplar = [g.OEE.values for _, g in v.groupby(level="VardiyaID")]
    f, p = stats.f_oneway(*gruplar)
    h, p_kw = stats.kruskal(*gruplar)
    ort = v.groupby(level="VardiyaID").OEE.mean()
    sonuc.append(("Vardiya → H1-FRZ OEE", "Tek yönlü ANOVA", f"F = {f:.1f}", p,
                  f"Ortalama OEE A {yuzde(ort['A'])}, B {yuzde(ort['B'])}, C {yuzde(ort['C'])}"))
    sonuc.append(("Vardiya → H1-FRZ OEE", "Kruskal-Wallis (dağılımdan bağımsız)", f"H = {h:.1f}", p_kw,
                  "ANOVA sonucunu doğruluyor"))
    # (b) Vardiya → hurda (ki-kare, Hat-1)
    t = BAZ[BAZ.Hat == "Hat-1"].groupby("VardiyaID")[["HurdaAdet", "SaglamAdet"]].sum()
    chi2, p_chi, _, _ = stats.chi2_contingency(t.values)
    sonuc.append(("Vardiya → hurda oranı (Hat-1)", "Ki-kare bağımsızlık testi", f"χ² = {chi2:.0f}", p_chi,
                  "Gece vardiyasında hurda oranı anlamlı biçimde yüksek"))
    # (c) Vardiya içi duruş dakikaları → vardiya sağlam çıktısı (çoklu doğrusal regresyon)
    cikti = BAZ[BAZ.MakineID == FRZ].groupby(["Tarih", "VardiyaID"]).agg(
        Saglam=("SaglamAdet", "sum"), Planlanan=("PlanlananSureDk", "sum"))
    dd = D[(D.MakineID == FRZ) & (D.Donem == "Baz") & (D.NedenID != "D09")].copy()
    dd["Grup"] = dd.NedenID.map({"D01": "AyarDk", "D02": "AyarDk", "D03": "ArizaDk", "D04": "ArizaDk"}).fillna("DigerDk")
    durus = dd.pivot_table(index=["Tarih", "VardiyaID"], columns="Grup", values="SureDk", aggfunc="sum")
    g = cikti.join(durus).fillna(0)
    g = g[g.Planlanan >= 440]  # tam vardiyalar (planlı bakım hariç)
    X = sm.add_constant(g[["AyarDk", "ArizaDk", "DigerDk"]])
    model = sm.OLS(g.Saglam, X).fit()
    katsayi, p_ayar = model.params["AyarDk"], model.pvalues["AyarDk"]
    sonuc.append(("Vardiyadaki duruş dakikaları → H1-FRZ vardiya çıktısı", "Çoklu doğrusal regresyon (OLS)",
                  f"ayar katsayısı = {katsayi:.2f} adet/dk, R² = {model.rsquared:.2f}", p_ayar,
                  f"H1-FRZ'de 1 dk duruş ≈ {abs(katsayi):.2f} sağlam parça kaybı"))
    g["ToplamDurusDk"] = g[["AyarDk", "ArizaDk", "DigerDk"]].sum(axis=1)
    OZET["frz_dk_basina_kayip_adet"] = abs(katsayi)
    OZET["frz_regresyon"] = {"r2": model.rsquared, "katsayilar": model.params.round(3).to_dict(),
                             "n_vardiya": int(model.nobs)}
    # (d) Pilot: ayar süresi (Welch t) ve arıza oranı (Poisson oran testi)
    st = D[(D.MakineID == FRZ) & (D.NedenID == "D01")]
    a, b = st[st.Donem == "Baz"].SureDk, st[st.Donem == "Pilot"].SureDk
    t_stat, p_t = stats.ttest_ind(a, b, equal_var=False)
    sonuc.append(("Pilot → H1-FRZ ayar süresi", "Welch t-testi", f"t = {t_stat:.1f}", p_t,
                  f"Ortalama {a.mean():.0f} dk → {b.mean():.0f} dk"))
    ariza = D[(D.MakineID == FRZ) & D.NedenID.isin(["D03", "D04"])]
    saat = U[U.MakineID == FRZ].groupby("Donem").CalismaSuresiDk.sum() / 60
    n_baz, n_pil = (ariza.Donem == "Baz").sum(), (ariza.Donem == "Pilot").sum()
    p_pois = stats.binomtest(int(n_pil), int(n_baz + n_pil), saat["Pilot"] / saat.sum(), alternative="less").pvalue
    sonuc.append(("Pilot → H1-FRZ arıza sıklığı", "Poisson oran testi (koşullu binom)",
                  f"{n_baz / saat['Baz'] * 100:.2f} → {n_pil / saat['Pilot'] * 100:.2f} arıza/100 çalışma saati",
                  p_pois, "TPM sonrası arıza sıklığı düştü"))
    df = pd.DataFrame(sonuc, columns=["Hipotez", "Test", "İstatistik", "p_degeri", "Yorum"])
    df["Sonuç (α = 0,05)"] = np.where(df.p_degeri < 0.05, "Anlamlı", "Anlamlı değil")
    df.to_csv(TABLO / "istatistik_testleri.csv", index=False, encoding="utf-8")
    OZET["istatistik_testleri"] = df.assign(p_degeri=df.p_degeri.map(lambda x: f"{x:.2e}")).to_dict("records")
    OZET["vardiya_oee_frz"] = ort.to_dict()
    return g


def grafik_durus_cikti(g: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 5.0))
    ax.scatter(g.ToplamDurusDk, g.Saglam, s=12, color=MAVI, alpha=0.4, lw=0, label="Vardiya (n = "
               f"{len(g)})")
    reg = stats.linregress(g.ToplamDurusDk, g.Saglam)
    xs = np.array([0, g.ToplamDurusDk.quantile(0.995)])
    ax.plot(xs, reg.intercept + reg.slope * xs, color=DARBOGAZ_RENK, lw=2.2, label="Doğrusal model")
    ax.set_xlabel("Vardiyadaki plansız duruş (dk)")
    ax.set_ylabel("H1-FRZ vardiya sağlam çıktısı (adet)")
    ax.grid(axis="x", visible=True)
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0)
    sayi_ekseni(ax)
    ax.legend(loc="upper right")
    kayip_10 = abs(reg.slope) * 10
    baslik(ax, f"H1-FRZ'de her 10 dakikalık duruş ≈ {sayi(kayip_10)} sağlam parça kaybı",
           f"Tam vardiyalar, baz dönem · R² = {sayi(reg.rvalue ** 2, 2)}, p < 0,001 · darboğazda kaybedilen süre telafi edilemez")
    kaynak_notu(fig)
    kaydet(fig, "07_durus_vardiya_cikti.png")


# --------------------------------------------------------------------------
# 4) SPC: X̄-R kontrol kartı ve süreç yeterliliği
# --------------------------------------------------------------------------
A2, D3, D4, d2 = 0.577, 0.0, 2.114, 2.326  # n = 5


def yeterlilik(x: np.ndarray, sigma_ic: float) -> dict:
    mu, s = x.mean(), x.std(ddof=1)
    return {"ort": mu, "s_genel": s, "s_ic": sigma_ic,
            "Cp": (SPC_USL - SPC_LSL) / (6 * sigma_ic),
            "Cpk": min(SPC_USL - mu, mu - SPC_LSL) / (3 * sigma_ic),
            "Ppk": min(SPC_USL - mu, mu - SPC_LSL) / (3 * s)}


def spc() -> None:
    alt = O.groupby(["Tarih", "VardiyaID", "AltGrupNo", "Donem"]).CapMm.agg(["mean", lambda x: x.max() - x.min(), "size"])
    alt.columns = ["Xbar", "R", "n"]
    alt = alt[alt.n == 5].reset_index().sort_values(["Tarih", "VardiyaID", "AltGrupNo"])
    baz = alt[alt.Donem == "Baz"]
    xbb, rbar = baz.Xbar.mean(), baz.R.mean()
    ucl, lcl = xbb + A2 * rbar, xbb - A2 * rbar
    limitler = {}  # iyileştirme sonrası limitler yeniden hesaplanır (faz bazlı kontrol kartı)
    for donem, g in alt.groupby("Donem"):
        limitler[donem] = (g.Xbar.mean() + A2 * g.R.mean(), g.Xbar.mean(), g.Xbar.mean() - A2 * g.R.mean())
    sonuc = {}
    for donem, g in O.groupby("Donem"):
        r_ort = alt[alt.Donem == donem].R.mean()
        sonuc[donem] = yeterlilik(g.CapMm.values, r_ort / d2)
    gece = O[(O.Donem == "Baz") & (O.VardiyaID == "C")]
    sonuc["Baz-Gece"] = yeterlilik(gece.CapMm.values, alt[(alt.Donem == "Baz") & (alt.VardiyaID == "C")].R.mean() / d2)
    gunduz = O[(O.Donem == "Baz") & (O.VardiyaID != "C")]
    sonuc["Baz-Gündüz"] = yeterlilik(gunduz.CapMm.values, alt[(alt.Donem == "Baz") & (alt.VardiyaID != "C")].R.mean() / d2)
    OZET["spc"] = sonuc
    OZET["spc_kontrol_limitleri"] = {d: {"UCL": u, "X̿": m, "LCL": l} for d, (u, m, l) in limitler.items()}
    son = alt[alt.Tarih >= "2026-08-15"].reset_index(drop=True)
    son["UCL"] = son.Donem.map(lambda d: limitler[d][0])
    son["LCL"] = son.Donem.map(lambda d: limitler[d][2])
    son["disari"] = (son.Xbar > son.UCL) | (son.Xbar < son.LCL)
    OZET["spc_kontrol_disi_oran_baz"] = float(((baz.Xbar > ucl) | (baz.Xbar < lcl)).mean())
    um = lambda v: (np.asarray(v) - 25.0) * 1000  # nominalden sapma, mikron  # noqa: E731

    fig = plt.figure(figsize=(9.5, 6.6) if SUNUM else (12, 7.2))  # slaytta yazılar okunur kalsın
    gs = fig.add_gridspec(2, 2, height_ratios=[1.25, 1], hspace=0.42, wspace=0.18)
    ax = fig.add_subplot(gs[0, :])
    x = np.arange(len(son))
    pilot_idx = son.index[son.Donem == "Pilot"].min()
    ax.axvspan(pilot_idx - 0.5, len(son) - 0.5, color=GOLGE, lw=0, zorder=0)
    ax.text((pilot_idx + len(son)) / 2, um(limitler["Baz"][0]) + 3.4, "Pilot: gece vardiyası ısınma prosedürü",
            ha="center", fontsize=8.5, color=IKINCIL)
    ax.plot(x, um(son.Xbar), color=EKSEN, lw=1, zorder=2)
    gece_mi = (son.VardiyaID == "C").values
    ax.scatter(x[~gece_mi], um(son.Xbar[~gece_mi]), s=16, color=GRI_SERI, zorder=3, label="Gündüz (A, B)")
    ax.scatter(x[gece_mi], um(son.Xbar[gece_mi]), s=16, color=GECE_RENK, zorder=3, label="Gece (C)")
    disari = son.disari.values
    ax.scatter(x[disari], um(son.Xbar[disari]), s=70, facecolors="none", edgecolors=DURUM["kritik"], lw=1.4,
               zorder=4, label="Kontrol dışı nokta")
    for donem, (x0, x1) in {"Baz": (-0.5, pilot_idx - 0.5), "Pilot": (pilot_idx - 0.5, len(son) - 0.5)}.items():
        u_, m_, l_ = limitler[donem]
        for deger, ad in ((u_, "UCL"), (m_, "X̿"), (l_, "LCL")):
            ax.hlines(um(deger), x0, x1, color=IKINCIL if ad != "X̿" else SOLUK, lw=1)
            if donem == "Pilot":
                ax.text(x1 + 0.6, um(deger), f"{ad} {sayi(um(deger), 1)}", va="center", fontsize=8, color=IKINCIL)
    ax.set_xlim(-1, len(son) + 10)
    ax.set_xticks([])
    ax.set_ylabel("Nominalden sapma (µm)")
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.02), ncols=3)
    ax.set_title("X̄ kontrol kartı · AM-200 çap, 15 Ağu – 31 Eki 2026, alt grup n = 5 · limitler faz bazlı",
                 fontsize=10.5, loc="left")

    kutular = (("Baz", "Baz dönem (12 ay)"), ("Pilot", "Pilot (Ekim 2026)"))
    for i, (donem, ad) in enumerate(kutular):
        axh = fig.add_subplot(gs[1, i])
        veri = um(O[O.Donem == donem].CapMm)
        axh.hist(veri, bins=np.arange(-20, 20.01, 1.0), color=MAVI if donem == "Pilot" else GRI_SERI,
                 edgecolor=YUZEY, linewidth=0.6)
        for sinir, ad_s in ((um(SPC_LSL), "LSL"), (um(SPC_USL), "USL")):
            axh.axvline(sinir, color=DURUM["kritik"], lw=1.4)
            axh.text(sinir, axh.get_ylim()[1] * 0.95, f" {ad_s}", color=MUREKKEP, fontsize=8, va="top")
        axh.axvline(0, color=SOLUK, lw=1)
        y = sonuc[donem]
        axh.set_title(f"{ad}: Cpk {sayi(y['Cpk'], 2)} · Ppk {sayi(y['Ppk'], 2)}", fontsize=10.5, loc="left")
        axh.set_xlim(-19, 19)
        axh.set_yticks([])
        axh.grid(False)
        axh.set_xlabel("Nominalden sapma (µm) · tolerans ±15 µm")
    ust_baslik(fig, f"Gece vardiyasında çap +{sayi((sonuc['Baz-Gece']['ort'] - 25) * 1000, 1)} µm kayıyor; "
                    f"pilotla Ppk {sayi(sonuc['Baz']['Ppk'], 2)} → {sayi(sonuc['Pilot']['Ppk'], 2)}", y_ana=0.99)
    kaynak_notu(fig)
    kaydet(fig, "08_spc_kontrol_karti_yeterlilik.png")


# --------------------------------------------------------------------------
# 5) Teslimat ve maliyet
# --------------------------------------------------------------------------
def grafik_teslimat() -> None:
    t = S.groupby(["Ay", "Hat"]).ZamanindaMi.mean().unstack("Hat")
    fig, ax = plt.subplots(figsize=(11, 5.2))
    pilot_golgesi(ax, 1.06)
    ax.axhline(0.95, color=EKSEN, lw=1.2)
    ax.text(t.index[-1] + pd.Timedelta(days=22), 0.94, "Hedef\n%95", fontsize=8.5, color=IKINCIL, va="top")
    ax.set_xlim(t.index[0] - pd.Timedelta(days=20), t.index[-1] + pd.Timedelta(days=45))
    for hat in ("Hat-2", "Hat-1"):
        ax.plot(t.index, t[hat], color=HAT_RENK[hat], lw=2.4 if hat == "Hat-1" else 2, marker="o", ms=4.5,
                label=hat, markeredgecolor=YUZEY, markeredgewidth=1.2)
    dip = t["Hat-1"].idxmin()
    ax.annotate(f"{AY_KISA[dip.month - 1]} {dip.year}: {yuzde(t['Hat-1'].min(), 0)}\nBayram tatili + yüksek talep",
                (dip, t["Hat-1"].min()), xytext=(28, 4), textcoords="offset points", fontsize=8.5, color=MUREKKEP,
                arrowprops={"arrowstyle": "-", "color": SOLUK, "lw": 0.8})
    ay_eksenini_ayarla(ax, t.index)
    ax.set_ylim(0, 1.1)
    yuzde_ekseni(ax)
    ax.legend(loc="lower left")
    baslik(ax, f"Hat-1'de siparişlerin {yuzde(1 - OZET['otd_hat1_baz'], 0)}'ü geç teslim edildi; Hat-2 sorunsuz",
           "Zamanında teslimat oranı (termin ayına göre) · sevk tarihi ≤ termin tarihi")
    kaynak_notu(fig)
    kaydet(fig, "09_zamaninda_teslimat.png")
    OZET["otd_aylik_hat1"] = {ay_etiketi(a): round(v, 3) for a, v in t["Hat-1"].items()}


def grafik_kotu_teslimat_maliyeti() -> None:
    ceza = S.groupby("Ay").CezaTutariTL.sum()
    ekspres = S.groupby("Ay").EkspresNakliyeTL.sum()
    mesai = M.groupby("Ay").MaliyetTL.sum()
    df = pd.concat([mesai, ceza, ekspres], axis=1, sort=True).fillna(0)
    df.columns = ["Fazla mesai (Pazar)", "Gecikme cezası", "Ekspres nakliye"]
    df = df.reindex(pd.date_range("2025-10-01", "2026-10-01", freq="MS"), fill_value=0)
    fig, ax = plt.subplots(figsize=(11, 5.2))
    alt = np.zeros(len(df))
    for kolon, renk in zip(df.columns, [MAVI, SU_YESILI, SARI]):
        ax.bar(df.index, df[kolon], bottom=alt, width=20, color=renk, label=kolon, edgecolor=YUZEY, linewidth=1.2)
        alt += df[kolon].values
    for x, v in zip(df.index, alt):
        if v > 0:
            ax.text(x, v + 15_000, sayi(v / 1000) + " bin", ha="center", fontsize=8, color=MUREKKEP)
    ay_eksenini_ayarla(ax, df.index)
    sayi_ekseni(ax, bolen=1000, sonek=" bin")
    ax.set_ylabel("TL")
    ax.legend(loc="upper left")
    toplam = df.loc[:"2026-09-01"].values.sum()
    baslik(ax, f"Kapasite açığının yıllık faturası {milyon_tl(toplam)}: fazla mesai, ceza ve ekspres nakliye",
           "Aylık maliyet, bin TL · Baz dönem + pilot ayı")
    kaynak_notu(fig)
    kaydet(fig, "10_kotu_teslimat_maliyeti.png")
    OZET["kapasite_acigi_maliyeti_baz_tl"] = toplam


def mtbf_mttr() -> pd.DataFrame:
    calisma = BAZ.groupby("MakineID").CalismaSuresiDk.sum() / 60
    ariza = D[(D.Donem == "Baz") & D.NedenID.isin(["D03", "D04"])].groupby("MakineID").SureDk.agg(["count", "mean"])
    t = pd.DataFrame({"CalismaSaat": calisma}).join(ariza)
    t["MTBF_saat"] = t.CalismaSaat / t["count"]
    t["MTTR_dk"] = t["mean"]
    t.to_csv(TABLO / "mtbf_mttr_baz.csv", encoding="utf-8")
    return t


def grafik_mtbf_mttr() -> None:
    t = mtbf_mttr()
    fig, ax = plt.subplots(figsize=(11, 5.4))
    # Etiket çakışmalarını önlemek için noktaya göre sabit kaydırmalar (punto)
    kaydirma = {"M02": (6, -14), "M03": (-10, -16), "M06": (-6, 8), "M05": (6, 6), "M09": (6, 6), "M08": (6, 4)}
    for m, r in t.iterrows():
        renk = DARBOGAZ_RENK if m == FRZ else GRI_SERI
        ax.scatter(r.MTBF_saat, r.MTTR_dk, s=110 if m == FRZ else 70, color=renk, edgecolor=YUZEY, lw=2, zorder=3)
        dx, dy = kaydirma.get(m, (8, 4))
        ax.annotate(KOD[m], (r.MTBF_saat, r.MTTR_dk), xytext=(dx, dy), textcoords="offset points", fontsize=9,
                    color=MUREKKEP, fontweight="semibold" if m == FRZ else "normal",
                    ha="right" if dx < 0 else "left")
    ax.set_xlabel("MTBF: arızalar arası ortalama çalışma süresi (saat) → daha iyi")
    ax.set_ylabel("MTTR: ortalama tamir süresi (dk)")
    ax.grid(axis="x", visible=True)
    ax.set_xlim(0, t.MTBF_saat.max() * 1.15)
    ax.set_ylim(0, t.MTTR_dk.max() * 1.2)
    f = t.loc[FRZ]
    baslik(ax, f"H1-FRZ en sık arızalanan makine: her {sayi(f.MTBF_saat, 0)} çalışma saatinde bir, "
               f"ortalama {sayi(f.MTTR_dk)} dk",
           "Mekanik + elektrik arızalar · Baz dönem")
    kaynak_notu(fig)
    kaydet(fig, "11_mtbf_mttr.png")
    OZET["mtbf_mttr_baz"] = {KOD[m]: {"MTBF_saat": round(r.MTBF_saat, 1), "MTTR_dk": round(r.MTTR_dk, 1)}
                             for m, r in t.iterrows()}


# --------------------------------------------------------------------------
# 6) Pilot: önce / sonra
# --------------------------------------------------------------------------
def grafik_pilot() -> None:
    st = D[(D.MakineID == FRZ) & (D.NedenID == "D01")].groupby("Donem").SureDk.mean()
    ariza = D[(D.MakineID == FRZ) & D.NedenID.isin(["D03", "D04"])].groupby("Donem").size()
    saat = U[U.MakineID == FRZ].groupby("Donem").CalismaSuresiDk.sum() / 60
    mtbf = saat / ariza
    olcutler = [
        ("FRZ OEE  ↑", OZET["frz_oee_baz"], OZET["frz_oee_pilot"], "yuzde"),
        ("Ayar süresi, dk  ↓", st["Baz"], st["Pilot"], "dk"),
        ("FRZ MTBF, saat  ↑", mtbf["Baz"], mtbf["Pilot"], "saat"),
        ("Hat-1 OTD  ↑", OZET["otd_hat1_baz"], OZET["otd_hat1_pilot"], "yuzde"),
        ("AM-200 çap Ppk  ↑", OZET["spc"]["Baz"]["Ppk"], OZET["spc"]["Pilot"]["Ppk"], "oran"),
    ]
    fig, eksenler = plt.subplots(1, len(olcutler), figsize=(13, 4.6))
    fig.subplots_adjust(left=0.02, right=0.99, top=0.76, wspace=0.3)
    for ax, (ad, once, sonra, tur) in zip(eksenler, olcutler):
        ax.bar([0, 1], [once, sonra], color=[GRI_SERI, MAVI], width=0.62)
        for i, v in enumerate((once, sonra)):
            metin = yuzde(v, 0) if tur == "yuzde" else sayi(v, 2 if tur == "oran" else 0)
            ax.text(i, v * 1.02, metin, ha="center", va="bottom", fontsize=10.5, color=MUREKKEP, fontweight="semibold")
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["Baz", "Pilot"])
        ax.set_yticks([])
        ax.grid(False)
        ax.set_ylim(0, max(once, sonra) * 1.22)
        ax.set_title(ad, fontsize=10, loc="left")
    eksenler[3].text(1, OZET["otd_hat1_pilot"] * 0.5, f"2.–4.\nhafta\n{yuzde(OZET['otd_hat1_pilot_2_4_hafta'], 0)}",
                     ha="center", va="center", fontsize=8, color="#ffffff")
    ust_baslik(fig, "Pilot ayı (Ekim 2026): darboğazda ölçülebilir iyileşme",
               "Baz: Eki 2025 – Eyl 2026 · Pilot: SMED + TPM + kampanya tipi planlama + gece vardiyası standart işi · "
               "↑/↓ daha iyi yön", y_ana=0.98, y_alt=0.87)
    kaynak_notu(fig)
    kaydet(fig, "12_pilot_once_sonra.png")
    OZET["pilot"] = {"ayar_dk_baz": st["Baz"], "ayar_dk_pilot": st["Pilot"],
                     "mtbf_baz": mtbf["Baz"], "mtbf_pilot": mtbf["Pilot"]}


# --------------------------------------------------------------------------
# 7) Simülasyon modeli için parametre kestirimi (veriden modele)
# --------------------------------------------------------------------------
def lognormal_ozet(x: pd.Series) -> dict:
    return {"ort": float(x.mean()), "cv": float(x.std(ddof=1) / x.mean()) if len(x) > 1 else 0.5, "n": int(len(x))}


def sim_parametreleri() -> None:
    parametre = {}
    for m in ["M01", "M02", "M03", "M04", "M05", "M06"]:
        u = BAZ[BAZ.MakineID == m]
        d = D[(D.MakineID == m) & (D.Donem == "Baz")].sort_values("BaslangicZamani")
        saat = u.CalismaSuresiDk.sum() / 60
        setup = d[d.NedenID == "D01"].copy()
        setup["Onceki"] = setup.UrunID.shift(1)
        setup["AyniAile"] = setup.apply(lambda r: r.Onceki is not None and AILE.get(r.Onceki) == AILE[r.UrunID], axis=1)
        ariza = d[d.NedenID.isin(["D03", "D04"])]
        diger = d[d.NedenID.isin(["D05", "D06", "D07", "D08"])]
        parametre[m] = {
            "kod": KOD[m],
            "ideal_cevrim_sn": IDEAL_CEVRIM[m],
            "performans": float(u.IdealSureDk.sum() / u.CalismaSuresiDk.sum()),
            "hurda_orani": float(u.HurdaAdet.sum() / u.UretilenAdet.sum()),
            "setup_ayni_aile": lognormal_ozet(setup[setup.AyniAile].SureDk),
            "setup_farkli_aile": lognormal_ozet(setup[~setup.AyniAile].SureDk),
            "ilk_parca_onayi": lognormal_ozet(d[d.NedenID == "D02"].SureDk),
            "mtbf_saat": float(saat / max(len(ariza), 1)),
            "tamir": lognormal_ozet(ariza.SureDk),
            "diger_durus_saat_arasi": float(saat / max(len(diger), 1)),
            "diger_durus": lognormal_ozet(diger.SureDk),
        }
    lot = V["lot"]
    talep = S[(S.Donem == "Baz") & (S.Hat == "Hat-1")]
    hafta_sayisi = (talep.TerminTarihi.max() - talep.TerminTarihi.min()).days / 7
    parametre["talep"] = {
        "haftalik_adet": {u: float(g.Adet.sum() / hafta_sayisi) for u, g in talep.groupby("UrunID")},
        "ort_lot_baz": float(lot[(lot.MakineID == FRZ) & (lot.Politika == "Acil")].LotAdet.mean()),
        "ort_lot_pilot": float(lot[(lot.MakineID == FRZ) & (lot.Politika == "Kampanya")].LotAdet.mean()),
    }
    gunluk = BAZ[(BAZ.Hat == "Hat-1") & (BAZ.MakineID == "M06") & (BAZ.FazlaMesai == 0)].groupby("Tarih").SaglamAdet.sum()
    parametre["dogrulama"] = {"hat1_gunluk_cikti_ort": float(gunluk.mean()),
                              "hat1_haftalik_cikti_6gun": float(gunluk.mean() * 6)}
    (TABLO / "sim_parametreleri.json").write_text(json.dumps(parametre, ensure_ascii=False, indent=2), encoding="utf-8")
    OZET["sim_parametre_ozeti"] = {parametre[m]["kod"]: {"MTBF_saat": round(parametre[m]["mtbf_saat"], 1),
                                                         "setup_farkli_ort": round(parametre[m]["setup_farkli_aile"]["ort"], 1)}
                                   for m in ["M04", "M06"]}


def main() -> None:
    kpi_ozeti()
    grafik_oee_trend()
    grafik_kapasite_kullanimi()
    grafik_kayip_selalesi()
    grafik_durus_pareto()
    grafik_vardiya_isi_haritasi()
    grafik_kalite()
    g = istatistik_testleri()
    grafik_durus_cikti(g)
    spc()
    grafik_teslimat()
    grafik_kotu_teslimat_maliyeti()
    grafik_mtbf_mttr()
    grafik_pilot()
    sim_parametreleri()
    ozet_yaz("analiz", OZET)
    print("Analiz tamamlandı. Önemli sayılar:")
    for k in ("frz_oee_baz", "frz_oee_pilot", "otd_hat1_baz", "otd_hat1_pilot", "otd_hat1_pilot_2_4_hafta",
              "otd_hat1_haziran", "hurda_gece_kat", "frz_dk_basina_kayip_adet", "kapasite_acigi_maliyeti_baz_tl"):
        print(f"  {k}: {OZET[k]:.3f}" if isinstance(OZET[k], float) else f"  {k}: {OZET[k]}")
    print("  SPC:", {k: round(v["Ppk"], 2) for k, v in OZET["spc"].items()})
    print(pd.DataFrame(OZET["istatistik_testleri"])[["Hipotez", "İstatistik", "p_degeri"]].to_string())


if __name__ == "__main__":
    main()
