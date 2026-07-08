# -*- coding: utf-8 -*-
"""
Простое персистентное хранилище сырых записей об авариях в формате JSON Lines.

Бот работает непрерывно и не может (в отличие от Telethon-варианта) задним
числом выгрузить историю сообщений — поэтому каждая распознанная запись
дописывается в файл сразу по получении, а отчёт строится по накопленным
с диска данным.
"""

import json
from datetime import datetime
from pathlib import Path

_DATETIME_KEY = "__datetime__"


def _json_default(obj):
    if isinstance(obj, datetime):
        return {_DATETIME_KEY: obj.isoformat()}
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _json_object_hook(d):
    if _DATETIME_KEY in d:
        return datetime.fromisoformat(d[_DATETIME_KEY])
    return d


def append_record(path, record):
    """Дописывает одну запись в конец файла (по одной записи на строку)."""
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=_json_default, ensure_ascii=False) + "\n")


def load_records(path):
    """Загружает все накопленные записи из файла. Пустой список, если файла ещё нет."""
    p = Path(path)
    if not p.exists():
        return []
    records = []
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line, object_hook=_json_object_hook))
    return records
