"""Tüm grafiklerin ortak görsel dili.

Renkler, doğrulanmış bir kategorik paletten (renk körlüğüne dayanıklı sıra),
ayrılmış durum renklerinden (iyi/uyarı/kritik) ve tek tonlu mavi rampadan gelir.
Kurallar: tek y-ekseni, ince işaretler, seçici etiket, sessiz ızgara.
"""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from ortak import GRAFIK, sayi  # noqa: E402

# SUNUM=1 ortam değişkeniyle çalıştırılınca grafikler slayt için üretilir:
# başlık ve kaynak notu çizilmez (slayt taşır), figür %80 boyutta → yazılar görece büyür.
SUNUM = os.environ.get("SUNUM") == "1"
if SUNUM:
    _subplots, _figure = plt.subplots, plt.figure

    def _olcekle(k: dict) -> dict:
        if k.get("figsize"):
            k["figsize"] = (k["figsize"][0] * 0.8, k["figsize"][1] * 0.8)
        return k

    plt.subplots = lambda *a, **k: _subplots(*a, **_olcekle(k))
    plt.figure = lambda *a, **k: _figure(*a, **_olcekle(k))

SERI = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
MAVI, TURUNCU, SU_YESILI, SARI = SERI[0], SERI[1], SERI[2], SERI[3]
GRI_SERI = "#aeaca3"          # vurgulanmayan seriler
DURUM = {"iyi": "#0ca30c", "uyari": "#fab219", "ciddi": "#ec835a", "kritik": "#d03b3b"}
YUZEY = "#fcfcfb"
MUREKKEP = "#0b0b0b"
IKINCIL = "#52514e"
SOLUK = "#898781"
IZGARA = "#e1e0d9"
EKSEN = "#c3c2b7"
BASARI_METIN = "#006300"
MAVI_RAMPA = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5",
              "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]

# Varlıkların sabit renkleri (renk varlığı izler, sırası değil)
HAT_RENK = {"Hat-1": MAVI, "Hat-2": SU_YESILI}
DARBOGAZ_RENK = TURUNCU
GOLGE = "#f0efec"             # pilot dönemi gölgesi
YAZI_TIPI = ["Segoe UI", "DejaVu Sans"]


def stil_uygula() -> None:
    plt.rcParams.update({
        "font.family": YAZI_TIPI,
        "font.size": 10,
        "figure.facecolor": YUZEY,
        "axes.facecolor": YUZEY,
        "savefig.facecolor": YUZEY,
        "axes.edgecolor": EKSEN,
        "axes.linewidth": 0.8,
        "axes.labelcolor": IKINCIL,
        "axes.labelsize": 10,
        "axes.titlesize": 13,
        "axes.titleweight": "semibold",
        "axes.titlecolor": MUREKKEP,
        "axes.titlelocation": "left",
        "axes.titlepad": 12,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "axes.axisbelow": True,
        "grid.color": IZGARA,
        "grid.linewidth": 0.8,
        "grid.linestyle": "-",
        "xtick.color": SOLUK,
        "ytick.color": SOLUK,
        "xtick.labelcolor": IKINCIL,
        "ytick.labelcolor": IKINCIL,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "ytick.left": False,
        "legend.frameon": False,
        "legend.fontsize": 9,
        "legend.labelcolor": IKINCIL,
        "lines.linewidth": 2,
        "lines.markersize": 6,
        "patch.linewidth": 0,
    })


def baslik(ax, ana: str, alt: str | None = None) -> None:
    """Sol hizalı eylem başlığı + gri alt başlık (alt başlık başlığın altında)."""
    if SUNUM:
        return
    ax.set_title(ana, loc="left", pad=26 if alt else 12)
    if alt:
        ax.text(0, 1.02, alt, transform=ax.transAxes, ha="left", va="bottom", fontsize=9.5, color=IKINCIL)


def ust_baslik(fig, ana: str, alt: str | None = None, y_ana: float = 1.02, y_alt: float = 0.955) -> None:
    """Çok panelli figürler için figür düzeyinde başlık (sunum modunda çizilmez)."""
    if SUNUM:
        return
    fig.suptitle(ana, x=0.01, ha="left", fontsize=13, fontweight="semibold", color=MUREKKEP, y=y_ana)
    if alt:
        fig.text(0.01, y_alt, alt, fontsize=9.5, color=IKINCIL, ha="left")


def yuzde_ekseni(ax, eksen: str = "y", ondalik: int = 0) -> None:
    fmt = FuncFormatter(lambda v, _: "%" + f"{v * 100:.{ondalik}f}".replace(".", ","))
    (ax.yaxis if eksen == "y" else ax.xaxis).set_major_formatter(fmt)


def sayi_ekseni(ax, eksen: str = "y", bolen: float = 1, sonek: str = "") -> None:
    fmt = FuncFormatter(lambda v, _: sayi(v / bolen) + sonek)
    (ax.yaxis if eksen == "y" else ax.xaxis).set_major_formatter(fmt)


def kaynak_notu(fig, metin: str = "Kaynak: Demirkanat MES/ERP (sentetik veri) · Analiz: Python") -> None:
    """Kaynak notu kaydederken en alttaki öğenin (eksen etiketleri dahil) altına yerleştirilir."""
    if not SUNUM:
        fig._kaynak_metni = metin


def kaydet(fig, dosya_adi: str) -> str:
    metin = getattr(fig, "_kaynak_metni", None)
    if metin:
        fig.canvas.draw()
        kutu = fig.get_tightbbox(fig.canvas.get_renderer())  # inç cinsinden
        y = (kutu.y0 - 0.08) / fig.get_figheight()
        x = max(kutu.x0, 0) / fig.get_figwidth()
        fig.text(x, y, metin, ha="left", va="top", fontsize=7.5, color=SOLUK)
    hedef = GRAFIK / "sunum" if SUNUM else GRAFIK
    hedef.mkdir(exist_ok=True)
    yol = hedef / dosya_adi
    fig.savefig(yol, dpi=200 if SUNUM else 180, bbox_inches="tight", pad_inches=0.15 if SUNUM else 0.25)
    plt.close(fig)
    return str(yol)
