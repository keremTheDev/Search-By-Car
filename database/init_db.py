import sqlite3
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")

from config import DB_PATH

def initialize_database():
    """Veritabanını oluşturur ve şemayı uygular."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS brands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            slug TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand_id INTEGER,
            name TEXT NOT NULL,
            slug TEXT NOT NULL,
            FOREIGN KEY(brand_id) REFERENCES brands(id),
            UNIQUE(brand_id, name, slug)
        );
        
        CREATE TABLE IF NOT EXISTS years (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id INTEGER,
            name TEXT NOT NULL,
            slug TEXT NOT NULL,
            FOREIGN KEY(model_id) REFERENCES models(id),
            UNIQUE(model_id, name, slug)
        );
        
        CREATE TABLE IF NOT EXISTS trims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id INTEGER,
            year_slug TEXT,
            slug TEXT NOT NULL,
            name TEXT NOT NULL,
            FOREIGN KEY(model_id) REFERENCES models(id),
            UNIQUE(model_id, year_slug, slug)
        );
        
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
        )
    ''')

    conn.commit()
    conn.close()
    print("Veritabanı başarıyla oluşturuldu ve şema uygulandı.")

if __name__ == "__main__":
    initialize_database()
