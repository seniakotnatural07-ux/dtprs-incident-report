# -*- coding: utf-8 -*-
"""
Парсер сообщений ecus_bot об аварийных ситуациях на сети.

Каждое сообщение бота представляет собой текст вида:

    Номер ПБ: 000000028034134
    Время создания ПБ: 07.07.2026 06:52:39
    Район: Уланский
    Город: Отрадное
    Узел сети: Отрадное DSLAM_E5600
    Группа исполнителей: ЕЦУС_Т1_Аст_СД
    Зона ответственности: Восточно-Казахстанский ДЭСД
    Характер повреждения ПБ: Станционное
    Подробное описание аварии: Устройство недоступно в Zabbix
    Источник аварии: Unavailable by ICMP ping
    Фактическая длительность: 0 сут. 3 ч. 15 мин.

parse_message() превращает такой текст в словарь с нормализованными полями.
"""

import re
from datetime import datetime

# Соответствие "человеческих" заголовков полей в сообщении бота -> ключи записи.
# Ключи в словаре ниже приведены к нижнему регистру и без лишних пробелов,
# чтобы разбор не зависел от мелких расхождений в оформлении заголовков ecus_bot.
FIELD_ALIASES = {
    "номер пб": "pb_number",
    "время создания пб": "created_at_raw",
    "район": "district",
    "город": "city",
    "узел сети": "node",
    "группа исполнителей": "executor_group",
    "зона ответственности": "zone",
    "характер повреждения пб": "damage_type",
    "подробное описание аварии": "description",
    "источник аварии": "source",
    "фактическая длительность": "duration_raw",
}

# Обязательные поля записи. Сообщение без Номера ПБ или длительности
# не может быть использовано для дедупликации/агрегации и отбрасывается.
REQUIRED_FIELDS = ("pb_number", "duration_raw")

_LINE_RE = re.compile(r"^\s*([^:]+?)\s*:\s*(.*\S)?\s*$")
_DURATION_RE = re.compile(
    r"(?:(\d+)\s*сут\.?)?\s*(?:(\d+)\s*ч\.?)?\s*(?:(\d+)\s*мин\.?)?",
    re.IGNORECASE,
)
_DATE_FORMATS = ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y")


def parse_duration_to_minutes(text):
    """Преобразует '0 сут. 3 ч. 15 мин.' в количество минут (int).

    Возвращает None, если строку не удалось разобрать.
    """
    if not text:
        return None
    match = _DURATION_RE.search(text)
    if not match or not any(match.groups()):
        return None
    days, hours, minutes = (int(g) if g else 0 for g in match.groups())
    return days * 24 * 60 + hours * 60 + minutes


def format_minutes(total_minutes):
    """Обратное преобразование: минуты -> 'N сут. N ч. N мин.'"""
    if total_minutes is None:
        return ""
    total_minutes = int(total_minutes)
    days, rem = divmod(total_minutes, 24 * 60)
    hours, minutes = divmod(rem, 60)
    return f"{days} сут. {hours} ч. {minutes} мин."


def parse_datetime(text):
    """Разбирает 'ДД.ММ.ГГГГ ЧЧ:ММ:СС' в datetime. None, если не удалось."""
    if not text:
        return None
    text = text.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def parse_message(text, subchat=None, message_date=None):
    """Разбирает текст сообщения ecus_bot в структурированную запись.

    Параметры:
        text: исходный текст сообщения Telegram.
        subchat: название подчата (темы), в котором опубликовано сообщение.
        message_date: datetime отправки сообщения в Telegram (метаданные
            платформы, а не поле "Время создания ПБ" из текста) — используется
            для листа "Текущие аварии" и листа "Сырые данные".

    Возвращает словарь записи или None, если сообщение не является
    валидным сообщением ecus_bot (не содержит обязательных полей).
    """
    if not text:
        return None

    fields = {}
    for raw_line in text.splitlines():
        m = _LINE_RE.match(raw_line)
        if not m:
            continue
        label, value = m.group(1), m.group(2) or ""
        key = FIELD_ALIASES.get(label.strip().lower())
        if key:
            fields[key] = value.strip()

    if not all(field in fields for field in REQUIRED_FIELDS):
        return None

    duration_minutes = parse_duration_to_minutes(fields.get("duration_raw"))
    if duration_minutes is None:
        return None

    created_at = parse_datetime(fields.get("created_at_raw"))

    record = {
        "subchat": subchat or "",
        "pb_number": fields.get("pb_number", ""),
        "created_at": created_at,
        "created_at_raw": fields.get("created_at_raw", ""),
        "district": fields.get("district", ""),
        "city": fields.get("city", ""),
        "node": fields.get("node", ""),
        "executor_group": fields.get("executor_group", ""),
        "zone": fields.get("zone", ""),
        "damage_type": fields.get("damage_type", ""),
        "description": fields.get("description", ""),
        "source": fields.get("source", ""),
        "duration_raw": fields.get("duration_raw", ""),
        "duration_minutes": duration_minutes,
        "message_date": message_date,
    }
    return record


def deduplicate(records):
    """Оставляет по каждому Номеру ПБ только запись с максимальной длительностью.

    При равной длительности побеждает запись с более поздним message_date
    (более свежее обновление).
    """
    best_by_pb = {}
    for rec in records:
        pb = rec.get("pb_number")
        if not pb:
            continue
        current = best_by_pb.get(pb)
        if current is None:
            best_by_pb[pb] = rec
            continue
        cur_dur = current.get("duration_minutes") or 0
        new_dur = rec.get("duration_minutes") or 0
        if new_dur > cur_dur:
            best_by_pb[pb] = rec
        elif new_dur == cur_dur:
            cur_date = current.get("message_date")
            new_date = rec.get("message_date")
            if new_date and (not cur_date or new_date > cur_date):
                best_by_pb[pb] = rec
    return list(best_by_pb.values())
