"""01 — Sentetik fabrika verisinin üretimi (MES + ERP).

Gerçekçi ve tutarlı bir veri seti için vardiya bazında küçük bir akış simülasyonu kullanılır:

* Darboğaz makine (Hat-1: H1-FRZ, Hat-2: H2-DTR) planlamacının lot kararlarıyla sürekli çalışır.
* Önceki istasyonlar onun akışını besler, sonraki istasyonlar çıktısını işler; boş kaldıkları
  süre "iş yok" sayılır ve OEE'nin planlanan süresine girmez (kapasite kullanımında görünür).
* Ayarlar, arızalar, operatör kaynaklı duruşlar, performans ve hurda; makineye, vardiyaya ve
  döneme (baz / pilot) bağlı olasılık dağılımlarından çekilir.
* Hat sonundaki sağlam ürün bitmiş ürün stoğuna girer, siparişler termin sırasıyla sevk edilir.
  Zamanında teslimat, fazla mesai ve cezalar bu dinamikten kendiliğinden ortaya çıkar.

Pilot (Ekim 2026): H1-FRZ'de SMED + önleyici bakım (TPM) + kampanya tipi lot planlama,
Hat-1 gece vardiyasında standart iş ve ısınma prosedürü.

Çıktı: veri/ham/*.csv
"""
from __future__ import annotations

import math
from collections import defaultdict, deque

import numpy as np
import pandas as pd

from ortak import (
    BAZ_BASLANGIC, BITIS, DURUS_NEDENLERI, GECMIS_BASLANGIC, HATA_TURLERI, IDEAL_CEVRIM, MAKINELER,
    MALIYET, MUSTERI_URUN_PAYI, MUSTERILER, NET_VARDIYA_DK, OPERASYON_MALIYET_ORANI, PILOT_BASLANGIC,
    RESMI_TATILLER, SPC_LSL, SPC_NOMINAL, SPC_USL, TOHUM, URUNLER, VARDIYA_BASLANGIC_SAAT, VARDIYALAR,
    VERI_HAM, sayi, yuzde,
)

rng = np.random.default_rng(TOHUM)
URUN = URUNLER.set_index("UrunID")
AILE = URUN["UrunAilesi"].to_dict()

# --------------------------------------------------------------------------
# Davranış parametreleri
# --------------------------------------------------------------------------
# neden: (450 dk'lık dolu vardiya başına beklenen olay sayısı, ortalama süre dk, değişkenlik katsayısı)
GENEL_DURUS = {
    "D03": (0.10, 70, 0.9),
    "D04": (0.05, 50, 0.8),
    "D05": (0.18, 12, 0.5),
    "D06": (0.10, 30, 0.7),
    "D07": (0.08, 20, 0.6),
    "D08": (0.07, 25, 0.7),
}
MAKINE_DURUS = {
    "M01": {"D05": (0.30, 10, 0.5)},
    "M02": {"D03": (0.12, 75, 0.9), "D05": (0.30, 12, 0.5)},
    "M03": {"D03": (0.14, 75, 0.9), "D05": (0.30, 12, 0.5)},
    "M04": {"D03": (0.45, 110, 0.9), "D04": (0.09, 60, 0.8), "D05": (0.45, 15, 0.5),
            "D06": (0.35, 35, 0.7), "D07": (0.10, 22, 0.6), "D08": (0.15, 35, 0.7)},
    "M05": {"D04": (0.10, 55, 0.8), "D08": (0.10, 30, 0.7)},
    "M06": {"D03": (0.12, 80, 0.9), "D05": (0.25, 14, 0.5), "D08": (0.12, 30, 0.7)},
    "M07": {"D03": (0.14, 85, 0.9), "D05": (0.25, 15, 0.5), "D06": (0.15, 35, 0.7)},
    "M08": {"D05": (0.30, 10, 0.5)},
    "M09": {"D04": (0.06, 40, 0.8)},
}
# (aynı aile içi ayar ort. dk, farklı aile ayar ort. dk, cv, ilk parça onayı ort. dk)
SETUP = {
    "M01": (8, 14, 0.4, 5), "M02": (22, 36, 0.45, 10), "M03": (22, 36, 0.45, 10),
    "M04": (56, 86, 0.45, 22), "M05": (12, 20, 0.4, 8), "M06": (24, 38, 0.45, 12),
    "M07": (28, 28, 0.45, 12), "M08": (14, 14, 0.4, 6), "M09": (8, 8, 0.4, 5),
}
PERF = {"M01": 0.92, "M02": 0.88, "M03": 0.88, "M04": 0.84, "M05": 0.93,
        "M06": 0.89, "M07": 0.88, "M08": 0.91, "M09": 0.93}
HURDA = {"M01": 0.004, "M02": 0.010, "M03": 0.010, "M04": 0.018, "M05": 0.008,
         "M06": 0.012, "M07": 0.015, "M08": 0.007, "M09": 0.009}
URUN_HURDA_CARPANI = {"P01": 1.0, "P02": 1.1, "P03": 0.9, "P04": 1.3, "P05": 1.0, "P06": 1.15}
MAKINE_HATA_DAGILIMI = {
    "M01": {"Q01": 0.85, "Q03": 0.15},
    "M02": {"Q01": 0.55, "Q03": 0.25, "Q02": 0.20},
    "M03": {"Q01": 0.55, "Q03": 0.25, "Q02": 0.20},
    "M04": {"Q01": 0.42, "Q02": 0.33, "Q03": 0.17, "Q06": 0.08},
    "M05": {"Q04": 0.70, "Q05": 0.30},
    "M06": {"Q01": 0.45, "Q06": 0.35, "Q03": 0.20},
    "M07": {"Q01": 0.40, "Q07": 0.35, "Q03": 0.25},
    "M08": {"Q08": 0.70, "Q02": 0.30},
    "M09": {"Q09": 1.0},
}
HAT1_MAKINELER = {"M01", "M02", "M03", "M04", "M05", "M06"}

# Aylık talep mevsimselliği (otomotiv: Ağustos ve Ocak düşük, Ekim–Kasım yüksek)
MEVSIM = np.array([0.88, 0.96, 1.05, 1.04, 0.97, 1.04, 0.98, 0.86, 1.02, 1.08, 1.07, 1.01])
MEVSIM = MEVSIM / MEVSIM.mean()


def lognormal(ortalama: float, cv: float) -> float:
    s2 = math.log(1 + cv * cv)
    return float(rng.lognormal(math.log(ortalama) - s2 / 2, math.sqrt(s2)))


def calisma_gunu_mu(tarih: pd.Timestamp) -> bool:
    return tarih.weekday() < 6 and tarih not in RESMI_TATILLER


def parametre(mid: str, vardiya: str, tarih: pd.Timestamp) -> dict:
    pilot = tarih >= PILOT_BASLANGIC
    durus = {k: list(v) for k, v in GENEL_DURUS.items()}
    for k, v in MAKINE_DURUS.get(mid, {}).items():
        durus[k] = list(v)
    gece = vardiya == "C"
    gece_standart = pilot and mid in HAT1_MAKINELER  # pilot: gece vardiyası standart işi
    if gece:
        durus["D07"][0] *= 1.4 if gece_standart else 3.0
        durus["D08"][0] *= 1.2 if gece_standart else 1.6
        durus["D03"][0] *= 1.1
    if tarih.weekday() == 0 and vardiya == "A":  # Pazar duruşu sonrası soğuk başlangıç
        durus["D03"][0] *= 1.0 if (pilot and mid == "M04") else 1.6
    s_ayni, s_farkli, s_cv, onay = SETUP[mid]
    perf = PERF[mid] + {"A": 0.01, "B": 0.0, "C": (-0.02 if gece_standart else -0.06)}[vardiya]
    hurda = HURDA[mid] * ((1.12 if gece_standart else 1.45) if gece else 1.0)
    planli_bakim = 0
    if pilot and mid == "M04":  # SMED + TPM + ilk parça ölçümünün makinede yapılması
        perf += 0.02  # TPM ile iş mili titreşimi giderildi, nominal ilerleme hızına dönüldü
        s_ayni, s_farkli, onay = s_ayni * 0.50, s_farkli * 0.48, onay * 0.45
        durus["D03"][0] *= 0.45
        durus["D03"][1] *= 0.80
        durus["D05"][0] *= 0.70
        durus["D08"][0] *= 0.70
        hurda *= 0.85
        if tarih.weekday() == 0 and vardiya == "A":
            planli_bakim = 90
    return {"durus": durus, "setup": (s_ayni, s_farkli, s_cv, onay), "perf": perf,
            "hurda": hurda, "planli_bakim": planli_bakim}


# --------------------------------------------------------------------------
# 1) ERP: aylık talep geçmişi (3 yıl) ve sipariş satırları (son 13 ay)
# --------------------------------------------------------------------------
def aylik_talep_uret() -> pd.DataFrame:
    aylar = pd.date_range(GECMIS_BASLANGIC, BITIS, freq="MS")
    satirlar = []
    for u in URUNLER.itertuples():
        for ay in aylar:
            k = (ay.year - 2026) * 12 + (ay.month - 1)
            seviye = u.AylikTalep2026 * (1.0045 ** k) * MEVSIM[ay.month - 1]
            if u.UrunID == "P04" and ay < pd.Timestamp("2025-03-01"):
                seviye *= 0.84  # OEM-Gama'nın yeni modeli öncesi
            talep = seviye * (1 + rng.normal(0, 0.045))
            satirlar.append((ay, u.UrunID, int(round(talep / 50) * 50)))
    return pd.DataFrame(satirlar, columns=["Ay", "UrunID", "Talep"])


def teslim_gunleri(ay: pd.Timestamp, gunler: list[int]) -> list[pd.Timestamp]:
    sonuc = []
    for g in pd.date_range(ay, ay + pd.offsets.MonthEnd(0), freq="D"):
        if g.weekday() in gunler:
            d = g
            while not calisma_gunu_mu(d):
                d -= pd.Timedelta(days=1)
            if d >= ay:
                sonuc.append(d)
    return sorted(set(sonuc))


def siparis_uret(talep: pd.DataFrame) -> pd.DataFrame:
    musteri = MUSTERILER.set_index("MusteriID")
    detay = talep[talep.Ay >= BAZ_BASLANGIC]
    satirlar = []
    for r in detay.itertuples():
        for mid, pay in MUSTERI_URUN_PAYI[r.UrunID].items():
            gunler = teslim_gunleri(r.Ay, [int(x) for x in musteri.at[mid, "TeslimGunleri"].split(",")])
            ortalama = r.Talep * pay / len(gunler)
            for termin in gunler:
                adet = max(50, int(round(ortalama * rng.lognormal(-0.0072, 0.12) / 50) * 50))
                siparis_tarihi = termin - pd.Timedelta(days=int(rng.integers(10, 22)))
                satirlar.append({"MusteriID": mid, "UrunID": r.UrunID, "SiparisTarihi": siparis_tarihi,
                                 "TerminTarihi": termin, "Adet": adet})
    df = pd.DataFrame(satirlar).sort_values(["TerminTarihi", "MusteriID", "UrunID"]).reset_index(drop=True)
    df.insert(0, "SiparisNo", [f"SP-{i:05d}" for i in range(10001, 10001 + len(df))])
    df["BirimFiyat"] = df.UrunID.map(URUN["BirimFiyat"])
    df["Tutar"] = df.Adet * df.BirimFiyat
    return df


# --------------------------------------------------------------------------
# 2) MES: vardiya bazlı akış simülasyonu
# --------------------------------------------------------------------------
class MakineDurumu:
    def __init__(self, mid: str):
        self.mid = mid
        self.urun: str | None = None          # makinenin şu an ayarlı olduğu ürün
        self.aktif_is: list | None = None     # [urun, kalan adet]
        self.devreden: tuple | None = None    # vardiya sonunda bitmemiş duruş (neden, kalan dk)
        self.kuyruk: deque = deque()          # darboğaz dışı makinelerde bekleyen iş


class Kayitlar:
    def __init__(self):
        self.uretim, self.durus, self.kalite, self.olcum, self.lot, self.mesai = [], [], [], [], [], []


KAYIT = Kayitlar()


def vardiya_calistir(md: MakineDurumu, tarih, vardiya, is_kaynagi, darbogaz: bool):
    """Bir makinenin tek vardiyasını dakika bazında yürütür."""
    p = parametre(md.mid, vardiya, tarih)
    T = NET_VARDIYA_DK
    olaylar: list[tuple] = []
    uretim = defaultdict(lambda: [0.0, 0.0])  # urun -> [çalışma dk, üretilen adet]
    t = 0.0

    def durus_ekle(neden: str, sure: float) -> None:
        nonlocal t
        d = min(sure, T - t)
        if d > 0.05:
            olaylar.append((neden, t, d, md.urun))
        t += d
        md.devreden = (neden, sure - d) if sure - d > 0.05 else None

    if p["planli_bakim"]:
        olaylar.append(("D09", 0.0, float(p["planli_bakim"]), md.urun))
        t = float(p["planli_bakim"])

    # İş yoksa darboğaz dışı makine boş kalır; devreden duruş boşta tamamlanmış sayılır.
    is_var = darbogaz or (md.aktif_is and md.aktif_is[1] > 0.5) or len(md.kuyruk) > 0
    if md.devreden and is_var:
        neden, kalan = md.devreden
        durus_ekle(neden, kalan)
    elif not is_var:
        md.devreden = None

    perf = float(np.clip(rng.normal(p["perf"], 0.03), 0.6, 0.99))
    oranlar = {k: v[0] for k, v in p["durus"].items()}
    toplam_oran = sum(oranlar.values()) / T
    nedenler, agirlik = list(oranlar), np.array(list(oranlar.values())) / sum(oranlar.values())

    while t < T - 1e-6:
        if md.aktif_is is None or md.aktif_is[1] <= 0.5:
            yeni = is_kaynagi()
            if yeni is None:
                break  # iş yok
            urun, adet = yeni
            if md.urun != urun:
                s_ayni, s_farkli, s_cv, onay = p["setup"]
                ayni_aile = md.urun is not None and AILE[md.urun] == AILE[urun]
                md.urun = urun
                durus_ekle("D01", lognormal(s_ayni if ayni_aile else s_farkli, s_cv))
                if md.devreden is None and t < T - 1e-6:
                    durus_ekle("D02", lognormal(onay, 0.5))
            md.aktif_is = [urun, float(adet)]
            if t >= T - 1e-6:
                break
        urun, kalan = md.aktif_is
        hiz = 60.0 * perf / IDEAL_CEVRIM[md.mid][urun]  # adet/dk
        t_bitis = kalan / hiz
        t_ariza = rng.exponential(1 / toplam_oran)
        dt = min(t_bitis, t_ariza, T - t)
        uretim[urun][0] += dt
        uretim[urun][1] += dt * hiz
        md.aktif_is[1] -= dt * hiz
        t += dt
        if dt == t_ariza and t < T - 1e-6:
            neden = str(rng.choice(nedenler, p=agirlik))
            ort, cv = p["durus"][neden][1], p["durus"][neden][2]
            durus_ekle(neden, lognormal(ort, cv))

    mesgul = min(t, T)
    return uretim, olaylar, mesgul, perf, p


def kaydet(md, tarih, vardiya, uretim, olaylar, mesgul, perf, p, fazla_mesai) -> dict:
    """Vardiya sonucunu üretim/duruş/kalite kayıtlarına yazar; ürün bazında sağlam adedi döndürür."""
    planli_bakim = sum(o[2] for o in olaylar if o[0] == "D09")
    planlanan = max(mesgul - planli_bakim, 0.0)
    if not uretim:
        uretim = {md.urun or next(iter(IDEAL_CEVRIM[md.mid])): [0.0, 0.0]}
    toplam_calisma = sum(v[0] for v in uretim.values())
    vardiya_bas = tarih + pd.Timedelta(hours=VARDIYA_BASLANGIC_SAAT[vardiya])
    for neden, bas, sure, urun in olaylar:
        KAYIT.durus.append((tarih, vardiya, md.mid, urun or next(iter(IDEAL_CEVRIM[md.mid])), neden,
                            vardiya_bas + pd.Timedelta(minutes=round(bas)), round(sure, 1), fazla_mesai))
    saglam_cikti = {}
    for urun, (calisma, adet) in uretim.items():
        pay = calisma / toplam_calisma if toplam_calisma > 0 else 1 / len(uretim)
        uretilen = int(adet)
        hurda = int(rng.binomial(uretilen, min(p["hurda"] * URUN_HURDA_CARPANI[urun], 0.5))) if uretilen else 0
        saglam = uretilen - hurda
        ideal = IDEAL_CEVRIM[md.mid][urun]
        hurda_maliyet = hurda * URUN.at[urun, "StdMaliyet"] * OPERASYON_MALIYET_ORANI[md.mid]
        KAYIT.uretim.append((tarih, vardiya, md.mid, urun, fazla_mesai, round(NET_VARDIYA_DK * pay, 2),
                             round(planlanan * pay, 2), round(calisma, 2), ideal, uretilen, saglam, hurda,
                             round(uretilen * ideal / 60, 2), round(hurda_maliyet, 2)))
        if hurda:
            dagilim = MAKINE_HATA_DAGILIMI[md.mid]
            adetler = rng.multinomial(hurda, list(dagilim.values()))
            for hata, n in zip(dagilim, adetler):
                if n:
                    KAYIT.kalite.append((tarih, vardiya, md.mid, urun, hata, int(n)))
        saglam_cikti[urun] = saglam
    return saglam_cikti


def spc_olcumleri(tarih, vardiya, adet: int) -> None:
    """AM-200 çap ölçüleri: vardiyada 4 alt grup × 5 parça (taşlama çıkışı)."""
    pilot = tarih >= PILOT_BASLANGIC
    kayma = {"A": 0.0, "B": 0.0010, "C": 0.0012 if pilot else 0.0055}[vardiya]
    sigma = 0.0033 if pilot else 0.0036
    vardiya_ort = SPC_NOMINAL + kayma + rng.normal(0, 0.0010)
    for alt in range(1, min(4, max(1, adet // 100)) + 1):
        alt_ort = vardiya_ort + rng.normal(0, 0.0007)
        for no in range(1, 6):
            KAYIT.olcum.append((tarih, vardiya, "M06", "P01", alt, no, round(alt_ort + rng.normal(0, sigma), 4)))


class Hat:
    def __init__(self, ad, darbogaz, yukari, asagi, urunler, kampanya_sirasi, her_zaman_kampanya):
        self.ad, self.urunler = ad, urunler
        self.md = {m: MakineDurumu(m) for m in [*yukari, darbogaz, *asagi]}
        self.pm, self.yukari, self.asagi = self.md[darbogaz], yukari, asagi
        self.kampanya_sirasi, self.kampanya_idx = kampanya_sirasi, -1
        self.her_zaman_kampanya = her_zaman_kampanya
        self.fg = {u: 0.0 for u in urunler}
        self.acik: dict[str, list] = {u: [] for u in urunler}
        self.sevk: list[dict] = []
        self.gunluk_cikis: list[float] = []
        self._bugun_cikis = 0.0
        self.kesilen_lot = 0

    # ---- planlama yardımcıları ----
    def hat_ici(self, urun) -> float:
        toplam = 0.0
        for m in self.asagi:
            md = self.md[m]
            toplam += sum(a for u, a in md.kuyruk if u == urun)
            if md.aktif_is and md.aktif_is[0] == urun:
                toplam += md.aktif_is[1]
        return toplam

    def lot_kalan(self, urun) -> float:
        a = self.pm.aktif_is
        return a[1] if a and a[0] == urun and a[1] > 0 else 0.0

    def net_ihtiyac(self, urun, tarih, gun) -> float:
        son = tarih + pd.Timedelta(days=gun)
        acik = sum(o["Adet"] for o in self.acik[urun] if o["TerminTarihi"] <= son)
        return acik - self.fg[urun] - self.hat_ici(urun) - self.lot_kalan(urun)

    def ilk_karsilanmayan_termin(self, urun):
        stok = self.fg[urun] + self.hat_ici(urun) + self.lot_kalan(urun)
        kum = 0
        for o in self.acik[urun]:
            kum += o["Adet"]
            if kum > stok:
                return o["TerminTarihi"]
        return None

    def sonraki_lot(self, tarih):
        """Sıradaki lotu seçer. Bitmiş ürün deposu sınırlı olduğundan (JIT tedarik) en fazla
        birkaç günlük ihtiyaç için üretilir; ihtiyaç yoksa None döner ve makine boş kalır."""
        kampanya = self.her_zaman_kampanya or tarih >= PILOT_BASLANGIC
        if max(self.net_ihtiyac(u, tarih, 7 if kampanya else 5) for u in self.urunler) <= 0:
            return None
        if kampanya:
            sira = self.kampanya_sirasi
            for ufuk in (5, 7):
                for k in range(len(sira)):
                    idx = (self.kampanya_idx + 1 + k) % len(sira)
                    ihtiyac = self.net_ihtiyac(sira[idx], tarih, ufuk)
                    if ihtiyac > 0:
                        self.kampanya_idx = idx
                        return sira[idx], int(math.ceil(np.clip(ihtiyac, 900, 2400) / 100) * 100)
            return None
        # Baz dönem: "yangın söndürme" — en acil siparişin ürününe küçük lot
        adaylar = []
        for u in self.urunler:
            termin = self.ilk_karsilanmayan_termin(u)
            if termin is not None and termin <= tarih + pd.Timedelta(days=4):
                adaylar.append((termin, u))
        if adaylar:
            _, u = min(adaylar)
            return u, int(math.ceil(np.clip(self.net_ihtiyac(u, tarih, 2), 250, 550) / 50) * 50)
        u = max(self.urunler, key=lambda x: self.net_ihtiyac(x, tarih, 5))
        return u, 400

    def acil_degisim_kontrolu(self, tarih) -> None:
        """Baz dönem: vardiya başında vardiya amiri en acil siparişe bakar; başka bir ürünün
        termini daha yakınsa yarım kalan lot kesilir ve makine o ürüne çevrilir."""
        if self.her_zaman_kampanya or tarih >= PILOT_BASLANGIC:
            return
        a = self.pm.aktif_is
        if not a or a[1] <= 0.5:
            return
        mevcut = self.ilk_karsilanmayan_termin(a[0]) or tarih + pd.Timedelta(days=30)
        terminler = [(self.ilk_karsilanmayan_termin(u), u) for u in self.urunler if u != a[0]]
        terminler = [(t, u) for t, u in terminler if t is not None]
        if terminler:
            en_acil, _ = min(terminler)
            if en_acil < mevcut and en_acil <= tarih + pd.Timedelta(days=3):
                self.pm.aktif_is = None
                self.kesilen_lot += 1

    # ---- vardiya ----
    def vardiya(self, tarih, vardiya, fazla_mesai: int) -> None:
        self.acil_degisim_kontrolu(tarih)

        def pm_kaynak():
            secim = self.sonraki_lot(tarih)
            if secim is None:
                return None
            urun, adet = secim
            KAYIT.lot.append((tarih, vardiya, self.pm.mid, urun, adet,
                              "Kampanya" if (self.her_zaman_kampanya or tarih >= PILOT_BASLANGIC) else "Acil"))
            return urun, adet

        sonuc = vardiya_calistir(self.pm, tarih, vardiya, pm_kaynak, darbogaz=True)
        saglam = kaydet(self.pm, tarih, vardiya, *sonuc, fazla_mesai)
        uretilen = {u: v[1] for u, v in sonuc[0].items()}

        # Önceki istasyonlar: darboğazın tükettiği malzemeyi (fire payıyla) hazırlar
        if self.yukari:
            kalemler = [(u, a * rng.uniform(1.0, 1.06)) for u, a in uretilen.items() if a > 1]
            for m in self.yukari:
                if m in ("M02", "M03"):
                    continue
                for u, a in kalemler:
                    self.md[m].kuyruk.append((u, a))
            tornalar = [m for m in self.yukari if m in ("M02", "M03")]
            if tornalar:
                if len(kalemler) == 1:
                    u, a = kalemler[0]
                    for m in tornalar:
                        self.md[m].kuyruk.append((u, a / 2))
                else:  # iş yükü en az olan tornaya ata
                    def yuk(m):
                        md = self.md[m]
                        bekleyen = sum(a * IDEAL_CEVRIM[m][u] for u, a in md.kuyruk)
                        return bekleyen + (md.aktif_is[1] * IDEAL_CEVRIM[m][md.aktif_is[0]] if md.aktif_is else 0)
                    for u, a in kalemler:
                        self.md[min(tornalar, key=yuk)].kuyruk.append((u, a))
            for m in self.yukari:
                md = self.md[m]
                sonuc_m = vardiya_calistir(md, tarih, vardiya, lambda md=md: md.kuyruk.popleft() if md.kuyruk else None,
                                           darbogaz=False)
                kaydet(md, tarih, vardiya, *sonuc_m, fazla_mesai)

        # Sonraki istasyonlar: sağlam çıktıyı sırayla işler; son istasyon bitmiş ürün stoğunu besler
        akis = saglam
        for m in self.asagi:
            md = self.md[m]
            for u, a in akis.items():
                if a > 0:
                    md.kuyruk.append((u, float(a)))
            sonuc_m = vardiya_calistir(md, tarih, vardiya, lambda md=md: md.kuyruk.popleft() if md.kuyruk else None,
                                       darbogaz=False)
            akis = kaydet(md, tarih, vardiya, *sonuc_m, fazla_mesai)
            if m == "M06" and akis.get("P01", 0) > 0:
                spc_olcumleri(tarih, vardiya, akis["P01"])
        for u, a in akis.items():
            self.fg[u] += a
            self._bugun_cikis += a

    def gun_sonu(self, tarih, calisma: bool) -> None:
        if calisma:
            self.gunluk_cikis.append(self._bugun_cikis)
            self._bugun_cikis = 0.0
            for u in self.urunler:
                kalan, engel = [], False
                for o in self.acik[u]:
                    if not engel and (o["TerminTarihi"] - tarih).days <= 3 and self.fg[u] >= o["Adet"]:
                        self.fg[u] -= o["Adet"]
                        o["SevkTarihi"] = tarih
                        self.sevk.append(o)
                    else:
                        engel = True
                        kalan.append(o)
                self.acik[u] = kalan

    def mesai_gerekli(self, tarih) -> bool:
        """Cumartesi akşamı planlama toplantısı: önümüzdeki haftanın açığı normal kapasiteyi
        aşıyorsa ya da termini geçmiş sipariş varsa Pazar günü 2 vardiya fazla mesai yazılır."""
        eksik = sum(max(0.0, self.net_ihtiyac(u, tarih, 8)) for u in self.urunler)
        gecmis = sum(o["Adet"] for u in self.urunler for o in self.acik[u] if o["TerminTarihi"] <= tarih)
        sonraki_hafta = pd.date_range(tarih + pd.Timedelta(days=2), periods=6, freq="D")
        is_gunu = sum(calisma_gunu_mu(g) for g in sonraki_hafta)
        kapasite = np.mean(self.gunluk_cikis[-10:]) * is_gunu if self.gunluk_cikis else np.inf
        if gecmis > 2500:
            return 3  # kriz: Pazar günü üç vardiya
        return 2 if (eksik > 0.92 * kapasite or gecmis > 400) else 0


def simulasyonu_calistir(siparis: pd.DataFrame, talep: pd.DataFrame):
    hat1 = Hat("Hat-1", "M04", ["M01", "M02", "M03"], ["M05", "M06"], ["P01", "P02", "P03", "P04"],
               ["P01", "P02", "P04", "P03"], her_zaman_kampanya=False)
    hat2 = Hat("Hat-2", "M07", [], ["M08", "M09"], ["P05", "P06"], ["P05", "P06"], her_zaman_kampanya=True)
    hatlar = {"Hat-1": hat1, "Hat-2": hat2}
    urun_hat = URUN["Hat"].to_dict()

    # Başlangıç bitmiş ürün stoğu: ~2 günlük talep
    ilk_ay = talep[talep.Ay == BAZ_BASLANGIC].set_index("UrunID")["Talep"]
    for u, t in ilk_ay.items():
        hatlar[urun_hat[u]].fg[u] = round(t / 26 * 2 / 50) * 50

    bekleyen = siparis.sort_values("SiparisTarihi").to_dict("records")
    sira = 0
    mesai_gunleri: dict[pd.Timestamp, int] = {}
    for tarih in pd.date_range(BAZ_BASLANGIC, BITIS, freq="D"):
        while sira < len(bekleyen) and bekleyen[sira]["SiparisTarihi"] <= tarih:
            o = dict(bekleyen[sira])
            o["SevkTarihi"] = pd.NaT
            hatlar[urun_hat[o["UrunID"]]].acik[o["UrunID"]].append(o)
            sira += 1
        for h in hatlar.values():
            for u in h.urunler:
                h.acik[u].sort(key=lambda o: (o["TerminTarihi"], o["SiparisNo"]))

        calisma = calisma_gunu_mu(tarih)
        mesai_vardiya = mesai_gunleri.get(tarih, 0)
        for vardiya in VARDIYALAR:
            if calisma:
                hat1.vardiya(tarih, vardiya, 0)
                hat2.vardiya(tarih, vardiya, 0)
            elif VARDIYALAR.index(vardiya) < mesai_vardiya:
                hat1.vardiya(tarih, vardiya, 1)
        if mesai_vardiya:
            KAYIT.mesai.append((tarih, "Hat-1", mesai_vardiya, 8 * mesai_vardiya,
                                mesai_vardiya * MALIYET["fazla_mesai_vardiya"]))
        for h in hatlar.values():
            h.gun_sonu(tarih, calisma)
        if tarih.weekday() == 5:
            pazar = tarih + pd.Timedelta(days=1)
            if pazar not in RESMI_TATILLER and pazar <= BITIS:
                karar = hat1.mesai_gerekli(tarih)
                if karar:
                    mesai_gunleri[pazar] = karar
    return hatlar


# --------------------------------------------------------------------------
# 3) Tabloları oluştur ve kaydet
# --------------------------------------------------------------------------
def main() -> None:
    talep = aylik_talep_uret()
    siparis = siparis_uret(talep)
    hatlar = simulasyonu_calistir(siparis, talep)

    uretim = pd.DataFrame(KAYIT.uretim, columns=[
        "Tarih", "VardiyaID", "MakineID", "UrunID", "FazlaMesai", "TakvimSuresiDk", "PlanlananSureDk",
        "CalismaSuresiDk", "IdealCevrimSn", "UretilenAdet", "SaglamAdet", "HurdaAdet", "IdealSureDk",
        "HurdaMaliyetiTL"])
    durus = pd.DataFrame(KAYIT.durus, columns=["Tarih", "VardiyaID", "MakineID", "UrunID", "NedenID",
                                               "BaslangicZamani", "SureDk", "FazlaMesai"])
    kalite = pd.DataFrame(KAYIT.kalite, columns=["Tarih", "VardiyaID", "MakineID", "UrunID", "HataID", "Adet"])
    olcum = pd.DataFrame(KAYIT.olcum, columns=["Tarih", "VardiyaID", "MakineID", "UrunID", "AltGrupNo",
                                               "OlcumNo", "CapMm"])
    olcum["Nominal"], olcum["LSL"], olcum["USL"] = SPC_NOMINAL, SPC_LSL, SPC_USL
    lotlar = pd.DataFrame(KAYIT.lot, columns=["Tarih", "VardiyaID", "MakineID", "UrunID", "LotAdet", "Politika"])
    mesai = pd.DataFrame(KAYIT.mesai, columns=["Tarih", "Hat", "VardiyaSayisi", "Saat", "MaliyetTL"])

    # Sipariş sonuçları
    sevk = {o["SiparisNo"]: o["SevkTarihi"] for h in hatlar.values() for o in h.sevk}
    siparis["SevkTarihi"] = siparis.SiparisNo.map(sevk)
    acik_mi = siparis.SevkTarihi.isna()
    gecikme = (siparis.SevkTarihi - siparis.TerminTarihi).dt.days.clip(lower=0)
    gecikme[acik_mi] = (BITIS - siparis.TerminTarihi[acik_mi]).dt.days + 1
    siparis["GecikmeGun"] = gecikme.astype(int)
    siparis["ZamanindaMi"] = (siparis.GecikmeGun == 0).astype(int)
    siparis["Durum"] = np.where(acik_mi, "Açık (gecikmede)", "Sevk edildi")
    oran = siparis.MusteriID.map(MUSTERILER.set_index("MusteriID")["GunlukCezaOrani"])
    siparis["CezaTutariTL"] = (siparis.Tutar * np.minimum(MALIYET["ceza_tavan"], oran * siparis.GecikmeGun)).round(2)
    siparis["EkspresNakliyeTL"] = np.where(siparis.GecikmeGun >= 2, MALIYET["ekspres_nakliye"], 0)

    durus.insert(0, "DurusID", range(1, len(durus) + 1))
    uretim.insert(0, "UretimID", range(1, len(uretim) + 1))
    kalite.insert(0, "KaliteID", range(1, len(kalite) + 1))
    olcum.insert(0, "OlcumID", range(1, len(olcum) + 1))

    tablolar = {"talep_aylik": talep, "siparis": siparis, "uretim": uretim, "durus": durus,
                "kalite": kalite, "olcum": olcum, "lot": lotlar, "fazla_mesai": mesai,
                "makine": MAKINELER, "urun": URUNLER, "musteri": MUSTERILER,
                "durus_nedeni": DURUS_NEDENLERI, "hata_turu": HATA_TURLERI}
    for ad, df in tablolar.items():
        df.to_csv(VERI_HAM / f"{ad}.csv", index=False, encoding="utf-8")

    _kontrol_ozeti(uretim, durus, siparis, mesai, olcum, lotlar, hatlar)


def _oee(df: pd.DataFrame) -> pd.Series:
    a = df.CalismaSuresiDk.sum() / df.PlanlananSureDk.sum()
    p = df.IdealSureDk.sum() / df.CalismaSuresiDk.sum()
    q = df.SaglamAdet.sum() / df.UretilenAdet.sum()
    return pd.Series({"A": a, "P": p, "Q": q, "OEE": a * p * q,
                      "Kullanim": df.PlanlananSureDk.sum() / df.TakvimSuresiDk.sum()})


def _kontrol_ozeti(uretim, durus, siparis, mesai, olcum, lotlar, hatlar) -> None:
    uretim["Donem"] = np.where(uretim.Tarih >= PILOT_BASLANGIC, "Pilot", "Baz")
    tablo = uretim.groupby(["MakineID", "Donem"]).apply(_oee, include_groups=False).unstack("Donem")
    print("\nMakine bazında OEE (Baz / Pilot):")
    print(tablo.round(3).to_string())
    siparis["Donem"] = np.where(siparis.TerminTarihi >= PILOT_BASLANGIC, "Pilot", "Baz")
    print("\nZamanında teslimat:", siparis.groupby("Donem").ZamanindaMi.mean().round(3).to_dict())
    siparis["Hat"] = siparis.UrunID.map(URUN["Hat"])
    print("Hat bazında OTD:", siparis.groupby(["Hat", "Donem"]).ZamanindaMi.mean().round(3).to_dict())
    pazarlar = pd.date_range(BAZ_BASLANGIC, BITIS, freq="W-SUN")
    mesai["Donem"] = np.where(mesai.Tarih >= PILOT_BASLANGIC, "Pilot", "Baz")
    print("Fazla mesai Pazarları:", mesai.groupby("Donem").size().to_dict(), "/", len(pazarlar))
    frz = durus[durus.MakineID == "M04"].copy()
    frz["Donem"] = np.where(frz.Tarih >= PILOT_BASLANGIC, "Pilot", "Baz")
    vardiya_sayisi = uretim[uretim.MakineID == "M04"].groupby("Donem").apply(
        lambda d: d[["Tarih", "VardiyaID"]].drop_duplicates().shape[0], include_groups=False)
    setup = frz[frz.NedenID == "D01"].groupby("Donem").SureDk.agg(["count", "mean"])
    setup["vardiya_basina"] = setup["count"] / vardiya_sayisi
    print("\nH1-FRZ setup:\n", setup.round(2).to_string())
    pay = frz[frz.Donem == "Baz"].groupby("NedenID").SureDk.sum()
    print("H1-FRZ baz duruş payı:", (pay / pay.sum()).round(3).to_dict())
    gece = olcum.assign(Donem=np.where(olcum.Tarih >= PILOT_BASLANGIC, "Pilot", "Baz"))
    for donem, g in gece.groupby("Donem"):
        mu, s = g.CapMm.mean(), g.CapMm.std()
        print(f"SPC {donem}: n={len(g)} ort={mu:.4f} s={s:.4f} Ppk={min(SPC_USL - mu, mu - SPC_LSL) / (3 * s):.2f}")
    print("Kesilen lot (acil değişim):", hatlar["Hat-1"].kesilen_lot)
    print("Lot ort. büyüklük:", lotlar.groupby(["MakineID", "Politika"]).LotAdet.mean().round(0).to_dict())
    print("Sevk edilmeyen sipariş:", int(siparis.SevkTarihi.isna().sum()),
          "| Ceza:", sayi(siparis.CezaTutariTL.sum()), "TL | Ekspres:", sayi(siparis.EkspresNakliyeTL.sum()), "TL")
    print("Hurda maliyeti:", sayi(uretim.HurdaMaliyetiTL.sum()), "TL | Fazla mesai:", sayi(mesai.MaliyetTL.sum()), "TL")
    print("Kayıt sayıları: üretim", len(uretim), "| duruş", len(durus), "| sipariş", len(siparis),
          "| ölçüm", len(olcum), "| Baz OTD", yuzde(siparis[siparis.Donem == "Baz"].ZamanindaMi.mean()))


if __name__ == "__main__":
    main()
