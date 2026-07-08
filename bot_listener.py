# -*- coding: utf-8 -*-
"""
Сборщик данных на основе Telegram-бота (Bot API, python-telegram-bot).

В отличие от варианта на Telethon (fetch_telegram.py, требует личный
аккаунт и my.telegram.org), этот бот не может выгрузить историю сообщений
задним числом — он должен работать непрерывно и копит распознанные
сообщения ecus_bot в локальный файл (CONFIG["DATA_FILE"]) по мере их
получения. Раз в CONFIG["REPORT_INTERVAL_MINUTES"] минут строится Excel-
отчёт по всем накопленным данным и проверяется условие эскалации (простой
> 8 часов), при срабатывании — отправляется уведомление в CONFIG["ALERT_CHAT"].

ВАЖНО: ecus_bot — тоже бот. Telegram по умолчанию не доставляет ботам
сообщения от других ботов в группе, даже с отключённым Group Privacy —
единственный надёжный способ это обойти: сделать этого бота
администратором группы-источника (см. README.md).

Первый запуск / настройка:
    1. Создать бота через @BotFather, получить токен -> CONFIG["BOT_TOKEN"].
    2. Добавить бота в группу-источник и сделать администратором.
    3. Запустить `python bot_listener.py` с пустым CONFIG["SOURCE_CHAT_ID"] —
       бот включит режим обнаружения и в консоли покажет chat_id группы при
       получении любого сообщения в ней.
    4. Вписать увиденный chat_id в CONFIG["SOURCE_CHAT_ID"], перезапустить.

Запуск:
    python bot_listener.py
"""

import sys
from datetime import datetime

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

import storage
from parser import parse_message
from report_builder import build_alert_text, build_report

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# --- Конфигурация -----------------------------------------------------------
#
# Секреты (токен, chat_id) не хранятся здесь напрямую — они подтягиваются из
# config_local.py, который в .gitignore и не попадает в репозиторий.
# Скопируйте config_local.example.py -> config_local.py и впишите реальные
# значения (см. README.md).

CONFIG = {
    "BOT_TOKEN": None,                       # обязательно: токен от @BotFather
    "SOURCE_CHAT_ID": None,                   # обязательно: numeric ID группы-источника (см. режим обнаружения выше)
    "ALERT_CHAT": None,                        # обязательно: chat_id/username чата для уведомлений об эскалации
    "BOT_SENDER": "ecus_bot",
    "DATA_FILE": "raw_messages.jsonl",
    "OUTPUT_PATH": "avariynyy_otchet.xlsx",
    "REPORT_INTERVAL_MINUTES": 60,
}

try:
    from config_local import CONFIG as _LOCAL_CONFIG
    CONFIG.update(_LOCAL_CONFIG)
except ImportError:
    pass

# message_thread_id -> название темы (подчата), заполняется по service-сообщениям
# "Тема создана" и живёт только в памяти процесса (после рестарта старые темы
# по умолчанию будут иметь пустое название до следующего создания темы;
# для уже существующих тем это не критично, т.к. поле "Подчат" используется
# только в информационных целях на листе "Сырые данные").
_topic_titles = {}


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if message is None:
        return

    chat_id = message.chat_id

    if CONFIG["SOURCE_CHAT_ID"] is None:
        print(f"[ОБНАРУЖЕНИЕ] chat_id={chat_id}  chat_title={message.chat.title!r}  thread_id={message.message_thread_id}")
        return

    if chat_id != CONFIG["SOURCE_CHAT_ID"]:
        return

    if message.forum_topic_created:
        _topic_titles[message.message_thread_id] = message.forum_topic_created.name
        return

    sender = message.from_user.username if message.from_user else None
    if sender != CONFIG["BOT_SENDER"]:
        return

    if not message.text:
        return

    subchat = _topic_titles.get(message.message_thread_id, "")
    record = parse_message(message.text, subchat=subchat, message_date=message.date)
    if record is None:
        return

    storage.append_record(CONFIG["DATA_FILE"], record)
    print(f"Записано: ПБ {record['pb_number']} ({record['city']}, {record['duration_raw']})")


async def build_and_check_report(context: ContextTypes.DEFAULT_TYPE):
    records = storage.load_records(CONFIG["DATA_FILE"])
    if not records:
        return

    output_path = build_report(records, CONFIG["OUTPUT_PATH"])
    print(f"[{datetime.now():%d.%m.%Y %H:%M:%S}] Отчёт обновлён: {output_path}")

    alert_text = build_alert_text(records)
    if not alert_text:
        return
    if not CONFIG["ALERT_CHAT"]:
        print("ВНИМАНИЕ: обнаружены аварии с простоем >8ч, но CONFIG['ALERT_CHAT'] не задан — уведомление не отправлено.")
        return

    await context.bot.send_message(CONFIG["ALERT_CHAT"], alert_text)
    print("Уведомление об эскалации отправлено.")


def main():
    if not CONFIG["BOT_TOKEN"]:
        raise RuntimeError("Заполните CONFIG['BOT_TOKEN'] (получить у @BotFather)")

    application = Application.builder().token(CONFIG["BOT_TOKEN"]).build()
    application.add_handler(MessageHandler(filters.ALL, handle_message))

    if CONFIG["SOURCE_CHAT_ID"] is None:
        print(
            "CONFIG['SOURCE_CHAT_ID'] не задан — режим обнаружения.\n"
            "Напишите любое сообщение в группе-источнике (или дождитесь очередного "
            "обновления от ecus_bot) и посмотрите вывод консоли ниже, чтобы узнать chat_id."
        )
    else:
        application.job_queue.run_repeating(
            build_and_check_report,
            interval=CONFIG["REPORT_INTERVAL_MINUTES"] * 60,
            first=30,
        )

    print("Бот запущен, ожидаю сообщения...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
