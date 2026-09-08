#!/bin/bash
set -e

echo "Starting CV Web Application startup validation..."

# Check required directories exist
echo "Checking directory structure..."
for dir in /app/data /app/data/cvs /app/data/exports /app/scripts /app/templates /app/pandoc; do
    if [ ! -d "$dir" ]; then
        echo "ERROR: Required directory $dir not found"
        exit 1
    fi
    echo "✓ Directory $dir exists"
done

# Check required files exist
echo "Checking required files..."
for file in /app/scripts/export.sh /app/templates/cv.latex /app/pandoc/defaults.yaml; do
    if [ ! -f "$file" ]; then
        echo "ERROR: Required file $file not found"
        exit 1
    fi
    echo "✓ File $file exists"
done

# Check Pandoc installation and version
echo "Checking Pandoc installation..."
if ! command -v pandoc &> /dev/null; then
    echo "ERROR: Pandoc not installed"
    exit 1
fi
PANDOC_VERSION=$(pandoc --version | head -n1)
echo "✓ Pandoc available: $PANDOC_VERSION"

# Check LaTeX installation
echo "Checking LaTeX installation..."
if ! command -v xelatex &> /dev/null; then
    echo "ERROR: XeLaTeX not installed"
    exit 1
fi
echo "✓ XeLaTeX available"

# Check Tectonic (optional)
if command -v tectonic &> /dev/null; then
    TECTONIC_VERSION=$(tectonic --version)
    echo "✓ Tectonic available: $TECTONIC_VERSION"
else
    echo "⚠ Tectonic not available (XeLaTeX will be used as fallback)"
fi

# Check Python dependencies
echo "Checking Python dependencies..."
python -c "
try:
    import fastapi
    import uvicorn
    import pydantic
    import yaml
    import aiofiles
    import httpx
    print('✓ All Python dependencies available')
except ImportError as e:
    print(f'ERROR: Missing Python dependency: {e}')
    exit(1)
"

# Test basic Pandoc functionality
echo "Testing Pandoc functionality..."
echo "# Test" | pandoc -f markdown -t html > /dev/null
if [ $? -eq 0 ]; then
    echo "✓ Pandoc basic functionality test passed"
else
    echo "ERROR: Pandoc functionality test failed"
    exit 1
fi

# Check write permissions for data directories
echo "Checking write permissions..."
for dir in /app/data/cvs /app/data/exports; do
    if [ ! -w "$dir" ]; then
        echo "ERROR: No write permission for $dir"
        exit 1
    fi
    echo "✓ Write permission for $dir"
done

echo "✅ Startup validation completed successfully"