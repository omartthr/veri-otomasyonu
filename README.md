# Üniversite Veri Otomasyonu (Kalite Güncellemesi v3)

Yüklenen kaynak Excel dosyalarındaki üniversiteleri ve URL'leri tarayarak program verilerini (program adları, kabul şartları, dil şartları, ücretler, süreler, GPA vb.) resmî web sitelerinden deterministik kural motoruyla çıkartan, 8 aşamalı kalite kontrolünden geçirip 48 sütunlu biçimi korunmuş Excel çıktısı üreten otomasyon sistemi.

---

## 🌟 Ana Özellikler ve Yenilikler (v3)

### 1. 🛡️ 8 Kalite Kuralı Motoru & Otomatik QA
Sistem, üretilen her veriyi 8 sert kalite kuralına göre değerlendirir:
1. **Yüksek Doluluk:** Kritik alanlar (Eğitim Süresi, GPA, Ücret vb.) için doluluk ölçümü.
2. **Yalnızca Gerçek + Doğrulanmış Programlar:** Genel katalog, haber, başvuru ve duyuru sayfalarını reddeden taksonomi ve kalite kapısı.
3. **Resmî Kaynak Doğrulaması:** Domain bazlı doğrulama ile yalnızca resmî kurumsal adreslerin taranması.
4. **Kapsama Uygun Veri:** Lisans/Yüksek Lisans politikalarının birleştirilmesi.
5. **Kaynak Yorumları:** Çıkarılan her alan için açık kanıt cümlesi ve kaynak URL kaydı.
6. **Tekilleştirme & Çöp Filtresi:** Çift kaydı önleyen noktalama/boşluk duyarsız anahtarlama ve çöp program adı engelleme.
7. **Uydurma Yok — Boş Bırak:** Kanıtı ve açık kaynağı olmayan hücrelerde sabit/hallucinated metin basılmaz, hücre boş bırakılır. Kural ihlali durumunda sert kapı devreye girer.
8. **Otomatik + Görsel QA Paneli:** Streamlit üzerinde 8 kural kartı, renk kodlu doluluk bar grafiği ve detaylı istatistikler.

### 2. 🔗 Akıllı URL Esnekliği ("Gerekli Değil" Fallback)
URL sütunlarında `"Gerekli değil (program verisi mevcut)"`, `"Mevcut"` veya `"N/A"` gibi metinler bulunduğunda bot üniversiteyi es geçmez; otomatik olarak `official_website` adresini fallback olarak kullanıp keşif taramasını başlatır.

### 3. 🔍 Gelişmiş Extractorlar
- **Eğitim Süresi (3 Tier):** Derece+yıl birlikteliği (0.93), bağlam cümleleri (0.88) ve kredi saatinden tahmin (0.78) katmanlarıyla yüksek doluluk.
- **Minimum GPA (Satır Bazlı):** Mezuniyet/sürdürme GPA'sını atlayıp kabul GPA'sını satır bazlı izole eder.
- **Dil ve Ücret Extractorları:** IELTS, TOEFL, Duolingo, Yıllık Ücret ve Başvuru Ücretlerini açık kanıtla toplar.

---

## 🛠️ Kurulum (Windows / PowerShell)

### 1. Depoyu Klonlayın
```powershell
git clone <depo-url>
cd uni-veri-otomasyonu-kalite-guncellemesi
```

### 2. Sanal Ortam Oluşturun ve Etkinleştirin
```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

### 3. Bağımlılıkları Yükleyin
```powershell
pip install -r requirements.txt
playwright install  # İsteğe bağlı browser motoru için
```

### 4. Uygulamayı Başlatın
```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

---

## 📂 Proje Yapısı

```
uni-veri-otomasyonu-kalite-guncellemesi/
├── app.py                      # Streamlit ana web uygulaması ve Görsel QA Paneli
├── requirements.txt            # Python kütüphane bağımlılıkları
├── .env.example                # Çalışma yapılandırması
├── .gitignore                  # Git hariç tutma kuralları (venv, data/input, data/output)
├── README.md
├── src/
│   ├── config.py               # Ayarlar ve veri yolları
│   ├── models.py               # Temel Pydantic modelleri
│   ├── domain_utils.py         # Domain ayrıştırma ve güvenlik kontrolleri
│   ├── extractors/             # Kural tabanlı veri çıkarıcılar
│   │   ├── duration.py         # 3 Katmanlı Eğitim Süresi çıkarıcı
│   │   ├── gpa.py              # Satır bazlı GPA çıkarıcı
│   │   ├── tuition.py          # Ücret çıkarıcı
│   │   ├── language_tests.py   # Dil testleri çıkarıcı
│   │   └── semantic_fields.py  # Anlatı ve politika alan çıkarıcıları
│   └── program_pipeline/       # 48 Sütunlu İş Akışı Motoru
│       ├── pipeline.py         # Ana orchestration ve paralelleştirme
│       ├── program_quality.py  # Kalite kapısı ve çöp filtresi
│       ├── source_excel_reader.py # "Gerekli değil" URL fallback desteği
│       ├── field_merger.py     # Güvenli politika birleştirici
│       ├── qa_exporter.py      # QA Raporlama ve sert kapı denetleyicisi
│       ├── evidence_validator.py# Kanıt doğrulayıcı
│       └── excel_writer.py     # Biçim korumalı 48 sütunlu Excel yazıcı
├── tests/                      # Otomatik Pytest test paketi (216+ test)
└── data/
    ├── input/                  # Girdi Excel dosyaları (Git'e eklenmez)
    ├── output/                 # Çıktı Excel dosyaları ve QA raporları (Git'e eklenmez)
    └── cache/                  # Web indirme önbelleği
```

---

## 🧪 Testleri Çalıştırma

Tüm birim ve entegrasyon testlerini çalıştırmak için:

```powershell
python -m pytest tests/ -v
```

---

## 🚀 Kullanım Adımları

1. Tarayıcıda açılan Streamlit arayüzünde **"Program Verilerini Doldur"** sekmesine geçin.
2. Takip/Kaynak Excel dosyasını (`[DOLDUR]` sütunlarını içeren) seçin.
3. Template Excel dosyasını (`Programlar` sayfasını içeren) seçin.
4. **"Program Pipeline Başlat"** butonuna tıklayın.
5. İşlem bittiğinde **Görsel QA Paneli**'nden 8 kural uyumunu inceleyin ve **⬇️ Doldurulmuş Excel'i İndir** butonundan çıktınızı alın.
