#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${SDAC_APP_DIR:-$(pwd)}"
PYTHON="${SDAC_PYTHON:-}"

if [[ -z "$PYTHON" ]]; then
    if [[ -x "$APP_DIR/venv/bin/python" ]]; then
        PYTHON="$APP_DIR/venv/bin/python"
    else
        PYTHON="$(command -v python3)"
    fi
fi

cd "$APP_DIR"

echo "SDAC release checklist"
echo "App directory: $APP_DIR"
echo

check() {
    local label="$1"
    shift
    printf '==> %s\n' "$label"
    "$@"
    echo
}

check "Python compile" "$PYTHON" -m py_compile \
    bot.py \
    dashboard.py \
    config.py \
    database_backend.py \
    database_migrations.py \
    observability.py \
    scripts/reset_admin_login.py

if command -v git >/dev/null 2>&1 && [[ -d .git ]]; then
    check "Git status" git status --short
fi

if [[ -f scripts/check_production.sh ]]; then
    echo "Optional production check:"
    echo "  SDAC_DOMAIN=your.domain bash scripts/check_production.sh"
fi

echo "Manual release review:"
echo "  - README and RELEASE.md updated for official releases."
echo "  - dist assets rebuilt with tools/build_installers.ps1."
echo "  - latest-experimental tested on your verification server."
echo "  - latest-official only moved after validation."
