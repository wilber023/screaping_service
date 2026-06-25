#!/bin/bash
set -e

# ─── AgroGraph — deploy automático para Ubuntu EC2 ───────────────────────────

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║         AgroGraph — Deploy en Ubuntu EC2             ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── 1. Instalar Docker si no existe ──────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  echo "[1/6] Instalando Docker..."
  sudo apt-get update -q
  sudo apt-get install -y docker.io git
  sudo systemctl enable --now docker
  sudo usermod -aG docker "$USER"
  echo "      Docker instalado. IMPORTANTE: cierra y vuelve a abrir la sesión SSH"
  echo "      y corre el script de nuevo para que el grupo 'docker' tome efecto."
  exit 0
else
  echo "[1/6] Docker ya instalado: $(docker --version)"
fi

# ── 2. Instalar Docker Compose si no existe ───────────────────────────────────
if ! command -v docker-compose &>/dev/null; then
  echo "[2/6] Instalando Docker Compose..."
  sudo curl -fsSL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
    -o /usr/local/bin/docker-compose
  sudo chmod +x /usr/local/bin/docker-compose
  echo "      Compose instalado: $(docker-compose --version)"
else
  echo "[2/6] Docker Compose ya instalado: $(docker-compose --version)"
fi

# ── 3. Validar .env ───────────────────────────────────────────────────────────
echo "[3/6] Validando .env..."
if [ ! -f .env ]; then
  echo "ERROR: no existe el archivo .env en $(pwd)"
  echo "Crea el .env con las variables requeridas y vuelve a correr el script."
  exit 1
fi

required_vars="DATABASE_URL REDIS_URL JWT_SECRET API_KEY_FRONTEND API_KEY_LLM POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB"
missing=""
for var in $required_vars; do
  if ! grep -q "^${var}=" .env; then
    missing="$missing $var"
  fi
done
if [ -n "$missing" ]; then
  echo "ERROR: faltan estas variables en .env:$missing"
  exit 1
fi
echo "      .env validado OK"

# ── 4. Build y levantar solo postgres + redis primero ────────────────────────
echo "[4/6] Construyendo imágenes..."
docker-compose pull postgres redis 2>/dev/null || true
docker-compose build --no-cache

echo "      Levantando postgres y redis..."
docker-compose up -d postgres redis

# ── 5. Esperar PostgreSQL y correr migraciones ANTES de levantar la API ───────
echo "[5/6] Esperando a PostgreSQL..."
attempt=0
until docker-compose exec -T postgres pg_isready -U "$(grep POSTGRES_USER .env | cut -d= -f2)" &>/dev/null; do
  attempt=$((attempt + 1))
  if [ $attempt -ge 30 ]; then
    echo "ERROR: PostgreSQL no respondió después de 30 intentos."
    docker-compose logs postgres
    exit 1
  fi
  echo "      Intento $attempt/30 — esperando..."
  sleep 2
done
echo "      PostgreSQL listo."

echo "      Corriendo migraciones Alembic..."
docker-compose run --rm api alembic upgrade head
echo "      Migraciones aplicadas."

echo "      Levantando todos los servicios..."
docker-compose up -d

# ── 6. Verificar health de la API ─────────────────────────────────────────────
echo "[6/6] Verificando API..."
attempt=0
until curl -sf http://localhost/health &>/dev/null; do
  attempt=$((attempt + 1))
  if [ $attempt -ge 20 ]; then
    echo "ERROR: API no respondió después de 20 intentos."
    docker-compose logs api
    exit 1
  fi
  echo "      Intento $attempt/20 — esperando API..."
  sleep 3
done

PUBLIC_IP=$(curl -sf http://checkip.amazonaws.com 2>/dev/null || echo "tu-ip-publica")

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   ✅  AgroGraph desplegado correctamente             ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  API:    http://$PUBLIC_IP                           "
echo "║  Health: http://$PUBLIC_IP/health                   "
echo "║  Docs:   http://$PUBLIC_IP/docs                     "
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "Credenciales (guárdalas):"
echo "  API_KEY_FRONTEND = $(grep API_KEY_FRONTEND .env | cut -d= -f2)"
echo "  API_KEY_LLM      = $(grep API_KEY_LLM .env | cut -d= -f2)"
echo ""
echo "Para ver logs:    docker-compose logs -f api"
echo "Para detener:     docker-compose down"
echo "Para actualizar:  git pull && docker-compose up -d --build"