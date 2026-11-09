"""Ortak ayarlar: klasör yolları, ana veriler ve grafik stili.

Demirkanat Otomotiv Yan Sanayi A.Ş. KURGUSAL bir şirkettir; tüm veriler
sentetiktir ve bu vaka çalışması için üretilmiştir.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# Klasörler
# --------------------------------------------------------------------------
KOK = Path(__file__).resolve().parents[1]
VERI_HAM = KOK / "veri" / "ham"
CIKTI = KOK / "ciktilar"
GRAFIK = CIKTI / "grafikler"
TABLO = CIKTI / "tablolar"
PBI_VERI = KOK / "powerbi" / "veri"
for _klasor in (VERI_HAM, GRAFIK, TABLO, PBI_VERI):
    _klasor.mkdir(parents=True, exist_ok=True)

OZET_DOSYA = CIKTI / "ozet_metrikler.json"
TOHUM = 2026

# --------------------------------------------------------------------------
# Hikâyenin zaman çizelgesi
# --------------------------------------------------------------------------
GECMIS_BASLANGIC = pd.Timestamp("2023-10-01")  # ERP aylık satış geçmişi
BAZ_BASLANGIC = pd.Timestamp("2025-10-01")     # MES detay verisi başlangıcı
PILOT_BASLANGIC = pd.Timestamp("2026-10-01")   # SMED + TPM + vardiya standardı pilotu
BITIS = pd.Timestamp("2026-10-31")
ISE_BASLAMA = pd.Timestamp("2026-08-03")       # Endüstri mühendisinin ilk iş günü
TAHMIN_UFKU_AY = 6                              # Kasım 2026 – Nisan 2027

VARDIYALAR = ["A", "B", "C"]
VARDIYA_SAAT = {"A": "07:00–15:00", "B": "15:00–23:00", "C": "23:00–07:00"}
VARDIYA_BASLANGIC_SAAT = {"A": 7, "B": 15, "C": 23}
NET_VARDIYA_DK = 450  # 480 dk vardiya − 30 dk mola

RESMI_TATILLER = pd.to_datetime([
    "2025-10-29", "2026-01-01", "2026-03-20", "2026-03-21", "2026-03-22",
    "2026-04-23", "2026-05-01", "2026-05-19", "2026-05-27", "2026-05-28",
    "2026-05-29", "2026-05-30", "2026-07-15", "2026-08-30", "2026-10-29",
    # Tahmin ufku (yaklaşık; Ramazan Bayramı 2027 tarihleri resmi takvimle teyit edilmeli)
    "2027-01-01", "2027-03-09", "2027-03-10", "2027-03-11", "2027-04-23",
])


def calisma_gunu_sayisi(ay_baslangici: pd.Timestamp) -> int:
    """Ayın Pazartesi–Cumartesi, resmi tatil olmayan gün sayısı."""
    gunler = pd.date_range(ay_baslangici, ay_baslangici + pd.offsets.MonthEnd(0), freq="D")
    return int(sum(g.weekday() < 6 and g not in RESMI_TATILLER for g in gunler))

AY_KISA = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
GUN_KISA = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]

# --------------------------------------------------------------------------
# Ana veriler
# --------------------------------------------------------------------------
URUNLER = pd.DataFrame(
    [
        ("P01", "AM-200", "Aks Mili Ø25", "Aks Mili", "Hat-1", 420, 300, 9900),
        ("P02", "AM-250", "Aks Mili Ø30", "Aks Mili", "Hat-1", 520, 370, 7200),
        ("P03", "RB-110", "Rot Başı Standart", "Rot Başı", "Hat-1", 260, 180, 10500),
        ("P04", "RB-140", "Rot Başı Ağır Hizmet", "Rot Başı", "Hat-1", 340, 240, 5550),
        ("P05", "FD-280", "Fren Diski Ø280", "Fren Diski", "Hat-2", 610, 450, 8000),
        ("P06", "FD-320", "Fren Diski Ø320", "Fren Diski", "Hat-2", 780, 570, 5500),
    ],
    columns=["UrunID", "UrunKodu", "Urun", "UrunAilesi", "Hat", "BirimFiyat", "StdMaliyet", "AylikTalep2026"],
)

MAKINELER = pd.DataFrame(
    [
        ("M01", "H1-TST", "Şerit Testere", "Hat-1", "Kesim", 1, 0),
        ("M02", "H1-TRN1", "CNC Torna 1", "Hat-1", "CNC Torna", 2, 0),
        ("M03", "H1-TRN2", "CNC Torna 2", "Hat-1", "CNC Torna", 2, 0),
        ("M04", "H1-FRZ", "CNC İşleme Merkezi", "Hat-1", "CNC Freze", 3, 0),
        ("M05", "H1-ISL", "Endüksiyon Sertleştirme", "Hat-1", "Isıl İşlem", 4, 0),
        ("M06", "H1-TSL", "Silindirik Taşlama", "Hat-1", "Taşlama", 5, 1),
        ("M07", "H2-DTR", "CNC Dik Torna", "Hat-2", "Dik Torna", 1, 0),
        ("M08", "H2-DLK", "CNC Delik Delme", "Hat-2", "Delme", 2, 0),
        ("M09", "H2-BLN", "Balans Makinesi", "Hat-2", "Balans", 3, 1),
    ],
    columns=["MakineID", "MakineKodu", "Makine", "Hat", "Istasyon", "RotaSirasi", "SonIstasyon"],
)

# Makine × ürün ideal çevrim süreleri (saniye/adet)
IDEAL_CEVRIM = {
    "M01": {"P01": 28, "P02": 32, "P03": 24, "P04": 26},
    "M02": {"P01": 60, "P02": 68, "P03": 44, "P04": 52},
    "M03": {"P01": 60, "P02": 68, "P03": 44, "P04": 52},
    "M04": {"P01": 38, "P02": 44, "P03": 30, "P04": 36},
    "M05": {"P01": 34, "P02": 38, "P03": 30, "P04": 30},
    "M06": {"P01": 36, "P02": 40, "P03": 30, "P04": 34},
    "M07": {"P05": 60, "P06": 72},
    "M08": {"P05": 30, "P06": 34},
    "M09": {"P05": 24, "P06": 26},
}

MUSTERILER = pd.DataFrame(
    [
        ("C1", "OEM-Alfa", "OEM", 0.010, "1,4"),
        ("C2", "OEM-Beta", "OEM", 0.008, "0,3"),
        ("C3", "OEM-Gama", "OEM", 0.012, "2"),
        ("C4", "Yedek Parça Dağıtım", "Yedek Parça", 0.0, "3"),
    ],
    columns=["MusteriID", "Musteri", "Segment", "GunlukCezaOrani", "TeslimGunleri"],
)

MUSTERI_URUN_PAYI = {
    "P01": {"C1": 0.75, "C4": 0.25},
    "P02": {"C2": 1.0},
    "P03": {"C1": 0.70, "C4": 0.30},
    "P04": {"C3": 1.0},
    "P05": {"C2": 0.80, "C4": 0.20},
    "P06": {"C3": 1.0},
}

DURUS_NEDENLERI = pd.DataFrame(
    [
        ("D01", "Ürün değişimi (setup)", "Ayar & Değişim", "Hayır"),
        ("D02", "İlk parça onayı / ayar", "Ayar & Değişim", "Hayır"),
        ("D03", "Mekanik arıza", "Arıza", "Hayır"),
        ("D04", "Elektrik/elektronik arıza", "Arıza", "Hayır"),
        ("D05", "Takım kırılması / uç değişimi", "Takım", "Hayır"),
        ("D06", "Malzeme bekleme", "Lojistik", "Hayır"),
        ("D07", "Operatör yok / geç başlama", "Organizasyon", "Hayır"),
        ("D08", "Kalite problemi / ölçüm", "Kalite", "Hayır"),
        ("D09", "Planlı bakım", "Planlı", "Evet"),
    ],
    columns=["NedenID", "Neden", "Kategori", "PlanliMi"],
)

HATA_TURLERI = pd.DataFrame(
    [
        ("Q01", "Ölçü dışı (çap/boy)", "Boyutsal"),
        ("Q02", "Çapak", "Yüzey"),
        ("Q03", "Yüzey hatası (çizik/darbe)", "Yüzey"),
        ("Q04", "Sertlik değeri dışı", "Malzeme/Isıl"),
        ("Q05", "Çatlak", "Malzeme/Isıl"),
        ("Q06", "Salgı / yuvarlaklık", "Boyutsal"),
        ("Q07", "Döküm boşluğu", "Malzeme/Isıl"),
        ("Q08", "Delik pozisyon hatası", "Boyutsal"),
        ("Q09", "Balans dışı", "Fonksiyonel"),
    ],
    columns=["HataID", "HataTuru", "HataGrubu"],
)

# SPC: AM-200 taşlama sonrası çap ölçüsü
SPC_NOMINAL, SPC_LSL, SPC_USL = 25.000, 24.985, 25.015

# Maliyet varsayımları (TL, 2026)
MALIYET = {
    "fazla_mesai_vardiya": 52_000,   # Hat-1 Pazar vardiyası: %50 zamlı işçilik + enerji + gözetim
    "ekspres_nakliye": 9_500,        # 2+ gün gecikmede özel araç (Bursa → OEM fabrikası)
    "ceza_tavan": 0.10,              # sözleşme ceza tavanı (sipariş bedelinin %10'u)
    "stok_tasima_aylik": 0.02,       # stok değeri üzerinden aylık taşıma maliyeti
}
# Bir operasyonda hurdaya çıkan parçanın maliyeti = StdMaliyet × bu oran
OPERASYON_MALIYET_ORANI = {
    "M01": 0.35, "M02": 0.55, "M03": 0.55, "M04": 0.72, "M05": 0.82,
    "M06": 0.95, "M07": 0.60, "M08": 0.80, "M09": 0.95,
}

# --------------------------------------------------------------------------
# Yardımcılar
# --------------------------------------------------------------------------
def urun_bilgisi(urun_id: str, alan: str):
    return URUNLER.set_index("UrunID").at[urun_id, alan]


def ozet_yaz(bolum: str, veri: dict) -> None:
    """Hikâye ve sunum için anahtar sayıları tek bir JSON dosyasında toplar."""
    ozet = {}
    if OZET_DOSYA.exists():
        ozet = json.loads(OZET_DOSYA.read_text(encoding="utf-8"))
    ozet[bolum] = veri
    OZET_DOSYA.write_text(json.dumps(ozet, ensure_ascii=False, indent=2, default=_json_cevir), encoding="utf-8")


def ozet_oku() -> dict:
    return json.loads(OZET_DOSYA.read_text(encoding="utf-8")) if OZET_DOSYA.exists() else {}


def _json_cevir(deger):
    if isinstance(deger, (np.integer,)):
        return int(deger)
    if isinstance(deger, (np.floating,)):
        return float(deger)
    if isinstance(deger, (pd.Timestamp,)):
        return deger.strftime("%Y-%m-%d")
    raise TypeError(type(deger))


def yuzde(x: float, ondalik: int = 1) -> str:
    """0.557 -> '%55,7' (Türkçe yazım)."""
    return "%" + f"{x * 100:.{ondalik}f}".replace(".", ",")


def sayi(x: float, ondalik: int = 0) -> str:
    """1234567.8 -> '1.234.568' (Türkçe binlik ayırıcı)."""
    metin = f"{x:,.{ondalik}f}"
    return metin.replace(",", "X").replace(".", ",").replace("X", ".")


def milyon_tl(x: float, ondalik: int = 1) -> str:
    return sayi(x / 1e6, ondalik) + " M TL"


def ay_etiketi(tarih: pd.Timestamp) -> str:
    return f"{AY_KISA[tarih.month - 1]} {str(tarih.year)[2:]}"
