# İlk 90 Gün: Veriyle Darboğazı Kırmak

Bir endüstri mühendisinin işe başladığı ilk 90 günde yürüttüğü uçtan uca iyileştirme projesi:
**veri modeli → istatistiksel analiz → talep tahmini → kesikli olay simülasyonu → optimizasyon →
Monte Carlo yatırım analizi → Power BI paneli → yönetim sunumu.**

> Demirkanat Otomotiv Yan Sanayi A.Ş. **kurgusal** bir şirkettir; tüm veriler **sentetiktir** ve bu vaka
> çalışması için üretilmiştir. Veri rastgele sayı değildir: vardiya bazlı bir akış simülasyonu planlama
> kararlarını, ayarları, arızaları, hurdayı ve sevkiyatı yürütür; darboğaz, fazla mesai ve gecikme
> sistemin dinamiğinden kendiliğinden doğar.

- **Sunum (19 slayt, konuşmacı notlu):** https://claude.ai/artifact/NnQkxMB85WWhyLiiK8J9iv
  (bağlantı varsayılan olarak yalnızca size açıktır; başkalarıyla paylaşmak için sayfadaki *Paylaş* menüsünü
  kullanın, aynı menüden PowerPoint veya PDF olarak indirebilirsiniz)
- **Power BI paneli:** `powerbi/Demirkanat_Fabrika.pbix` (verisiyle hazır) ve
  `powerbi/Demirkanat_Fabrika_Dashboard.pdf` (6 sayfanın çıktısı)

---

## Hikâye (DMAIC)

### 1. Tanımla — 3 Ağustos 2026, ilk iş günü
Bursa'daki kurgusal bir otomotiv yan sanayi fabrikası; iki hat, altı ürün (aks mili, rot başı, fren diski),
dört müşteri. Haziran 2026'da Hat-1 siparişlerinin **yalnızca %18'i** zamanında gitti ve bir OEM resmi
uyarı gönderdi. Görev: gecikmelerin kök nedenini bulmak, 90 günde ölçülebilir bir iyileştirme göstermek ve
8,5 M TL'lik yeni makine yatırımı gerekip gerekmediğine karar verdirmek.

| Başlangıç göstergesi (Eki 2025 – Eyl 2026) | Değer | Hedef |
|---|---|---|
| Hat-1 zamanında teslimat (OTD) | %84,0 (Haziran: %18) | %95 |
| Hat-2 zamanında teslimat | %99,5 | %95 |
| Darboğaz makinesi (H1-FRZ) OEE | %60,4 | %75 |
| Kapasite açığının yıllık faturası | 1,69 M TL (fazla mesai 1,14 · ceza 0,32 · ekspres 0,22) | — |

### 2. Ölç
13 aylık MES verisi (9.565 üretim kaydı, 11.052 duruş olayı, 14.686 hata satırı, 5.450 çap ölçümü) ve
37 aylık ERP talep geçmişi + 728 sipariş tek bir yıldız şemaya bağlandı (7 boyut, 7 olgu tablosu).
Python analizleri ve Power BI aynı tabloları okur.

### 3. Analiz et
| Bulgu | Kanıt |
|---|---|
| Darboğaz **H1-FRZ** CNC işleme merkezi | Kapasite kullanımı %100; diğer makineler %20–74 |
| Planlı sürenin yalnızca %60'ı değer üretiyor | Kayıp şelalesi: ayar %10,6 · arıza %9,9 · diğer duruş %4,6 · hız %13,2 · kalite %1,3 |
| Duruşların %69'u iki kaynaktan | Pareto: mekanik arıza %36, ürün değişimi %32; MTBF 10,9 sa, MTTR 87 dk, ayar başına 96 dk |
| Darboğazda 1 dk duruş = 1,14 sağlam parça | Vardiya bazlı çoklu regresyon, R² 0,72 |
| Gece vardiyası 6,3 puan geride | ANOVA F = 18,6, p < 0,001; Kruskal-Wallis doğruluyor |
| Gece hurdası 1,43 kat | Ki-kare, p < 0,001; hurdanın %53'ü boyutsal |
| Gece çapı +5,4 µm kayıyor | X̄ kartı; gece Cpk 0,86, gündüz 1,36, genel Ppk 0,98 |

### 4. İyileştir
- **Talep tahmini:** ETS(M,Ad,M), geriye dönük test MAPE %5,3 (mevsimsel naif %6,4). Önümüzdeki 6 ayda talep
  geçen yılın aynı dönemine göre %8 yüksek; mevcut OEE ile FRZ 6 ayın 4'ünde %109–118 yükte.
- **Simülasyon (SimPy):** Parametreleri MES verisinden kestirilen model doğrulandı (haftalık çıktı −%0,5,
  OEE %60,0 vs %60,4). 7 senaryo × 25 tekrar:

  | Senaryo | Kapasite | Darboğaz |
  |---|---|---|
  | S0 Mevcut durum | 7.813 adet/hafta | Freze |
  | S1 SMED | +%7 | Freze |
  | S2 TPM | +%5 | Freze |
  | S3 SMED + TPM | +%12 | Freze |
  | **S4 SMED + TPM + kampanya planlama** | **+%15** | Freze |
  | S5 Yeni işleme merkezi | +%35 | **Taşlama'ya kayıyor** |
  | S6 Aynı iyileştirme yalnızca Taşlama'da | +%0 | Freze |

- **Pilot (Ekim 2026):** FRZ OEE %60 → %70 (simülasyon öngörüsü %68,6), ayar 74 → 29 dk, MTBF 10,9 → 16,8 sa,
  Ppk 0,98 → 1,33, Hat-1 OTD %88 (devreden ilk hafta hariç %94). Ayar ve arıza değişimleri istatistiksel olarak anlamlı.
- **Optimizasyon (PuLP + CBC, MILP):** Kasım–Nisan üretim planı. Bugünkü yöntem 4,93 M TL ve 44 Pazar
  vardiyası; optimal plan + pilot verimi 0,35 M TL ve 0 vardiya (−%93). Darboğazda bir saatin değeri ≈ 6.700 TL.
- **Yatırım kararı (Monte Carlo, N = 10.000, 5 yıl, reel %12):**

  | Seçenek | NPV medyan | NPV P10 | Not |
  |---|---|---|---|
  | A Yalın paket | 47,3 M TL | 23,8 M TL | Geri ödeme ~3 ay, P(NPV > 0) %100 |
  | B Yeni makine hemen | 47,4 M TL | 12,0 M TL | Geri ödeme ~19 ay |
  | **C Aşamalı: yalın şimdi, talep +%8 eşiğinde makine** | **55,9 M TL** | 23,7 M TL | Senaryoların %72'sinde en iyi |

### 5. Kontrol et
Altı sayfalık Power BI paneli (Yönetici Özeti, OEE ve Darboğaz, Duruş ve Bakım, Kalite ve SPC, Teslimat ve
Maliyet, Tahmin ve Senaryolar) **Python'dan üretildi** (TMDL anlamsal model + PBIR rapor), Power BI Desktop'ta
açılıp doğrulandı. Hedef ve durum renkleri DAX ölçülerinden gelir; makine yatırımı tetikleyicisi buradan izlenir.

---

## Klasör yapısı

```
├── run_all.py                 tüm akışı sırayla çalıştırır
├── requirements.txt
├── src/
│   ├── ortak.py               yollar, ana veriler (makine, ürün, müşteri…), maliyet varsayımları
│   ├── grafik_stili.py        ortak grafik dili (renk körlüğüne dayanıklı palet), SUNUM modu
│   ├── veri_yukle.py          ham veriyi okuma + OEE yardımcıları
│   ├── 01_veri_uretimi.py     sentetik MES/ERP verisi (vardiya bazlı akış simülasyonu)
│   ├── 02_analiz.py           KPI, kayıp şelalesi, Pareto, ANOVA/ki-kare/regresyon, SPC, pilot
│   ├── 03_talep_tahmini.py    ETS + geriye dönük test + darboğaz yük oranı
│   ├── 04_simulasyon.py       SimPy modeli, kapasite ve talep deneyleri, doğrulama
│   ├── 05_optimizasyon.py     MILP üretim planı, 4 durum, darboğaz saatinin değeri
│   ├── 06_finans_monte_carlo.py  NPV, reel opsiyon (aşamalı yatırım), Monte Carlo
│   ├── 07_powerbi_veri.py     Power BI yıldız şema CSV'leri
│   └── 08_pbip_olustur.py     Power BI projesini koddan üretir (TMDL + PBIR + tema + DAX belgesi)
├── veri/ham/                  üretilen ham MES/ERP tabloları (CSV)
├── ciktilar/
│   ├── grafikler/             21 analiz grafiği (+ sunum/ altında başlıksız slayt sürümleri)
│   ├── tablolar/              test sonuçları, simülasyon tekrarları, plan, maliyet eğrileri…
│   └── ozet_metrikler.json    hikâyedeki bütün sayılar
└── powerbi/
    ├── Demirkanat_Fabrika.pbix            verisiyle hazır panel
    ├── Demirkanat_Fabrika.pbip (+ .SemanticModel, .Report)   kaynak kod hâli
    ├── Demirkanat_Fabrika_Dashboard.pdf   6 sayfanın PDF çıktısı
    ├── DAX_Olculer.md                     59 ölçünün açıklamalı listesi
    ├── tema/DemirkanatTema.json           rapor teması
    ├── ekran/                             sayfa görüntüleri (PNG)
    └── veri/                              modelin okuduğu CSV'ler
```

## Çalıştırma

```bash
python -m venv .venv
```

```bash
.venv\Scripts\python -m pip install -r requirements.txt
```

```bash
.venv\Scripts\python run_all.py
```

Seçenekler: `--sunum` slayt için başlıksız grafik sürümlerini, `--pbip` Power BI projesini yeniden üretir.
Tüm akış yaklaşık 3 dakika sürer ve sabit rastgelelik tohumu (2026) sayesinde her seferinde aynı sonucu verir.

## Power BI

- **Hızlı yol:** `powerbi/Demirkanat_Fabrika.pbix` dosyasını açın; veriler içindedir.
- **Kaynak kod yolu:** `powerbi/Demirkanat_Fabrika.pbip` dosyasını açıp *Yenile*'ye basın.
- Proje klasörünü taşırsanız: *Dönüştür › Parametreleri düzenle › VeriKlasoru* değerini yeni
  `powerbi\veri\` yoluna çevirip yenileyin.
- Model: 21 tablo, 26 ilişki (tek yönlü, çoktan bire), 59 ölçü `_Ölçüler` tablosunda, otomatik tarih tablosu kapalı,
  örtük ölçüler engelli. Sayılar CSV'den `en-US` kültürüyle okunur (Türkçe Windows'ta ondalık hatasını önler).

## Yöntem notları ve varsayımlar

- OEE = Kullanılabilirlik × Performans × Kalite; planlı bakım ve iş olmayan süre planlanan süreye girmez.
- Simülasyon zamanı çalışma dakikasıdır (3 × 450 dk/gün, 6 gün/hafta); arızalar çalışma süresine bağlıdır.
- Optimizasyon darboğaz kapasitesinin en fazla %93'ünü planlar (değişkenliğe karşı koruma tamponu).
- Finansal analiz sabit 2026 fiyatlarıyla ve %12 reel iskonto oranıyla yapılmıştır; makine fiyatı Euro bazlı
  varsayılıp kur riski yatırım tutarı dağılımına yansıtılmıştır.
- 2027 Ramazan Bayramı tarihleri yaklaşık alınmıştır.

## Sınırlamalar

- Veri sentetiktir; gerçek bir fabrikada parametreler MES/ERP'den aynı betiklerle yeniden kestirilmelidir.
- Pilot tek aydır; kalıcılık, Monte Carlo'da %55–100 gerçekleşme aralığıyla temsil edilmiştir.
- Kampanya planlaması kapasite kazandırır ama tedarik süresini uzatabilir (simülasyonda S3 2,8 gün, S4 4,2 gün);
  kampanya büyüklüğü bu dengeye göre ayarlanmalıdır.
