# -*- coding: utf-8 -*-
"""
Сборщик данных: подключается к Telegram, обходит подчаты (темы) группы-
источника, собирает сообщения ecus_bot, строит Excel-отчёт и при
необходимости отправляет эскалационное уведомление.

Запуск:
    python fetch_telegram.py            # обычный запуск, выгрузка из Telegram
    python fetch_telegram.py --demo     # тестовый прогон на встроенных
                                         # примерах сообщений, без Telegram
                                         # (для проверки parser.py/report_builder.py)

Первый запуск потребует авторизации: Telethon запросит номер телефона и код
подтверждения, после чего сессия сохранится в файле CONFIG["SESSION_NAME"].session.
"""

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone

from parser import parse_message
from report_builder import build_report, build_alert_text

# Консоль Windows по умолчанию использует cp1251/cp866, где нет эмодзи из
# текста уведомлений — переключаем stdout/stderr на UTF-8, чтобы print() не падал.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# --- Конфигурация -----------------------------------------------------------
# Получить API_ID/API_HASH: https://my.telegram.org -> API development tools
#
# Секреты не хранятся здесь напрямую — подтягиваются из config_local.py
# (в .gitignore, не попадает в репозиторий). Скопируйте
# config_local.example.py -> config_local.py и впишите реальные значения.

CONFIG = {
    "API_ID": None,                              # обязательно: числовой ID приложения
    "API_HASH": None,                             # обязательно: хеш приложения
    "SESSION_NAME": "dtprs_session",
    "SOURCE_GROUP": "Minor ПБ (оповещ...)",       # название/username/ID группы-источника
    "ALERT_CHAT": None,                            # обязательно: чат/username/ID для эскалаций
    "BOT_SENDER": "ecus_bot",
    "DAYS_BACK": 7,
    "DATE_FROM": None,                             # datetime, переопределяет DAYS_BACK
    "DATE_TO": None,                                # datetime, по умолчанию — сейчас
    "OUTPUT_PATH": "avariynyy_otchet.xlsx",
}

try:
    from config_local import CONFIG as _LOCAL_CONFIG
    CONFIG.update(_LOCAL_CONFIG)
except ImportError:
    pass


def _resolve_period():
    date_to = CONFIG["DATE_TO"] or datetime.now(timezone.utc)
    if CONFIG["DATE_FROM"]:
        date_from = CONFIG["DATE_FROM"]
    else:
        date_from = date_to - timedelta(days=CONFIG["DAYS_BACK"])
    return _as_utc(date_from), _as_utc(date_to)


def _as_utc(dt):
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def _find_group_entity(client, source_group):
    """Находит диалог группы-источника по ID или по (под)строке названия.

    Приватные группы без публичного username нельзя получить через
    get_entity() по имени напрямую — поэтому ищем среди диалогов аккаунта.
    """
    if isinstance(source_group, int) or (isinstance(source_group, str) and source_group.lstrip("-").isdigit()):
        return await client.get_entity(int(source_group))

    async for dialog in client.iter_dialogs():
        if source_group.lower() in (dialog.name or "").lower():
            return dialog.entity

    raise RuntimeError(
        f"Группа '{source_group}' не найдена среди диалогов аккаунта. "
        "Проверьте CONFIG['SOURCE_GROUP'] и то, что аккаунт состоит в группе."
    )


async def _iter_forum_topics(client, entity):
    """Возвращает список (topic_id, topic_title) для форума с подчатами.

    Если группа не является форумом (нет тем), возвращает [(None, '')] —
    сообщения будут собраны из общего потока группы.
    """
    from telethon.tl.functions.channels import GetForumTopicsRequest

    if not getattr(entity, "forum", False):
        return [(None, "")]

    topics = []
    offset_date = 0
    offset_id = 0
    offset_topic = 0
    while True:
        result = await client(GetForumTopicsRequest(
            channel=entity, offset_date=offset_date, offset_id=offset_id,
            offset_topic=offset_topic, limit=100,
        ))
        if not result.topics:
            break
        for topic in result.topics:
            topics.append((topic.id, getattr(topic, "title", "")))
        if len(result.topics) < 100:
            break
        last = result.topics[-1]
        offset_topic = last.id
        offset_id = last.top_message
        offset_date = 0
    return topics


async def _fetch_topic_messages(client, entity, topic_id, topic_title, date_from, date_to):
    records = []
    kwargs = {"from_user": CONFIG["BOT_SENDER"], "offset_date": date_to}
    if topic_id is not None:
        kwargs["reply_to"] = topic_id

    async for message in client.iter_messages(entity, **kwargs):
        if not message.date or not message.message:
            continue
        msg_date = _as_utc(message.date)
        if msg_date < date_from:
            break
        record = parse_message(message.message, subchat=topic_title, message_date=msg_date)
        if record:
            records.append(record)
    return records


async def fetch_and_build_report():
    from telethon import TelegramClient

    if not CONFIG["API_ID"] or not CONFIG["API_HASH"]:
        raise RuntimeError("Заполните CONFIG['API_ID'] и CONFIG['API_HASH'] (см. https://my.telegram.org)")

    date_from, date_to = _resolve_period()

    async with TelegramClient(CONFIG["SESSION_NAME"], CONFIG["API_ID"], CONFIG["API_HASH"]) as client:
        entity = await _find_group_entity(client, CONFIG["SOURCE_GROUP"])
        topics = await _iter_forum_topics(client, entity)

        all_records = []
        for topic_id, topic_title in topics:
            records = await _fetch_topic_messages(client, entity, topic_id, topic_title, date_from, date_to)
            all_records.extend(records)
            print(f"  [{topic_title or 'основной поток'}] сообщений: {len(records)}")

        print(f"Всего собрано записей: {len(all_records)}")

        output_path = build_report(all_records, CONFIG["OUTPUT_PATH"])
        print(f"Отчёт сохранён: {output_path}")

        alert_text = build_alert_text(all_records)
        if alert_text:
            if not CONFIG["ALERT_CHAT"]:
                print("ВНИМАНИЕ: обнаружены аварии с простоем >8ч, но CONFIG['ALERT_CHAT'] не задан — уведомление не отправлено.")
            else:
                await client.send_message(CONFIG["ALERT_CHAT"], alert_text)
                print("Уведомление об эскалации отправлено.")
        else:
            print("Аварий с простоем >8ч не обнаружено, уведомление не требуется.")


# --- Демонстрационный режим (без подключения к Telegram) -------------------

_DEMO_MESSAGES = [
    ("Восточно-Казахстанский ДЭСД", """
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
Фактическая длительность: 0 сут. 9 ч. 15 мин.
""", 0),
    ("Карагандинский ДЭСД", """
Номер ПБ: 000000028034200
Время создания ПБ: 07.07.2026 10:00:00
Район: Октябрьский
Город: Караганда
Узел сети: Караганда MSAN_12
Группа исполнителей: ЕЦУС_Т1_Кар_СД
Зона ответственности: Карагандинский ДЭСД
Характер повреждения ПБ: Линейное
Подробное описание аварии: Обрыв кабеля
Источник аварии: Fiber cut alarm
Фактическая длительность: 0 сут. 1 ч. 30 мин.
""", 1),
]


def _run_demo():
    """Строит тестовый отчёт из встроенных примеров — без обращения к Telegram."""
    from parser import parse_message

    now = datetime.now()
    records = []
    for subchat, text, hours_ago in _DEMO_MESSAGES:
        records.append(parse_message(text.strip(), subchat=subchat, message_date=now - timedelta(hours=hours_ago)))

    output_path = build_report(records, CONFIG["OUTPUT_PATH"], now=now)
    print(f"[DEMO] Отчёт сохранён: {output_path}")

    alert_text = build_alert_text(records)
    print("[DEMO] Текст уведомления об эскалации:" if alert_text else "[DEMO] Эскалаций нет.")
    if alert_text:
        print(alert_text)


def main():
    parser_args = argparse.ArgumentParser()
    parser_args.add_argument("--demo", action="store_true", help="тестовый прогон без Telegram")
    args = parser_args.parse_args()

    if args.demo:
        _run_demo()
        return

    try:
        asyncio.run(fetch_and_build_report())
    except RuntimeError as exc:
        print(f"Ошибка конфигурации: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
