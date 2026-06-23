#!/usr/bin/env bash
# =====================================================
# PocketLedger - Git Bash / macOS / Linux startup
# Portable: no hardcoded paths, auto-finds Python
# =====================================================
set -e

cd "$(dirname "$0")/.."
PROJ="$(pwd)"

VPY="my_env/Scripts/python.exe"

echo
echo "=============================================================="
echo "  PocketLedger - Personal Finance Analysis System"
echo "=============================================================="

# ---- 0. Ensure venv exists ----
if [ ! -x "$VPY" ]; then
    echo
    echo "[0/4] No venv found. Looking for Python..."
    SYS_PY=""

    # Scan known install dirs first (clean standalone Pythons)
    for base in "$LOCALAPPDATA/Programs/Python" "/c/Users/$USER/AppData/Local/Programs/Python"; do
        if [ -d "$base" ]; then
            for d in "$base"/*/python.exe; do
                if [ -x "$d" ]; then SYS_PY="$d"; break 2; fi
            done
        fi
    done

    # Fallback: python on PATH (skip Conda + Windows Store stubs)
    if [ -z "$SYS_PY" ] && command -v python >/dev/null 2>&1; then
        if python -c "import sys; sys.exit(1 if 'conda' in sys.version.lower() else 0)" 2>/dev/null; then
            SYS_PY="python"
        fi
    fi

    if [ -z "$SYS_PY" ]; then
        echo "[FAIL] No Python found on this system."
        echo "       Install Python 3.10+ from https://python.org"
        read -rp "Press Enter to exit..."
        exit 1
    fi

    echo "Found: $SYS_PY ($(command -v "$SYS_PY"))"
    "$SYS_PY" -m venv "my_env"
    echo "[ OK ] my_env created"
fi

# ---- 1. Check & install dependencies ----
echo
echo "[2/4] Checking dependencies..."

if "$VPY" -c "import fastapi,pandas,numpy,openpyxl,mlxtend,prophet,statsmodels,tabulate,uvicorn,python_multipart" 2>/dev/null; then
    echo "[ OK ] All dependencies ready"
else
    echo "[INFO] Installing dependencies..."
    "$VPY" -m pip install -r "start/requirements.txt" \
        -i https://pypi.tuna.tsinghua.edu.cn/simple \
        --trusted-host pypi.tuna.tsinghua.edu.cn 2>/dev/null || \
    "$VPY" -m pip install -r "start/requirements.txt"
    echo "[ OK ] Dependencies installed"
fi

# ---- 2. Data directories ----
echo
echo "[3/4] Checking data directories..."
mkdir -p data predata logs
if [ -f "data/my_payment.csv" ]; then
    lines=$(wc -l < "data/my_payment.csv")
    echo "[ OK ] data/my_payment.csv ready ($((lines - 1)) records)"
else
    echo "[INFO] No data yet - upload via web UI"
fi

# ---- 3. Start ----
echo
echo "[4/4] Starting server on http://127.0.0.1:8765"
echo "=============================================================="
echo

"$VPY" src/mypayment_api.py
