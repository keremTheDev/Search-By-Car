import requests
import sqlite3
import time
import json
import os
from config import API_BASE_URL, ENDPOINTS, DB_PATH

BATCH_SIZE = 100
PROGRESS_FILE = "progress_tires.json"


# ===================== PROGRESS OKUMA / YAZMA =====================
def load_progress():
    """progress_tires.json dosyasından son kaldığı trim_id'yi okur."""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r") as f:
                data = json.load(f)
                return data.get("last_trim_id")
        except (json.JSONDecodeError, KeyError):
            print("⚠️ progress_tires.json bozuk veya geçersiz. Sıfırdan başlatılıyor.")
    return None


def save_progress(trim_id):
    """progress_tires.json dosyasına son işlenen trim_id'yi kaydeder."""
    with open(PROGRESS_FILE, "w") as f:
        json.dump({"last_trim_id": trim_id}, f)
    print(f"💾 Progress kaydedildi: last_trim_id={trim_id}")


# ===================== TRIM OKUMA =====================
def get_all_trims():
    """
    Veritabanındaki trim kayıtlarını okur ve
    brand_slug, model_slug, year_slug, trim_slug bilgileriyle döndürür.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    rows = cursor.execute("""
        SELECT 
            t.id AS trim_id,
            t.model_id,
            t.year_slug,
            t.slug AS trim_slug,
            m.slug AS model_slug,
            b.slug AS brand_slug
        FROM trims t
        JOIN models m ON t.model_id = m.id
        JOIN brands b ON m.brand_id = b.id
        ORDER BY t.id
    """).fetchall()

    conn.close()

    trims = []
    for (trim_id, model_id, year_slug, trim_slug, model_slug, brand_slug) in rows:
        trims.append({
            "trim_id": trim_id,
            "model_id": model_id,
            "year_slug": year_slug,
            "trim_slug": trim_slug,
            "model_slug": model_slug,
            "brand_slug": brand_slug
        })
    return trims


# ===================== API'DEN LASTİK BİLGİSİ ÇEKME =====================
def fetch_tires(brand_slug, model_slug, year_slug, trim_slug, retries=3):
    """
    API'den [brand_slug, model_slug, year_slug, trim_slug] kombinasyonu için
    lastik (tire) ve jant (rim) bilgisi çeker.
    Dönen veriden wheels listesi ve technical bilgisi parse edilir.
    """
    url = (
        API_BASE_URL + ENDPOINTS["tires"] +
        f"?make={brand_slug}&model={model_slug}&year={year_slug}&trim={trim_slug}&user_key=undefined"
    )

    print(f"🚗 Lastikler çekiliyor: {brand_slug} -> {model_slug} -> {year_slug} -> Trim: {trim_slug}")

    for attempt in range(retries):
        resp = requests.get(url)
        if resp.status_code == 200:
            try:
                data = resp.json()
                if "result" in data and "data" in data["result"]:
                    data_list = data["result"]["data"]
                    if not data_list:
                        print(f"⚠️ /tires: 'data' boş -> {brand_slug}-{model_slug}-{year_slug}-{trim_slug}")
                        return []

                    # İlk kayıttaki wheels ve technical bilgisi
                    wheels = data_list[0].get("wheels") or []
                    technical = data_list[0].get("technical") or {}
                    stud_holes = technical.get("stud_holes", None)
                    pcd = technical.get("pcd", None)

                    tire_data = []

                    for wheel in wheels:
                        wheel = wheel or {}

                        # FRONT
                        front = wheel.get("front") or {}
                        front_tire = {
                            "position": "front",
                            "tire_width": front.get("tire_width"),
                            "tire_aspect_ratio": front.get("tire_aspect_ratio"),
                            "rim_diameter": front.get("rim_diameter"),
                            "rim_width": front.get("rim_width"),
                            "rim_offset": front.get("rim_offset"),
                            "rim": front.get("rim", ""),
                            "tire": front.get("tire", ""),
                            "tire_full": front.get("tire_full", ""),
                            "stud_holes": stud_holes,
                            "pcd": pcd
                        }

                        # REAR
                        rear = wheel.get("rear") or {}
                        rear_tire = {
                            "position": "rear",
                            "tire_width": rear.get("tire_width"),
                            "tire_aspect_ratio": rear.get("tire_aspect_ratio"),
                            "rim_diameter": rear.get("rim_diameter"),
                            "rim_width": rear.get("rim_width"),
                            "rim_offset": rear.get("rim_offset"),
                            "rim": rear.get("rim", ""),
                            "tire": rear.get("tire", ""),
                            "tire_full": rear.get("tire_full", ""),
                            "stud_holes": stud_holes,
                            "pcd": pcd
                        }

                        tire_data.append(front_tire)
                        tire_data.append(rear_tire)

                    print(f"✅ Lastik verisi alındı: {brand_slug}-{model_slug}-{year_slug}-{trim_slug}")
                    return tire_data
                else:
                    print(f"⚠️ /tires API yanıtında 'result.data' yok: {brand_slug}-{model_slug}-{year_slug}-{trim_slug}")
                    return []
            except ValueError:
                print(f"❌ JSON parse hatası: {brand_slug}-{model_slug}-{year_slug}-{trim_slug}")
                return []
        elif resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 2))
            print(f"⏳ 429 Too Many Requests: {retry_after}s bekleniyor...")
            time.sleep(retry_after)
        else:
            print(f"❌ /tires isteği başarısız! HTTP {resp.status_code}")
            return []

    print(f"❌ {retries} deneme sonrası başarısız: {brand_slug}-{model_slug}-{year_slug}-{trim_slug}")
    return []


# ===================== TIRES TABLOSUNU (SİLMEDEN) HAZIRLAMA =====================
def initialize_tires_table(cursor):
    """
    'tires' tablosunu sadece yoksa oluşturur.
    Tabloya UNIQUE constraint eklenmiştir, ON CONFLICT IGNORE ile duplicate veriler atlanır.
    """
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS tires (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trim_id INTEGER NOT NULL,
            position TEXT NOT NULL,
            tire_width INTEGER,
            tire_aspect_ratio INTEGER,
            rim_diameter INTEGER,
            rim_width FLOAT,
            rim_offset INTEGER,
            rim TEXT,
            tire TEXT,
            tire_full TEXT,
            stud_holes INTEGER,
            pcd INTEGER,
            FOREIGN KEY(trim_id) REFERENCES trims(id),
            UNIQUE(trim_id, position, tire_full) ON CONFLICT IGNORE
        );
    ''')
    print("✅ 'tires' tablosu hazır veya zaten mevcut.")


# ===================== VERİ KAYDETME (ON CONFLICT) =====================
def save_tires_to_db(trims):
    """
    1) 'tires' tablosu yoksa oluşturur; varsa dokunmaz.
    2) Tüm trimler için lastik verilerini çek.
    3) ON CONFLICT ile duplicate kayıtları atla.
    4) Kaldığı yerden devam etmek için progress mekanizması kullan.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Tabloyu yoksa oluştur
    initialize_tires_table(cursor)

    last_trim_id = load_progress()
    skip_mode = True if last_trim_id else False
    insert_count = 0

    for trim in trims:
        current_trim_id = trim["trim_id"]

        # Daha önce işlenen trim'e gelene kadar atla
        if skip_mode:
            if current_trim_id == last_trim_id:
                skip_mode = False
            continue

        # API'den lastik/jant verisi çek
        tire_list = fetch_tires(
            trim["brand_slug"],
            trim["model_slug"],
            trim["year_slug"],
            trim["trim_slug"]
        )

        if tire_list:
            for tire in tire_list:
                cursor.execute("""
                    INSERT INTO tires (
                        trim_id, position, 
                        tire_width, tire_aspect_ratio,
                        rim_diameter, rim_width, rim_offset,
                        rim, tire, tire_full,
                        stud_holes, pcd
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(trim_id, position, tire_full) DO NOTHING
                """, (
                    current_trim_id,
                    tire["position"] or "unknown",
                    tire["tire_width"],
                    tire["tire_aspect_ratio"],
                    tire["rim_diameter"],
                    tire["rim_width"],
                    tire["rim_offset"],
                    tire["rim"],
                    tire["tire"],
                    tire["tire_full"],
                    tire["stud_holes"],
                    tire["pcd"]
                ))
                insert_count += 1

                if insert_count % BATCH_SIZE == 0:
                    conn.commit()
                    print(f"📝 {insert_count} satır eklendi, ara commit yapıldı.")

        # Bu trim tamamlandı, progress'i güncelle
        save_progress(current_trim_id)

    conn.commit()
    conn.close()
    print(f"✅ İşlem bitti! Toplam {insert_count} satır eklendi.")


def main():
    trims = get_all_trims()
    if not trims:
        print("❌ Hiç trim bulunamadı.")
        return

    # Artık tabloyu silmeden sadece varsa oluşturuyor
    # ve kaldığı yerden devam ediyor
    save_tires_to_db(trims)


if __name__ == "__main__":
    main()
