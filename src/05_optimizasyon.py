"""05 — Optimizasyon: Hat-1 için 6 aylık toplu üretim planı (MILP, PuLP + CBC).

Karar değişkenleri (ürün i, ay t)
    x[i,t]  üretim (adet)            I[i,t]  dönem sonu stok        B[i,t]  birikmiş (geciken) sipariş
    n[i,t]  kampanya sayısı (tam sayı)  u[i,t]  emniyet stoğu açığı   F[t]    Pazar fazla mesai vardiyası (tam sayı)
Amaç
    min  fazla mesai + stok taşıma + gecikme + ayar + emniyet stoğu açığı maliyeti
Kısıtlar
    stok dengesi · H1-FRZ ve H1-TSL kapasitesi (ayar süreleri dahil) · kampanya büyüklüğü üst sınırı
    · depo kapasitesi · Nisan sonunda geciken sipariş kalmaması

Dört durum karşılaştırılır: {mevcut planlama, optimal plan} × {mevcut verim, pilot verimi}.
Ayrıca darboğazdaki bir saatin parasal değeri (gölge fiyat) yeniden çözümle hesaplanır.
"""
from __future__ import annotations

import math

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pulp

from grafik_stili import (EKSEN, IKINCIL, MAVI, MUREKKEP, SARI, SERI, SU_YESILI, SUNUM, YUZEY, baslik, kaydet,
                          kaynak_notu, sayi_ekseni, stil_uygula)
from ortak import (IDEAL_CEVRIM, MALIYET, PILOT_BASLANGIC, RESMI_TATILLER, TABLO, URUNLER, ay_etiketi,
                   calisma_gunu_sayisi, milyon_tl, ozet_yaz, sayi, yuzde)
from veri_yukle import oku

stil_uygula()
URUN = URUNLER.set_index("UrunID")
HAT1 = ["P01", "P02", "P03", "P04"]
GUN_DK, VARDIYA_DK = 1350, 450
KAMPANYA_UST_SINIR = 2400      # FG deposu ve hammadde partisi nedeniyle bir kampanyada en fazla adet
DEPO_KAPASITESI = 12000        # Hat-1 bitmiş ürün deposu (adet)
EMNIYET_GUN = 1.5              # emniyet stoğu: 1,5 günlük talep
AYAR_MALIYETI = 2500           # TL / kampanya: ilk parça hurdası + ayarcı işçiliği
GECIKME_ORANI = 0.15           # TL / adet-ay: birim fiyatın %15'i (ceza + ekspres + itibar)
EMNIYET_ACIGI_ORANI = 0.03     # TL / adet-ay: birim fiyatın %3'ü
KAPASITE_TAMPONU = 0.93        # darboğaz kapasitesinin en fazla %93'ü planlanır (değişkenliğe karşı koruma)
KAYIP_SATIS_ORANI = 0.45       # ufuk sonunda hâlâ karşılanmamış talep: katkı payı + itibar (birim fiyatın %45'i)


def verim_parametreleri() -> dict:
    """Baz ve pilot dönemleri için H1-FRZ ve H1-TSL verim parametreleri (MES verisinden)."""
    u, d = oku("uretim", ("Tarih",)), oku("durus", ("Tarih",))
    u["Donem"] = np.where(u.Tarih >= PILOT_BASLANGIC, "Pilot", "Baz")
    d["Donem"] = np.where(d.Tarih >= PILOT_BASLANGIC, "Pilot", "Baz")
    sonuc = {}
    for donem in ("Baz", "Pilot"):
        for m in ("M04", "M06"):
            uu, dd = u[(u.MakineID == m) & (u.Donem == donem)], d[(d.MakineID == m) & (d.Donem == donem)]
            planlanan = uu.PlanlananSureDk.sum() + dd[dd.NedenID == "D09"].SureDk.sum()
            setup_dk = dd[dd.NedenID.isin(["D01", "D02"])].SureDk.sum()
            diger_dk = planlanan - uu.CalismaSuresiDk.sum() - setup_dk  # arıza + küçük duruş + planlı bakım
            n_setup = int((dd.NedenID == "D01").sum())
            sonuc[(donem, m)] = {
                "P": uu.IdealSureDk.sum() / uu.CalismaSuresiDk.sum(),
                "Q": uu.SaglamAdet.sum() / uu.UretilenAdet.sum(),
                "alfa": diger_dk / planlanan,
                "setup_dk": setup_dk / max(n_setup, 1),
                "setup_1000": n_setup / uu.UretilenAdet.sum() * 1000,
            }
    return sonuc


def pazar_sayisi(ay: pd.Timestamp) -> int:
    gunler = pd.date_range(ay, ay + pd.offsets.MonthEnd(0), freq="D")
    return int(sum(g.weekday() == 6 and g not in RESMI_TATILLER for g in gunler))


def veri_hazirla(talep_carpani: float = 1.0):
    t = pd.read_csv(TABLO / "talep_tahmini.csv", parse_dates=["Ay"])
    t = t[t.UrunID.isin(HAT1)]
    aylar = sorted(t.Ay.unique())
    talep = {(r.UrunID, r.Ay): float(r.Tahmin) * talep_carpani for r in t.itertuples()}
    gun = {a: calisma_gunu_sayisi(a) for a in aylar}
    pazar = {a: pazar_sayisi(a) for a in aylar}
    ilk = aylar[0]
    emniyet = {i: EMNIYET_GUN * talep[(i, ilk)] / gun[ilk] for i in HAT1}
    baslangic_stok = {i: round(emniyet[i] / 50) * 50 for i in HAT1}
    return aylar, talep, gun, pazar, emniyet, baslangic_stok


def maliyet_parametreleri():
    return {
        "h": {i: MALIYET["stok_tasima_aylik"] * URUN.at[i, "StdMaliyet"] for i in HAT1},
        "b": {i: GECIKME_ORANI * URUN.at[i, "BirimFiyat"] for i in HAT1},
        "p_ss": {i: EMNIYET_ACIGI_ORANI * URUN.at[i, "BirimFiyat"] for i in HAT1},
        "mesai": MALIYET["fazla_mesai_vardiya"],
        # ufuk sonunda karşılanamayan talep = kayıp satış: katkı payı (%28) + itibar kaybı
        "kayip": {i: KAYIP_SATIS_ORANI * URUN.at[i, "BirimFiyat"] for i in HAT1},
    }


def dakika_birim(m: str, i: str, v: dict) -> float:
    """Bir sağlam ürün için gereken çalışma dakikası (performans ve kalite kaybı dahil)."""
    return IDEAL_CEVRIM[m][i] / 60 / (v["P"] * v["Q"])


def optimal_plan(verim: dict, ek_frz_dk: float = 0.0, ad: str = "plan", talep_carpani: float = 1.0,
                 frz_kapasite: float = 1.0) -> dict:
    aylar, talep, gun, pazar, emniyet, s0 = veri_hazirla(talep_carpani)
    c = maliyet_parametreleri()
    model = pulp.LpProblem(ad, pulp.LpMinimize)
    idx = [(i, t) for i in HAT1 for t in aylar]
    x = pulp.LpVariable.dicts("x", idx, lowBound=0)
    stok = pulp.LpVariable.dicts("I", idx, lowBound=0)
    gec = pulp.LpVariable.dicts("B", idx, lowBound=0)
    acik = pulp.LpVariable.dicts("u", idx, lowBound=0)
    n = pulp.LpVariable.dicts("n", idx, lowBound=0, cat="Integer")
    mesai = {t: pulp.LpVariable(f"F_{t:%Y%m}", lowBound=0, upBound=2 * pazar[t], cat="Integer") for t in aylar}

    son = aylar[-1]
    model += pulp.lpSum(c["mesai"] * mesai[t] for t in aylar) + pulp.lpSum(
        c["h"][i] * stok[i, t] + c["b"][i] * gec[i, t] + AYAR_MALIYETI * n[i, t] + c["p_ss"][i] * acik[i, t]
        for i, t in idx) + pulp.lpSum(c["kayip"][i] * gec[i, son] for i in HAT1)

    for k, t in enumerate(aylar):
        for i in HAT1:
            onceki_stok = s0[i] if k == 0 else stok[i, aylar[k - 1]]
            onceki_gec = 0 if k == 0 else gec[i, aylar[k - 1]]
            model += onceki_stok - onceki_gec + x[i, t] - talep[(i, t)] == stok[i, t] - gec[i, t]
            model += x[i, t] <= KAMPANYA_UST_SINIR * n[i, t]
            model += acik[i, t] >= emniyet[i] - stok[i, t]
        for m in ("M04", "M06"):
            v = verim[m]
            sure = gun[t] * GUN_DK + VARDIYA_DK * mesai[t] + (ek_frz_dk if m == "M04" else 0)
            kat = frz_kapasite if m == "M04" else 1.0
            model += pulp.lpSum(dakika_birim(m, i, v) * x[i, t] + v["setup_dk"] * n[i, t] for i in HAT1) \
                <= sure * kat * (1 - v["alfa"]) * KAPASITE_TAMPONU
        model += pulp.lpSum(stok[i, t] for i in HAT1) <= DEPO_KAPASITESI
    durum = model.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=60))
    assert pulp.LpStatus[durum] == "Optimal", pulp.LpStatus[durum]
    return _sonuc_tablosu(aylar, talep, gun,
                          {k: v.value() for k, v in x.items()}, {k: v.value() for k, v in stok.items()},
                          {k: v.value() for k, v in gec.items()}, {k: v.value() for k, v in n.items()},
                          {k: v.value() for k, v in acik.items()}, {t: v.value() for t, v in mesai.items()},
                          verim, c, pulp.value(model.objective))


def mevcut_yontem(verim: dict, setup_1000: float, talep_carpani: float = 1.0, frz_kapasite: float = 1.0) -> dict:
    """Bugünkü pratik: her ay talebi + birikmişi üret ("chase"), yetmezse Pazar mesaisi, yine yetmezse gecik.
    Ürün değişimi sıklığı yangın söndürme planlamasının gerçekleşen oranıdır (1000 adette setup).
    frz_kapasite = 2 → ikinci işleme merkezi (yatırım seçeneği)."""
    aylar, talep, gun, pazar, emniyet, s0 = veri_hazirla(talep_carpani)
    c = maliyet_parametreleri()
    x, stok, gec, n, acik, mesai = {}, {}, {}, {}, {}, {}
    st, bo = dict(s0), {i: 0.0 for i in HAT1}
    for t in aylar:
        hedef = {i: max(0.0, talep[(i, t)] + bo[i] + emniyet[i] - st[i]) for i in HAT1}

        def gereken(m, miktar):
            v = verim[m]
            kat = frz_kapasite if m == "M04" else 1.0
            return sum((dakika_birim(m, i, v) + v["setup_dk"] * setup_1000 / 1000) * miktar[i] for i in HAT1) \
                / ((1 - v["alfa"]) * KAPASITE_TAMPONU * kat)
        ihtiyac = max(gereken("M04", hedef), gereken("M06", hedef))
        normal = gun[t] * GUN_DK
        f = min(2 * pazar[t], max(0, math.ceil((ihtiyac - normal) / VARDIYA_DK)))
        oran = min(1.0, (normal + f * VARDIYA_DK) / ihtiyac) if ihtiyac > 0 else 1.0
        for i in HAT1:
            uretim = hedef[i] * oran
            net = st[i] - bo[i] + uretim - talep[(i, t)]
            st[i], bo[i] = max(net, 0.0), max(-net, 0.0)
            x[(i, t)], stok[(i, t)], gec[(i, t)] = uretim, st[i], bo[i]
            n[(i, t)] = uretim * setup_1000 / 1000
            acik[(i, t)] = max(0.0, emniyet[i] - st[i])
        mesai[t] = f
    toplam = sum(c["mesai"] * mesai[t] for t in aylar) + sum(
        c["h"][i] * stok[i, t] + c["b"][i] * gec[i, t] + AYAR_MALIYETI * n[i, t] + c["p_ss"][i] * acik[i, t]
        for i in HAT1 for t in aylar) + sum(c["kayip"][i] * gec[i, aylar[-1]] for i in HAT1)
    return _sonuc_tablosu(aylar, talep, gun, x, stok, gec, n, acik, mesai, verim, c, toplam)


def _sonuc_tablosu(aylar, talep, gun, x, stok, gec, n, acik, mesai, verim, c, toplam) -> dict:
    plan = pd.DataFrame([{"Ay": t, "UrunID": i, "Talep": talep[(i, t)], "Uretim": x[(i, t)],
                          "Stok": stok[(i, t)], "Birikmis": gec[(i, t)], "Kampanya": n[(i, t)]}
                         for i in HAT1 for t in aylar])
    kalemler = {
        "Fazla mesai": sum(c["mesai"] * mesai[t] for t in aylar),
        "Gecikme (ceza + ekspres)": sum(c["b"][i] * gec[(i, t)] for i in HAT1 for t in aylar)
        + sum(c["kayip"][i] * gec[(i, aylar[-1])] for i in HAT1),
        "Stok taşıma": sum(c["h"][i] * stok[(i, t)] for i in HAT1 for t in aylar),
        "Ürün değişimi (ayar)": sum(AYAR_MALIYETI * n[(i, t)] for i in HAT1 for t in aylar),
        "Emniyet stoğu açığı": sum(c["p_ss"][i] * acik[(i, t)] for i in HAT1 for t in aylar),
    }
    kullanim = {}
    for t in aylar:
        v = verim["M04"]
        gerekli = sum(dakika_birim("M04", i, v) * x[(i, t)] + v["setup_dk"] * n[(i, t)] for i in HAT1)
        kullanim[t] = gerekli / (gun[t] * GUN_DK * (1 - v["alfa"]))  # normal vardiyaya göre yük
    return {"plan": plan, "kalemler": kalemler, "toplam": float(toplam), "mesai": dict(mesai),
            "frz_yuk": kullanim}


def main() -> None:
    v = verim_parametreleri()
    mevcut = {"M04": v[("Baz", "M04")], "M06": v[("Baz", "M06")]}
    pilot = {"M04": v[("Pilot", "M04")], "M06": v[("Pilot", "M06")]}
    print("Verim (FRZ):", {k: {a: round(b, 3) for a, b in d.items()} for k, d in v.items() if k[1] == "M04"})

    durumlar = {
        "A": ("Mevcut planlama\nmevcut verim", mevcut_yontem(mevcut, v[("Baz", "M04")]["setup_1000"])),
        "B": ("Optimal plan\nmevcut verim", optimal_plan(mevcut, ad="B")),
        "C": ("Mevcut planlama\npilot verimi", mevcut_yontem(pilot, v[("Baz", "M04")]["setup_1000"])),
        "D": ("Optimal plan\npilot verimi", optimal_plan(pilot, ad="D")),
    }
    for k, (ad, s) in durumlar.items():
        print(f"{k} {ad.replace(chr(10), ' / ')}: {milyon_tl(s['toplam'], 2)} | mesai vardiyası "
              f"{sum(s['mesai'].values()):.0f} | {', '.join(f'{a}: {sayi(b)}' for a, b in s['kalemler'].items())}")

    # Darboğaz saatinin değeri: B durumunda her aya +60 dk FRZ kapasitesi eklenip yeniden çözülür
    ek = optimal_plan(mevcut, ek_frz_dk=600, ad="B_ek")
    saat_degeri = (durumlar["B"][1]["toplam"] - ek["toplam"]) / (10 * 6)
    print("FRZ'de 1 saatin değeri ≈", sayi(saat_degeri), "TL")

    # ---- Tablolar (Power BI için) ----
    planlar, maliyetler, kapasite = [], [], []
    for k, (ad, s) in durumlar.items():
        etiket = f"{k}: {ad.replace(chr(10), ' · ')}"
        planlar.append(s["plan"].assign(Durum=etiket))
        maliyetler += [(etiket, kalem, tutar) for kalem, tutar in s["kalemler"].items()]
        kapasite += [(etiket, t, s["mesai"][t], s["frz_yuk"][t]) for t in s["mesai"]]
    pd.concat(planlar).round({"Talep": 0, "Uretim": 0, "Stok": 0, "Birikmis": 0, "Kampanya": 2}).to_csv(
        TABLO / "opt_plan.csv", index=False, encoding="utf-8")
    pd.DataFrame(maliyetler, columns=["Durum", "Kalem", "TutarTL"]).round(0).to_csv(
        TABLO / "opt_maliyet.csv", index=False, encoding="utf-8")
    pd.DataFrame(kapasite, columns=["Durum", "Ay", "FazlaMesaiVardiya", "FRZYuk"]).to_csv(
        TABLO / "opt_kapasite.csv", index=False, encoding="utf-8")

    # ---- Grafik 18: dört durumun maliyeti ----
    fig, ax = plt.subplots(figsize=(11, 5.4))
    gruplar = {k: [k] for k in durumlar["A"][1]["kalemler"]}
    renkler = [MAVI, SU_YESILI, SARI, SERI[4], SERI[6]]
    x = np.arange(len(durumlar))
    alt = np.zeros(len(durumlar))
    for (kalem, alt_kalemler), renk in zip(gruplar.items(), renkler):
        degerler = np.array([sum(s["kalemler"][a] for a in alt_kalemler) for _, s in durumlar.values()])
        ax.bar(x, degerler, bottom=alt, color=renk, width=0.58, label=kalem, edgecolor=YUZEY, linewidth=1.2)
        alt += degerler
    taban = durumlar["A"][1]["toplam"]
    for xi, (k, (_, s)) in zip(x, durumlar.items()):
        fark = "" if k == "A" else f"\n−{yuzde(1 - s['toplam'] / taban, 0)}"
        ax.text(xi, s["toplam"] + taban * 0.015, milyon_tl(s["toplam"], 2) + fark, ha="center", va="bottom",
                fontsize=9.5, color=MUREKKEP, fontweight="semibold")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{k}\n{ad}" for k, (ad, _) in durumlar.items()])
    ax.set_ylim(0, taban * 1.25)
    sayi_ekseni(ax, bolen=1e6, sonek=" M")
    ax.set_ylabel("6 aylık maliyet (milyon TL)")
    ax.legend(loc="upper right", ncols=2)
    d_tasarruf = 1 - durumlar["D"][1]["toplam"] / taban
    baslik(ax, f"Optimal plan + pilot verimi, 6 aylık plan maliyetini {yuzde(d_tasarruf, 0)} düşürüyor",
           "Kasım 2026 – Nisan 2027 · fazla mesai, gecikme, stok, ayar ve emniyet stoğu açığı maliyetleri · MILP (PuLP + CBC)")
    kaynak_notu(fig, "Kaynak: Talep tahmini (03) + MES verim parametreleri · Optimizasyon: PuLP/CBC")
    kaydet(fig, "18_opt_maliyet_karsilastirma.png")

    # ---- Grafik 19: önerilen plan (D) ----
    plan = durumlar["D"][1]["plan"]
    tablo = plan.pivot(index="Ay", columns="UrunID", values="Uretim")
    talep_toplam = plan.groupby("Ay").Talep.sum()
    stok_toplam = plan.groupby("Ay").Stok.sum()
    fig, ax = plt.subplots(figsize=(11, 5.4))
    xa = np.arange(len(tablo))
    alt = np.zeros(len(tablo))
    for i, renk in zip(HAT1, SERI[:4]):
        ax.bar(xa, tablo[i], bottom=alt, color=renk, width=0.58, label=f"{URUN.at[i, 'UrunKodu']} üretim",
               edgecolor=YUZEY, linewidth=1.2)
        alt += tablo[i].values
    ax.plot(xa, talep_toplam.values, color=MUREKKEP, lw=2, marker="o", ms=6, markeredgecolor=YUZEY,
            label="Talep (tahmin)")
    ax.plot(xa, stok_toplam.values, color=IKINCIL, lw=1.6, ls="-", marker="s", ms=5, markeredgecolor=YUZEY,
            label="Ay sonu stok")
    for xi, t in zip(xa, tablo.index):
        f = durumlar["D"][1]["mesai"][t]
        if f > 0.5:
            ax.text(xi, alt[xi] + 600, f"+{f:.0f} Pazar\nvardiyası", ha="center", fontsize=8.5, color=MUREKKEP)
    ax.set_xticks(xa)
    ax.set_xticklabels([ay_etiketi(a) for a in tablo.index])
    ax.set_ylim(0, alt.max() * 1.22)
    sayi_ekseni(ax)
    ax.set_ylabel("Adet")
    ax.legend(loc="upper left", ncols=3)
    on_uretim = (tablo.sum(axis=1) - talep_toplam)
    yigma_ay = on_uretim.idxmax()
    baslik(ax, f"Optimal plan zirveden önce stok yapıyor: {ay_etiketi(yigma_ay)} ayında talebin "
               f"{sayi(on_uretim.max())} adet üstünde üretim",
           "Önerilen 6 aylık plan (durum D: optimal plan + pilot verimi) · kampanya üst sınırı 2.400 adet, depo 12.000 adet")
    kaynak_notu(fig, "Kaynak: MILP optimizasyonu (PuLP + CBC)")
    kaydet(fig, "19_opt_onerilen_plan.png")

    ozet_yaz("optimizasyon", {
        "verim": {f"{k[0]}_{k[1]}": d for k, d in v.items()},
        "durumlar": {k: {"ad": ad.replace("\n", " · "), "toplam_tl": s["toplam"], "kalemler": s["kalemler"],
                         "mesai_vardiya": sum(s["mesai"].values())} for k, (ad, s) in durumlar.items()},
        "tasarruf_D_vs_A": d_tasarruf,
        "tasarruf_B_vs_A": 1 - durumlar["B"][1]["toplam"] / taban,
        "frz_saat_degeri_tl": saat_degeri,
        "on_uretim_ayi": ay_etiketi(yigma_ay),
    })


if __name__ == "__main__":
    main()
