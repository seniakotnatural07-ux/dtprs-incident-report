# -*- coding: utf-8 -*-
"""
Шаблон локальной конфигурации с секретами.

Скопируйте этот файл в config_local.py (он уже добавлен в .gitignore и не
попадёт в git-репозиторий) и впишите реальные значения. Достаточно
заполнить поля, нужные для выбранного варианта сборщика данных
(bot_listener.py ИЛИ fetch_telegram.py).
"""

CONFIG = {
    # --- для bot_listener.py (вариант с ботом, см. README.md) ---
    "BOT_TOKEN": "123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",  # токен от @BotFather
    "SOURCE_CHAT_ID": -1001234567890,   # chat_id группы-источника (режим обнаружения покажет его в консоли)
    "ALERT_CHAT": -1009876543210,        # chat_id/username чата для уведомлений об эскалации

    # --- для fetch_telegram.py (вариант с личным аккаунтом, Telethon) ---
    # "API_ID": 12345678,
    # "API_HASH": "0123456789abcdef0123456789abcdef",
}
