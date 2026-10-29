#!/usr/bin/env bash

# Resolve the directory of this script
cd "$(cd "$(dirname "$0")" && pwd)"

# ANSI colors
GREEN="\033[1;32m"
BLUE="\033[1;34m"
YELLOW="\033[1;33m"
RED="\033[1;31m"
NC="\033[0m" # No Color

echo -e "${BLUE}========================================================${NC}"
echo -e "${BLUE}                 Starting PDFly Suite                   ${NC}"
echo -e "${BLUE}========================================================${NC}"
echo ""

# Find Python executable
PYTHON_CMD=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
fi

if [ -z "$PYTHON_CMD" ]; then
    echo -e "${RED}[ERROR] Python is not installed or not found in PATH!${NC}"
    echo "Please install Python 3.10+ from https://www.python.org/"
    exit 1
fi

# Activate virtual environment if present
if [ -f "venv/bin/activate" ]; then
    echo -e "${GREEN}[INFO] Activating virtual environment (venv)...${NC}"
    source "venv/bin/activate"
    PYTHON_CMD="python"
elif [ -f ".venv/bin/activate" ]; then
    echo -e "${GREEN}[INFO] Activating virtual environment (.venv)...${NC}"
    source ".venv/bin/activate"
    PYTHON_CMD="python"
elif [ -f "venv/Scripts/activate" ]; then
    # Git Bash on Windows
    echo -e "${GREEN}[INFO] Activating virtual environment (venv/Scripts)...${NC}"
    source "venv/Scripts/activate"
    PYTHON_CMD="python"
elif [ -f ".venv/Scripts/activate" ]; then
    # Git Bash on Windows
    echo -e "${GREEN}[INFO] Activating virtual environment (.venv/Scripts)...${NC}"
    source ".venv/Scripts/activate"
    PYTHON_CMD="python"
fi

# Verify dependencies
echo -e "${GREEN}[INFO] Checking dependencies...${NC}"
if ! $PYTHON_CMD -c "import django, pymupdf, pypdf, reportlab, PIL, whitenoise" >/dev/null 2>&1; then
    echo -e "${YELLOW}[INFO] Installing missing dependencies from requirements.txt...${NC}"
    $PYTHON_CMD -m pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo -e "${RED}[ERROR] Failed to install required dependencies.${NC}"
        exit 1
    fi
fi

# Run database migrations
echo -e "${GREEN}[INFO] Applying database migrations...${NC}"
$PYTHON_CMD manage.py migrate --noinput

# Launch default browser in the background after 2 seconds
URL="http://127.0.0.1:8000"
(
    sleep 2
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$URL" >/dev/null 2>&1 &
    elif command -v open >/dev/null 2>&1; then
        open "$URL" >/dev/null 2>&1 &
    elif command -v cmd.exe >/dev/null 2>&1; then
        cmd.exe /c start "$URL" >/dev/null 2>&1 &
    elif command -v explorer.exe >/dev/null 2>&1; then
        explorer.exe "$URL" >/dev/null 2>&1 &
    fi
) &

echo ""
echo -e "${GREEN}========================================================${NC}"
echo -e "${GREEN}  PDFly is running successfully!                         ${NC}"
echo ""
echo -e "  * URL:         ${BLUE}${URL}${NC}"
echo -e "  * Stop Server: Press ${YELLOW}Ctrl+C${NC} in this window"
echo -e "${GREEN}========================================================${NC}"
echo ""

# Start Django development server
$PYTHON_CMD manage.py runserver 127.0.0.1:8000
