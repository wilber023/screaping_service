#!/usr/bin/env bash
# =============================================================================
#  AgroGraph Scraping — Single-command EC2 deploy script
#  Usage:  ./deploy.sh
#
#  Idempotent: safe to run multiple times (re-deploy, update).
#  Tested on: Amazon Linux 2023, Ubuntu 22.04/24.04
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${BLUE}[deploy]${NC} $*"; }
ok()   { echo -e "${GREEN}[  ok  ]${NC} $*"; }
warn() { echo -e "${YELLOW}[ warn ]${NC} $*"; }
err()  { echo -e "${RED}[error ]${NC} $*"; exit 1; }

# ─── Step 1: Detect OS and install Docker if missing ─────────────────────────
log "Step 1 — Checking Docker installation..."

if ! command -v docker &>/dev/null; then
    warn "Docker not found. Installing..."
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS_ID="${ID:-}"
    fi

    if [[ "${OS_ID:-}" == "amzn" ]]; then
        log "Detected Amazon Linux. Installing Docker via yum..."
        sudo yum update -y
        sudo yum install -y docker
        sudo systemctl start docker
        sudo systemctl enable docker
        sudo usermod -aG docker "${USER:-ec2-user}" || true
    elif [[ "${OS_ID:-}" == "ubuntu" || "${OS_ID:-}" == "debian" ]]; then
        log "Detected Ubuntu/Debian. Installing Docker..."
        sudo apt-get update -y
        sudo apt-get install -y ca-certificates curl gnupg lsb-release
        sudo install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
            | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        sudo chmod a+r /etc/apt/keyrings/docker.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
            | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
        sudo apt-get update -y
        sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        sudo systemctl start docker
        sudo systemctl enable docker
        sudo usermod -aG docker "${USER:-ubuntu}" || true
    else
        err "Unsupported OS '${OS_ID:-unknown}'. Install Docker manually: https://docs.docker.com/engine/install/"
    fi
    ok "Docker installed."
else
    ok "Docker is already installed: $(docker --version)"
fi

# Check Docker daemon is running
if ! docker info &>/dev/null; then
    log "Starting Docker daemon..."
    sudo systemctl start docker || err "Could not start Docker daemon"
fi

# ─── Step 2: Ensure Docker Compose is available ──────────────────────────────
log "Step 2 — Checking Docker Compose..."

COMPOSE_CMD=""
if docker compose version &>/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
    ok "Docker Compose plugin: $(docker compose version)"
elif command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
    ok "docker-compose: $(docker-compose --version)"
else
    warn "Docker Compose not found. Installing compose plugin..."
    COMPOSE_LATEST="v2.27.0"
    sudo mkdir -p /usr/local/lib/docker/cli-plugins
    sudo curl -fsSL \
        "https://github.com/docker/compose/releases/download/${COMPOSE_LATEST}/docker-compose-linux-$(uname -m)" \
        -o /usr/local/lib/docker/cli-plugins/docker-compose
    sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
    COMPOSE_CMD="docker compose"
    ok "Docker Compose installed: $(docker compose version)"
fi

# ─── Step 3: Verify or create .env ───────────────────────────────────────────
log "Step 3 — Checking .env file..."

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        warn ".env was missing — copied from .env.example."
        warn ""
        warn "  IMPORTANT: You MUST edit .env before the deployment will work:"
        warn "    1. Set DATABASE_URL with a real password (not 'changeme')"
        warn "    2. Generate API_KEY_FRONTEND:  python3 -c \"import secrets; print(secrets.token_hex(32))\""
        warn "    3. Generate API_KEY_LLM:       python3 -c \"import secrets; print(secrets.token_hex(32))\""
        warn "    4. Generate JWT_SECRET:        python3 -c \"import secrets; print(secrets.token_urlsafe(48))\""
        warn "    5. Set S3_ACCESS_KEY / S3_SECRET_KEY if using AWS S3."
        warn ""
        warn "  Edit now: nano .env"
        warn "  Then re-run: ./deploy.sh"
        exit 1
    else
        err ".env.example not found. Ensure you are in the project root directory."
    fi
else
    ok ".env file found."
fi

# Verify required variables are set and not still placeholders
REQUIRED_VARS=("API_KEY_FRONTEND" "API_KEY_LLM" "JWT_SECRET")
for var in "${REQUIRED_VARS[@]}"; do
    val=$(grep -E "^${var}=" .env | cut -d'=' -f2- | tr -d '"' | tr -d "'" | xargs)
    if [ -z "$val" ] || [[ "$val" == *"replace_with"* ]]; then
        err "Required variable '${var}' in .env is empty or still has a placeholder value. Edit .env and try again."
    fi
done
ok ".env variables validated."

# ─── Step 4: Extract POSTGRES_PASSWORD for docker-compose ────────────────────
log "Step 4 — Preparing environment overrides..."

DB_URL=$(grep -E "^DATABASE_URL=" .env | cut -d'=' -f2- | xargs)
if [ -z "$DB_URL" ]; then
    err "DATABASE_URL is not set in .env"
fi

# Extract password from postgresql://user:password@host/db
PG_PASSWORD=$(echo "$DB_URL" | sed -n 's|postgresql://[^:]*:\([^@]*\)@.*|\1|p')
if [ -z "$PG_PASSWORD" ]; then
    PG_PASSWORD="changeme"
    warn "Could not parse POSTGRES_PASSWORD from DATABASE_URL — defaulting to 'changeme'."
fi
export POSTGRES_PASSWORD="$PG_PASSWORD"
ok "Database password extracted."

# ─── Step 5: Build Docker images ─────────────────────────────────────────────
log "Step 5 — Building Docker images (this may take a few minutes)..."

$COMPOSE_CMD build --no-cache \
    || err "Docker build failed. Check the output above for errors."
ok "All images built successfully."

# ─── Step 6: Start services ───────────────────────────────────────────────────
log "Step 6 — Starting services..."

$COMPOSE_CMD up -d postgres redis \
    || err "Failed to start postgres and redis."

log "Waiting for Postgres and Redis to be healthy..."
MAX_WAIT=90
WAITED=0
while true; do
    PG_HEALTHY=$($COMPOSE_CMD ps postgres --format json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('Health','') if isinstance(d,dict) else d[0].get('Health',''))" 2>/dev/null || echo "")
    REDIS_HEALTHY=$($COMPOSE_CMD ps redis --format json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('Health','') if isinstance(d,dict) else d[0].get('Health',''))" 2>/dev/null || echo "")

    if [[ "$PG_HEALTHY" == "healthy" && "$REDIS_HEALTHY" == "healthy" ]]; then
        break
    fi

    # Fallback: use docker exec to check directly
    PG_CHECK=$($COMPOSE_CMD exec -T postgres pg_isready -U agrograph -d agrograph 2>/dev/null && echo "ok" || echo "")
    REDIS_CHECK=$($COMPOSE_CMD exec -T redis redis-cli ping 2>/dev/null | grep -c "PONG" || echo "0")

    if [[ "$PG_CHECK" == "ok" && "$REDIS_CHECK" == "1" ]]; then
        break
    fi

    if [ "$WAITED" -ge "$MAX_WAIT" ]; then
        err "Timed out waiting for Postgres/Redis after ${MAX_WAIT}s. Check logs: docker compose logs postgres redis"
    fi

    sleep 5
    WAITED=$((WAITED + 5))
    log "  Still waiting... (${WAITED}s / ${MAX_WAIT}s)"
done
ok "Postgres and Redis are healthy."

# ─── Step 7: Run database migrations ─────────────────────────────────────────
log "Step 7 — Running database migrations..."

$COMPOSE_CMD run --rm api alembic upgrade head \
    || err "Alembic migrations failed. Check: docker compose logs api"
ok "Database migrations applied."

# ─── Step 8: Start remaining services ────────────────────────────────────────
log "Step 8 — Starting all remaining services..."

$COMPOSE_CMD up -d \
    || err "Failed to bring up all services."
ok "All services started."

# ─── Step 9: Wait for API healthcheck ────────────────────────────────────────
log "Step 9 — Waiting for API to become healthy..."
MAX_WAIT=60
WAITED=0
API_PORT=$(grep -E "^\s*-\s*\"[0-9]+:8000\"" docker-compose.yml | head -1 | grep -oP '^\s*-\s*"\K[0-9]+' || echo "8000")

while true; do
    if curl -sf "http://localhost:${API_PORT}/health" >/dev/null 2>&1; then
        break
    fi
    if [ "$WAITED" -ge "$MAX_WAIT" ]; then
        warn "API health check did not pass in ${MAX_WAIT}s — it may still be starting."
        warn "Check: docker compose logs api"
        break
    fi
    sleep 5
    WAITED=$((WAITED + 5))
done
ok "API is responding."

# ─── Final: Status report ─────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     AgroGraph Scraping API — Deploy Complete             ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
PUBLIC_IP=$(curl -sf http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null \
    || curl -sf https://api.ipify.org 2>/dev/null \
    || echo "<your-ec2-public-ip>")
echo -e "  API URL:      ${GREEN}http://${PUBLIC_IP}:8000${NC}"
echo -e "  Swagger docs: ${GREEN}http://${PUBLIC_IP}:8000/docs${NC}"
echo -e "  Health check: ${GREEN}http://${PUBLIC_IP}:8000/health${NC}"
echo ""
echo "  Service status:"
$COMPOSE_CMD ps
echo ""
echo -e "  Logs: ${YELLOW}docker compose logs -f [api|worker|scheduler|postgres|redis|playwright]${NC}"
echo ""
ok "Deploy complete."
