"""07 — Power BI için yıldız şema veri modeli (powerbi/veri/*.csv).

Boyutlar : DimTarih, DimMakine, DimUrun, DimMusteri, DimVardiya, DimDurusNedeni, DimHataTuru
Olgular  : FaktUretim, FaktDurus, FaktKalite, FaktSiparis, FaktOlcum, FaktMesai, FaktTalep
Senaryo  : SimKapasite, SimKullanim, OptPlan, OptMaliyet, FinansOzet, FinansNPV
Kolon adları Power BI'da doğrudan görünecek şekilde Türkçe ve okunaklıdır; anahtarlar ASCII'dir.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from ortak import (AY_KISA, BAZ_BASLANGIC, DURUS_NEDENLERI, GECMIS_BASLANGIC, GUN_KISA, HATA_TURLERI, MAKINELER,
                   MUSTERILER, PBI_VERI, PILOT_BASLANGIC, RESMI_TATILLER, TABLO, URUNLER, VARDIYA_SAAT, ay_etiketi)
from veri_yukle import oku


def yaz(df: pd.DataFrame, ad: str) -> None:
    df.to_csv(PBI_VERI / f"{ad}.csv", index=False, encoding="utf-8", date_format="%Y-%m-%d")
    print(f"{ad:<16} {len(df):>6} satır")


def dim_tarih() -> pd.DataFrame:
    g = pd.date_range(GECMIS_BASLANGIC, "2027-04-30", freq="D")
    df = pd.DataFrame({"Tarih": g})
    df["Yıl"] = df.Tarih.dt.year
    df["AyNo"] = df.Tarih.dt.month
    df["Ay"] = df.AyNo.map(lambda m: AY_KISA[m - 1])
    df["YılAyNo"] = df.Yıl * 100 + df.AyNo
    df["Yıl-Ay"] = df.Tarih.map(lambda t: ay_etiketi(t.replace(day=1)))
    df["Hafta Başı"] = df.Tarih - pd.to_timedelta(df.Tarih.dt.day_of_week, unit="D")
    df["GünNo"] = df.Tarih.dt.day_of_week + 1
    df["Gün"] = df.Tarih.dt.day_of_week.map(lambda d: GUN_KISA[d])
    df["Çalışma Günü"] = np.where((df.Tarih.dt.day_of_week < 6) & ~df.Tarih.isin(RESMI_TATILLER), "Evet", "Hayır")
    df["DönemNo"] = np.select([df.Tarih < BAZ_BASLANGIC, df.Tarih < PILOT_BASLANGIC, df.Tarih < "2026-11-01"],
                              [1, 2, 3], 4)
    df["Dönem"] = df.DönemNo.map({1: "Geçmiş (ERP)", 2: "Baz dönem", 3: "Pilot (Eki 26)", 4: "Tahmin ufku"})
    return df


def main() -> None:
    yaz(dim_tarih(), "DimTarih")
    m = MAKINELER.rename(columns={"MakineKodu": "Makine Kodu", "Istasyon": "İstasyon", "RotaSirasi": "Rota Sırası",
                                  "SonIstasyon": "Son İstasyon"})
    m["Darboğaz"] = np.where(m.MakineID == "M04", "Evet", "Hayır")
    yaz(m, "DimMakine")
    yaz(URUNLER.drop(columns="AylikTalep2026").rename(columns={
        "UrunKodu": "Ürün Kodu", "Urun": "Ürün", "UrunAilesi": "Ürün Ailesi", "BirimFiyat": "Birim Fiyat",
        "StdMaliyet": "Standart Maliyet"}), "DimUrun")
    yaz(MUSTERILER[["MusteriID", "Musteri", "Segment", "GunlukCezaOrani"]].rename(columns={
        "Musteri": "Müşteri", "GunlukCezaOrani": "Günlük Ceza Oranı"}), "DimMusteri")
    yaz(pd.DataFrame({"VardiyaID": ["A", "B", "C"],
                      "Vardiya": [f"{v} · {VARDIYA_SAAT[v]}" for v in "ABC"],
                      "Vardiya Tipi": ["Gündüz", "Akşam", "Gece"]}), "DimVardiya")
    yaz(DURUS_NEDENLERI.rename(columns={"PlanliMi": "Planlı mı"}), "DimDurusNedeni")
    yaz(HATA_TURLERI.rename(columns={"HataTuru": "Hata Türü", "HataGrubu": "Hata Grubu"}), "DimHataTuru")

    u = oku("uretim", ("Tarih",)).drop(columns=["UretimID", "IdealCevrimSn"])
    yaz(u, "FaktUretim")
    d = oku("durus", ("Tarih", "BaslangicZamani"))
    d["BaslangicZamani"] = d.BaslangicZamani.dt.strftime("%Y-%m-%d %H:%M")
    yaz(d, "FaktDurus")
    yaz(oku("kalite", ("Tarih",)).drop(columns="KaliteID"), "FaktKalite")
    s = oku("siparis", ("SiparisTarihi", "TerminTarihi", "SevkTarihi"))
    yaz(s, "FaktSiparis")
    o = oku("olcum", ("Tarih",)).drop(columns="OlcumID")
    yaz(o, "FaktOlcum")
    yaz(oku("fazla_mesai", ("Tarih",)), "FaktMesai")

    gecmis = oku("talep_aylik", ("Ay",)).rename(columns={"Talep": "Adet"})
    gecmis["Tür"] = "Gerçekleşen"
    tahmin = pd.read_csv(TABLO / "talep_tahmini.csv", parse_dates=["Ay"]).rename(
        columns={"Tahmin": "Adet", "Alt80": "Alt %80", "Ust80": "Üst %80"})
    tahmin["Tür"] = "Tahmin"
    yaz(pd.concat([gecmis, tahmin[["Ay", "UrunID", "Adet", "Alt %80", "Üst %80", "Tür"]]], ignore_index=True),
        "FaktTalep")

    ozet = json.loads((TABLO.parent / "ozet_metrikler.json").read_text(encoding="utf-8"))
    sim = ozet["simulasyon"]
    yaz(pd.DataFrame([{"Senaryo": k, "Senaryo Adı": f"{k} · {v['ad']}", "Haftalık Çıktı": round(v["haftalik_cikti"]),
                       "GA Yarı Genişlik": round(v["ci_yari"]), "Kapasite Artışı": round(v["artis"], 4),
                       "FRZ OEE": round(v["frz_oee"], 4), "Darboğaz": v["darbogaz"],
                       "Tedarik Süresi (gün)": round(sim["talep"][k]["tedarik_gun"], 2),
                       "Talebi Karşılıyor": "Hayır" if sim["talep"][k]["kararsiz"] else "Evet"}
                      for k, v in sim["kapasite"].items()]), "SimKapasite")
    yaz(pd.DataFrame([{"Senaryo": k, "İstasyon": i, "İstasyon Sırası": n + 1, "Kullanım": round(kul, 4)}
                      for k, v in sim["kapasite"].items() for n, (i, kul) in enumerate(v["kullanim"].items())]),
        "SimKullanim")
    plan = pd.read_csv(TABLO / "opt_plan.csv", parse_dates=["Ay"])
    yaz(plan.rename(columns={"Uretim": "Üretim", "Birikmis": "Birikmiş"}), "OptPlan")
    yaz(pd.read_csv(TABLO / "opt_maliyet.csv").rename(columns={"TutarTL": "Tutar TL"}), "OptMaliyet")
    fin = ozet["finans"]
    yaz(pd.DataFrame([{"Seçenek": ad, "NPV P10 (M TL)": round(fin[k]["npv_p10"] / 1e6, 1),
                       "NPV Medyan (M TL)": round(fin[k]["npv_p50"] / 1e6, 1),
                       "NPV P90 (M TL)": round(fin[k]["npv_p90"] / 1e6, 1),
                       "Pozitif NPV Olasılığı": round(fin[k]["pozitif_olasilik"], 3),
                       "En İyi Seçenek Olasılığı": round(fin["en_iyi_secenek_olasilik"][k], 3)}
                      for k, ad in (("A", "A · Yalın paket"), ("B", "B · Yeni işleme merkezi"),
                                    ("C", "C · Aşamalı (yalın + tetikli makine)"))]), "FinansOzet")
    npv = pd.read_csv(TABLO / "monte_carlo_npv_dagilimi.csv")
    npv["NPV (M TL)"] = (npv.NPVOrta / 1e6).round(1)
    yaz(npv[["Secenek", "NPV (M TL)", "Frekans"]].rename(columns={"Secenek": "Seçenek"}), "FinansNPV")


if __name__ == "__main__":
    main()
