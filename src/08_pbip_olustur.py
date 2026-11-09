"""08 — Power BI projesini (PBIP) koddan üretir: TMDL anlamsal model + PBIR rapor.

Çıktı: powerbi/Demirkanat_Fabrika.pbip
       powerbi/Demirkanat_Fabrika.SemanticModel/  (tablolar, ilişkiler, ~50 DAX ölçüsü)
       powerbi/Demirkanat_Fabrika.Report/         (6 sayfa, tema, görseller)
       powerbi/DAX_Olculer.md                     (ölçülerin belgesi)

Power BI Desktop'ta .pbip dosyasını açın ve "Yenile"ye basın. Veri klasörü VeriKlasoru
parametresindedir; proje taşınırsa Dönüştür > Parametreleri düzenle'den güncelleyin.
"""
from __future__ import annotations

import csv
import json
import shutil
import uuid
from pathlib import Path

from ortak import KOK, PBI_VERI

AD = "Demirkanat_Fabrika"
PBI = KOK / "powerbi"
SM = PBI / f"{AD}.SemanticModel"
RP = PBI / f"{AD}.Report"
OLCU = "_Ölçüler"
BAZ_TEMA = Path(r"C:\Program Files\Microsoft Power BI Desktop\bin\WebView2Resources\minerva\SHAREDRESOURCES\BASETHEMES\CY24SU10.JSON")
SEMA = "https://developer.microsoft.com/json-schemas/fabric"

# --------------------------------------------------------------------------
# 1) Anlamsal model tanımı
# --------------------------------------------------------------------------
T, I, N, D, DT = "string", "int64", "double", "date", "datetime"
GIZLI = {"hidden": True}

TABLOLAR: dict[str, list[tuple]] = {
    "DimTarih": [("Tarih", D, {"key": True}), ("Yıl", I), ("AyNo", I, GIZLI), ("Ay", T, {"sort": "AyNo"}),
                 ("YılAyNo", I, GIZLI), ("Yıl-Ay", T, {"sort": "YılAyNo"}), ("Hafta Başı", D), ("GünNo", I, GIZLI),
                 ("Gün", T, {"sort": "GünNo"}), ("Çalışma Günü", T), ("DönemNo", I, GIZLI),
                 ("Dönem", T, {"sort": "DönemNo"})],
    "DimMakine": [("MakineID", T, GIZLI), ("Makine Kodu", T, {"sort": "MakineID"}), ("Makine", T), ("Hat", T),
                  ("İstasyon", T), ("Rota Sırası", I), ("Son İstasyon", I), ("Darboğaz", T)],
    "DimUrun": [("UrunID", T, GIZLI), ("Ürün Kodu", T), ("Ürün", T), ("Ürün Ailesi", T), ("Hat", T),
                ("Birim Fiyat", N, {"fmt": "#,0"}), ("Standart Maliyet", N, {"fmt": "#,0"})],
    "DimMusteri": [("MusteriID", T, GIZLI), ("Müşteri", T), ("Segment", T), ("Günlük Ceza Oranı", N, {"fmt": "0.0%"})],
    "DimVardiya": [("VardiyaID", T, GIZLI), ("Vardiya", T), ("Vardiya Tipi", T)],
    "DimDurusNedeni": [("NedenID", T, GIZLI), ("Neden", T), ("Kategori", T), ("Planlı mı", T)],
    "DimHataTuru": [("HataID", T, GIZLI), ("Hata Türü", T), ("Hata Grubu", T)],
    "FaktUretim": [("Tarih", D, GIZLI), ("VardiyaID", T, GIZLI), ("MakineID", T, GIZLI), ("UrunID", T, GIZLI),
                   ("FazlaMesai", I, GIZLI), ("TakvimSuresiDk", N, GIZLI), ("PlanlananSureDk", N, GIZLI),
                   ("CalismaSuresiDk", N, GIZLI), ("UretilenAdet", I, GIZLI), ("SaglamAdet", I, GIZLI),
                   ("HurdaAdet", I, GIZLI), ("IdealSureDk", N, GIZLI), ("HurdaMaliyetiTL", N, GIZLI)],
    "FaktDurus": [("DurusID", I, GIZLI), ("Tarih", D, GIZLI), ("VardiyaID", T, GIZLI), ("MakineID", T, GIZLI),
                  ("UrunID", T, GIZLI), ("NedenID", T, GIZLI), ("BaslangicZamani", DT, GIZLI), ("SureDk", N, GIZLI),
                  ("FazlaMesai", I, GIZLI)],
    "FaktKalite": [("Tarih", D, GIZLI), ("VardiyaID", T, GIZLI), ("MakineID", T, GIZLI), ("UrunID", T, GIZLI),
                   ("HataID", T, GIZLI), ("Adet", I, GIZLI)],
    "FaktSiparis": [("SiparisNo", T), ("MusteriID", T, GIZLI), ("UrunID", T, GIZLI), ("SiparisTarihi", D),
                    ("TerminTarihi", D), ("SevkTarihi", D), ("Adet", I, GIZLI), ("BirimFiyat", N, GIZLI),
                    ("Tutar", N, GIZLI), ("GecikmeGun", I), ("ZamanindaMi", I, GIZLI), ("Durum", T),
                    ("CezaTutariTL", N, GIZLI), ("EkspresNakliyeTL", N, GIZLI)],
    "FaktOlcum": [("Tarih", D, GIZLI), ("VardiyaID", T, GIZLI), ("MakineID", T, GIZLI), ("UrunID", T, GIZLI),
                  ("AltGrupNo", I, GIZLI), ("OlcumNo", I, GIZLI), ("CapMm", N, GIZLI), ("Nominal", N, GIZLI),
                  ("LSL", N, GIZLI), ("USL", N, GIZLI)],
    "FaktMesai": [("Tarih", D, GIZLI), ("Hat", T, GIZLI), ("VardiyaSayisi", I, GIZLI), ("Saat", N, GIZLI),
                  ("MaliyetTL", N, GIZLI)],
    "FaktTalep": [("Ay", D, GIZLI), ("UrunID", T, GIZLI), ("Adet", N, GIZLI), ("Alt %80", N, GIZLI),
                  ("Üst %80", N, GIZLI), ("Tür", T, GIZLI)],
    "SimKapasite": [("Senaryo", T), ("Senaryo Adı", T, {"sort": "Senaryo"}), ("Haftalık Çıktı", N, {"fmt": "#,0"}),
                    ("GA Yarı Genişlik", N, {"fmt": "#,0"}), ("Kapasite Artışı", N, {"fmt": "+0%;-0%;0%"}),
                    ("FRZ OEE", N, {"fmt": "0.0%"}), ("Darboğaz", T), ("Tedarik Süresi (gün)", N, {"fmt": "0.0"}),
                    ("Talebi Karşılıyor", T)],
    "SimKullanim": [("Senaryo", T), ("İstasyon", T, {"sort": "İstasyon Sırası"}), ("İstasyon Sırası", I, GIZLI),
                    ("Kullanım", N, {"fmt": "0%"})],
    "OptPlan": [("Ay", D, GIZLI), ("UrunID", T, GIZLI), ("Talep", N, {"fmt": "#,0"}), ("Üretim", N, {"fmt": "#,0"}),
                ("Stok", N, {"fmt": "#,0"}), ("Birikmiş", N, {"fmt": "#,0"}), ("Kampanya", N, {"fmt": "0.0"}),
                ("Durum", T)],
    "OptMaliyet": [("Durum", T), ("Kalem", T), ("Tutar TL", N, {"fmt": "#,0"})],
    "FinansOzet": [("Seçenek", T), ("NPV P10 (M TL)", N, {"fmt": "0.0"}), ("NPV Medyan (M TL)", N, {"fmt": "0.0"}),
                   ("NPV P90 (M TL)", N, {"fmt": "0.0"}), ("Pozitif NPV Olasılığı", N, {"fmt": "0%"}),
                   ("En İyi Seçenek Olasılığı", N, {"fmt": "0%"})],
    "FinansNPV": [("Seçenek", T), ("NPV (M TL)", N, {"fmt": "0.0"}), ("Frekans", I)],
}

ILISKILER = [
    ("FaktUretim", "Tarih", "DimTarih", "Tarih"), ("FaktUretim", "MakineID", "DimMakine", "MakineID"),
    ("FaktUretim", "UrunID", "DimUrun", "UrunID"), ("FaktUretim", "VardiyaID", "DimVardiya", "VardiyaID"),
    ("FaktDurus", "Tarih", "DimTarih", "Tarih"), ("FaktDurus", "MakineID", "DimMakine", "MakineID"),
    ("FaktDurus", "UrunID", "DimUrun", "UrunID"), ("FaktDurus", "VardiyaID", "DimVardiya", "VardiyaID"),
    ("FaktDurus", "NedenID", "DimDurusNedeni", "NedenID"),
    ("FaktKalite", "Tarih", "DimTarih", "Tarih"), ("FaktKalite", "MakineID", "DimMakine", "MakineID"),
    ("FaktKalite", "UrunID", "DimUrun", "UrunID"), ("FaktKalite", "VardiyaID", "DimVardiya", "VardiyaID"),
    ("FaktKalite", "HataID", "DimHataTuru", "HataID"),
    ("FaktSiparis", "TerminTarihi", "DimTarih", "Tarih"), ("FaktSiparis", "UrunID", "DimUrun", "UrunID"),
    ("FaktSiparis", "MusteriID", "DimMusteri", "MusteriID"),
    ("FaktOlcum", "Tarih", "DimTarih", "Tarih"), ("FaktOlcum", "MakineID", "DimMakine", "MakineID"),
    ("FaktOlcum", "UrunID", "DimUrun", "UrunID"), ("FaktOlcum", "VardiyaID", "DimVardiya", "VardiyaID"),
    ("FaktMesai", "Tarih", "DimTarih", "Tarih"),
    ("FaktTalep", "Ay", "DimTarih", "Tarih"), ("FaktTalep", "UrunID", "DimUrun", "UrunID"),
    ("OptPlan", "Ay", "DimTarih", "Tarih"), ("OptPlan", "UrunID", "DimUrun", "UrunID"),
]

# (ad, DAX, biçim, klasör, açıklama)
OLCULER = [
    # 1 OEE
    ("Planlanan Süre (saat)", "DIVIDE ( SUM ( FaktUretim[PlanlananSureDk] ), 60 )", "#,0", "1 OEE",
     "OEE'ye giren planlı üretim süresi (iş yüklenen süre, planlı bakım hariç)."),
    ("Çalışma Süresi (saat)", "DIVIDE ( SUM ( FaktUretim[CalismaSuresiDk] ), 60 )", "#,0", "1 OEE",
     "Makinenin fiilen parça işlediği süre."),
    ("Kullanılabilirlik", "DIVIDE ( SUM ( FaktUretim[CalismaSuresiDk] ), SUM ( FaktUretim[PlanlananSureDk] ) )",
     "0.0%", "1 OEE", "Çalışma süresi / planlanan süre."),
    ("Performans", "DIVIDE ( SUM ( FaktUretim[IdealSureDk] ), SUM ( FaktUretim[CalismaSuresiDk] ) )", "0.0%",
     "1 OEE", "İdeal çevrim süresiyle gereken süre / çalışma süresi (hız kaybı ve küçük duruşlar)."),
    ("Kalite", "DIVIDE ( SUM ( FaktUretim[SaglamAdet] ), SUM ( FaktUretim[UretilenAdet] ) )", "0.0%", "1 OEE",
     "Sağlam adet / üretilen adet."),
    ("OEE", "[Kullanılabilirlik] * [Performans] * [Kalite]", "0.0%", "1 OEE",
     "Toplam Ekipman Etkinliği = Kullanılabilirlik × Performans × Kalite."),
    ("OEE Hedef", "IF ( NOT ISBLANK ( [OEE] ), 0.75 )", "0%", "1 OEE",
     "Şirket hedefi; yalnızca OEE verisi olan dönemlerde gösterilir."),
    ("OEE Hedefe Fark", "IF ( NOT ISBLANK ( [OEE] ), [OEE] - [OEE Hedef] )", "+0.0%;-0.0%;0.0%", "1 OEE", ""),
    ("OEE Renk", 'SWITCH ( TRUE (), ISBLANK ( [OEE] ), BLANK (), [OEE] >= 0.75, "#0CA30C", [OEE] >= 0.65, '
                 '"#FAB219", "#D03B3B" )', "", "1 OEE", "Durum rengi: hedef üstü / yakın / altı."),
    ("OEE Zemin", 'SWITCH ( TRUE (), ISBLANK ( [OEE] ), BLANK (), [OEE] >= 0.75, "#DDF2DD", [OEE] >= 0.65, '
                  '"#FDEFCF", "#F6D8D8" )', "", "1 OEE", "Matris hücre zemini için açık durum rengi."),
    ("Kapasite Kullanımı", "DIVIDE ( SUM ( FaktUretim[PlanlananSureDk] ), SUM ( FaktUretim[TakvimSuresiDk] ) )",
     "0%", "1 OEE", "İş yüklenen süre / vardiya takvimi. Darboğazda %100'e yakındır."),
    ("OEE Önceki Ay", "CALCULATE ( [OEE], DATEADD ( DimTarih[Tarih], -1, MONTH ) )", "0.0%", "1 OEE", ""),
    ("OEE Aylık Değişim (puan)", "IF ( NOT ISBLANK ( [OEE Önceki Ay] ), ( [OEE] - [OEE Önceki Ay] ) * 100 )",
     "+0.0;-0.0;0.0", "1 OEE", ""),
    # 2 Üretim & Kalite
    ("Üretilen Adet", "SUM ( FaktUretim[UretilenAdet] )", "#,0", "2 Üretim ve Kalite", ""),
    ("Sağlam Adet", "SUM ( FaktUretim[SaglamAdet] )", "#,0", "2 Üretim ve Kalite", ""),
    ("Hurda Adet", "SUM ( FaktUretim[HurdaAdet] )", "#,0", "2 Üretim ve Kalite", ""),
    ("Hurda Oranı", "DIVIDE ( [Hurda Adet], [Üretilen Adet] )", "0.00%", "2 Üretim ve Kalite", ""),
    ("Hurda Maliyeti (TL)", "SUM ( FaktUretim[HurdaMaliyetiTL] )", "#,0", "2 Üretim ve Kalite",
     "Hurda adedi × standart maliyet × operasyondaki birikmiş maliyet oranı."),
    ("Hat Çıkışı (adet)", "CALCULATE ( [Sağlam Adet], DimMakine[Son İstasyon] = 1 )", "#,0", "2 Üretim ve Kalite",
     "Son istasyondan çıkan sağlam ürün."),
    ("Hata Adedi", "SUM ( FaktKalite[Adet] )", "#,0", "2 Üretim ve Kalite", ""),
    ("Hata Payı", "DIVIDE ( [Hata Adedi], CALCULATE ( [Hata Adedi], ALLSELECTED ( DimHataTuru ) ) )", "0%",
     "2 Üretim ve Kalite", ""),
    ("Hata Kümülatif Pay",
     "VAR mevcut = [Hata Adedi]\nVAR tablo = ADDCOLUMNS ( ALLSELECTED ( DimHataTuru[Hata Türü] ), \"@a\", [Hata Adedi] )\n"
     "RETURN IF ( NOT ISBLANK ( mevcut ), DIVIDE ( SUMX ( FILTER ( tablo, [@a] >= mevcut ), [@a] ), SUMX ( tablo, [@a] ) ) )",
     "0%", "2 Üretim ve Kalite", "Pareto için kümülatif pay."),
    ("Çap Ortalama (mm)", "AVERAGE ( FaktOlcum[CapMm] )", "0.0000", "2 Üretim ve Kalite", "AM-200 taşlama çıkışı."),
    ("Çap Std Sapma (mm)", "STDEV.S ( FaktOlcum[CapMm] )", "0.0000", "2 Üretim ve Kalite", ""),
    ("Ppk",
     "VAR mu = [Çap Ortalama (mm)]\nVAR s = [Çap Std Sapma (mm)]\nRETURN DIVIDE ( MIN ( 25.015 - mu, mu - 24.985 ), 3 * s )",
     "0.00", "2 Üretim ve Kalite", "Genel süreç performans indeksi (tolerans 25,000 ± 0,015 mm)."),
    ("Ppk Hedef", "IF ( NOT ISBLANK ( [Ppk] ), 1.33 )", "0.00", "2 Üretim ve Kalite", "Müşteri şartı."),
    ("Ölçüm Sayısı", "COUNTROWS ( FaktOlcum )", "#,0", "2 Üretim ve Kalite", ""),
    # 3 Duruş & Bakım
    ("Duruş Süresi (saat)", "DIVIDE ( SUM ( FaktDurus[SureDk] ), 60 )", "#,0", "3 Duruş ve Bakım", ""),
    ("Duruş Adedi", "COUNTROWS ( FaktDurus )", "#,0", "3 Duruş ve Bakım", ""),
    ("Plansız Duruş (saat)", 'CALCULATE ( [Duruş Süresi (saat)], DimDurusNedeni[Planlı mı] = "Hayır" )', "#,0",
     "3 Duruş ve Bakım", ""),
    ("Duruş Payı", "DIVIDE ( [Plansız Duruş (saat)], CALCULATE ( [Plansız Duruş (saat)], ALLSELECTED ( DimDurusNedeni ) ) )",
     "0%", "3 Duruş ve Bakım", ""),
    ("Duruş Kümülatif Pay",
     "VAR mevcut = [Plansız Duruş (saat)]\nVAR tablo = ADDCOLUMNS ( ALLSELECTED ( DimDurusNedeni[Neden] ), \"@s\", [Plansız Duruş (saat)] )\n"
     "RETURN IF ( NOT ISBLANK ( mevcut ), DIVIDE ( SUMX ( FILTER ( tablo, [@s] >= mevcut ), [@s] ), SUMX ( tablo, [@s] ) ) )",
     "0%", "3 Duruş ve Bakım", "Pareto için kümülatif pay."),
    ("Arıza Sayısı", 'CALCULATE ( [Duruş Adedi], DimDurusNedeni[Kategori] = "Arıza" )', "#,0", "3 Duruş ve Bakım", ""),
    ("Arıza Süresi (saat)", 'CALCULATE ( [Duruş Süresi (saat)], DimDurusNedeni[Kategori] = "Arıza" )', "#,0",
     "3 Duruş ve Bakım", ""),
    ("MTBF (saat)", "DIVIDE ( [Çalışma Süresi (saat)], [Arıza Sayısı] )", "#,0.0", "3 Duruş ve Bakım",
     "Arızalar arası ortalama çalışma süresi."),
    ("MTTR (dk)", "DIVIDE ( [Arıza Süresi (saat)] * 60, [Arıza Sayısı] )", "#,0", "3 Duruş ve Bakım",
     "Ortalama tamir süresi."),
    ("Ayar Sayısı", 'CALCULATE ( [Duruş Adedi], DimDurusNedeni[NedenID] = "D01" )', "#,0", "3 Duruş ve Bakım", ""),
    ("Ortalama Ayar Süresi (dk)",
     'DIVIDE ( CALCULATE ( SUM ( FaktDurus[SureDk] ), DimDurusNedeni[NedenID] = "D01" ), [Ayar Sayısı] )',
     "#,0", "3 Duruş ve Bakım", "Ürün değişimi (setup) ortalaması."),
    # 4 Teslimat & Maliyet
    ("Sipariş Sayısı", "COUNTROWS ( FaktSiparis )", "#,0", "4 Teslimat ve Maliyet", ""),
    ("Zamanında Teslimat", "DIVIDE ( CALCULATE ( COUNTROWS ( FaktSiparis ), FaktSiparis[ZamanindaMi] = 1 ), [Sipariş Sayısı] )",
     "0.0%", "4 Teslimat ve Maliyet", "Termin tarihinde veya öncesinde sevk edilen siparişlerin oranı."),
    ("OTD Hedef", "IF ( NOT ISBLANK ( [Zamanında Teslimat] ), 0.95 )", "0%", "4 Teslimat ve Maliyet", ""),
    ("Geciken Sipariş", "CALCULATE ( [Sipariş Sayısı], FaktSiparis[ZamanindaMi] = 0 )", "#,0", "4 Teslimat ve Maliyet", ""),
    ("Ort. Gecikme (gün)", "CALCULATE ( AVERAGE ( FaktSiparis[GecikmeGun] ), FaktSiparis[ZamanindaMi] = 0 )", "0.0",
     "4 Teslimat ve Maliyet", "Geciken siparişlerde ortalama gecikme."),
    ("Ciro (TL)", "SUM ( FaktSiparis[Tutar] )", "#,0", "4 Teslimat ve Maliyet", ""),
    ("Gecikme Cezası (TL)", "SUM ( FaktSiparis[CezaTutariTL] )", "#,0", "4 Teslimat ve Maliyet", ""),
    ("Ekspres Nakliye (TL)", "SUM ( FaktSiparis[EkspresNakliyeTL] )", "#,0", "4 Teslimat ve Maliyet", ""),
    ("Fazla Mesai (TL)", "SUM ( FaktMesai[MaliyetTL] )", "#,0", "4 Teslimat ve Maliyet", ""),
    ("Fazla Mesai Vardiyası", "SUM ( FaktMesai[VardiyaSayisi] )", "#,0", "4 Teslimat ve Maliyet", ""),
    ("Kapasite Açığı Maliyeti (TL)", "[Fazla Mesai (TL)] + [Gecikme Cezası (TL)] + [Ekspres Nakliye (TL)]", "#,0",
     "4 Teslimat ve Maliyet", "Fazla mesai + gecikme cezası + ekspres nakliye."),
    # 5 Tahmin & Senaryolar
    ("Talep (adet)", 'CALCULATE ( SUM ( FaktTalep[Adet] ), FaktTalep[Tür] = "Gerçekleşen" )', "#,0",
     "5 Tahmin ve Senaryolar", ""),
    ("Talep Tahmini (adet)", 'CALCULATE ( SUM ( FaktTalep[Adet] ), FaktTalep[Tür] = "Tahmin" )', "#,0",
     "5 Tahmin ve Senaryolar", "ETS(M,Ad,M) + satış girdisi."),
    ("Tahmin Alt %80", 'CALCULATE ( SUM ( FaktTalep[Alt %80] ), FaktTalep[Tür] = "Tahmin" )', "#,0",
     "5 Tahmin ve Senaryolar", ""),
    ("Tahmin Üst %80", 'CALCULATE ( SUM ( FaktTalep[Üst %80] ), FaktTalep[Tür] = "Tahmin" )', "#,0",
     "5 Tahmin ve Senaryolar", ""),
    ("Sim Haftalık Çıktı", "SUM ( SimKapasite[Haftalık Çıktı] )", "#,0", "5 Tahmin ve Senaryolar",
     "SimPy kapasite testi, 25 tekrar ortalaması."),
    ("Sim Kullanım", "AVERAGE ( SimKullanim[Kullanım] )", "0%", "5 Tahmin ve Senaryolar", ""),
    ("Opt Üretim", "SUM ( OptPlan[Üretim] )", "#,0", "5 Tahmin ve Senaryolar", ""),
    ("Opt Talep", "SUM ( OptPlan[Talep] )", "#,0", "5 Tahmin ve Senaryolar", ""),
    ("Opt Stok", "SUM ( OptPlan[Stok] )", "#,0", "5 Tahmin ve Senaryolar", ""),
    ("Opt Maliyet (TL)", "SUM ( OptMaliyet[Tutar TL] )", "#,0", "5 Tahmin ve Senaryolar", "6 aylık plan maliyeti."),
]


def guid(*parcalar: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "demirkanat/" + "/".join(parcalar)))


def tmdl_ad(ad: str) -> str:
    return "'" + ad.replace("'", "''") + "'"


M_TIP = {T: "type text", I: "Int64.Type", N: "type number", D: "type date", DT: "type datetime"}
TMDL_TIP = {T: "string", I: "int64", N: "double", D: "dateTime", DT: "dateTime"}


def tablo_tmdl(ad: str, kolonlar: list[tuple]) -> str:
    with open(PBI_VERI / f"{ad}.csv", encoding="utf-8") as f:
        baslik = next(csv.reader(f))
    tanim = {k[0]: k for k in kolonlar}
    assert set(baslik) == set(tanim), f"{ad}: CSV {baslik} ≠ model {list(tanim)}"
    satir = [f"table {tmdl_ad(ad)}", f"\tlineageTag: {guid(ad)}"]
    if ad == "DimTarih":
        satir.insert(1, "\tdataCategory: Time")
    satir.append("")
    for kolon in baslik:
        _, tip, *ek = tanim[kolon]
        ozellik = ek[0] if ek else {}
        satir.append(f"\tcolumn {tmdl_ad(kolon)}")
        satir.append(f"\t\tdataType: {TMDL_TIP[tip]}")
        if ozellik.get("key"):
            satir.append("\t\tisKey")
        if ozellik.get("hidden"):
            satir.append("\t\tisHidden")
        if tip == D:
            satir.append("\t\tformatString: dd.mm.yyyy")
        elif tip == DT:
            satir.append("\t\tformatString: dd.mm.yyyy hh:nn")
        elif "fmt" in ozellik:
            satir.append(f"\t\tformatString: {ozellik['fmt']}")
        elif tip in (I, N):
            satir.append("\t\tformatString: #,0" if tip == I else "\t\tformatString: #,0.00")
        satir.append(f"\t\tlineageTag: {guid(ad, kolon)}")
        satir.append("\t\tsummarizeBy: none")
        satir.append(f'\t\tsourceColumn: "{kolon}"')
        if "sort" in ozellik:
            satir.append(f"\t\tsortByColumn: {tmdl_ad(ozellik['sort'])}")
        if tip == D:
            satir += ["", "\t\tannotation UnderlyingDateTimeDataType = Date"]
        satir.append("")
    donusum = ", ".join(f'{{"{k}", {M_TIP[tanim[k][1]]}}}' for k in baslik)
    satir += [
        f"\tpartition {tmdl_ad(ad)} = m",
        "\t\tmode: import",
        "\t\tsource =",
        "\t\t\t\tlet",
        f'\t\t\t\t    Kaynak = Csv.Document(File.Contents(VeriKlasoru & "{ad}.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
        "\t\t\t\t    Basliklar = Table.PromoteHeaders(Kaynak, [PromoteAllScalars = true]),",
        f'\t\t\t\t    Tipler = Table.TransformColumnTypes(Basliklar, {{{donusum}}}, "en-US")',
        "\t\t\t\tin",
        "\t\t\t\t    Tipler",
        "",
        "\tannotation PBI_ResultType = Table",
        "",
    ]
    return "\n".join(satir)


def olcu_tablosu_tmdl() -> str:
    satir = [f"table {tmdl_ad(OLCU)}", f"\tlineageTag: {guid(OLCU)}", ""]
    for ad, dax, bicim, klasor, aciklama in OLCULER:
        if aciklama:
            satir.append(f"\t/// {aciklama}")
        if "\n" in dax:
            satir.append(f"\tmeasure {tmdl_ad(ad)} =")
            satir += [f"\t\t\t{s}" for s in dax.split("\n")]
        else:
            satir.append(f"\tmeasure {tmdl_ad(ad)} = {dax}")
        if bicim:
            satir.append(f"\t\tformatString: {bicim}")
        satir.append(f"\t\tdisplayFolder: {klasor}")
        satir.append(f"\t\tlineageTag: {guid(OLCU, ad)}")
        satir.append("")
    satir += [
        "\tcolumn Kolon1",
        "\t\tdataType: string",
        "\t\tisHidden",
        f"\t\tlineageTag: {guid(OLCU, 'Kolon1')}",
        "\t\tsummarizeBy: none",
        "\t\tsourceColumn: Kolon1",
        "",
        f"\tpartition {tmdl_ad(OLCU)} = m",
        "\t\tmode: import",
        "\t\tsource =",
        "\t\t\t\tlet",
        '\t\t\t\t    Kaynak = #table(type table [Kolon1 = text], {})',
        "\t\t\t\tin",
        "\t\t\t\t    Kaynak",
        "",
        "\tannotation PBI_ResultType = Table",
        "",
    ]
    return "\n".join(satir)


def model_yaz() -> None:
    if SM.exists():
        shutil.rmtree(SM)
    (SM / "definition" / "tables").mkdir(parents=True)
    (SM / "definition.pbism").write_text(json.dumps({
        "$schema": f"{SEMA}/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.0", "settings": {}}, indent=2), encoding="utf-8")
    d = SM / "definition"
    (d / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1567\n\n", encoding="utf-8")
    tablolar = [OLCU, *TABLOLAR]
    sorgu_sirasi = json.dumps(["VeriKlasoru", *tablolar], ensure_ascii=False)
    (d / "model.tmdl").write_text("\n".join([
        "model Model",
        "\tculture: tr-TR",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tdiscourageImplicitMeasures",
        "\tsourceQueryCulture: tr-TR",
        "\tdataAccessOptions",
        "\t\tlegacyRedirects",
        "\t\treturnErrorValuesAsNull",
        "",
        f"annotation PBI_QueryOrder = {sorgu_sirasi}",
        "",
        "annotation __PBI_TimeIntelligenceEnabled = 0",
        "",
        *[f"ref table {tmdl_ad(t)}" for t in tablolar],
        "",
    ]), encoding="utf-8")
    klasor = str(PBI_VERI).rstrip("\\") + "\\"
    (d / "expressions.tmdl").write_text("\n".join([
        f'expression VeriKlasoru = "{klasor}" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]',
        f"\tlineageTag: {guid('VeriKlasoru')}",
        "",
        "\tannotation PBI_ResultType = Text",
        "",
    ]), encoding="utf-8")
    satir = []
    for kaynak, kolon, hedef, hedef_kolon in ILISKILER:
        satir += [f"relationship {guid('iliski', kaynak, kolon)}",
                  f"\tfromColumn: {tmdl_ad(kaynak)}.{tmdl_ad(kolon)}",
                  f"\ttoColumn: {tmdl_ad(hedef)}.{tmdl_ad(hedef_kolon)}", ""]
    (d / "relationships.tmdl").write_text("\n".join(satir), encoding="utf-8")
    (d / "tables" / f"{OLCU}.tmdl").write_text(olcu_tablosu_tmdl(), encoding="utf-8")
    for ad, kolonlar in TABLOLAR.items():
        (d / "tables" / f"{ad}.tmdl").write_text(tablo_tmdl(ad, kolonlar), encoding="utf-8")


# --------------------------------------------------------------------------
# 2) Rapor (PBIR)
# --------------------------------------------------------------------------
GORSEL_SEMA = f"{SEMA}/item/report/definition/visualContainer/1.4.0/schema.json"
RENK = {"mavi": "#2A78D6", "turuncu": "#EB6834", "su": "#1BAF7A", "sari": "#EDA100", "gri": "#AEACA3",
        "murekkep": "#0B0B0B", "ikincil": "#52514E", "zemin": "#F3F3F0", "cizgi": "#E1E0D9", "mor": "#6250D6"}


def lit(deger) -> dict:
    if isinstance(deger, bool):
        v = "true" if deger else "false"
    elif isinstance(deger, (int, float)):
        v = f"{deger}D"
    else:
        v = "'" + str(deger).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": v}}}


def dolgu(hex_renk: str) -> dict:
    return {"solid": {"color": lit(hex_renk)}}


def kolon(tablo: str, ad: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": tablo}}, "Property": ad}}


def olcu(ad: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": OLCU}}, "Property": ad}}


def ref(alan: dict) -> str:
    ic = alan.get("Column") or alan.get("Measure")
    return f"{ic['Expression']['SourceRef']['Entity']}.{ic['Property']}"


def projeksiyon(alan: dict, aktif: bool = False) -> dict:
    ic = alan.get("Column") or alan.get("Measure")
    p = {"field": alan, "queryRef": ref(alan), "nativeQueryRef": ic["Property"]}
    if aktif:
        p["active"] = True
    return p


class Sayfa:
    def __init__(self, ad: str, baslik: str):
        self.ad, self.baslik, self.gorseller = ad, baslik, []

    def ekle(self, ad, tur, x, y, w, h, roller=None, sirala=None, nesneler=None, kap=None, baslik=None):
        g = {"$schema": GORSEL_SEMA, "name": ad,
             "position": {"x": x, "y": y, "z": len(self.gorseller) * 1000, "height": h, "width": w,
                          "tabOrder": len(self.gorseller) * 1000},
             "visual": {"visualType": tur}}
        if roller:
            durum = {}
            for rol, alanlar in roller.items():
                durum[rol] = {"projections": [projeksiyon(a, aktif=rol in ("Category", "Rows", "Values")
                                                          and "Column" in a and tur == "slicer" or
                                                          (rol in ("Category", "Rows") and "Column" in a))
                                              for a in alanlar]}
            g["visual"]["query"] = {"queryState": durum}
            if sirala:
                alan, yon = sirala
                g["visual"]["query"]["sortDefinition"] = {"sort": [{"field": alan, "direction": yon}],
                                                          "isDefaultSort": True}
        if nesneler:
            g["visual"]["objects"] = nesneler
        kap = dict(kap or {})
        if baslik:
            kap["title"] = [{"properties": {"show": lit(True), "text": lit(baslik)}}]
        if kap:
            g["visual"]["visualContainerObjects"] = kap
        g["visual"]["drillFilterOtherVisuals"] = True
        self.gorseller.append(g)
        return g

    def metin(self, ad, x, y, w, h, satirlar):
        paragraflar = [{"textRuns": [{"value": t, "textStyle": {"fontFamily": "Segoe UI", "fontSize": f"{s}pt",
                                                                 "fontWeight": "bold" if b else "normal", "color": c}}]}
                       for t, s, b, c in satirlar]
        g = {"$schema": GORSEL_SEMA, "name": ad,
             "position": {"x": x, "y": y, "z": len(self.gorseller) * 1000, "height": h, "width": w,
                          "tabOrder": len(self.gorseller) * 1000},
             "visual": {"visualType": "textbox",
                        "objects": {"general": [{"properties": {"paragraphs": paragraflar}}]},
                        "visualContainerObjects": {"background": [{"properties": {"show": lit(False)}}],
                                                   "border": [{"properties": {"show": lit(False)}}]},
                        "drillFilterOtherVisuals": True}}
        self.gorseller.append(g)

    # ---- yardımcı kalıplar ----
    def ust_bilgi(self, alt_baslik: str, dilimleyiciler=(("Hat", kolon("DimUrun", "Hat")),
                                                         ("Dönem", kolon("DimTarih", "Dönem")))):
        self.metin(f"{self.ad}_baslik", 20, 8, 760, 60, [
            (self.baslik, 18, True, RENK["murekkep"]), (alt_baslik, 10, False, RENK["ikincil"])])
        for k, (ad, alan) in enumerate(dilimleyiciler):
            x = 1260 - (len(dilimleyiciler) - k) * 232
            self.ekle(f"{self.ad}_dilim{k + 1}", "slicer", x, 12, 220, 56, roller={"Values": [alan]},
                      nesneler={"data": [{"properties": {"mode": lit("Dropdown")}}]}, baslik=ad)

    def kartlar(self, olculer: list[str], y=80, h=96):
        n = len(olculer)
        w = (1240 - (n - 1) * 12) / n
        for k, ad in enumerate(olculer):
            self.ekle(f"{self.ad}_kart{k + 1}", "card", round(20 + k * (w + 12)), y, round(w), h,
                      roller={"Values": [olcu(ad)]},
                      nesneler={"labels": [{"properties": {"fontSize": lit(22), "color": dolgu(RENK["murekkep"])}}],
                                "categoryLabels": [{"properties": {"show": lit(True), "fontSize": lit(10)}}]})


def seri_renkleri(eslesme: dict[str, str]) -> list[dict]:
    return [{"properties": {"fill": dolgu(r)}, "selector": {"metadata": ref(olcu(m))}} for m, r in eslesme.items()]


def ay() -> dict:
    return kolon("DimTarih", "Yıl-Ay")


def sayfalar() -> list[Sayfa]:
    s1 = Sayfa("p1_ozet", "Yönetici Özeti")
    s1.ust_bilgi("Demirkanat Otomotiv (kurgusal) · Hat-1 darboğaz odaklı performans · sentetik MES/ERP verisi")
    s1.kartlar(["OEE", "Kullanılabilirlik", "Performans", "Kalite", "Zamanında Teslimat", "Kapasite Açığı Maliyeti (TL)"])
    s1.ekle("p1_oee_trend", "lineChart", 20, 188, 610, 256, roller={"Category": [ay()], "Y": [olcu("OEE"), olcu("OEE Hedef")]},
            nesneler={"dataPoint": seri_renkleri({"OEE": RENK["mavi"], "OEE Hedef": RENK["gri"]})},
            baslik="Aylık OEE ve hedef (%75)")
    s1.ekle("p1_oee_makine", "clusteredBarChart", 650, 188, 610, 256,
            roller={"Category": [kolon("DimMakine", "Makine Kodu")], "Y": [olcu("OEE")]},
            sirala=(olcu("OEE"), "Ascending"),
            nesneler={"dataPoint": [{"properties": {"fill": {"solid": {"color": {"expr": olcu("OEE Renk")}}}},
                                     "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}],
                      "labels": [{"properties": {"show": lit(True)}}]},
            baslik="Makine bazında OEE · yeşil ≥ %75 · sarı ≥ %65 · kırmızı < %65")
    s1.ekle("p1_otd", "lineChart", 20, 456, 610, 252,
            roller={"Category": [ay()], "Y": [olcu("Zamanında Teslimat"), olcu("OTD Hedef")]},
            nesneler={"dataPoint": seri_renkleri({"Zamanında Teslimat": RENK["mavi"], "OTD Hedef": RENK["gri"]})},
            baslik="Zamanında teslimat ve hedef (%95)")
    s1.ekle("p1_maliyet", "columnChart", 650, 456, 610, 252,
            roller={"Category": [ay()], "Y": [olcu("Fazla Mesai (TL)"), olcu("Gecikme Cezası (TL)"),
                                               olcu("Ekspres Nakliye (TL)")]},
            nesneler={"dataPoint": seri_renkleri({"Fazla Mesai (TL)": RENK["mavi"], "Gecikme Cezası (TL)": RENK["su"],
                                                  "Ekspres Nakliye (TL)": RENK["sari"]})},
            baslik="Kapasite açığının maliyeti (TL / ay)")

    s2 = Sayfa("p2_oee", "OEE ve Darboğaz")
    s2.ust_bilgi("Hangi makine, hangi vardiya? OEE = Kullanılabilirlik × Performans × Kalite")
    s2.ekle("p2_matris", "pivotTable", 20, 80, 620, 330,
            roller={"Rows": [kolon("DimMakine", "Makine Kodu")], "Columns": [kolon("DimVardiya", "Vardiya")],
                    "Values": [olcu("OEE")]},
            nesneler={"values": [{"properties": {"backColor": {"solid": {"color": {"expr": olcu("OEE Zemin")}}}},
                                  "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}],
                                               "metadata": ref(olcu("OEE"))}}]},
            baslik="OEE · makine × vardiya")
    s2.ekle("p2_kullanim", "clusteredBarChart", 660, 80, 600, 330,
            roller={"Category": [kolon("DimMakine", "Makine Kodu")], "Y": [olcu("Kapasite Kullanımı")]},
            sirala=(olcu("Kapasite Kullanımı"), "Descending"),
            nesneler={"dataPoint": seri_renkleri({"Kapasite Kullanımı": RENK["turuncu"]}),
                      "labels": [{"properties": {"show": lit(True)}}]},
            baslik="Kapasite kullanımı · darboğaz %100'e dayanır")
    s2.ekle("p2_bilesen", "clusteredColumnChart", 20, 424, 1240, 284,
            roller={"Category": [kolon("DimMakine", "Makine Kodu")],
                    "Y": [olcu("Kullanılabilirlik"), olcu("Performans"), olcu("Kalite")]},
            nesneler={"dataPoint": seri_renkleri({"Kullanılabilirlik": RENK["mavi"], "Performans": RENK["su"],
                                                  "Kalite": RENK["sari"]})},
            baslik="OEE bileşenleri, makine bazında")

    s3 = Sayfa("p3_durus", "Duruş ve Bakım")
    s3.ust_bilgi("Pareto, MTBF / MTTR ve ayar süreleri · makine filtresiyle H1-FRZ'ye odaklanın",
                 (("Makine", kolon("DimMakine", "Makine Kodu")), ("Dönem", kolon("DimTarih", "Dönem"))))
    s3.ekle("p3_pareto", "lineClusteredColumnComboChart", 20, 80, 760, 330,
            roller={"Category": [kolon("DimDurusNedeni", "Neden")], "Y": [olcu("Duruş Payı")],
                    "Y2": [olcu("Duruş Kümülatif Pay")]},
            sirala=(olcu("Duruş Payı"), "Descending"),
            nesneler={"valueAxis": [{"properties": {"secShow": lit(False)}}],
                      "dataPoint": seri_renkleri({"Duruş Payı": RENK["mavi"], "Duruş Kümülatif Pay": RENK["ikincil"]}),
                      "labels": [{"properties": {"show": lit(True)}}]},
            baslik="Plansız duruş Pareto'su (pay ve kümülatif pay, tek eksen)")
    s3.ekle("p3_tablo", "tableEx", 800, 80, 460, 330,
            roller={"Values": [kolon("DimMakine", "Makine Kodu"), olcu("MTBF (saat)"), olcu("MTTR (dk)"),
                               olcu("Arıza Sayısı"), olcu("Ayar Sayısı"), olcu("Ortalama Ayar Süresi (dk)")]},
            sirala=(olcu("MTBF (saat)"), "Ascending"), baslik="Bakım göstergeleri")
    s3.ekle("p3_trend", "columnChart", 20, 424, 1240, 284,
            roller={"Category": [ay()], "Series": [kolon("DimDurusNedeni", "Kategori")], "Y": [olcu("Plansız Duruş (saat)")]},
            baslik="Aylık plansız duruş (saat), kategori")

    s4 = Sayfa("p4_kalite", "Kalite ve SPC")
    s4.ust_bilgi("Hurda, hata türleri ve AM-200 çap süreç yeterliliği (Ppk)")
    s4.kartlar(["Hurda Oranı", "Hurda Maliyeti (TL)", "Ppk", "Ölçüm Sayısı"])
    s4.ekle("p4_pareto", "lineClusteredColumnComboChart", 20, 190, 620, 272,
            roller={"Category": [kolon("DimHataTuru", "Hata Türü")], "Y": [olcu("Hata Payı")],
                    "Y2": [olcu("Hata Kümülatif Pay")]},
            sirala=(olcu("Hata Payı"), "Descending"),
            nesneler={"valueAxis": [{"properties": {"secShow": lit(False)}}],
                      "dataPoint": seri_renkleri({"Hata Payı": RENK["mavi"], "Hata Kümülatif Pay": RENK["ikincil"]})},
            baslik="Hata türü Pareto'su")
    s4.ekle("p4_vardiya", "clusteredColumnChart", 660, 190, 600, 272,
            roller={"Category": [kolon("DimVardiya", "Vardiya")], "Y": [olcu("Hurda Oranı")]},
            nesneler={"dataPoint": seri_renkleri({"Hurda Oranı": RENK["mavi"]}),
                      "labels": [{"properties": {"show": lit(True)}}]},
            baslik="Hurda oranı, vardiya")
    s4.ekle("p4_ppk", "lineChart", 20, 476, 1240, 232, roller={"Category": [ay()], "Y": [olcu("Ppk"), olcu("Ppk Hedef")]},
            nesneler={"dataPoint": seri_renkleri({"Ppk": RENK["mavi"], "Ppk Hedef": RENK["gri"]})},
            baslik="Aylık Ppk (AM-200 çap) ve müşteri şartı 1,33")

    s5 = Sayfa("p5_teslimat", "Teslimat ve Maliyet")
    s5.ust_bilgi("Zamanında teslimat, gecikmeler ve kapasite açığının maliyeti")
    s5.kartlar(["Zamanında Teslimat", "Geciken Sipariş", "Ort. Gecikme (gün)", "Gecikme Cezası (TL)",
                "Fazla Mesai Vardiyası"])
    s5.ekle("p5_trend", "lineChart", 20, 190, 760, 272,
            roller={"Category": [ay()], "Series": [kolon("DimUrun", "Hat")], "Y": [olcu("Zamanında Teslimat")]},
            baslik="Zamanında teslimat, hat bazında")
    s5.ekle("p5_musteri", "clusteredBarChart", 800, 190, 460, 272,
            roller={"Category": [kolon("DimMusteri", "Müşteri")], "Y": [olcu("Zamanında Teslimat")]},
            sirala=(olcu("Zamanında Teslimat"), "Ascending"),
            nesneler={"labels": [{"properties": {"show": lit(True)}}]}, baslik="Müşteri bazında zamanında teslimat")
    s5.ekle("p5_tablo", "tableEx", 20, 476, 1240, 232,
            roller={"Values": [kolon("FaktSiparis", "SiparisNo"), kolon("DimMusteri", "Müşteri"),
                               kolon("DimUrun", "Ürün Kodu"), kolon("FaktSiparis", "TerminTarihi"),
                               kolon("FaktSiparis", "SevkTarihi"), kolon("FaktSiparis", "GecikmeGun"),
                               kolon("FaktSiparis", "Durum")]},
            sirala=(kolon("FaktSiparis", "GecikmeGun"), "Descending"), baslik="Siparişler · en çok gecikenden başlayarak")

    s6 = Sayfa("p6_senaryo", "Tahmin ve Senaryolar")
    s6.ust_bilgi("Talep tahmini (ETS), SimPy senaryoları, MILP planı ve Monte Carlo yatırım analizi",
                 (("Hat", kolon("DimUrun", "Hat")),))
    s6.ekle("p6_tahmin", "lineChart", 20, 80, 620, 300,
            roller={"Category": [ay()], "Y": [olcu("Talep (adet)"), olcu("Talep Tahmini (adet)"),
                                               olcu("Tahmin Alt %80"), olcu("Tahmin Üst %80")]},
            nesneler={"dataPoint": seri_renkleri({"Talep (adet)": RENK["ikincil"], "Talep Tahmini (adet)": RENK["mavi"],
                                                  "Tahmin Alt %80": RENK["gri"], "Tahmin Üst %80": RENK["gri"]})},
            baslik="Talep: gerçekleşen ve 6 aylık tahmin (%80 aralık)")
    s6.ekle("p6_sim", "clusteredBarChart", 660, 80, 600, 300,
            roller={"Category": [kolon("SimKapasite", "Senaryo Adı")], "Y": [olcu("Sim Haftalık Çıktı")]},
            sirala=(kolon("SimKapasite", "Senaryo Adı"), "Ascending"),
            nesneler={"labels": [{"properties": {"show": lit(True)}}]},
            baslik="Simülasyon: azami haftalık çıktı (adet)")
    s6.ekle("p6_opt", "columnChart", 20, 394, 620, 314,
            roller={"Category": [kolon("OptMaliyet", "Durum")], "Series": [kolon("OptMaliyet", "Kalem")],
                    "Y": [olcu("Opt Maliyet (TL)")]},
            baslik="Optimizasyon: 6 aylık plan maliyeti (TL)")
    s6.ekle("p6_finans", "tableEx", 660, 394, 600, 314,
            roller={"Values": [kolon("FinansOzet", "Seçenek"), kolon("FinansOzet", "NPV P10 (M TL)"),
                               kolon("FinansOzet", "NPV Medyan (M TL)"), kolon("FinansOzet", "NPV P90 (M TL)"),
                               kolon("FinansOzet", "Pozitif NPV Olasılığı"),
                               kolon("FinansOzet", "En İyi Seçenek Olasılığı")]},
            baslik="Monte Carlo: 5 yıllık NPV (milyon TL, N = 10.000)")
    return [s1, s2, s3, s4, s5, s6]


def tema() -> dict:
    return {
        "name": "Demirkanat Fabrika",
        "dataColors": ["#2A78D6", "#EB6834", "#1BAF7A", "#EDA100", "#E87BA4", "#008300", "#6250D6", "#E34948"],
        "foreground": "#0B0B0B", "foregroundNeutralSecondary": "#52514E", "foregroundNeutralTertiary": "#898781",
        "background": "#FFFFFF", "backgroundLight": "#F6F6F3", "backgroundNeutral": "#E1E0D9",
        "tableAccent": "#2A78D6", "good": "#0CA30C", "neutral": "#FAB219", "bad": "#D03B3B",
        "maximum": "#104281", "center": "#86B6EF", "minimum": "#E8F1FC",
        "textClasses": {
            "callout": {"fontSize": 22, "fontFace": "Segoe UI Semibold", "color": "#0B0B0B"},
            "title": {"fontSize": 11, "fontFace": "Segoe UI Semibold", "color": "#0B0B0B"},
            "header": {"fontSize": 11, "fontFace": "Segoe UI Semibold", "color": "#0B0B0B"},
            "label": {"fontSize": 9, "fontFace": "Segoe UI", "color": "#52514E"},
        },
        "visualStyles": {
            "*": {"*": {
                "background": [{"show": True, "color": {"solid": {"color": "#FFFFFF"}}, "transparency": 0}],
                "border": [{"show": True, "color": {"solid": {"color": "#E1E0D9"}}, "radius": 8}],
                "dropShadow": [{"show": False}],
            }},
            "page": {"*": {
                "background": [{"color": {"solid": {"color": "#F3F3F0"}}, "transparency": 0}],
                "outspace": [{"color": {"solid": {"color": "#F3F3F0"}}}],
            }},
        },
    }


def rapor_yaz() -> None:
    if RP.exists():
        shutil.rmtree(RP)
    d = RP / "definition"
    (d / "pages").mkdir(parents=True)
    (RP / "definition.pbir").write_text(json.dumps({
        "$schema": f"{SEMA}/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": f"../{AD}.SemanticModel"}}}, indent=2),
        encoding="utf-8")
    (d / "version.json").write_text(json.dumps({
        "$schema": f"{SEMA}/item/report/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"},
        indent=2), encoding="utf-8")
    tema_adi = "DemirkanatTema.json"
    (d / "report.json").write_text(json.dumps({
        "$schema": f"{SEMA}/item/report/definition/report/1.2.0/schema.json",
        "themeCollection": {
            "baseTheme": {"name": "CY24SU10", "reportVersionAtImport": "5.59", "type": "SharedResources"},
            "customTheme": {"name": tema_adi, "reportVersionAtImport": "5.59", "type": "RegisteredResources"}},
        "layoutOptimization": "None",
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": "CY24SU10", "path": "BaseThemes/CY24SU10.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": tema_adi, "path": tema_adi, "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "defaultDrillFilterOtherVisuals": True,
                     "allowChangeFilterTypes": True, "useEnhancedTooltips": True,
                     "useDefaultAggregateDisplayName": True},
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    paylasilan = RP / "StaticResources" / "SharedResources" / "BaseThemes"
    kayitli = RP / "StaticResources" / "RegisteredResources"
    paylasilan.mkdir(parents=True)
    kayitli.mkdir(parents=True)
    shutil.copyfile(BAZ_TEMA, paylasilan / "CY24SU10.json")
    (kayitli / tema_adi).write_text(json.dumps(tema(), indent=2, ensure_ascii=False), encoding="utf-8")
    (PBI / "tema").mkdir(exist_ok=True)
    (PBI / "tema" / tema_adi).write_text(json.dumps(tema(), indent=2, ensure_ascii=False), encoding="utf-8")

    liste = sayfalar()
    (d / "pages" / "pages.json").write_text(json.dumps({
        "$schema": f"{SEMA}/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [s.ad for s in liste], "activePageName": liste[0].ad}, indent=2), encoding="utf-8")
    for s in liste:
        sd = d / "pages" / s.ad
        (sd / "visuals").mkdir(parents=True)
        (sd / "page.json").write_text(json.dumps({
            "$schema": f"{SEMA}/item/report/definition/page/1.3.0/schema.json",
            "name": s.ad, "displayName": s.baslik, "displayOption": "FitToPage", "height": 720, "width": 1280,
            "objects": {"background": [{"properties": {"color": dolgu(RENK["zemin"]), "transparency": lit(0)}}],
                        "outspace": [{"properties": {"color": dolgu(RENK["zemin"])}}]},
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        for g in s.gorseller:
            (sd / "visuals" / g["name"]).mkdir()
            (sd / "visuals" / g["name"] / "visual.json").write_text(
                json.dumps(g, indent=2, ensure_ascii=False), encoding="utf-8")
    (PBI / f"{AD}.pbip").write_text(json.dumps({
        "$schema": f"{SEMA}/pbip/pbipProperties/1.0.0/schema.json", "version": "1.0",
        "artifacts": [{"report": {"path": f"{AD}.Report"}}], "settings": {"enableAutoRecovery": True}},
        indent=2), encoding="utf-8")
    (PBI / ".gitignore").write_text("**/.pbi/localSettings.json\n**/.pbi/cache.abf\n", encoding="utf-8")


def dax_belgesi() -> None:
    satir = ["# DAX ölçüleri", "", f"Tüm ölçüler `{OLCU}` tablosundadır; görüntüleme klasörlerine göre gruplanmıştır.", ""]
    klasor = None
    for ad, dax, bicim, k, aciklama in OLCULER:
        if k != klasor:
            satir += [f"## {k}", ""]
            klasor = k
        satir += [f"### {ad}", "", aciklama, "", "```dax", f"{ad} =", *[f"    {x}" for x in dax.split("\n")], "```",
                  f"Biçim: `{bicim or 'metin'}`", ""]
    (PBI / "DAX_Olculer.md").write_text("\n".join(satir), encoding="utf-8")


def main() -> None:
    model_yaz()
    rapor_yaz()
    dax_belgesi()
    gorsel = sum(len(s.gorseller) for s in sayfalar())
    print(f"PBIP üretildi: {PBI / (AD + '.pbip')}")
    print(f"  {len(TABLOLAR) + 1} tablo · {len(ILISKILER)} ilişki · {len(OLCULER)} ölçü · 6 sayfa · {gorsel} görsel")


if __name__ == "__main__":
    main()
