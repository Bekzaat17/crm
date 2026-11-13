"""Только тесты: обе стороны протокола с настоящей моделью Resident в одной временной БД."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[4] / "rehubpro-main"))
from config.settings import *  # noqa: F403,E402

INSTALLED_APPS = [*INSTALLED_APPS, "references", "residents", "crm_bridge"]  # noqa: F405
ROOT_URLCONF = "crm.tests.bridge_urls"
CRM_BRIDGE_ENABLED = True
