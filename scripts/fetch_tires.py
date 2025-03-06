import requests
import sqlite3
import time
from config import API_BASE_URL, ENDPOINTS, DB_PATH


def get_all_trims():
    """Veritabanındaki trim bilgilerini alır."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    rows = cursor.execute("""
        SELECT 
            t.id AS trim_id, t.model_id, t.year_slug, t.slug AS trim_slug,
            m.slug AS model_slug, b.slug AS brand_slug
        FROM trims t
        JOIN models m ON t.model_id = m.id
        JOIN brands b ON m.brand_id = b.id
        ORDER BY b.id, m.id, t.id
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


def fetch_tires(brand_slug, model_slug, year_slug, trim_slug, retries=3):
    """Bir trim (alt model) için lastik-jant bilgilerini API'den çeker ve retry mekanizması uygular."""
    url = API_BASE_URL + ENDPOINTS["tires"] + f"?make={brand_slug}&model={model_slug}&year={year_slug}&trim={trim_slug}&user_key=undefined"

    print(f"🚗 Lastikler çekiliyor: {brand_slug} -> {model_slug} -> {year_slug} -> Trim: {trim_slug}")

    for attempt in range(retries):
        response = requests.get(url)

        if response.status_code == 200:
            try:
                data = response.json()
                if "result" in data and isinstance(data["result"], list) and len(data["result"]) > 0:
                    wheels = data["result"][0].get("wheels", [])
                    tire_data = []

                    print(f"✅ Lastik verisi başarıyla çekildi ({brand_slug}-{model_slug}-{year_slug}-{trim_slug})")

                    for wheel in wheels:
                        # Ön lastik bilgisi
                        front = wheel.get("front", {})
                        front_tire_pressure = front.get("tire_pressure", {}) or {}
                        front_psi = front_tire_pressure.get("psi", None)

                        front_tire = {
                            "position": "front",
                            "tire_pressure_psi": front_psi if front_psi is not None else "Bilinmiyor",
                            "rim": front.get("rim", "Bilinmiyor"),
                            "tire": front.get("tire", "Bilinmiyor"),
                            "load_index": front.get("load_index", "Bilinmiyor"),
                            "speed_index": front.get("speed_index", "Bilinmiyor")
                        }

                        # Arka lastik bilgisi
                        rear = wheel.get("rear", {})
                        rear_tire_pressure = rear.get("tire_pressure", {}) or {}
                        rear_psi = rear_tire_pressure.get("psi", None)

                        if not rear.get("tire"):  # Eğer lastik boşsa
                            rear_tire = {
                                "position": "rear",
                                "tire_pressure_psi": rear_psi if rear_psi is not None else "Bilinmiyor",
                                "rim": "YOK",
                                "tire": "YOK",
                                "load_index": "YOK",
                                "speed_index": "YOK"
                            }
                        else:
                            rear_tire = {
                                "position": "rear",
                                "tire_pressure_psi": rear_psi if rear_psi is not None else "Bilinmiyor",
                                "rim": rear.get("rim", "Bilinmiyor"),
                                "tire": rear.get("tire", "Bilinmiyor"),
                                "load_index": rear.get("load_index", "Bilinmiyor"),
                                "speed_index": rear.get("speed_index", "Bilinmiyor")
                            }

                        tire_data.append(front_tire)
                        tire_data.append(rear_tire)

                    return tire_data

                else:
                    print(f"⚠️ /tires API yanıtında lastik bilgisi bulunamadı: {brand_slug}-{model_slug}-{year_slug}-{trim_slug}")
                    return []

            except ValueError:
                print(f"❌ JSON parse hatası: {brand_slug}-{model_slug}-{year_slug}-{trim_slug}")
                return []
        elif response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 2))
            print(f"⏳ 429 Too Many Requests: {retry_after}s bekleniyor... ({brand_slug}-{model_slug}-{year_slug}-{trim_slug})")
            time.sleep(retry_after)
        else:
            print(f"❌ /tires isteği başarısız! HTTP {response.status_code} - {brand_slug}-{model_slug}-{year_slug}-{trim_slug}")
            return []

    print(f"❌ {retries} deneme sonrası başarısız: {brand_slug}-{model_slug}-{year_slug}-{trim_slug}")
    return []


def save_tires_to_db(trims):
    """Lastik verilerini veritabanına kaydeder."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS tires (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trim_id INTEGER,
            position TEXT NOT NULL,
            tire_pressure_psi INTEGER,
            rim TEXT,
            tire TEXT,
            load_index TEXT,
            speed_index TEXT,
            FOREIGN KEY(trim_id) REFERENCES trims(id)
        );
    ''')

    for trim in trims:
        trim_id = trim["trim_id"]
        tires = fetch_tires(trim["brand_slug"], trim["model_slug"], trim["year_slug"], trim["trim_slug"])

        if tires:
            for tire in tires:
                cursor.execute("""
                    INSERT INTO tires (trim_id, position, tire_pressure_psi, rim, tire, load_index, speed_index)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    trim_id,
                    tire["position"],
                    tire["tire_pressure_psi"],
                    tire["rim"],
                    tire["tire"],
                    tire["load_index"],
                    tire["speed_index"]
                ))

    conn.commit()
    conn.close()
    print("✅ Tüm lastik verileri başarıyla kaydedildi!")


def main():
    trims = get_all_trims()
    if not trims:
        print("❌ Veritabanında trim verisi yok.")
        return

    save_tires_to_db(trims)


if __name__ == "__main__":
    main()
