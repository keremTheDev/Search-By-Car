import requests
import sqlite3
import time
from config import API_BASE_URL, ENDPOINTS, DB_PATH

# 📌 API Rate Limit (Saniyede Kaç İstek Yapılabilir)
MAX_REQUESTS_PER_SECOND = 10
REQUEST_INTERVAL = 1 / MAX_REQUESTS_PER_SECOND  # Örn: 0.2 saniye = 5 istek/saniye

def fetch_models_from_db():
    """Veritabanındaki tüm modelleri alır (brand_id, model_id, model_slug)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT id, brand_id, slug FROM models")
    models = cursor.fetchall()

    conn.close()
    return models

def fetch_years(brand_slug, model_slug, retries=5):
    """
    Belirtilen marka ve model için API'den yılları çeker.
    Dönen JSON yapısı genelde:
    {
      "result": {
        "data": [
          { "name": "2020", "slug": "2020" },
          ...
        ],
        "meta": {...}
      },
      ...
    }
    Dolayısıyla 'data["result"]["data"]' üzerinden yıl listesine ulaşıyoruz.
    """
    url = API_BASE_URL + ENDPOINTS["years"] + f"?make={brand_slug}&model={model_slug}"
    print(f"DEBUG fetch_years URL: {url}")

    for attempt in range(retries):
        response = requests.get(url)

        if response.status_code == 200:
            try:
                data = response.json()
                # Burada "result" bir dict, içinde "data" adında bir liste var mı kontrol edelim
                if "result" in data and "data" in data["result"]:
                    year_list = data["result"]["data"]
                    years = [
                        {"name": year["name"], "slug": year["slug"]}
                        for year in year_list
                    ]
                    print(f"✅ {brand_slug} {model_slug} için {len(years)} yıl bulundu.")
                    return years
                else:
                    print(f"⚠️ {brand_slug} {model_slug} için API yanıtında 'result.data' alanı bulunamadı.")
                    return []
            except ValueError:
                print(f"❌ {brand_slug} {model_slug} için JSON formatında hata!")
                return []
        elif response.status_code == 429:
            # Too Many Requests - biraz bekleyip tekrar dene
            retry_after = int(response.headers.get("Retry-After", 2))
            print(f"⏳ {brand_slug} {model_slug} için HTTP 429! {retry_after} saniye bekleniyor...")
            time.sleep(retry_after)
        else:
            print(f"❌ {brand_slug} {model_slug} için hata oluştu! HTTP {response.status_code}")
            return []

    print(f"❌ {brand_slug} {model_slug} için {retries} deneme sonrası başarısız!")
    return []

def save_years_to_database(model_years):
    """Tüm yılları tek seferde veritabanına kaydeder."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Eğer tablo yoksa oluştur
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS years (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id INTEGER,
            name TEXT NOT NULL,
            slug TEXT NOT NULL,
            FOREIGN KEY(model_id) REFERENCES models(id),
            UNIQUE(model_id, name, slug)
        )
    ''')

    for model_info in model_years:
        model_id = model_info["model_id"]
        years = model_info["years"]

        for year in years:
            cursor.execute(
                "INSERT OR IGNORE INTO years (model_id, name, slug) VALUES (?, ?, ?)",
                (model_id, year["name"], year["slug"])
            )

    conn.commit()
    conn.close()
    print("✅ Tüm yıllar başarıyla veritabanına kaydedildi!")

def main():
    """Tüm modeller için yılları çekerek veritabanına kaydeden ana fonksiyon."""
    models = fetch_models_from_db()
    if not models:
        print("❌ Veritabanında model bulunamadı, işlem durduruldu.")
        return

    model_years = []
    for model_id, brand_id, model_slug in models:
        # 📌 Önce markanın slug'ını al
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT slug FROM brands WHERE id = ?", (brand_id,))
        brand_slug_row = cursor.fetchone()
        conn.close()

        if not brand_slug_row:
            print(f"⚠️ Marka bulunamadı: brand_id={brand_id}")
            continue

        brand_slug = brand_slug_row[0]  # Tuple içindeki değeri al

        # 📌 API'den yılları çek
        years = fetch_years(brand_slug, model_slug)
        model_years.append({"model_id": model_id, "years": years})

        # 📌 API rate limitine saygı göster
        time.sleep(REQUEST_INTERVAL)

    save_years_to_database(model_years)

if __name__ == "__main__":
    main()
