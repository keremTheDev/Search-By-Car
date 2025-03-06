import os
from dotenv import load_dotenv

# API Ana URL
API_BASE_URL = os.getenv('API_BASE_URL')

# API endpoint'leri
ENDPOINTS = {
    "brands": "GetCarMakers/",
    "models": "GetCarModels/",
    "years": "GetCarYears/",
    "trims": "GetCarTrims/",
    "tires": "GetCarTires/"
}

# Ana dizinler
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(BASE_DIR, "database", "car_data.db")

# JSON geçici dosyaları
TEMP_FILES = {
    "brands": os.path.join(DATA_DIR, "brands.json"),
    "models": os.path.join(DATA_DIR, "models.json"),
    "years": os.path.join(DATA_DIR, "years.json"),
    "trims": os.path.join(DATA_DIR, "trims1.json"),
    "tires": os.path.join(DATA_DIR, "tires.json")
}

