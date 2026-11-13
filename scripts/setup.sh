#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python_bin="${CRM_PYTHON:-python3}"
"$python_bin" -c 'import sys; assert sys.version_info >= (3, 10), "Для CRM нужен Python 3.10 или новее"'
if [[ ! -d .venv ]]; then "$python_bin" -m venv .venv; fi
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python - <<'PY'
from pathlib import Path
import base64
import secrets
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def b64(data):
    return base64.urlsafe_b64encode(data).decode().rstrip('=')


def vapid_keys():
    key = ec.generate_private_key(ec.SECP256R1())
    private = key.private_numbers().private_value.to_bytes(32, 'big')
    public = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return b64(private), b64(public)


p = Path('.env')
if not p.exists():
    content = Path('.env.example').read_text()
    content = content.replace('CRM_INTEGRATION_KEY=\n', 'CRM_INTEGRATION_KEY='+Fernet.generate_key().decode()+'\n')
    content = content.replace('CRM_SECRET_KEY=\n', f'CRM_SECRET_KEY={secrets.token_urlsafe(48)}\n')
    content = content.replace('CRM_DB_PASSWORD=\n', f'CRM_DB_PASSWORD={secrets.token_urlsafe(32)}\n')
    p.write_text(content)
    p.chmod(0o600)
    print('Создан отдельный локальный конфиг CRM.')
# Администратор платформы: единственный, кто создаёт компании.
content = p.read_text()
if 'CRM_SUPERUSER_EMAIL=' not in content:
    content = content.rstrip('\n') + f'\nCRM_SUPERUSER_EMAIL=admin@localhost\nCRM_SUPERUSER_PASSWORD={secrets.token_urlsafe(18)}\n'
    p.write_text(content)
    print('Добавлены учётные данные администратора платформы в .env.')
# Ключи Web Push добавляются и в ранее созданный .env, если их там нет.
content = p.read_text()
if 'CRM_VAPID_PRIVATE_KEY=' not in content or 'CRM_VAPID_PRIVATE_KEY=\n' in content:
    private, public = vapid_keys()
    lines = [l for l in content.splitlines() if not l.startswith(('CRM_VAPID_PRIVATE_KEY=', 'CRM_VAPID_PUBLIC_KEY='))]
    lines += [f'CRM_VAPID_PUBLIC_KEY={public}', f'CRM_VAPID_PRIVATE_KEY={private}']
    p.write_text('\n'.join(lines) + '\n')
    print('Добавлены ключи уведомлений браузера (VAPID).')
PY
(cd web && npm ci --no-audit --no-fund)
(cd backend && ../.venv/bin/python manage.py migrate && ../.venv/bin/python manage.py ensure_superuser)
printf '%s\n' 'CRM подготовлена. Запуск: ./scripts/dev.sh'
