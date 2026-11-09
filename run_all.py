"""Projenin tüm akışını sırayla çalıştırır.

    python run_all.py            # veri → analiz → tahmin → simülasyon → optimizasyon → finans → Power BI verisi
    python run_all.py --sunum    # + slaytlar için başlıksız grafik sürümleri (ciktilar/grafikler/sunum)
    python run_all.py --pbip     # + Power BI projesini (PBIP) koddan yeniden üretir

--pbip, powerbi/Demirkanat_Fabrika.SemanticModel klasörünü yeniden yazar; Power BI Desktop'ta
açtıktan sonra "Yenile" demeniz gerekir. Hazır .pbix dosyası bu adımdan etkilenmez.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

KOK = Path(__file__).resolve().parent
ADIMLAR = [
    ("01_veri_uretimi.py", "Sentetik MES/ERP verisi (vardiya bazlı akış simülasyonu)"),
    ("02_analiz.py", "OEE, Pareto, istatistiksel testler, SPC, grafikler"),
    ("03_talep_tahmini.py", "ETS talep tahmini ve darboğaz yük oranı"),
    ("04_simulasyon.py", "SimPy kesikli olay simülasyonu, 7 senaryo"),
    ("05_optimizasyon.py", "MILP üretim planı (PuLP + CBC)"),
    ("06_finans_monte_carlo.py", "NPV + Monte Carlo yatırım analizi"),
    ("07_powerbi_veri.py", "Power BI yıldız şema CSV'leri"),
]
SUNUM_ADIMLARI = ["02_analiz.py", "03_talep_tahmini.py", "04_simulasyon.py", "05_optimizasyon.py",
                  "06_finans_monte_carlo.py"]


def calistir(betik: str, aciklama: str, ortam: dict | None = None) -> None:
    print(f"▶ {betik:<26} {aciklama}", flush=True)
    bas = time.perf_counter()
    sonuc = subprocess.run([sys.executable, betik], cwd=KOK / "src", env=ortam or os.environ.copy(),
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    if sonuc.returncode != 0:
        print(sonuc.stdout[-3000:], sonuc.stderr[-3000:], sep="\n")
        sys.exit(f"✖ {betik} hata verdi (çıkış kodu {sonuc.returncode})")
    print(f"  ✓ {time.perf_counter() - bas:,.1f} sn")


def main() -> None:
    for betik, aciklama in ADIMLAR:
        calistir(betik, aciklama)
    if "--sunum" in sys.argv:
        ortam = {**os.environ, "SUNUM": "1"}
        for betik in SUNUM_ADIMLARI:
            calistir(betik, "sunum grafikleri", ortam)
    if "--pbip" in sys.argv:
        calistir("08_pbip_olustur.py", "Power BI projesi (TMDL + PBIR)")
    print("\nTamamlandı. Grafikler: ciktilar/grafikler · Özet: ciktilar/ozet_metrikler.json · Power BI: powerbi/")


if __name__ == "__main__":
    main()
