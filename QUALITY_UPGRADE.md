# Program Otomasyonu Kalite Güncellemesi

Bu sürüm, iki Excel dosyasından `Programlar` sheetini dolduran akışın
yüksek-hassasiyetli sürümüdür.

## Düzeltilen ana problemler

- HTML paragraf ve listelerinin çıkarım sırasında kaybolması giderildi.
- Resmî domaindeki her sayfanın program sayılması engellendi.
- `JSON-LD Structured Data`, program listeleri, blog, kayıt, başvuru ve genel
  politika sayfaları program satırı olarak reddediliyor.
- Program adı; H1, sayfa başlığı, URL ve sayfa içeriği birlikte doğrulanarak
  seçiliyor.
- Aynı programın yinelenen URL/başlık varyasyonları tekilleştiriliyor.
- Resmî akademik katalog PDF'leri keşfediliyor; yalnızca tam program adının
  çevresindeki bölüm program-özel veri için kullanılıyor.
- Genel kabul/dil/ücret bilgileri program-özel bilgilerle kanıt ve kapsam
  önceliğine göre birleştiriliyor.
- Başvuru türü, belgeler, zorunlu maddeler, koşullu mülakat, İngilizce
  yeterlilik, standart test politikası, transkript şartı, akademik yıl ve
  kariyer çıktıları için deterministik çıkarıcılar eklendi.
- Program kaynağı `Program Adı` hücresinin yorumuna yazılıyor; program URL'si
  artık yanlışlıkla `Kabul Verisi Kaynağı` sütununa konulmuyor.
- Checkpoint yüzünden yeni çıktıda üniversitelerin kaybolması engellendi.
- PDF ham içeriği korunuyor ve gerçekten PDF ayrıştırıcısına iletiliyor.
- `PROXY_URL`, HTTP + curl + Playwright katmanlarının tümünde kullanılıyor.
- Gemini/API anahtarı gereksinimi ve eski ayarları kaldırıldı.

## Doğrulama

- Ağsız Phoenix-benzeri tam pilot: gerçek program kabul, kayıt sayfası ret,
  48 sütunlu Excel'e kanıtlı zengin satır yazımı.
- Yerel test paketi: `207 passed`, canlı ağ testleri hariç.

Canlı siteler erişim engeli, içerik değişikliği veya PDF tarama kalitesi
nedeniyle bazı alanlarda yine boş sonuç üretebilir. Sistem kanıt yoksa hücreyi
boş bırakacak şekilde tasarlanmıştır.
