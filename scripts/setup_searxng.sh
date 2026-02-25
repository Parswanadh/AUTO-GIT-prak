#!/bin/bash
# ============================================
# SearXNG Setup Script for Windows/WSL + Docker
# ============================================
# This script sets up SearXNG as a self-hosted metasearch engine
# RAM usage: ~150-200MB (optimized for low resource usage)
# Port: 8888
# ============================================

set -e  # Exit on error

echo "============================================"
echo "SearXNG Setup - Self-Hosted Search Engine"
echo "============================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    echo "Please install Docker Desktop for Windows: https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo -e "${RED}Error: Docker is not running${NC}"
    echo "Please start Docker Desktop"
    exit 1
fi

echo -e "${GREEN}✓${NC} Docker is running"

# Create project directory
PROJECT_DIR="$HOME/searxng-project"
SEARXNG_DIR="$PROJECT_DIR/searxng"

echo ""
echo "Creating directory structure..."
mkdir -p "$SEARXNG_DIR"
cd "$SEARXNG_DIR"
echo -e "${GREEN}✓${NC} Created directory: $SEARXNG_DIR"

# Generate secret key
echo ""
echo "Generating secret key..."
SECRET_KEY=$(openssl rand -hex 32)
echo -e "${GREEN}✓${NC} Secret key generated"

# Create docker-compose.yml
echo ""
echo "Creating docker-compose.yml..."
cat > docker-compose.yml << 'EOF'
version: '3.7'

services:
  searxng:
    container_name: searxng
    image: searxng/searxng:latest
    restart: unless-stopped
    ports:
      - "8888:8080"
    volumes:
      - ./settings.yml:/etc/searxng/settings.yml:ro
      - ./uwsgi.ini:/etc/searxng/uwsgi.ini:ro
    environment:
      - SEARXNG_BASE_URL=http://localhost:8888/
      - SEARXNG_SECRET=${SECRET_KEY}
    networks:
      - searxng
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

networks:
  searxng:
    driver: bridge
EOF

# Replace secret key in docker-compose.yml
sed -i "s/\${SECRET_KEY}/$SECRET_KEY/g" docker-compose.yml

echo -e "${GREEN}✓${NC} docker-compose.yml created"

# Create optimized settings.yml
echo ""
echo "Creating settings.yml..."
cat > settings.yml << 'EOF'
# SearXNG Configuration - Optimized for API usage
# RAM usage: ~150-200MB

general:
  debug: false
  instance_name: "SearXNG"
  privacypolicy_url: false
  donation_url: false
  contact_url: false
  enable_metrics: false

search:
  safe_search: 0  # 0=off, 1=moderate, 2=strict
  autocomplete: ""
  default_lang: "en"
  ban_time_on_fail: 5
  max_ban_time_on_fail: 120
  formats:
    - html
    - json

server:
  port: 8080
  bind_address: "0.0.0.0"
  secret_key: "REPLACE_WITH_SECRET"
  limiter: false  # Disabled for localhost
  image_proxy: false
  method: "GET"
  default_http_headers:
    X-Content-Type-Options: nosniff
    X-Download-Options: noopen
    X-Robots-Tag: noindex, nofollow
    Referrer-Policy: no-referrer

ui:
  static_use_hash: true
  default_locale: "en"
  query_in_title: true
  infinite_scroll: false
  center_alignment: false
  results_on_new_tab: false
  advanced_search: true
  default_theme: simple
  theme_args:
    simple_style: auto

# Enabled search engines - optimized selection
engines:
  - name: google
    engine: google
    shortcut: go
    use_mobile_ui: false
    
  - name: bing
    engine: bing
    shortcut: bi
    
  - name: duckduckgo
    engine: duckduckgo
    shortcut: ddg
    
  - name: wikipedia
    engine: wikipedia
    shortcut: wp
    base_url: 'https://{language}.wikipedia.org/'
    
  - name: github
    engine: github
    shortcut: gh
    
  - name: stack overflow
    engine: stackexchange
    shortcut: so
    api_site: 'stackoverflow'
    categories: [it, q&a]
    
  - name: arxiv
    engine: arxiv
    shortcut: arx
    categories: science
    
  - name: python documentation
    engine: xpath
    shortcut: pydoc
    categories: [it]
    paging: true
    search_url: https://docs.python.org/3/search.html?q={query}&check_keywords=yes&area=default
    url_xpath: //li[@class="search-result"]/a/@href
    title_xpath: //li[@class="search-result"]/a
    content_xpath: //li[@class="search-result"]/p
    first_page_num: 0

enabled_plugins:
  - 'Hash plugin'
  - 'Self Information'
  - 'Tracker URL remover'
  - 'Open Access DOI rewrite'

doi_resolvers:
  oadoi.org: 'https://oadoi.org/'
  doi.org: 'https://doi.org/'

default_doi_resolver: 'oadoi.org'
EOF

# Replace secret key in settings.yml
sed -i "s/REPLACE_WITH_SECRET/$SECRET_KEY/g" settings.yml

echo -e "${GREEN}✓${NC} settings.yml created"

# Create optimized uwsgi.ini for low RAM usage
echo ""
echo "Creating uwsgi.ini (RAM optimized)..."
cat > uwsgi.ini << 'EOF'
[uwsgi]
# uWSGI core
# ----------
# https://uwsgi-docs.readthedocs.io/en/latest/Options.html#uwsgi-core

# Who will run the code
uid = searxng
gid = searxng

# Disable logging for privacy (remove if debugging)
disable-logging = true
logger = stderr

# Number of workers (processes)
# Optimized for low RAM: 1 worker = ~150MB
workers = 1

# Number of threads per worker
# 4 threads is optimal for I/O bound tasks (web search)
threads = 4

# The right granted on the created socket
chmod-socket = 666

# Plugin to use and interpreter config
single-interpreter = true
master = true
plugin = python3
lazy-apps = true
enable-threads = 4

# Buffer size
buffer-size = 8192

# Load application
module = searx.webapp
pythonpath = /usr/local/searxng/

# Serve static files
static-map = /static=/usr/local/searxng/searx/static

# Set the SCRIPT_NAME variable
manage-script-name = true

# Disable request logging (privacy)
# Remove these if you need to debug
disable-logging = false
log-slow = 1000
log-large = 8192

# No keep-alive
# See https://github.com/searxng/searxng-docker/issues/24
add-header = Connection: close

# uwsgi serves the static files
static-map = /static=/usr/local/searxng/searx/static
# expires set to one day
static-expires = /* 86400
static-gzip-all = true
offload-threads = 4
EOF

echo -e "${GREEN}✓${NC} uwsgi.ini created"

# Start SearXNG
echo ""
echo "Starting SearXNG container..."
docker-compose up -d

echo -e "${GREEN}✓${NC} SearXNG container started"

# Wait for SearXNG to be ready
echo ""
echo "Waiting for SearXNG to start (this may take 30-60 seconds)..."
sleep 10

MAX_RETRIES=30
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:8888 > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} SearXNG is ready!"
        break
    fi
    echo -n "."
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo -e "${RED}Error: SearXNG failed to start${NC}"
    echo "Check logs with: docker logs searxng"
    exit 1
fi

# Test the API
echo ""
echo "Testing SearXNG API..."
TEST_RESULT=$(curl -s "http://localhost:8888/search?q=test&format=json" | head -c 100)

if [ -n "$TEST_RESULT" ]; then
    echo -e "${GREEN}✓${NC} SearXNG API is working!"
else
    echo -e "${YELLOW}⚠${NC} API test returned empty response (might still be initializing)"
fi

# Print success message
echo ""
echo "============================================"
echo -e "${GREEN}✓ SearXNG Setup Complete!${NC}"
echo "============================================"
echo ""
echo "Access Points:"
echo "  Web UI:  http://localhost:8888"
echo "  API:     http://localhost:8888/search?q=query&format=json"
echo ""
echo "Configuration:"
echo "  Directory: $SEARXNG_DIR"
echo "  Settings:  $SEARXNG_DIR/settings.yml"
echo "  Compose:   $SEARXNG_DIR/docker-compose.yml"
echo ""
echo "Resource Usage:"
echo "  RAM: ~150-200MB"
echo "  Port: 8888"
echo ""
echo "Docker Commands:"
echo "  View logs:   docker logs searxng"
echo "  Restart:     docker restart searxng"
echo "  Stop:        docker stop searxng"
echo "  Start:       docker start searxng"
echo "  Remove:      docker-compose down"
echo ""
echo "Test API:"
echo "  curl 'http://localhost:8888/search?q=python&format=json'"
echo ""
echo -e "${GREEN}Happy searching!${NC}"
