#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python_bin="${CRM_PYTHON:-python3}"
"$python_bin" -c 'import sys; assert sys.version_info >= (3, 10), "Для CRM нужен Python 3.10 или новее"'
if [[ ! -d .venv ]]; then "$python_bin" -m venv .venv; fi
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python - <<'PY'
from pathlib import Path
import secrets
from cryptography.fernet import Fernet
p = Path('.env')
if not p.exists():
    content = Path('.env.example').read_text()
    content = content.replace('CRM_INTEGRATION_KEY=\n', 'CRM_INTEGRATION_KEY='+Fernet.generate_key().decode()+'\n')
    content = content.replace('CRM_SECRET_KEY=\n', f'CRM_SECRET_KEY={secrets.token_urlsafe(48)}\n')
    content = content.replace('CRM_DB_PASSWORD=\n', f'CRM_DB_PASSWORD={secrets.token_urlsafe(32)}\n')
    p.write_text(content)
    p.chmod(0o600)
    print('Создан отдельный локальный конфиг CRM.')
PY
(cd web && npm ci --no-audit --no-fund)
(cd backend && ../.venv/bin/python manage.py migrate)
printf '%s\n' 'CRM подготовлена. Запуск: ./scripts/dev.sh'
