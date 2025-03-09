import unittest
from unittest.mock import patch, MagicMock
import os
import json

from fetch_trims import fetch_trims, save_progress, load_progress, PROGRESS_FILE


class TestFetchTrims(unittest.TestCase):

    def setUp(self):
        """Test öncesi hazırlık: progress.json dosyasını temizle"""
        if os.path.exists(PROGRESS_FILE):
            os.remove(PROGRESS_FILE)

    def tearDown(self):
        """Test sonrası temizleme: progress.json dosyasını sil"""
        if os.path.exists(PROGRESS_FILE):
            os.remove(PROGRESS_FILE)

    @patch("fetch_trims.requests.get")
    def test_fetch_trims_success(self, mock_get):
        """✅ API başarılı yanıt dönerse trimlerin düzgün çekildiğini test eder"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Kod "result" -> "data" şeklinde bir sözlük ve liste bekliyor
        mock_response.json.return_value = {
            "result": {
                "data": [
                    {
                        "slug": "test-trim-1",
                        "name": "Trim 1",
                        "generation": "Gen 1",
                        "production_start_year": 2020,
                        "production_end_year": 2022
                    },
                    {
                        "slug": "test-trim-2",
                        "name": "Trim 2",
                        "generation": "Gen 2",
                        "production_start_year": 2018,
                        "production_end_year": 2021
                    }
                ]
            }
        }
        mock_get.return_value = mock_response

        trims = fetch_trims("test-brand", "test-model", "2021")

        self.assertEqual(len(trims), 2)
        self.assertEqual(trims[0]["slug"], "test-trim-1")
        self.assertEqual(trims[1]["slug"], "test-trim-2")

    @patch("fetch_trims.requests.get")
    def test_fetch_trims_400_error(self, mock_get):
        """❌ API 400 hatası dönerse programın kapandığını ve progress.json dosyasına yazıldığını test eder"""
        mock_response = MagicMock()
        mock_response.status_code = 400
        # JSON içeriği önemli değil, 400 hatasında kod exit(1) yapıyor
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response

        with self.assertRaises(SystemExit) as cm:
            fetch_trims("test-brand", "test-model", "2021")

        # Programın exit(1) ile kapanması bekleniyor
        self.assertEqual(cm.exception.code, 1)

        # progress.json dosyasının yazılıp yazılmadığını kontrol et
        self.assertTrue(os.path.exists(PROGRESS_FILE))

        with open(PROGRESS_FILE, "r") as f:
            progress_data = json.load(f)

        self.assertEqual(progress_data["brand_slug"], "test-brand")
        self.assertEqual(progress_data["model_slug"], "test-model")
        self.assertEqual(progress_data["year_slug"], "2021")

    @patch("fetch_trims.requests.get")
    def test_fetch_trims_429_error(self, mock_get):
        """⏳ API 429 hatası dönerse bekleyip tekrar denediğini test eder"""
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {"Retry-After": "1"}

        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        # Başarılı yanıtta yine "result": { "data": [...] } formatı
        mock_response_200.json.return_value = {
            "result": {
                "data": [
                    {
                        "slug": "test-trim-3",
                        "name": "Trim 3",
                        "generation": "Gen 3",
                        "production_start_year": 2019,
                        "production_end_year": 2023
                    }
                ]
            }
        }

        # İlk çağrıda 429 hatası, ikinci çağrıda 200 yanıtı
        mock_get.side_effect = [mock_response_429, mock_response_200]

        trims = fetch_trims("test-brand", "test-model", "2021")

        self.assertEqual(len(trims), 1)
        self.assertEqual(trims[0]["slug"], "test-trim-3")

    @patch("fetch_trims.requests.get")
    def test_fetch_trims_500_error(self, mock_get):
        """❌ API 500 hatası dönerse belirli bir tekrar denemesinden sonra hata verdiğini test eder"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        # JSON içeriği önemli değil, 500'de kod boş liste dönüyor
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response

        trims = fetch_trims("test-brand", "test-model", "2021")

        # 500 hatasında, trim listesinin boş dönmesi bekleniyor
        self.assertEqual(len(trims), 0)

    def test_save_and_load_progress(self):
        """📌 progress.json dosyasının düzgün çalıştığını test eder"""
        save_progress("test-brand", "test-model", "2022")

        progress_data = load_progress()
        self.assertEqual(progress_data["brand_slug"], "test-brand")
        self.assertEqual(progress_data["model_slug"], "test-model")
        self.assertEqual(progress_data["year_slug"], "2022")


if __name__ == "__main__":
    unittest.main()
