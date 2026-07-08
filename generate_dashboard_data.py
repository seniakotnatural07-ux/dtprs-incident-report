# -*- coding: utf-8 -*-
"""
Генерирует docs/data.json для веб-дашборда (docs/index.html).

По умолчанию берёт встроенные ТЕСТОВЫЕ данные (demo_data.py). Флаг
--source real переключает на реальные данные из локального хранилища
(raw_messages.jsonl) — используйте осознанно: это публикует данные на
GitHub Pages, видимые всем в интернете.

Запуск:
    python generate_dashboard_data.py                # демо-данные
    python generate_dashboard_data.py --source real   # реальные данные из raw_messages.jsonl
"""

import argparse
from datetime import datetime

from report_builder import export_dashboard_json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--source", choices=["demo", "real"], default="demo",
        help="demo — встроенные тестовые сообщения; real — локальный файл с реальными данными",
    )
    ap.add_argument(
        "--input", default="raw_messages.jsonl",
        help="путь к файлу с реальными записями (используется только при --source real)",
    )
    args = ap.parse_args()

    now = datetime.now()
    if args.source == "real":
        import storage
        records = storage.load_records(args.input)
    else:
        from demo_data import get_demo_records
        records = get_demo_records(now=now)

    path = export_dashboard_json(records, "docs/data.json", now=now)
    print(f"Данные для дашборда сохранены: {path} (источник: {args.source}, записей: {len(records)})")


if __name__ == "__main__":
    main()
