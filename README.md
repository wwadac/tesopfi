# 🤖 Phoenix Bot — Telegram бот для сервера

## Структура проекта

```
phoenix_bot/
├── bot.py          # Точка запуска
├── config.py       # ⚙️ НАСТРОЙКИ (заполни первым делом!)
├── database.py     # База данных SQLite
├── handlers.py     # Все обработчики команд
├── keyboards.py    # Все клавиатуры
├── states.py       # FSM состояния
├── texts.py        # Тексты сообщений
└── requirements.txt
```

---

## 🚀 Установка и запуск

### 1. Установи Python 3.10+
```bash
python --version  # должно быть 3.10+
```

### 2. Установи зависимости
```bash
pip install -r requirements.txt
```

### 3. Настрой config.py
Открой `config.py` и заполни:

```python
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"   # токен от @BotFather
ADMIN_ID = 123456789                 # твой Telegram ID (узнать у @userinfobot)
ADMIN_CHAT_ID = None                 # ID группы для уведомлений (или None = в личку)
TASK_BOT_LINK = "https://t.me/..."  # ссылка на бот из задания
```

### 4. Запусти бота
```bash
python bot.py
```

---

## ⚙️ Что умеет бот

### Для игроков:
- 📋 **Задания** — описание, ссылка, отправка скрина на проверку
- 👤 **Профиль** — ID, юзернейм, ник Minecraft, баланс
- 💸 **Вывод** — заявка на вывод от 200k монет через аукцион
- 🆘 **Тех. поддержка** — живой чат с администратором

### Для администратора:
- Получает скрины заявок с кнопками ✅ Оплатить / ❌ Отклонить
- Может написать комментарий к скрину
- Получает заявки на вывод с ником и суммой
- Может ответить игроку в поддержке прямо из уведомления

---

## 📦 Хостинг (VPS)

Для работы 24/7 запусти через screen или systemd:

```bash
# Вариант 1 — screen
screen -S phoenix_bot
python bot.py
# Ctrl+A, D — свернуть

# Вариант 2 — systemd (создай /etc/systemd/system/phoenix_bot.service)
[Unit]
Description=Phoenix Telegram Bot

[Service]
WorkingDirectory=/path/to/phoenix_bot
ExecStart=/usr/bin/python3 bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```
