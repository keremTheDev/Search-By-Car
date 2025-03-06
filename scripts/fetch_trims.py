import requests
import sqlite3
import time
import json
import os
from config import API_BASE_URL, ENDPOINTS, DB_PATH
import csv

PROGRESS_FILE = "progress.json"
BATCH_SIZE = 100  # Kaç trimde bir veritabanına kaydedilecek
LOG_FILE = "processed_years.csv"


def load_progress():
    """Son kaydedilen noktayı yükler."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {"brand_slug": None, "model_slug": None, "year_slug": None}


def save_progress(brand_slug, model_slug, year_slug):
    """Son kaydedilen noktayı dosyaya yazar."""
    with open(PROGRESS_FILE, "w") as f:
        json.dump({"brand_slug": brand_slug, "model_slug": model_slug, "year_slug": year_slug}, f)


def get_all_models_years():
    """Veritabanındaki brand -> model -> year ilişkisini alır."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    rows = cursor.execute("""
        SELECT 
            b.id AS brand_id, b.name AS brand_name, b.slug AS brand_slug,
            m.id AS model_id, m.name AS model_name, m.slug AS model_slug,
            y.id AS year_id, y.name AS year_name, y.slug AS year_slug
        FROM brands b
        JOIN models m ON b.id = m.brand_id
        JOIN years y ON m.id = y.model_id
        ORDER BY b.id, m.id, y.id
    """).fetchall()

    conn.close()

    brands = []
    brand_dict = {}

    for (b_id, b_name, b_slug, m_id, m_name, m_slug, y_id, y_name, y_slug) in rows:
        # Eğer brand_dict içinde marka yoksa ekleyelim
        if b_id not in brand_dict:
            brand_dict[b_id] = {
                "id": b_id,
                "name": b_name,
                "slug": b_slug,
                "models": {}  # Modelleri burada saklayacağız
            }

        # Eğer model dict içinde yoksa ekleyelim
        if m_id not in brand_dict[b_id]["models"]:
            brand_dict[b_id]["models"][m_id] = {
                "id": m_id,
                "name": m_name,
                "slug": m_slug,
                "years": []  # Yılları burada saklayacağız
            }

        # Modelin yıllarına ekleyelim
        brand_dict[b_id]["models"][m_id]["years"].append({
            "id": y_id,
            "name": y_name,
            "slug": y_slug
        })

        # Son olarak dict -> liste formatına çevirelim
    for b_id, b_val in brand_dict.items():
        models_list = []
        for m_id, m_val in b_val["models"].items():
            models_list.append(m_val)  # Modelleri listeye çeviriyoruz
        b_val["models"] = models_list  # Modelleri ekleyelim
        brands.append(b_val)

    return brands


def fetch_trims(brand_slug, model_slug, year_slug, retries=3):
    """Bir modelin trimlerini API’den çeker ve trim yoksa uyarı gösterir."""
    try:
        model_year = int(year_slug)
        if model_year < 1995:
            print(f"⏩ {brand_slug} -> {model_slug} -> {year_slug} atlandı (1995 öncesi)")
            return []  # Boş liste döndürerek işlemi atla
    except ValueError:
        print(f"⚠️ Geçersiz yıl formatı: {year_slug}")
        return []

    url = API_BASE_URL + ENDPOINTS["trims"] + f"?make={brand_slug}&model={model_slug}&year={year_slug}"
    print(f"🚀 Trimler çekiliyor: {brand_slug} -> {model_slug} -> {year_slug}")

    for attempt in range(retries):
        response = requests.get(url)

        if response.status_code == 200:
            try:
                data = response.json()
                if "result" in data and "data" in data["result"] and len(data["result"]["data"]) > 0:
                    trims = []
                    for trim in data["result"]["data"]:
                        if isinstance(trim, dict):
                            # `year_ranges` yerine doğrudan `start_year` ve `end_year` kontrol et
                            start_year = trim.get("start_year", "???")
                            end_year = trim.get("end_year", "???")

                            if start_year == "???" and end_year == "???":
                                # Eğer `start_year` ve `end_year` API'den gelmemişse, year_ranges'ı kontrol et
                                year_range = trim.get("year_ranges", ["???-???"])[0]
                                start_year, end_year = year_range.split("-") if "-" in year_range else (
                                year_range, "???")

                            production_info = f"{start_year}-{end_year}"
                            trim_name = f"{trim.get('name', 'Bilinmeyen Trim')} {production_info}"
                        else:
                            print(f"⚠️ Beklenmeyen veri formatı! trim = {trim}")
                            trim_name = "Bilinmeyen Trim ???-???"
                            production_info = "???-???"

                        print(f"✅ Trim bulundu: {trim_name} (Slug: {trim.get('slug', 'no-slug')})")

                        trims.append({
                            "slug": trim.get("slug", "no-slug"),
                            "name": trim_name,
                            "start_year": start_year,
                            "end_year": end_year
                        })
                    print(f"📌 {brand_slug} -> {model_slug} -> {year_slug}: {len(trims)} trim bulundu.")
                    return trims
                else:
                    print(f"⚠️ Trim bulunamadı: {brand_slug} -> {model_slug} -> {year_slug}")
                    return []
            except ValueError:
                print(f"❌ JSON parse hatası: {brand_slug} -> {model_slug} -> {year_slug}")
                return []
        elif response.status_code in [429, 500, 502, 503]:
            retry_after = int(response.headers.get("Retry-After", 2))
            print(f"⏳ Sunucu hatası ({response.status_code}). {retry_after}s bekleniyor... ({brand_slug} -> {model_slug} -> {year_slug})")
            time.sleep(retry_after)
        elif response.status_code == 400:
            print(f"❌ API 400 Bad Request: Trim verisi alınamıyor ({brand_slug} -> {model_slug} -> {year_slug})")
            save_progress(brand_slug, model_slug, year_slug)
            print(f"📌 Program durduruldu. Kaldığı yer: {brand_slug} -> {model_slug} -> {year_slug}")
            exit(1)
        else:
            print(f"❌ /trims isteği başarısız! HTTP {response.status_code} - {brand_slug} -> {model_slug} -> {year_slug}")
            return []

    print(f"❌ {retries} deneme sonrası başarısız: {brand_slug} -> {model_slug} -> {year_slug}")
    return []


def save_trims_to_db(trim_batch):
    """Trim verilerini veritabanına kaydeder (100 trimde bir)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.executescript('''
            CREATE TABLE IF NOT EXISTS trims (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id INTEGER,
                year_slug TEXT,
                slug TEXT NOT NULL,
                name TEXT NOT NULL,
                FOREIGN KEY(model_id) REFERENCES models(id),
                UNIQUE(model_id, year_slug, slug) ON CONFLICT IGNORE
            );
        ''')

    cursor.executemany("""
            INSERT INTO trims (model_id, year_slug, slug, name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(model_id, year_slug, slug) DO NOTHING;
        """, [(tr["model_id"], tr["year_slug"], tr["slug"], tr["name"]) for tr in trim_batch])

    conn.commit()
    conn.close()
    print(f"✅ {len(trim_batch)} trim işleme alındı. Zaten var olanlar atlandı.")




def main():
    all_brands = get_all_models_years()
    if not all_brands:
        print("❌ Veritabanında brand-model-year verisi yok.")
        return

    progress = load_progress()

    # Bayraklar
    foundBrand = (progress["brand_slug"] is None)
    foundModel = (progress["model_slug"] is None)
    foundYear = (progress["year_slug"] is None)

    for b in all_brands:
        brand_slug = b["slug"]

        # Eğer henüz markayı bulmadıysak
        if not foundBrand:
            if brand_slug == progress["brand_slug"]:
                # Tam kaldığımız markaya geldik
                foundBrand = True
            else:
                # Bu marka, progress'deki markaya ulaşana kadar atlıyoruz
                continue

        for m in b["models"]:
            model_slug = m["slug"]

            # Eğer markayı bulduk ama modeli bulmadıysak
            if not foundModel:
                if model_slug == progress["model_slug"]:
                    # Kaldığımız modele geldik
                    foundModel = True
                else:
                    # Model henüz progress'deki modele gelmedi
                    continue

            for y in m["years"]:
                year_slug = y["slug"]

                # Eğer modeli bulduk ama yılı bulmadıysak
                if not foundYear:
                    if year_slug == progress["year_slug"]:
                        # Tam kaldığımız yıla geldik
                        foundYear = True
                    else:
                        continue

                # ⏰ Artık brand->model->year tam eşleşme sağlandı, bu kombinasyonu işleyebiliriz
                print(f"🚀 İşleniyor: {brand_slug} -> {model_slug} -> {year_slug}")
                trims = fetch_trims(brand_slug, model_slug, year_slug)

                if trims:
                    # Trimleri veritabanına ekleyelim
                    save_trims_to_db([
                        {
                            "model_id": m["id"],
                            "year_slug": year_slug,
                            "slug": t["slug"],
                            "name": t["name"]
                        }
                        for t in trims
                    ])

                # Bu yıl tamamlandı, progress'i güncelle
                save_progress(brand_slug, model_slug, year_slug)

            # Tüm yıllar bittiğinde, bir sonraki model için foundYear'ı resetlememize gerek yok;
            # ÇÜNKÜ bir sonraki model döngüsünde "if not foundModel" devre dışı (True) olduktan sonra
            # her yıla girecek.

        # Bir sonraki marka için foundModel = True, foundYear = True ayarlayabiliriz (zaten bulduk)
        foundModel = True
        foundYear = True


if __name__ == "__main__":
    main()


