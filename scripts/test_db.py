import sqlite3
from config import DB_PATH

def test_trims_and_tires():
    """trims ve tires tablolarını test etmek için örnek veri ekler ve doğrular."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1) Tabloları kontrol et
    tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
    print("📌 Veritabanındaki tablolar:", tables)

    # 2) trims tablosuna örnek veri ekle
    # trims eklemek için önce bir brand, model, year kaydı lazım
    # eğer yoksa ekleyelim (örnek)

    cursor.execute("INSERT OR IGNORE INTO brands (name, slug) VALUES (?, ?)", ("Test Brand", "test-brand"))
    brand_id = cursor.execute("SELECT id FROM brands WHERE slug = ?", ("test-brand",)).fetchone()[0]

    cursor.execute("INSERT OR IGNORE INTO models (brand_id, name, slug) VALUES (?, ?, ?)",
                   (brand_id, "Test Model", "test-model"))
    model_id = cursor.execute("SELECT id FROM models WHERE slug = ?", ("test-model",)).fetchone()[0]

    cursor.execute("INSERT OR IGNORE INTO years (model_id, name, slug) VALUES (?, ?, ?)",
                   (model_id, "2023", "2023"))
    # year tablosuna eklenen kaydı okuyalım
    cursor.execute("SELECT id FROM years WHERE model_id = ? AND slug = ?", (model_id, "2023"))
    year_row = cursor.fetchone()
    if year_row:
        year_id = year_row[0]
    else:
        year_id = None  # Normalde buraya düşmeyecektir

    # Şimdi trims tablosuna ekleyeceğiz
    cursor.execute("INSERT OR IGNORE INTO trims (model_id, year_slug, slug, name) VALUES (?, ?, ?, ?)",
                   (model_id, "2023", "test-trim", "Test Trim 2023"))
    cursor.execute("SELECT id FROM trims WHERE slug = ?", ("test-trim",))
    trim_id = cursor.fetchone()[0]

    # 3) tires tablosuna örnek veri ekle
    # Örneğin ön lastik ve arka lastik verisi
    cursor.execute("""
        INSERT INTO tires (trim_id, position, tire_pressure_psi, rim, tire, load_index, speed_index)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (trim_id, "front", 30, "8Jx18 ET34 5x110", "235/60ZR18", "103", "W"))

    cursor.execute("""
        INSERT INTO tires (trim_id, position, tire_pressure_psi, rim, tire, load_index, speed_index)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (trim_id, "rear", 33, "", "", None, None))

    conn.commit()

    # 4) Eklenen verileri geri okuyalım
    print("\n📌 trims tablosundaki veriler:")
    for row in cursor.execute("SELECT * FROM trims"):
        print(row)

    print("\n📌 tires tablosundaki veriler:")
    for row in cursor.execute("SELECT * FROM tires"):
        print(row)

    conn.close()

if __name__ == "__main__":
    test_trims_and_tires()
