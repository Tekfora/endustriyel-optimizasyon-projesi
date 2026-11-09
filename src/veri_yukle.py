"""Ham veriyi okuyup analizde kullanılan ortak türev alanları ekler."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ortak import BITIS, MAKINELER, PILOT_BASLANGIC, URUNLER, VERI_HAM


def oku(ad: str, tarih_kolonlari: tuple[str, ...] = ()) -> pd.DataFrame:
    return pd.read_csv(VERI_HAM / f"{ad}.csv", parse_dates=list(tarih_kolonlari))


def donem(tarih: pd.Series) -> np.ndarray:
    return np.where(tarih >= PILOT_BASLANGIC, "Pilot", "Baz")


def yukle() -> dict[str, pd.DataFrame]:
    v = {
        "uretim": oku("uretim", ("Tarih",)),
        "durus": oku("durus", ("Tarih", "BaslangicZamani")),
        "kalite": oku("kalite", ("Tarih",)),
        "olcum": oku("olcum", ("Tarih",)),
        "siparis": oku("siparis", ("SiparisTarihi", "TerminTarihi", "SevkTarihi")),
        "mesai": oku("fazla_mesai", ("Tarih",)),
        "talep": oku("talep_aylik", ("Ay",)),
        "lot": oku("lot", ("Tarih",)),
    }
    makine = MAKINELER.set_index("MakineID")
    for ad in ("uretim", "durus", "kalite", "olcum", "lot"):
        df = v[ad]
        df["Donem"] = donem(df.Tarih)
        df["Ay"] = df.Tarih.dt.to_period("M").dt.to_timestamp()
        df["Hat"] = df.MakineID.map(makine["Hat"])
        df["MakineKodu"] = df.MakineID.map(makine["MakineKodu"])
    s = v["siparis"]
    s["Donem"] = donem(s.TerminTarihi)
    s["Ay"] = s.TerminTarihi.dt.to_period("M").dt.to_timestamp()
    s["Hat"] = s.UrunID.map(URUNLER.set_index("UrunID")["Hat"])
    v["mesai"]["Donem"] = donem(v["mesai"].Tarih)
    v["mesai"]["Ay"] = v["mesai"].Tarih.dt.to_period("M").dt.to_timestamp()
    assert v["uretim"].Tarih.max() <= BITIS
    return v


def oee_tablosu(df: pd.DataFrame, by) -> pd.DataFrame:
    """Toplamlar üzerinden (ağırlıklı) OEE bileşenleri."""
    g = df.groupby(by, observed=True).agg(
        Takvim=("TakvimSuresiDk", "sum"), Planlanan=("PlanlananSureDk", "sum"),
        Calisma=("CalismaSuresiDk", "sum"), Ideal=("IdealSureDk", "sum"),
        Uretilen=("UretilenAdet", "sum"), Saglam=("SaglamAdet", "sum"), Hurda=("HurdaAdet", "sum"))
    g["Kullanilabilirlik"] = g.Calisma / g.Planlanan
    g["Performans"] = g.Ideal / g.Calisma
    g["Kalite"] = g.Saglam / g.Uretilen
    g["OEE"] = g.Kullanilabilirlik * g.Performans * g.Kalite
    g["KapasiteKullanimi"] = g.Planlanan / g.Takvim
    return g
