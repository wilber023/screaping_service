"""
Script de arranque local para pruebas sin Docker/Postgres/Redis.
Usa SQLite, sin Redis (caching deshabilitado), sin S3.
Ejecutar desde la raiz del proyecto:
    .venv\Scripts\python run_local.py
"""
import os
import sys
import unittest.mock as _mock

# ─── Variables de entorno ANTES de cualquier import del módulo ────────────────
os.environ.setdefault("DATABASE_URL", "sqlite:///./local_test.db")
os.environ.setdefault("REDIS_URL", "")                 # caching deshabilitado
os.environ.setdefault("API_KEY_FRONTEND", "localfrontendkey1234567890abcdef1234567890abcdef1234567890ab")
os.environ.setdefault("API_KEY_LLM",      "localllmkey1234567890abcdef1234567890abcdef1234567890abcdef12")
os.environ.setdefault("JWT_SECRET",       "local_jwt_secret_for_testing_minimum_32_characters_long")
os.environ.setdefault("JWT_ALGORITHM",    "HS256")
os.environ.setdefault("JWT_EXPIRATION_MINUTES", "1440")
os.environ.setdefault("DEBUG", "true")

# ─── Mock de boto3/S3 para no necesitar AWS ───────────────────────────────────
sys.modules.setdefault("boto3",             _mock.MagicMock())
sys.modules.setdefault("botocore",          _mock.MagicMock())
sys.modules.setdefault("botocore.exceptions", _mock.MagicMock())

# ─── Crear tablas SQLite ──────────────────────────────────────────────────────
print("[setup] Creando tablas en SQLite...")
from scraping.models.base import Base
from scraping.models.product import Product
from scraping.models.price_history import PriceHistory
from scraping.storage.database import engine, SessionLocal

Base.metadata.create_all(bind=engine)
print("[setup] Tablas creadas: products, price_history")

# ─── Sembrar productos de ejemplo ─────────────────────────────────────────────
from datetime import datetime
import hashlib, uuid

db = SessionLocal()
existing = db.query(Product).count()
if existing == 0:
    print("[setup] Sembrando productos de ejemplo...")
    sample_products = [
        {
            "id": str(uuid.uuid4()),
            "source": "syngenta",
            "source_url": "https://www.syngenta.com.mx/productos/amistar-top",
            "name": "Amistar Top 325 SC",
            "manufacturer": "Syngenta",
            "active_ingredient": "Azoxistrobina 200 g/L + Difenoconazol 125 g/L",
            "product_type": "fungicida",
            "target_crops": ["tomate", "papa", "uva", "fresa"],
            "target_diseases": ["tizon tardio", "alternaria", "botrytis", "oidio"],
            "price_amount": 1250.00, "price_currency": "MXN", "price_original_currency": "MXN",
            "price_last_updated": datetime.utcnow(),
            "stock_status": "in_stock", "stock_quantity": None,
            "availability_regions": ["MX"], "scraped_at": datetime.utcnow(),
            "hash_dedup": hashlib.sha256(b"syngenta|amistar top 325 sc|azoxistrobina").hexdigest(),
            "is_active": True,
        },
        {
            "id": str(uuid.uuid4()),
            "source": "bayer",
            "source_url": "https://www.cropscience.bayer.mx/productos/previcur-energy",
            "name": "Previcur Energy",
            "manufacturer": "Bayer",
            "active_ingredient": "Fosetil aluminio 310 g/L + Propamocarb 530 g/L",
            "product_type": "fungicida",
            "target_crops": ["tomate", "papa", "calabaza"],
            "target_diseases": ["tizon tardio", "mildiu", "damping-off"],
            "price_amount": 890.00, "price_currency": "MXN", "price_original_currency": "MXN",
            "price_last_updated": datetime.utcnow(),
            "stock_status": "in_stock", "stock_quantity": 30,
            "availability_regions": ["MX"], "scraped_at": datetime.utcnow(),
            "hash_dedup": hashlib.sha256(b"bayer|previcur energy|fosetil").hexdigest(),
            "is_active": True,
        },
        {
            "id": str(uuid.uuid4()),
            "source": "basf",
            "source_url": "https://agriculture.basf.com/mx/es/productos/cabrio-duo.html",
            "name": "Cabrio Duo",
            "manufacturer": "BASF",
            "active_ingredient": "Piraclostrobina 133 g/L + Metiram 467 g/L",
            "product_type": "fungicida",
            "target_crops": ["tomate", "papa", "maiz", "uva"],
            "target_diseases": ["tizon tardio", "alternaria", "antracnosis"],
            "price_amount": 1100.00, "price_currency": "MXN", "price_original_currency": "MXN",
            "price_last_updated": datetime.utcnow(),
            "stock_status": "in_stock", "stock_quantity": None,
            "availability_regions": ["MX"], "scraped_at": datetime.utcnow(),
            "hash_dedup": hashlib.sha256(b"basf|cabrio duo|piraclostrobina").hexdigest(),
            "is_active": True,
        },
        {
            "id": str(uuid.uuid4()),
            "source": "mercadolibre",
            "source_url": "https://www.mercadolibre.com.mx/karate-zeon",
            "name": "Karate Zeon 250 CS",
            "manufacturer": "Syngenta",
            "active_ingredient": "Lambda-cialotrina 250 g/L",
            "product_type": "insecticida",
            "target_crops": ["tomate", "maiz", "papa", "frijol"],
            "target_diseases": ["trips", "mosca blanca", "gusano cogollero", "afidos"],
            "price_amount": 620.00, "price_currency": "MXN", "price_original_currency": "MXN",
            "price_last_updated": datetime.utcnow(),
            "stock_status": "in_stock", "stock_quantity": 15,
            "availability_regions": ["MX"], "scraped_at": datetime.utcnow(),
            "hash_dedup": hashlib.sha256(b"mercadolibre|karate zeon 250 cs|lambda-cialotrina").hexdigest(),
            "is_active": True,
        },
        {
            "id": str(uuid.uuid4()),
            "source": "agrofy",
            "source_url": "https://www.agrofy.com.ar/agroquimicos/herbicidas/glifosato-48",
            "name": "Glifosato 48% SL",
            "manufacturer": "AgroFlex",
            "active_ingredient": "Glifosato 480 g/L",
            "product_type": "herbicida",
            "target_crops": ["maiz", "soja", "frijol"],
            "target_diseases": ["malezas de hoja ancha", "gramineas anuales"],
            "price_amount": 280.00, "price_currency": "MXN", "price_original_currency": "ARS",
            "price_last_updated": datetime.utcnow(),
            "stock_status": "in_stock", "stock_quantity": 100,
            "availability_regions": ["AR", "MX"], "scraped_at": datetime.utcnow(),
            "hash_dedup": hashlib.sha256(b"agrofy|glifosato 48% sl|glifosato").hexdigest(),
            "is_active": True,
        },
        {
            "id": str(uuid.uuid4()),
            "source": "syngenta",
            "source_url": "https://www.syngenta.com.mx/productos/actara",
            "name": "Actara 25 WG",
            "manufacturer": "Syngenta",
            "active_ingredient": "Tiametoxam 250 g/kg",
            "product_type": "insecticida",
            "target_crops": ["tomate", "papa", "naranja", "uva", "fresa"],
            "target_diseases": ["mosca blanca", "afidos", "trips", "escama"],
            "price_amount": 780.00, "price_currency": "MXN", "price_original_currency": "MXN",
            "price_last_updated": datetime.utcnow(),
            "stock_status": "in_stock", "stock_quantity": None,
            "availability_regions": ["MX"], "scraped_at": datetime.utcnow(),
            "hash_dedup": hashlib.sha256(b"syngenta|actara 25 wg|tiametoxam").hexdigest(),
            "is_active": True,
        },
    ]
    for p in sample_products:
        db.add(Product(**p))
    db.commit()
    print(f"[setup] {len(sample_products)} productos sembrados en SQLite")
else:
    print(f"[setup] Ya existen {existing} productos en la base de datos")

db.close()

# ─── Mostrar credenciales de prueba ──────────────────────────────────────────
from scraping.auth.jwt_auth import create_access_token

token_aprendiz   = create_access_token("user-test-001", "aprendiz")
token_agricultor = create_access_token("user-test-002", "agricultor_experimentado")
token_admin      = create_access_token("user-test-003", "admin")

print("\n" + "="*60)
print(" CREDENCIALES DE PRUEBA")
print("="*60)
print(f"\n  X-API-Key:      {os.environ['API_KEY_FRONTEND']}")
print(f"\n  JWT aprendiz:   {token_aprendiz}")
print(f"  JWT agricultor: {token_agricultor}")
print(f"  JWT admin:      {token_admin}")
print("\n  http://localhost:8000/health")
print("  http://localhost:8000/docs")
print("  http://localhost:8000/products")
print("="*60)
print("\n  Iniciando API en http://localhost:8000 ...\n")

# ─── Arrancar uvicorn ─────────────────────────────────────────────────────────
import uvicorn
uvicorn.run("scraping.api.main:app", host="0.0.0.0", port=8000, reload=False, log_level="info")