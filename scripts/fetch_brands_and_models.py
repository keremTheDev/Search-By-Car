import requests
import sqlite3
import time
from config import API_BASE_URL, ENDPOINTS, DB_PATH


def fetch_brands():
    """
    API'den marka listesini çeker.
    Dönen JSON yapısı şu şekildedir:
    {
      "result": {
        "data": [
          { "slug": "acura", "name": "Acura", ... },
          ...
        ],
        "meta": { "count": ... }
      },
      ...
    }
    Bu nedenle 'data["result"]["data"]' üzerinden listeye ulaşıyoruz.
    """
    url = API_BASE_URL + ENDPOINTS["brands"]
    print("DEBUG URL:", url)

    response = requests.get(url)
    print("DEBUG Status:", response.status_code)
    print("DEBUG Body:", response.text)  # Yanıtın ham halini inceleyelim

    if response.status_code == 200:
        try:
            data = response.json()
            print("DEBUG JSON:", data)  # Parse edilen JSON
            if "result" in data and "data" in data["result"]:
                # Burada brand_list, "data" anahtarındaki gerçek marka listesi
                brand_list = data["result"]["data"]
                brands = [
                    {"name": brand["name"], "slug": brand["slug"]}
                    for brand in brand_list
                ]
                print(f"{len(brands)} marka bulundu.")
                return brands
            else:
                print("API yanıtında 'result.data' alanı bulunamadı:", data)
                return []
        except ValueError:
            print("JSON formatında bir yanıt alınamadı!")
            return []
    else:
        print(f"Hata oluştu! HTTP Durum Kodu: {response.status_code}")
        return []


def fetch_models(brand_slug, retries=3):
    """
    Belirtilen marka için modelleri çeker ve hem name hem slug olarak saklar.
    Bu fonksiyon da benzer bir JSON yapısı bekliyorsa,
    "result" -> "data" yapısını kontrol etmeliyiz.
    """
    url = API_BASE_URL + ENDPOINTS["brands"] + f"?make={brand_slug}"

    for attempt in range(retries):
        response = requests.get(url)

        if response.status_code == 200:
            try:
                data = response.json()
                # Kontrol edelim: "result" var mı, içinde "data" var mı?
                if "result" in data and "data" in data["result"]:
                    model_list = data["result"]["data"]
                    models = [
                        {"name": model["name"], "slug": model["slug"]}
                        for model in model_list
                    ]
                    print(f"{brand_slug} için {len(models)} model bulundu.")
                    return models
                else:
                    print(f"{brand_slug} için API yanıtında 'result.data' alanı bulunamadı.")
                    return []
            except ValueError:
                print(f"{brand_slug} için JSON parse hatası!")
                return []
        elif response.status_code == 429:
            wait_time = (attempt + 1) * 2  # İlk deneme 2sn, ikinci 4sn, üçüncü 6sn bekler
            print(f"{brand_slug} için HTTP 429 hatası! {wait_time} saniye bekleniyor...")
            time.sleep(wait_time)
        else:
            print(f"{brand_slug} için hata oluştu! HTTP Durum Kodu: {response.status_code}")
            return []

    print(f"{brand_slug} için {retries} deneme sonrası başarısız!")
    return []


def save_to_database(brand_models):
    """
    Tüm markaları ve modelleri tek seferde veritabanına kaydeder.
    brand_models = [
      { "name": "...", "slug": "...", "models": [ {"name": "...", "slug": "..."}, ... ] },
      ...
    ]
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Eğer tablo yoksa oluştur
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS brands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            slug TEXT UNIQUE NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand_id INTEGER,
            name TEXT NOT NULL,
            slug TEXT NOT NULL,
            FOREIGN KEY(brand_id) REFERENCES brands(id),
            UNIQUE(brand_id, name, slug)
        )
    ''')

    for brand_info in brand_models:
        brand_name = brand_info["name"]
        brand_slug = brand_info["slug"]
        models = brand_info["models"]

        # Markayı veritabanına ekle (yoksa ekler, varsa atlar)
        cursor.execute("INSERT OR IGNORE INTO brands (name, slug) VALUES (?, ?)",
                       (brand_name, brand_slug))
        # Ekledikten sonra brand_id'yi al
        brand_id = cursor.execute("SELECT id FROM brands WHERE slug = ?",
                                  (brand_slug,)).fetchone()[0]

        # Modelleri veritabanına ekle
        for model in models:
            cursor.execute("INSERT OR IGNORE INTO models (brand_id, name, slug) VALUES (?, ?, ?)",
                           (brand_id, model["name"], model["slug"]))

    conn.commit()
    conn.close()
    print("Tüm markalar ve modeller başarıyla veritabanına kaydedildi!")


def main():
    """Tüm markaları ve modelleri çekerek veritabanına kaydeden ana fonksiyon."""
    brands = fetch_brands()
    if not brands:
        print("Markalar alınamadı, işlem durduruldu.")
        return

    brand_models = []
    for brand_info in brands:
        models = fetch_models(brand_info["slug"])
        brand_info["models"] = models  # Modelleri markaya ekliyoruz
        brand_models.append(brand_info)

        # API'ye aşırı yüklenmeyi önlemek için bekleme ekleyelim
        time.sleep(0.5)

    save_to_database(brand_models)


if __name__ == "__main__":
    main()
