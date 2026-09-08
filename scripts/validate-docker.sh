#!/bin/bash
set -e

echo "🐳 Docker Setup Validation Script"
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    if [ "$1" -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
    else
        echo -e "${RED}❌ $2${NC}"
        exit 1
    fi
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "ℹ️  $1"
}

# Run from the repository root regardless of where the script was invoked.
ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

# Check Docker installation
print_info "Checking Docker installation..."
docker --version > /dev/null 2>&1
print_status $? "Docker is installed"

# Compose ships either as a `docker compose` plugin or as a standalone
# `docker-compose` binary. Accept whichever is present rather than assuming.
print_info "Checking Docker Compose installation..."
COMPOSE=""
if docker compose version > /dev/null 2>&1; then
    COMPOSE="docker compose"
elif docker-compose version > /dev/null 2>&1; then
    COMPOSE="docker-compose"
fi

if [ -z "$COMPOSE" ]; then
    echo -e "${RED}❌ Docker Compose is not installed${NC}"
    echo "   Install Docker Desktop, or 'brew install docker-compose'."
    exit 1
fi
echo -e "${GREEN}✅ Docker Compose is installed ($COMPOSE)${NC}"

# Check if Docker daemon is running
print_info "Checking Docker daemon..."
docker info > /dev/null 2>&1
print_status $? "Docker daemon is running"

# Validate compose file syntax
print_info "Validating docker-compose.yml..."
$COMPOSE config > /dev/null 2>&1
print_status $? "docker-compose.yml is valid"

print_info "Validating docker-compose.prod.yml..."
$COMPOSE -f docker-compose.prod.yml config > /dev/null 2>&1
print_status $? "docker-compose.prod.yml is valid"

# Check required directories. These are bind-mounted at run time and hold
# personal data, so they are gitignored and may legitimately be absent on a
# fresh clone.
print_info "Checking required directories..."
for dir in data cv exports pandoc templates scripts; do
    if [ -d "./$dir" ]; then
        echo -e "${GREEN}✅ Directory $dir exists${NC}"
    else
        print_warning "Directory $dir does not exist - will be created during startup"
    fi
done

# Check required files
print_info "Checking required files..."
required_files=(
    "backend/requirements.txt"
    "frontend-next/package.json"
    "Dockerfile"
    "docker-compose.yml"
    "docker-compose.prod.yml"
    "scripts/export.sh"
    "templates/cv.latex"
    "pandoc/defaults.yaml"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✅ File $file exists${NC}"
    else
        echo -e "${RED}❌ Required file $file is missing${NC}"
        exit 1
    fi
done

# Check available system resources
print_info "Checking system resources..."
available_memory=$(docker system info --format '{{.MemTotal}}' 2>/dev/null || echo "0")
if [ "$available_memory" -gt 2000000000 ]; then
    echo -e "${GREEN}✅ Sufficient memory available (>2GB)${NC}"
else
    print_warning "Less than 2GB memory available - the TeX build layer may struggle"
fi

# Check disk space. The image bundles a TeX distribution and needs ~3GB.
available_space=$(df -k . | tail -1 | awk '{print $4}')
if [ "$available_space" -gt 3000000 ]; then
    echo -e "${GREEN}✅ Sufficient disk space available (>3GB)${NC}"
else
    print_warning "Less than 3GB disk space available - the image bundles TeX and may not fit"
fi

echo ""
echo "🎉 Docker setup validation completed successfully!"
echo ""
echo "Next steps:"
echo "1. Build and run:    $COMPOSE up --build -d"
echo "2. Production run:   $COMPOSE -f docker-compose.prod.yml up --build -d"
echo "3. Check health:     curl http://localhost:8002/health"
echo ""
echo "For more information, see README.md"
