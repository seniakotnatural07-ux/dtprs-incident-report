# -*- coding: utf-8 -*-
"""
Генерирует docs/data.json для веб-дашборда (docs/index.html) на основе
встроенных ТЕСТОВЫХ данных (demo_data.py).

Репозиторий публичный, поэтому в docs/ (GitHub Pages) сознательно не
попадают реальные данные об авариях на сети — только демонстрационный
набор. Реальный отчёт (.xlsx) строится локально ботом и никуда не публикуется.

Запуск:
    python generate_dashboard_data.py
"""

from datetime import datetime

from demo_data import get_demo_records
from report_builder import export_dashboard_json

if __name__ == "__main__":
    now = datetime.now()
    records = get_demo_records(now=now)
    path = export_dashboard_json(records, "docs/data.json", now=now)
    print(f"Демо-данные для дашборда сохранены: {path}")
