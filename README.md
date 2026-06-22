# AgroGraph Scraping API

Servicio de catálogo agrícola dinámico para AgroGraph. Obtiene, normaliza y centraliza información de productos fitosanitarios (fungicidas, insecticidas, herbicidas, fertilizantes) para los **14 cultivos** principales, desde múltiples fuentes (Agrofy, MercadoLibre, Syngenta, Bayer, BASF), y los expone vía API REST para ser consumidos por el módulo de diagnóstico de IA y el frontend de AgroGraph.

---

## Tabla de contenidos

1. [Descripción general](#1-descripción-general)
2. [Cómo desplegar en EC2](#2-cómo-desplegar-en-ec2)
3. [Security Groups requeridos](#3-security-groups-requeridos-en-la-ec2)
4. [Autenticación](#4-autenticación)
5. [Catálogo de endpoints](#5-catálogo-de-endpoints)
6. [Guía de integración para el LLM](#6-guía-de-integración-para-el-llm)
7. [Guía de integración para el Frontend](#7-guía-de-integración-para-el-frontend)
8. [Variables de entorno](#8-variables-de-entorno)
9. [Troubleshooting del deploy](#9-troubleshooting-del-deploy)

---

## 1. Descripción general

### Cultivos soportados
`calabaza` · `frijol` · `manzana` · `mora` · `cereza` · `maíz` · `durazno` · `uva` · `naranja` · `pimienta` · `papa` · `frambuesa` · `soja` · `fresa` · `tomate`

### Fuentes de datos
| Fuente | Tipo | País principal |
|---|---|---|
| Agrofy | Marketplace agrícola (headless browser) | Argentina |
| MercadoLibre | API pública REST | México |
| Syngenta | Catálogo oficial del fabricante | México |
| Bayer CropScience | Catálogo oficial del fabricante | México |
| BASF | Catálogo oficial del fabricante | México |

### Stack tecnológico
- **API:** FastAPI 0.111 + Uvicorn
- **Workers:** Celery 5.4 + Redis (broker)
- **Scheduler:** Celery Beat (jobs periódicos cada 6-12h)
- **DB:** PostgreSQL 16
- **Cache:** Redis 7
- **Snapshots:** AWS S3 (archival de HTML crudo)
- **Headless scraping:** Playwright (contenedor dedicado)

---

## 2. Cómo desplegar en EC2

### Requisitos previos
- Instancia EC2 con Amazon Linux 2023 o Ubuntu 22.04/24.04
- La instancia debe tener al menos **t3.medium** (2 vCPU, 4 GB RAM recomendado por Playwright)
- Un archivo `.env` correctamente configurado (ver [sección 8](#8-variables-de-entorno))
- Acceso SSH a la instancia
- Security Groups habilitados (ver [sección 3](#3-security-groups-requeridos-en-la-ec2))

### Despliegue

```bash
# 1. Conectarse a la EC2
ssh -i tu-key.pem ec2-user@<ip-publica>

# 2. Clonar o subir el proyecto
git clone <repo-url> /opt/agrograph-scraping
cd /opt/agrograph-scraping

# 3. Configurar variables de entorno
cp .env.example .env
nano .env   # completar todos los valores requeridos

# 4. Un único comando para desplegar todo
chmod +x deploy.sh
./deploy.sh
```

El script `deploy.sh` se encarga de:
1. Instalar Docker y Docker Compose si no están presentes (compatible con Amazon Linux 2023 y Ubuntu)
2. Validar que `.env` tenga todos los valores necesarios
3. Construir las imágenes Docker
4. Levantar todos los servicios
5. Esperar a que Postgres y Redis estén sanos (`HEALTHCHECK`)
6. Ejecutar las migraciones de base de datos (`alembic upgrade head`)
7. Verificar que la API responde en `/health`
8. Mostrar las URLs de acceso y el estado de todos los servicios

> **Es idempotente:** ejecutar `./deploy.sh` varias veces es seguro — actualizará imágenes y reiniciará servicios sin perder datos.

---

## 3. Security Groups requeridos en la EC2

Estas reglas de entrada (inbound rules) deben estar habilitadas en el Security Group de la instancia **antes del primer despliegue**:

| Puerto | Protocolo | Origen recomendado | Propósito |
|---|---|---|---|
| **22** | TCP | IP fija del equipo de desarrollo (NO `0.0.0.0/0`) | SSH para administración |
| **8000** | TCP | `0.0.0.0/0` (o IP del backend/LLM/frontend si tienen IP fija) | API FastAPI — consumo por LLM y frontend |
| **443** | TCP | `0.0.0.0/0` | HTTPS si se coloca Nginx/reverse proxy con certificado SSL |
| **80** | TCP | `0.0.0.0/0` | Redirección HTTP→HTTPS (si se usa reverse proxy) |

**Puertos que NO deben quedar expuestos públicamente:**
- `5432` (PostgreSQL) — solo tráfico interno entre contenedores
- `6379` (Redis) — solo tráfico interno entre contenedores
- `8001` (Playwright service) — solo tráfico interno entre contenedores

---

## 4. Autenticación

Todos los endpoints (excepto `/health`) requieren **dos headers simultáneos**:

```
X-API-Key: <api-key>
Authorization: Bearer <jwt-token>
```

### 4.1 API Key

Identifica al sistema cliente (frontend, LLM, jobs internos). Se configura en `.env`:

```
API_KEY_FRONTEND=<hex-64-chars>
API_KEY_LLM=<hex-64-chars>
```

Genera claves con:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 4.2 JWT Token

El JWT identifica al usuario final y su tipo. Debe incluir:

```json
{
  "user_id": "uuid-del-usuario",
  "user_type": "aprendiz | agricultor_experimentado | admin",
  "exp": 1750000000
}
```

**Tipos de usuario y permisos:**

| `user_type` | Acceso |
|---|---|
| `aprendiz` | Lectura del catálogo (nombre, tipo, cultivos, enfermedades). **Sin precios ni stock detallado.** |
| `agricultor_experimentado` | Acceso completo: precios, stock, históricos, filtros avanzados. |
| `admin` | Todo lo anterior + endpoints `/admin/*` para disparar scrapers y ver status. |

### 4.3 Errores de autenticación

| Código | Error | Causa |
|---|---|---|
| `401` | `invalid_api_key` | `X-API-Key` ausente o inválida |
| `401` | `invalid_token` | JWT ausente, expirado o malformado |
| `403` | `insufficient_permissions` | JWT válido pero `user_type` no autorizado |

### 4.4 Ejemplo con curl

```bash
curl -X GET "http://<ec2-ip>:8000/products?crop=tomate&page=1&per_page=10" \
  -H "X-API-Key: tu_api_key_aqui" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

## 5. Catálogo de endpoints

### Base URL: `http://<ec2-ip>:8000`
### Documentación interactiva: `http://<ec2-ip>:8000/docs`

---

### `GET /health`
> No requiere autenticación. Para healthchecks de infraestructura.

**Respuesta:**
```json
{ "status": "ok", "service": "agrograph-scraping-api" }
```

---

### `GET /products`
Lista productos con filtros opcionales.

**Query params:**

| Param | Tipo | Descripción |
|---|---|---|
| `crop` | string | Filtrar por cultivo (e.g. `tomate`, `papa`) |
| `disease` | string | Filtrar por enfermedad (match parcial) |
| `product_type` | string | `fungicida` \| `insecticida` \| `herbicida` \| `fertilizante` |
| `manufacturer` | string | Filtrar por fabricante (match parcial) |
| `source` | string | `agrofy` \| `mercadolibre` \| `syngenta` \| `bayer` \| `basf` |
| `page` | int | Página (default: 1) |
| `per_page` | int | Items por página (default: 20, max: 100) |

**Respuesta:**
```json
{
  "total": 142,
  "page": 1,
  "per_page": 20,
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "source": "syngenta",
      "source_url": "https://www.syngenta.com.mx/productos/amistar-top",
      "name": "Amistar Top",
      "manufacturer": "Syngenta",
      "active_ingredient": "Azoxistrobina + Difenoconazol",
      "product_type": "fungicida",
      "target_crops": ["tomate", "papa", "uva"],
      "target_diseases": ["tizón tardío", "alternaria", "botrytis"],
      "price": {
        "amount": 450.00,
        "currency": "MXN",
        "original_currency": "MXN",
        "last_updated": "2025-06-15T10:00:00Z"
      },
      "stock": {
        "status": "in_stock",
        "quantity": null
      },
      "availability_regions": ["MX"],
      "scraped_at": "2025-06-15T10:00:00Z"
    }
  ]
}
```

> **Nota para `aprendiz`:** los campos `price.amount` y `stock.quantity` se omiten.

---

### `GET /products/{id}`
Detalle de un producto.

**Respuesta:** mismo schema que un item de `/products`.

---

### `GET /products/{id}/price-history`
> Requiere `agricultor_experimentado` o `admin`.

**Respuesta:**
```json
{
  "product_id": "550e8400-...",
  "product_name": "Amistar Top",
  "history": [
    { "amount": 420.00, "currency": "MXN", "original_currency": "MXN", "recorded_at": "2025-05-01T08:00:00Z" },
    { "amount": 450.00, "currency": "MXN", "original_currency": "MXN", "recorded_at": "2025-06-15T10:00:00Z" }
  ]
}
```

---

### `GET /crops`
Lista los 14 cultivos soportados.

```json
{ "crops": ["calabaza", "frijol", "manzana", "mora", "cereza", "maíz", ...] }
```

---

### `GET /crops/{crop}/treatments`
Productos disponibles para tratar enfermedades de un cultivo.

**Params:** `page`, `per_page`

**Respuesta:** igual que `/products`.

---

### `GET /diseases/{disease}/products`
Productos que tratan una enfermedad específica (búsqueda parcial).

**Ejemplo:** `/diseases/tizón/products`

**Respuesta:** igual que `/products`.

---

### `GET /llm/context`
Resumen compacto del catálogo optimizado para inyección como contexto del LLM.

**Query params:**
- `crop` (optional): limitar a un cultivo
- `limit` (default: 200, max: 500): número máximo de productos

**Respuesta:**
```json
{
  "total_products": 87,
  "by_crop": {
    "tomate": ["Amistar Top", "Previcur Energy", "Movento"],
    "papa": ["Infinito", "Acrobat MZ"]
  },
  "by_type": {
    "fungicida": 45,
    "insecticida": 28,
    "herbicida": 10,
    "fertilizante": 4
  },
  "products": [
    {
      "id": "550e8400-...",
      "name": "Amistar Top",
      "type": "fungicida",
      "active_ingredient": "Azoxistrobina + Difenoconazol",
      "manufacturer": "Syngenta",
      "crops": ["tomate", "papa", "uva"],
      "diseases": ["tizón tardío", "alternaria"],
      "price_usd": 25.71,
      "stock": "in_stock"
    }
  ],
  "generated_at": "2025-06-15T12:00:00Z"
}
```

---

### `POST /admin/trigger-scrape`
> Requiere `admin`.

**Query param:** `source` — nombre del scraper (`agrofy`, `mercadolibre`, `syngenta`, `bayer`, `basf`, `all`)

**Respuesta:**
```json
{
  "status": "queued",
  "source": "syngenta",
  "task_id": "abc123-...",
  "queued_at": "2025-06-15T12:00:00Z"
}
```

---

### `GET /admin/scrape-status`
> Requiere `admin`.

**Query param (opcional):** `task_id` — consulta el estado de una tarea específica.

**Sin `task_id`:** devuelve el estado de todos los workers activos.

---

## 6. Guía de integración para el LLM

### Flujo recomendado

```
1. Al iniciar una sesión de diagnóstico:
   GET /llm/context?crop={cultivo_detectado}&limit=100
   → Inyectar la respuesta como contexto del system prompt

2. Cuando el usuario pide tratamientos específicos:
   GET /crops/{crop}/treatments
   → Complementar la respuesta del LLM con datos actualizados

3. Para una enfermedad específica:
   GET /diseases/{disease}/products
   → Enriquecer la recomendación con productos disponibles

4. Para detalle de precio/disponibilidad:
   GET /products/{id}
```

### Headers para el LLM

```python
headers = {
    "X-API-Key": os.environ["API_KEY_LLM"],
    "Authorization": f"Bearer {llm_service_jwt}",
}
```

El JWT del servicio LLM debe tener `user_type: "agricultor_experimentado"` para acceder a precios completos.

### Manejo de errores

| HTTP | Acción recomendada |
|---|---|
| `401` | Renovar el JWT o verificar la API Key |
| `403` | Verificar que el `user_type` del JWT sea el correcto |
| `429` | Esperar y reintentar con backoff exponencial |
| `5xx` | Reintentar hasta 3 veces; si persiste, usar catálogo local en cache |

### Formato de contexto para el prompt

```python
context_response = requests.get(
    f"{API_BASE}/llm/context",
    params={"crop": detected_crop, "limit": 100},
    headers=headers,
    timeout=10,
).json()

system_context = f"""
Catálogo de productos fitosanitarios disponibles para {detected_crop}:
Total: {context_response['total_products']} productos
Tipos disponibles: {context_response['by_type']}

Productos recomendados:
{json.dumps(context_response['products'][:20], ensure_ascii=False, indent=2)}
"""
```

---

## 7. Guía de integración para el Frontend

### Flujo de autenticación

El frontend debe:
1. Obtener la API Key del backend de AgroGraph (nunca exponerla directamente en el cliente)
2. Enviar ambos headers en cada request a esta API
3. Mapear el `user_type` del usuario logueado al JWT que envía a esta API

```typescript
// Ejemplo TypeScript / React
const apiClient = axios.create({
  baseURL: process.env.REACT_APP_SCRAPING_API_URL,
  headers: {
    "X-API-Key": process.env.REACT_APP_SCRAPING_API_KEY,
    "Authorization": `Bearer ${userJwt}`,   // JWT con user_type del usuario
  },
});

// Listar productos para tomate
const { data } = await apiClient.get("/products", {
  params: { crop: "tomate", product_type: "fungicida", page: 1, per_page: 20 },
});
```

### Mapeo de roles

| Rol en la app AgroGraph | `user_type` en el JWT de esta API |
|---|---|
| Usuario nuevo / en aprendizaje | `aprendiz` |
| Usuario con experiencia / premium | `agricultor_experimentado` |
| Administrador de la plataforma | `admin` |

### Diferencias de respuesta por tipo de usuario

- **`aprendiz`:** campos `price.amount` y `stock.quantity` vienen `null`. Solo ve nombre, tipo, cultivos y enfermedades.
- **`agricultor_experimentado`:** respuesta completa con precios en MXN (normalizados) y stock.
- **Ambos:** el endpoint `/products/{id}/price-history` solo es accesible para `agricultor_experimentado` y `admin`.

---

## 8. Variables de entorno

Copiar `.env.example` como `.env` y completar todos los valores:

| Variable | Requerida | Descripción |
|---|---|---|
| `DATABASE_URL` | ✅ | URL de conexión a Postgres. Formato: `postgresql://user:password@postgres:5432/agrograph` |
| `REDIS_URL` | ✅ | URL de Redis. Formato: `redis://redis:6379/0` |
| `S3_BUCKET` | ✅ | Nombre del bucket S3 para snapshots HTML |
| `S3_ACCESS_KEY` | ✅ | AWS Access Key ID (o MinIO) |
| `S3_SECRET_KEY` | ✅ | AWS Secret Access Key (o MinIO) |
| `S3_REGION` | — | Región AWS (default: `us-east-1`) |
| `S3_ENDPOINT_URL` | — | Solo si usas MinIO u otro compatible con S3 |
| `PROXY_LIST` | — | Lista de proxies separados por coma: `http://user:pass@host:port,...` |
| `SCRAPE_INTERVAL_HOURS` | — | Intervalo entre ciclos de scraping por fuente (default: `6`) |
| `API_KEY_FRONTEND` | ✅ | API Key para el frontend (hex 64 chars mínimo) |
| `API_KEY_LLM` | ✅ | API Key para el servicio LLM (hex 64 chars mínimo) |
| `JWT_SECRET` | ✅ | Secreto para firmar JWTs (mínimo 32 chars aleatorios) |
| `JWT_ALGORITHM` | — | Algoritmo JWT (default: `HS256`) |
| `JWT_EXPIRATION_MINUTES` | — | Expiración del token en minutos (default: `1440` = 24h) |
| `DEBUG` | — | `true` / `false` — activa logs debug (default: `false`) |

---

## 9. Troubleshooting del deploy

### El contenedor `api` no arranca

```bash
docker compose logs api
```
Causas comunes:
- Variables de `.env` con placeholder sin reemplazar
- `DATABASE_URL` con password incorrecto
- Puerto 8000 ya ocupado en la EC2

### Las migraciones fallan

```bash
docker compose run --rm api alembic upgrade head
```
Verifica que `postgres` esté corriendo y sano:
```bash
docker compose exec postgres pg_isready -U agrograph -d agrograph
```

### El worker no procesa tareas

```bash
docker compose logs worker
docker compose exec worker celery -A scraping.workers.celery_worker inspect active
```
Causa probable: `REDIS_URL` incorrecto o Redis no responde.

### Error "Port 8000 already in use"

```bash
sudo lsof -i :8000
sudo kill -9 <PID>
./deploy.sh
```

### S3 bucket no existe / permiso denegado

Si `S3_ENDPOINT_URL` está vacío, el sistema intenta usar AWS S3 real. Las credenciales deben tener permisos `s3:PutObject` y `s3:CreateBucket` sobre el bucket configurado.

Para ignorar S3 en pruebas, los snapshots simplemente no se guardan (logging warning, no error fatal).

### `deploy.sh` falla en el paso de Docker Compose

```
Error: Cannot connect to the Docker daemon
```
Solución:
```bash
sudo systemctl start docker
sudo usermod -aG docker $USER
newgrp docker
./deploy.sh
```

### Ver todos los logs en tiempo real

```bash
docker compose logs -f
# O por servicio específico:
docker compose logs -f api worker scheduler
```

### Re-deploy completo (sin perder datos)

```bash
./deploy.sh   # idempotente — actualiza imágenes y reinicia servicios
```

### Reset completo (destruye datos)

```bash
docker compose down -v   # ⚠️ elimina volúmenes (DB, Redis)
./deploy.sh
```
