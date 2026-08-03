#!/usr/bin/env bash
# Deploy de SELQUET en el droplet: trae los cambios de GitHub, instala deps si
# cambiaron y reinicia el proceso. Uso:  cd /var/www/selquet && ./deploy.sh
set -euo pipefail

cd "$(dirname "$0")"

echo "→ Trayendo cambios de GitHub…"
git pull --ff-only

echo "→ Instalando dependencias…"
./venv/bin/pip install -q -r requirements.txt

echo "→ Reiniciando la app…"
pm2 restart selquet >/dev/null

echo "✓ Deploy OK: $(git log --oneline -1)"
