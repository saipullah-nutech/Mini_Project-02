# Mini Project 2 — End-to-End Data Pipeline

API artikel dan HR attrition menggunakan FastAPI dan PostgreSQL.

## Tabel

- ai_engineer.articles_saipul_ai2
- ai_engineer.raw_attrition_saipul_ai2

## Instalasi

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

## Konfigurasi

Salin .env.example menjadi .env dan isi koneksi database serta autentikasi.

## Menjalankan API

.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000

## Endpoint Tugas

- GET /articles/search
- GET /articles/stats
- GET /attrition/department/{dept_name}
- GET /attrition/risk-profile

Endpoint terlindungi menerima API key atau JWT Bearer token.