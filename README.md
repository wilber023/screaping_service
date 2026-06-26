# AgroGraph — Microservicio de Catálogo Agrícola

Microservicio de scraping, normalización y API REST de productos fitosanitarios para el sistema **AgroGraph**. Extrae productos **reales** de marketplaces en línea (Amazon México), los normaliza y los expone como API para el módulo de diagnóstico por IA y el frontend web.

> **Los productos del catálogo son reales.** Provienen de páginas públicas de venta en línea en México, con precios, imágenes y descripciones tal como aparecen en los sitios de origen. Los únicos productos con datos de referencia curada son los etiquetados como `source: syngenta / bayer / basf / mercadolibre` en el seed inicial.

---

## Tabla de contenidos

1. [Descripción general](#1-descripción-general)
2. [Técnica de extracción — Qué es y cómo funciona el web scraping](#2-técnica-de-extracción)
3. [Fuentes de datos y productos reales](#3-fuentes-de-datos)
4. [Pipeline de datos](#4-pipeline-de-datos)
5. [Stack tecnológico](#5-stack-tecnológico)
6. [Despliegue en EC2](#6-despliegue-en-ec2)
7. [Autenticación](#7-autenticación)
8. [Endpoints de la API](#8-endpoints-de-la-api)
9. [Integración con el LLM](#9-integración-con-el-llm)
10. [Variables de entorno](#10-variables-de-entorno)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Descripción general

AgroGraph Scraping es un **microservicio independiente** que:

1. Extrae productos fitosanitarios de marketplaces mexicanos usando técnicas de web scraping con bypass de protecciones anti-bot
2. Normaliza nombres, precios (MXN), cultivos objetivo y enfermedades
3. Almacena en PostgreSQL con historial de precios
4. Expone una API REST que el módulo LLM usa para generar recomendaciones costo-beneficio

### Cultivos objetivo (7)

| Cultivo | Categoría | Plagas/enfermedades principales |
|---|---|---|
| **Tomate** | Hortaliza | Tizón tardío, mildiu, botrytis, mosca blanca, minador |
| **Papa** | Tubérculo | Tizón tardío, Phytophthora, rhizoctonia, pulgón |
| **Fresa** | Fruta | Botrytis, oidio, araña roja, trips |
| **Maíz** | Cereal | Gusano cogollero, roya, coquillo, zacate Johnson |
| **Frijol** | Leguminosa | Antracnosis, roya, pulgón, diabrótica |
| **Mora** | Fruta | Botrytis, monilia, oidio |
| **Calabaza** | Hortaliza | Cenicilla, mosca blanca, áfidos |

---

## 2. Técnica de extracción

### ¿Qué es web scraping?

Web scraping es la extracción automatizada de datos de páginas web públicas. El programa accede a la misma URL que un navegador humano, descarga el HTML de la página y extrae información estructurada (nombres, precios, imágenes).

En México, el scraping de páginas públicas para uso informativo es una práctica legal y común en el ámbito de la investigación de mercados, siempre que no se vulneren sistemas de seguridad ni se usen los datos con fines fraudulentos.

### Problema: protecciones anti-bot

Los sitios de e-commerce modernos (Amazon, MercadoLibre) detectan bots mediante:

| Protección | Cómo funciona |
|---|---|
| **TLS Fingerprinting** | Verifica que el handshake SSL sea de un navegador real, no de Python/requests |
| **Cloudflare Turnstile** | Desafío JavaScript que valida comportamiento humano |
| **Akamai WAF** | Analiza patrones de tráfico y bloquea IPs de datacenter conocidas |
| **User-Agent detection** | Rechaza peticiones con headers de librerías HTTP genéricas |
| **Rate limiting** | Bloquea si se hacen muchas peticiones en poco tiempo |

### Solución: Cascada de 3 estrategias

El sistema usa una cascada inteligente definida en [scraping/scrapers/base_scraper.py](scraping/scrapers/base_scraper.py):

```
Intento 1: cloudscraper (bypass de TLS fingerprinting)
    ↓ Si falla o devuelve página de desafío
Intento 2: CF Browser Rendering API (Chromium headless real)
    ↓ Si no está disponible o falla
Intento 3: httpx directo + proxy (si PROXY_URL configurado)
```

#### Estrategia 1 — cloudscraper

```python
import cloudscraper
scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)
```

**cloudscraper** imita exactamente el handshake TLS de Chrome, incluyendo las extensiones TLS específicas que usa cada versión de Chrome. Esto es técnicamente distinto de un navegador headless — opera a nivel de protocolo de red, no renderiza JavaScript.

- Velocidad: ~1-3 segundos por página
- Efectivo contra: detección por User-Agent, TLS fingerprinting básico
- No efectivo contra: Cloudflare Turnstile (requiere JavaScript)

#### Estrategia 2 — Cloudflare Browser Rendering API

Cuando cloudscraper recibe una página de desafío JavaScript, el sistema usa la **Cloudflare Browser Rendering API** (servicio de Chromium real en la nube):

```python
POST https://api.cloudflare.com/client/v4/accounts/{account_id}/browser-rendering/content
{
    "url": "https://www.amazon.com.mx/s?k=fungicida+tomate",
    "waitFor": ".s-search-results"
}
```

Esta API ejecuta un navegador Chromium real en los servidores de Cloudflare, renderiza la página incluyendo JavaScript y devuelve el HTML final. Al ser Cloudflare quien ejecuta el navegador, sus propias reglas WAF no lo bloquean.

- Límite free tier: 10 minutos/día, 1 petición cada 10 segundos
- Efectivo contra: Cloudflare Turnstile, páginas con JavaScript obligatorio

#### Comportamiento anti-bot adicional

El módulo [scraping/utils/anti_blocking.py](scraping/utils/anti_blocking.py) implementa:

- **Delays humanizados**: espera aleatoria de 3-7 segundos entre peticiones, con un 15% de probabilidad de pausa adicional de 3-8 segundos
- **Detección de bloqueo**: identifica páginas de captcha, "suspicious traffic", "challenge validation" por contenido del HTML
- **Backoff exponencial**: si se detecta bloqueo, espera mínimo 5s hasta máximo 60s antes de reintentar

### Limitación conocida: IPs de datacenter

Las IPs de AWS EC2 están en listas de reputación negativa para Akamai WAF (usado por gob.mx, COFEPRIS). Por eso:

- **Amazon.com.mx**: funciona con cloudscraper (no usa Akamai)
- **COFEPRIS/gob.mx**: bloqueado — requeriría proxy residencial
- **MercadoLibre**: requiere OAuth API (disponible registrando app en developers.mercadolibre.com)

Para habilitar proxy residencial:
```bash
PROXY_URL=http://usuario:contraseña@proxy-host:puerto
```

---

## 3. Fuentes de datos

### Amazon México — Fuente principal de productos reales

**URL base:** `https://www.amazon.com.mx`  
**Técnica:** cloudscraper → CF Browser Rendering  
**Estado:** Activo ✅

Los productos scraped de Amazon son **100% reales**: nombres tal como aparecen en el sitio, precios en MXN actuales, imágenes del CDN de Amazon, y ASIN como identificador único de deduplicación.

#### Queries de búsqueda utilizados

El scraper ejecuta 19 búsquedas especializadas por categoría y cultivo:

| Query | Cultivos objetivo |
|---|---|
| `fungicida tomate fresa botrytis tizón` | Tomate, Fresa |
| `fungicida papa tizón tardío phytophthora` | Papa, Tomate |
| `fungicida maiz roya tizón foliar` | Maíz |
| `fungicida frijol antracnosis roya agricola` | Frijol, Maíz |
| `fungicida mora fresa botrytis monilia` | Mora, Fresa |
| `fungicida tebuconazol trifloxystrobin agricola` | Tomate, Papa, Fresa, Maíz |
| `insecticida tomate mosca blanca minador trips` | Tomate, Papa, Fresa |
| `insecticida maiz gusano cogollero pulgón` | Maíz, Frijol |
| `insecticida papa frijol pulgón diabrótica` | Papa, Frijol, Maíz |
| `insecticida abamectina araña roja ácaros` | Tomate, Fresa, Papa, Mora |
| `insecticida imidacloprid mosca blanca áfidos` | Tomate, Calabaza, Papa |
| `insecticida espinosad trips mosca blanca cultivos` | Tomate, Fresa, Papa |
| `herbicida maiz atrazina coquillo pre-emergente` | Maíz |
| `herbicida clethodim jitomate tomate gramíneas` | Tomate, Frijol, Papa |
| `herbicida glifosato maleza agricola` | Maíz, Frijol |
| `fertilizante tomate fresa NPK soluble` | Tomate, Fresa |
| `fertilizante maiz papa NPK agricola` | Maíz, Papa, Frijol, Calabaza |
| `humus lombriz abono organico cultivos` | Todos |
| `fertilizante foliar micronutrientes hortalizas` | Tomate, Papa, Fresa, Calabaza |

#### Productos excluidos automáticamente

El filtro de exclusión descarta ~40% de resultados que Amazon devuelve como "relacionados":

- **Herramientas**: esparcidores, sembradoras, dispensadores de fertilizante
- **Repelentes de animales vertebrados**: conejos, ciervos, topos, armadillos (no son plagas agrícolas de cultivo)
- **Trampas físicas/adhesivas**: papeles amarillos, bug zappers (no son agroquímicos)
- **Plantas ornamentales**: orquídeas, bromelias, cactáceas
- **Productos domésticos**: para interiores, jardines decorativos, mascotas
- **Accesorios de equipo**: boquillas, inyectores venturi, mangueras
- **Productos con precio > $5,000 MXN**: outliers de conversión USD→MXN mal calculada

### Datos de referencia curada (seed)

Además del scraping automático, el catálogo incluye **32 productos de referencia** cargados con `seed_demo.py`. Estos son productos con registro COFEPRIS/SENASICA verificado:

| Grupo | Productos incluidos | Precio típico |
|---|---|---|
| Syngenta | Amistar Top, Actara, Karate Zeon, Engeo, Switch, Ridomil Gold | $620–$1,180 MXN |
| Bayer | Previcur Energy, Confidor, Decis, Infinito, Movento, Teldor | $380–$1,380 MXN |
| BASF | Cabrio Duo, Headline, Bellis, Luna Sensation, Basagran | $460–$1,560 MXN |
| Comerciales MX | Consist Max, PRONTIUS, Rotaprid, Abamectina Instar AD | $299–$875 MXN |
| Herbicidas MX | Hierbamina (2,4-D), Atrazina Sellador, Legacy Mesotriona, Jeren Clethodim | $190–$790 MXN |
| Fertilizantes | Ultrasol Tomate, Novatec NPK, Humus de Lombriz, Kristalon | $99–$1,450 MXN |

Estos productos son reales — corresponden a marcas y formulaciones comercializadas legalmente en México. Las URLs apuntan a los sitios oficiales de los fabricantes o a Mercado Libre.

---

## 4. Pipeline de datos

```
Amazon.com.mx
     │
     ▼ cloudscraper / CF Browser Rendering
[HTML crudo]
     │
     ▼ amazon_scraper.py — _parse_card()
[RawProduct]
  source, name, price_amount, image_url,
  product_type_raw, target_crops_raw, rating, reviews
     │
     ▼ product_parser.py — ProductParser.parse()
[ParsedProduct]
  Precio normalizado (PriceParser)
  Stock normalizado (StockParser)
  hash_dedup = SHA256(source|name|ingredient|url)
     │
     ▼ product_normalizer.py — ProductNormalizer.normalize()
[NormalizedProduct]
  Cultivos canonizados (aliases: maiz→maíz, tomato→tomate)
  Tipo normalizado (fungicide→fungicida)
  Precio convertido a MXN (CurrencyNormalizer)
     │
     ▼ tasks.py — run_scraper()
[PostgreSQL]
  products table + price_history table
     │
     ▼ Redis cache (TTL 30 min)
     │
     ▼ API FastAPI
  /products, /products/cultivo/{cultivo}, /llm/context
```

### Deduplicación

Cada producto se identifica por un hash SHA-256 calculado sobre:
```python
hash_dedup = SHA256(f"{source}|{name.lower()}|{ingredient.lower()}|{url}")
```

Si el mismo producto aparece en múltiples scrapes, se **actualiza el precio** y se registra un nuevo entry en `price_history` solo si el precio cambió.

### Normalización de cultivos

El normalizador reconoce aliases en español e inglés:

```python
"maiz" → "maíz"
"maize" → "maíz"
"tomato" → "tomate"
"jitomate" → "tomate"
"strawberry" → "fresa"
"blackberry" → "mora"
"potato" → "papa"
```

---

## 5. Stack tecnológico

| Componente | Tecnología | Versión | Rol |
|---|---|---|---|
| API | FastAPI + Uvicorn | 0.111 | REST API, autenticación JWT |
| Workers | Celery | 5.4 | Ejecución asíncrona de scrapers |
| Scheduler | Celery Beat | 5.4 | Disparo automático cada 6-12h |
| Base de datos | PostgreSQL | 16 | Almacenamiento de productos |
| Cache | Redis | 7 | Cache de respuestas (TTL 30 min) |
| Scraping HTTP | cloudscraper | 1.2.71 | Bypass TLS fingerprinting |
| Scraping headless | CF Browser Rendering API | — | Páginas con Cloudflare/JS |
| HTTP client | httpx | — | Fallback scraping |
| HTML parsing | BeautifulSoup4 + lxml | — | Extracción de datos del DOM |
| Migraciones DB | Alembic | — | Schema versioning |
| Contenedores | Docker + Docker Compose | — | Despliegue y orquestación |
| Infraestructura | AWS EC2 | t3.medium | Servidor en producción |

### Diagrama de contenedores

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Compose                        │
│                                                         │
│  ┌──────────┐   ┌──────────┐   ┌─────────────────────┐ │
│  │   api    │   │  worker  │   │     scheduler       │ │
│  │ :80→8000 │   │ (Celery) │   │   (Celery Beat)     │ │
│  └────┬─────┘   └────┬─────┘   └──────────┬──────────┘ │
│       │              │                     │            │
│       └──────┬───────┘─────────────────────┘            │
│              │                                          │
│    ┌─────────▼─────────┐   ┌──────────────────────┐    │
│    │     PostgreSQL    │   │       Redis           │    │
│    │   (port 5432)     │   │    (port 6379)        │    │
│    │   products        │   │    cache + broker     │    │
│    │   price_history   │   └──────────────────────┘    │
│    └───────────────────┘                                │
└─────────────────────────────────────────────────────────┘
         │
         ▼ Puerto 80 expuesto públicamente
    http://44.196.107.153/
```

---

## 6. Despliegue en EC2

### Requisitos

- EC2 Ubuntu 22.04/24.04, t3.small o superior
- Puerto 80 abierto al público (Security Group)
- Archivo `.env` configurado
- Git acceso al repositorio

### Primer despliegue

```bash
ssh -i tu-key.pem ubuntu@44.196.107.153

git clone https://github.com/wilber023/screaping_service ~/screaping_service
cd ~/screaping_service

cp .env.example .env
nano .env   # completar variables

docker-compose build
docker-compose run --rm api alembic upgrade head
docker-compose up -d
docker-compose exec api python seed_demo.py
```

### Actualizar después de cambios en código

```bash
cd ~/screaping_service
git pull
docker-compose build api worker
docker-compose up -d
# Si hay nuevas migraciones:
docker-compose run --rm api alembic upgrade head
```

### Ejecutar scraper manualmente

```bash
# Amazon México
docker-compose exec worker python -c "
import logging; logging.basicConfig(level=logging.INFO)
from scraping.workers.tasks import run_scraper
print(run_scraper.apply(args=['amazon']).result)
"

# Todos los scrapers activos en paralelo
docker-compose exec worker python -c "
from scraping.workers.tasks import run_all_scrapers
print(run_all_scrapers.apply().result)
"
```

### Verificar estado

```bash
# Health check
curl http://localhost/health

# Ver logs en tiempo real
docker-compose logs -f worker

# Contar productos por fuente
docker-compose exec postgres psql -U agrograph -d agrograph -c "
SELECT source, COUNT(*) as total, 
       AVG(price_amount)::numeric(10,0) as precio_promedio_MXN
FROM products 
WHERE is_active = true
GROUP BY source ORDER BY total DESC;"
```

---

## 7. Autenticación

Todos los endpoints (excepto `/health`) requieren **dos headers simultáneos**:

```
X-API-Key: <api-key>
Authorization: Bearer <jwt-token>
```

### Obtener token JWT

```bash
TOKEN=$(curl -s -X POST "http://44.196.107.153/auth/token?user_type=agricultor_experimentado" \
  -H "X-API-Key: TU_API_KEY" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

### Tipos de usuario

| `user_type` | Precios | Price history | Admin |
|---|---|---|---|
| `aprendiz` | Ocultos | No | No |
| `agricultor_experimentado` | Visibles en MXN | Sí | No |
| `admin` | Visibles | Sí | Sí |

---

## 8. Endpoints de la API

**Base URL:** `http://44.196.107.153`  
**Docs interactivas:** `http://44.196.107.153/docs`

### Health

```
GET /health
```
No requiere autenticación.
```json
{ "status": "ok", "service": "agrograph-scraping-api" }
```

### Listar productos

```
GET /products
```

| Param | Tipo | Ejemplo |
|---|---|---|
| `crop` | string | `tomate` |
| `disease` | string | `botrytis` |
| `product_type` | string | `fungicida` \| `insecticida` \| `herbicida` \| `fertilizante` |
| `source` | string | `amazon` \| `syngenta` \| `bayer` \| `basf` \| `mercadolibre` |
| `active_ingredient` | string | `imidacloprid` |
| `page` | int | `1` |
| `per_page` | int | `20` (max 100) |

### Productos por cultivo (shortcut)

```
GET /products/cultivo/{cultivo}
```
Equivale a `/products?crop={cultivo}`.

**Ejemplo:** `GET /products/cultivo/papa` → todos los fungicidas, insecticidas y herbicidas para papa.

### Productos por enfermedad (shortcut)

```
GET /products/enfermedad/{enfermedad}
```
**Ejemplo:** `GET /products/enfermedad/botrytis`

### Detalle de producto

```
GET /products/{id}
```

### Historial de precios

```
GET /products/{id}/price-history
```
Requiere `agricultor_experimentado` o `admin`.

```json
{
  "product_id": "...",
  "product_name": "Fungicida Tebuconazol",
  "history": [
    { "amount": 765.0, "currency": "MXN", "recorded_at": "2026-06-20T10:00:00" },
    { "amount": 775.0, "currency": "MXN", "recorded_at": "2026-06-26T04:00:00" }
  ]
}
```

### Contexto para LLM

```
GET /llm/context?crop=tomate&limit=100
```

Devuelve resumen compacto optimizado para inyección en system prompt del modelo de IA.

### Admin — Disparar scraper

```
POST /admin/trigger-scrape?source=amazon
```
Requiere `admin`.

### Lista de cultivos

```
GET /crops
```
```json
{ "crops": ["calabaza", "frijol", "mora", "maíz", "papa", "fresa", "tomate"] }
```

---

## 9. Integración con el LLM

### Flujo recomendado

```python
import requests, os

SCRAPING_API = "http://44.196.107.153"
HEADERS = {
    "X-API-Key": os.environ["SCRAPING_API_KEY"],
    "Authorization": f"Bearer {llm_service_jwt}",
}

def get_context_for_crop(crop: str) -> dict:
    """Obtiene catálogo de productos para el modelo de IA."""
    return requests.get(
        f"{SCRAPING_API}/llm/context",
        params={"crop": crop, "limit": 50},
        headers=HEADERS,
        timeout=10,
    ).json()

def get_products_for_disease(disease: str) -> list:
    """Todos los productos que tratan una enfermedad."""
    r = requests.get(
        f"{SCRAPING_API}/products/enfermedad/{disease}",
        headers=HEADERS,
        timeout=10,
    ).json()
    return r["items"]
```

### Prompt de sistema con catálogo

```python
ctx = get_context_for_crop("tomate")

system_prompt = f"""
Eres un asesor agronómico para cultivos de {cultivo} en México.

Catálogo de productos disponibles ({ctx['total']} productos):
{json.dumps(ctx['items'], ensure_ascii=False, indent=2)}

Instrucciones:
- Recomienda tratamientos basándote en costo-beneficio
- Si hay 3+ productos para la misma plaga, compara precios y sugiere la opción más económica
- Considera que el agricultor puede combinar productos para reducir costo total
- Menciona siempre el precio en MXN y el ingrediente activo
"""
```

---

## 10. Variables de entorno

Archivo `.env` en la raíz del proyecto:

| Variable | Requerida | Descripción |
|---|---|---|
| `DATABASE_URL` | ✅ | `postgresql://agrograph:password@postgres:5432/agrograph` |
| `REDIS_URL` | ✅ | `redis://redis:6379/0` |
| `API_KEY_FRONTEND` | ✅ | Hex 64 chars. Genera: `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `API_KEY_LLM` | ✅ | Hex 64 chars distinto al anterior |
| `JWT_SECRET` | ✅ | Mínimo 32 chars aleatorios |
| `CF_ACCOUNT_ID` | ✅ | ID de cuenta Cloudflare (para Browser Rendering) |
| `CF_API_TOKEN` | ✅ | Token de API Cloudflare con permisos Browser Rendering |
| `ML_CLIENT_ID` | — | App ID de MercadoLibre (para activar scraper ML) |
| `ML_CLIENT_SECRET` | — | Secret Key de MercadoLibre |
| `PROXY_URL` | — | `http://user:pass@host:port` (proxy residencial opcional) |
| `POSTGRES_USER` | ✅ | Usuario de PostgreSQL |
| `POSTGRES_PASSWORD` | ✅ | Contraseña de PostgreSQL |
| `POSTGRES_DB` | ✅ | Nombre de la base de datos |
| `S3_BUCKET` | — | Bucket S3 para snapshots HTML (opcional) |
| `DEBUG` | — | `true` para logs detallados |

---

## 11. Troubleshooting

### Verificar que el scraper encuentra productos

```bash
docker-compose exec worker python -c "
import logging; logging.basicConfig(level=logging.DEBUG)
from scraping.scrapers.amazon_scraper import AmazonScraper
s = AmazonScraper()
products = s.scrape()
print(f'Encontrados: {len(products)}')
for p in products[:3]:
    print(f'  - {p.name[:60]} | ${p.price_amount} | cultivos={p.target_crops_raw}')
"
```

### Verificar productos en BD por cultivo

```bash
docker-compose exec postgres psql -U agrograph -d agrograph -c "
SELECT name, price_amount, array_to_string(target_crops, ',') as cultivos
FROM products 
WHERE 'papa' = ANY(target_crops) AND is_active = true
ORDER BY price_amount
LIMIT 10;"
```

### Scraper devuelve 0 productos

**Causa 1 — Bloqueo temporal de Amazon:**
```bash
# Esperar 30 min y reintentar. Amazon bloquea después de muchas peticiones rápidas.
```

**Causa 2 — CF Browser Rendering sin cuota:**
```bash
# El plan gratuito tiene 10 min/día. Verificar en dashboard.cloudflare.com
docker-compose logs worker | grep "CF Browser"
```

**Causa 3 — Cambio de estructura HTML de Amazon:**
```bash
# Los selectores CSS pueden cambiar. Verificar el HTML:
docker-compose exec worker python -c "
from scraping.scrapers.base_scraper import BaseScraper
class Test(BaseScraper):
    source = 'test'
    def scrape(self): return []
t = Test()
html = t._fetch_html('https://www.amazon.com.mx/s?k=fungicida+agricola')
print(html[:2000])
"
```

### API no responde en puerto 80

```bash
# Verificar que el contenedor API está corriendo
docker-compose ps api

# Ver logs del API
docker-compose logs api --tail=50

# El API está en puerto 80, NO 8000
curl http://localhost/health   # correcto
curl http://localhost:8000/health   # incorrecto (no expuesto al host)
```

### Base de datos: ver estado actual

```bash
docker-compose exec postgres psql -U agrograph -d agrograph -c "
SELECT source, product_type, COUNT(*) as total,
       MIN(price_amount) as precio_min,
       MAX(price_amount) as precio_max
FROM products WHERE is_active = true
GROUP BY source, product_type
ORDER BY source, product_type;"
```

### Reset de productos Amazon (re-scrape limpio)

```bash
docker-compose exec postgres psql -U agrograph -d agrograph -c "
DELETE FROM price_history ph USING products p 
WHERE ph.product_id = p.id AND p.source = 'amazon';
DELETE FROM products WHERE source = 'amazon';"

docker-compose exec worker python -c "
from scraping.workers.tasks import run_scraper
print(run_scraper.apply(args=['amazon']).result)"
```

---

## Estructura del proyecto

```
screaping/
├── scraping/
│   ├── api/
│   │   ├── main.py                  # FastAPI app, CORS, routers
│   │   └── routes/
│   │       ├── products.py          # /products, /cultivo/, /enfermedad/
│   │       ├── auth.py              # /auth/token
│   │       ├── crops.py             # /crops
│   │       └── llm.py               # /llm/context
│   ├── scrapers/
│   │   ├── base_scraper.py          # Clase base: cascada cloudscraper→CF→httpx
│   │   ├── amazon_scraper.py        # Scraper Amazon.com.mx (activo)
│   │   ├── mercadolibre_scraper.py  # Scraper ML (requiere OAuth)
│   │   ├── agrofy_scraper.py        # Scraper Agrofy.com.ar
│   │   ├── bayer_scraper.py         # Catálogo Bayer (bloqueado desde EC2)
│   │   ├── syngenta_scraper.py      # Catálogo Syngenta (bloqueado desde EC2)
│   │   └── basf_scraper.py          # Catálogo BASF (bloqueado desde EC2)
│   ├── parsers/
│   │   └── product_parser.py        # RawProduct → ParsedProduct
│   ├── normalizers/
│   │   └── product_normalizer.py    # ParsedProduct → NormalizedProduct
│   ├── models/
│   │   ├── product.py               # SQLAlchemy ORM Product
│   │   └── price_history.py         # PriceHistory (historial de precios)
│   ├── workers/
│   │   ├── celery_worker.py         # Configuración Celery
│   │   └── tasks.py                 # run_scraper(), run_all_scrapers()
│   └── utils/
│       ├── anti_blocking.py         # Delays, detección de bloqueos, backoff
│       └── cf_browser.py            # Cliente CF Browser Rendering API
├── migrations/                      # Alembic migrations
├── seed_demo.py                     # 32 productos de referencia con datos reales
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```
