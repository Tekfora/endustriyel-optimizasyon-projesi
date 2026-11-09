# DAX ölçüleri

Tüm ölçüler `_Ölçüler` tablosundadır; görüntüleme klasörlerine göre gruplanmıştır.

## 1 OEE

### Planlanan Süre (saat)

OEE'ye giren planlı üretim süresi (iş yüklenen süre, planlı bakım hariç).

```dax
Planlanan Süre (saat) =
    DIVIDE ( SUM ( FaktUretim[PlanlananSureDk] ), 60 )
```
Biçim: `#,0`

### Çalışma Süresi (saat)

Makinenin fiilen parça işlediği süre.

```dax
Çalışma Süresi (saat) =
    DIVIDE ( SUM ( FaktUretim[CalismaSuresiDk] ), 60 )
```
Biçim: `#,0`

### Kullanılabilirlik

Çalışma süresi / planlanan süre.

```dax
Kullanılabilirlik =
    DIVIDE ( SUM ( FaktUretim[CalismaSuresiDk] ), SUM ( FaktUretim[PlanlananSureDk] ) )
```
Biçim: `0.0%`

### Performans

İdeal çevrim süresiyle gereken süre / çalışma süresi (hız kaybı ve küçük duruşlar).

```dax
Performans =
    DIVIDE ( SUM ( FaktUretim[IdealSureDk] ), SUM ( FaktUretim[CalismaSuresiDk] ) )
```
Biçim: `0.0%`

### Kalite

Sağlam adet / üretilen adet.

```dax
Kalite =
    DIVIDE ( SUM ( FaktUretim[SaglamAdet] ), SUM ( FaktUretim[UretilenAdet] ) )
```
Biçim: `0.0%`

### OEE

Toplam Ekipman Etkinliği = Kullanılabilirlik × Performans × Kalite.

```dax
OEE =
    [Kullanılabilirlik] * [Performans] * [Kalite]
```
Biçim: `0.0%`

### OEE Hedef

Şirket hedefi; yalnızca OEE verisi olan dönemlerde gösterilir.

```dax
OEE Hedef =
    IF ( NOT ISBLANK ( [OEE] ), 0.75 )
```
Biçim: `0%`

### OEE Hedefe Fark



```dax
OEE Hedefe Fark =
    IF ( NOT ISBLANK ( [OEE] ), [OEE] - [OEE Hedef] )
```
Biçim: `+0.0%;-0.0%;0.0%`

### OEE Renk

Durum rengi: hedef üstü / yakın / altı.

```dax
OEE Renk =
    SWITCH ( TRUE (), ISBLANK ( [OEE] ), BLANK (), [OEE] >= 0.75, "#0CA30C", [OEE] >= 0.65, "#FAB219", "#D03B3B" )
```
Biçim: `metin`

### OEE Zemin

Matris hücre zemini için açık durum rengi.

```dax
OEE Zemin =
    SWITCH ( TRUE (), ISBLANK ( [OEE] ), BLANK (), [OEE] >= 0.75, "#DDF2DD", [OEE] >= 0.65, "#FDEFCF", "#F6D8D8" )
```
Biçim: `metin`

### Kapasite Kullanımı

İş yüklenen süre / vardiya takvimi. Darboğazda %100'e yakındır.

```dax
Kapasite Kullanımı =
    DIVIDE ( SUM ( FaktUretim[PlanlananSureDk] ), SUM ( FaktUretim[TakvimSuresiDk] ) )
```
Biçim: `0%`

### OEE Önceki Ay



```dax
OEE Önceki Ay =
    CALCULATE ( [OEE], DATEADD ( DimTarih[Tarih], -1, MONTH ) )
```
Biçim: `0.0%`

### OEE Aylık Değişim (puan)



```dax
OEE Aylık Değişim (puan) =
    IF ( NOT ISBLANK ( [OEE Önceki Ay] ), ( [OEE] - [OEE Önceki Ay] ) * 100 )
```
Biçim: `+0.0;-0.0;0.0`

## 2 Üretim ve Kalite

### Üretilen Adet



```dax
Üretilen Adet =
    SUM ( FaktUretim[UretilenAdet] )
```
Biçim: `#,0`

### Sağlam Adet



```dax
Sağlam Adet =
    SUM ( FaktUretim[SaglamAdet] )
```
Biçim: `#,0`

### Hurda Adet



```dax
Hurda Adet =
    SUM ( FaktUretim[HurdaAdet] )
```
Biçim: `#,0`

### Hurda Oranı



```dax
Hurda Oranı =
    DIVIDE ( [Hurda Adet], [Üretilen Adet] )
```
Biçim: `0.00%`

### Hurda Maliyeti (TL)

Hurda adedi × standart maliyet × operasyondaki birikmiş maliyet oranı.

```dax
Hurda Maliyeti (TL) =
    SUM ( FaktUretim[HurdaMaliyetiTL] )
```
Biçim: `#,0`

### Hat Çıkışı (adet)

Son istasyondan çıkan sağlam ürün.

```dax
Hat Çıkışı (adet) =
    CALCULATE ( [Sağlam Adet], DimMakine[Son İstasyon] = 1 )
```
Biçim: `#,0`

### Hata Adedi



```dax
Hata Adedi =
    SUM ( FaktKalite[Adet] )
```
Biçim: `#,0`

### Hata Payı



```dax
Hata Payı =
    DIVIDE ( [Hata Adedi], CALCULATE ( [Hata Adedi], ALLSELECTED ( DimHataTuru ) ) )
```
Biçim: `0%`

### Hata Kümülatif Pay

Pareto için kümülatif pay.

```dax
Hata Kümülatif Pay =
    VAR mevcut = [Hata Adedi]
    VAR tablo = ADDCOLUMNS ( ALLSELECTED ( DimHataTuru[Hata Türü] ), "@a", [Hata Adedi] )
    RETURN IF ( NOT ISBLANK ( mevcut ), DIVIDE ( SUMX ( FILTER ( tablo, [@a] >= mevcut ), [@a] ), SUMX ( tablo, [@a] ) ) )
```
Biçim: `0%`

### Çap Ortalama (mm)

AM-200 taşlama çıkışı.

```dax
Çap Ortalama (mm) =
    AVERAGE ( FaktOlcum[CapMm] )
```
Biçim: `0.0000`

### Çap Std Sapma (mm)



```dax
Çap Std Sapma (mm) =
    STDEV.S ( FaktOlcum[CapMm] )
```
Biçim: `0.0000`

### Ppk

Genel süreç performans indeksi (tolerans 25,000 ± 0,015 mm).

```dax
Ppk =
    VAR mu = [Çap Ortalama (mm)]
    VAR s = [Çap Std Sapma (mm)]
    RETURN DIVIDE ( MIN ( 25.015 - mu, mu - 24.985 ), 3 * s )
```
Biçim: `0.00`

### Ppk Hedef

Müşteri şartı.

```dax
Ppk Hedef =
    IF ( NOT ISBLANK ( [Ppk] ), 1.33 )
```
Biçim: `0.00`

### Ölçüm Sayısı



```dax
Ölçüm Sayısı =
    COUNTROWS ( FaktOlcum )
```
Biçim: `#,0`

## 3 Duruş ve Bakım

### Duruş Süresi (saat)



```dax
Duruş Süresi (saat) =
    DIVIDE ( SUM ( FaktDurus[SureDk] ), 60 )
```
Biçim: `#,0`

### Duruş Adedi



```dax
Duruş Adedi =
    COUNTROWS ( FaktDurus )
```
Biçim: `#,0`

### Plansız Duruş (saat)



```dax
Plansız Duruş (saat) =
    CALCULATE ( [Duruş Süresi (saat)], DimDurusNedeni[Planlı mı] = "Hayır" )
```
Biçim: `#,0`

### Duruş Payı



```dax
Duruş Payı =
    DIVIDE ( [Plansız Duruş (saat)], CALCULATE ( [Plansız Duruş (saat)], ALLSELECTED ( DimDurusNedeni ) ) )
```
Biçim: `0%`

### Duruş Kümülatif Pay

Pareto için kümülatif pay.

```dax
Duruş Kümülatif Pay =
    VAR mevcut = [Plansız Duruş (saat)]
    VAR tablo = ADDCOLUMNS ( ALLSELECTED ( DimDurusNedeni[Neden] ), "@s", [Plansız Duruş (saat)] )
    RETURN IF ( NOT ISBLANK ( mevcut ), DIVIDE ( SUMX ( FILTER ( tablo, [@s] >= mevcut ), [@s] ), SUMX ( tablo, [@s] ) ) )
```
Biçim: `0%`

### Arıza Sayısı



```dax
Arıza Sayısı =
    CALCULATE ( [Duruş Adedi], DimDurusNedeni[Kategori] = "Arıza" )
```
Biçim: `#,0`

### Arıza Süresi (saat)



```dax
Arıza Süresi (saat) =
    CALCULATE ( [Duruş Süresi (saat)], DimDurusNedeni[Kategori] = "Arıza" )
```
Biçim: `#,0`

### MTBF (saat)

Arızalar arası ortalama çalışma süresi.

```dax
MTBF (saat) =
    DIVIDE ( [Çalışma Süresi (saat)], [Arıza Sayısı] )
```
Biçim: `#,0.0`

### MTTR (dk)

Ortalama tamir süresi.

```dax
MTTR (dk) =
    DIVIDE ( [Arıza Süresi (saat)] * 60, [Arıza Sayısı] )
```
Biçim: `#,0`

### Ayar Sayısı



```dax
Ayar Sayısı =
    CALCULATE ( [Duruş Adedi], DimDurusNedeni[NedenID] = "D01" )
```
Biçim: `#,0`

### Ortalama Ayar Süresi (dk)

Ürün değişimi (setup) ortalaması.

```dax
Ortalama Ayar Süresi (dk) =
    DIVIDE ( CALCULATE ( SUM ( FaktDurus[SureDk] ), DimDurusNedeni[NedenID] = "D01" ), [Ayar Sayısı] )
```
Biçim: `#,0`

## 4 Teslimat ve Maliyet

### Sipariş Sayısı



```dax
Sipariş Sayısı =
    COUNTROWS ( FaktSiparis )
```
Biçim: `#,0`

### Zamanında Teslimat

Termin tarihinde veya öncesinde sevk edilen siparişlerin oranı.

```dax
Zamanında Teslimat =
    DIVIDE ( CALCULATE ( COUNTROWS ( FaktSiparis ), FaktSiparis[ZamanindaMi] = 1 ), [Sipariş Sayısı] )
```
Biçim: `0.0%`

### OTD Hedef



```dax
OTD Hedef =
    IF ( NOT ISBLANK ( [Zamanında Teslimat] ), 0.95 )
```
Biçim: `0%`

### Geciken Sipariş



```dax
Geciken Sipariş =
    CALCULATE ( [Sipariş Sayısı], FaktSiparis[ZamanindaMi] = 0 )
```
Biçim: `#,0`

### Ort. Gecikme (gün)

Geciken siparişlerde ortalama gecikme.

```dax
Ort. Gecikme (gün) =
    CALCULATE ( AVERAGE ( FaktSiparis[GecikmeGun] ), FaktSiparis[ZamanindaMi] = 0 )
```
Biçim: `0.0`

### Ciro (TL)



```dax
Ciro (TL) =
    SUM ( FaktSiparis[Tutar] )
```
Biçim: `#,0`

### Gecikme Cezası (TL)



```dax
Gecikme Cezası (TL) =
    SUM ( FaktSiparis[CezaTutariTL] )
```
Biçim: `#,0`

### Ekspres Nakliye (TL)



```dax
Ekspres Nakliye (TL) =
    SUM ( FaktSiparis[EkspresNakliyeTL] )
```
Biçim: `#,0`

### Fazla Mesai (TL)



```dax
Fazla Mesai (TL) =
    SUM ( FaktMesai[MaliyetTL] )
```
Biçim: `#,0`

### Fazla Mesai Vardiyası



```dax
Fazla Mesai Vardiyası =
    SUM ( FaktMesai[VardiyaSayisi] )
```
Biçim: `#,0`

### Kapasite Açığı Maliyeti (TL)

Fazla mesai + gecikme cezası + ekspres nakliye.

```dax
Kapasite Açığı Maliyeti (TL) =
    [Fazla Mesai (TL)] + [Gecikme Cezası (TL)] + [Ekspres Nakliye (TL)]
```
Biçim: `#,0`

## 5 Tahmin ve Senaryolar

### Talep (adet)



```dax
Talep (adet) =
    CALCULATE ( SUM ( FaktTalep[Adet] ), FaktTalep[Tür] = "Gerçekleşen" )
```
Biçim: `#,0`

### Talep Tahmini (adet)

ETS(M,Ad,M) + satış girdisi.

```dax
Talep Tahmini (adet) =
    CALCULATE ( SUM ( FaktTalep[Adet] ), FaktTalep[Tür] = "Tahmin" )
```
Biçim: `#,0`

### Tahmin Alt %80



```dax
Tahmin Alt %80 =
    CALCULATE ( SUM ( FaktTalep[Alt %80] ), FaktTalep[Tür] = "Tahmin" )
```
Biçim: `#,0`

### Tahmin Üst %80



```dax
Tahmin Üst %80 =
    CALCULATE ( SUM ( FaktTalep[Üst %80] ), FaktTalep[Tür] = "Tahmin" )
```
Biçim: `#,0`

### Sim Haftalık Çıktı

SimPy kapasite testi, 25 tekrar ortalaması.

```dax
Sim Haftalık Çıktı =
    SUM ( SimKapasite[Haftalık Çıktı] )
```
Biçim: `#,0`

### Sim Kullanım



```dax
Sim Kullanım =
    AVERAGE ( SimKullanim[Kullanım] )
```
Biçim: `0%`

### Opt Üretim



```dax
Opt Üretim =
    SUM ( OptPlan[Üretim] )
```
Biçim: `#,0`

### Opt Talep



```dax
Opt Talep =
    SUM ( OptPlan[Talep] )
```
Biçim: `#,0`

### Opt Stok



```dax
Opt Stok =
    SUM ( OptPlan[Stok] )
```
Biçim: `#,0`

### Opt Maliyet (TL)

6 aylık plan maliyeti.

```dax
Opt Maliyet (TL) =
    SUM ( OptMaliyet[Tutar TL] )
```
Biçim: `#,0`
