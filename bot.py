import asyncio
import logging
import os
from telethon import TelegramClient
from telethon.errors import RPCError

# ================= НАСТРОЙКИ =================
# На хостинге задайте эти переменные в панели управления.
# Если их там нет, код автоматически возьмет дефолтные значения ниже.
API_ID = int(os.getenv("TELEGRAM_API_ID", 39228996))
API_HASH = os.getenv("TELEGRAM_API_HASH", "0d5e411837c3957946e56edd9bcbf4d4")
BOT_USERNAME = '@Ononchatbot'

BTN_SEARCH = 'Найти собеседника'  # Опечатка 'ф' удалена
BTN_END = 'Завершить чат'
MESSAGE_TO_SEND = "Приветик, я Лена мне 19, хочу развивать свой iнtimнblй канал. \n\nНо не придумала иного варианта как здесь.\n\nЕсли тебе нравятся красивые пышечки.\n\n3аходи: https://t.me/+DlivJqlknxI5Y2Vl \n\n!!!я не бот!!! \n\nЗаходи не пожалеешь😉"
WAIT_AFTER_START  = 2
WAIT_AFTER_SEARCH = 2
WAIT_BEFORE_END   = 3
WAIT_AFTER_END    = 5
TIMEOUT_FIND      = 180
POLL_INTERVAL     = 2
WAIT_AFTER_FOUND  = 4 
CYCLE_DELAY       = 10  # Обязательная пауза между кругами спама для защиты от бана
# =============================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

client = TelegramClient('anon_session', API_ID, API_HASH)


async def click_button(bot_entity, button_text):
    async for msg in client.iter_messages(bot_entity, limit=10):
        if msg.out or not msg.buttons:
            continue
        for row in msg.buttons:
            for btn in row:
                if btn.text == button_text:
                    logger.info(f"Нажата кнопка: '{button_text}'")
                    await btn.click()
                    return True
    return False


async def wait_for_partner(bot_entity, timeout, seen_ids):
    logger.info(f"Жду собеседника (таймаут {timeout}с)...")
    deadline = asyncio.get_event_loop().time() + timeout

    BOT_PHRASES = [
        "Собеседник найден",
        "Ищем собеседника",
        "Поиск отменён",
        "Чат завершён",
        "собеседник покинул",
    ]

    async for msg in client.iter_messages(bot_entity, limit=10):
        if msg.id in seen_ids or msg.out:
            continue
        seen_ids.add(msg.id)
        if "Собеседник найден" in msg.raw_text:
            logger.info("✅ Собеседник найден мгновенно!")
            return True

    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(POLL_INTERVAL)
        async for msg in client.iter_messages(bot_entity, limit=10):
            if msg.id in seen_ids or msg.out:
                continue
            seen_ids.add(msg.id)
            text = msg.raw_text

            if not any(phrase in text for phrase in BOT_PHRASES):
                logger.info(f"Пропускаю (сообщение собеседника): {text[:50]!r}")
                continue

            logger.info(f"Сообщение бота: {text[:80]!r}")

            if "Собеседник найден" in text:
                logger.info("✅ Собеседник найден!")
                return True

    logger.warning("⏰ Таймаут: собеседник не найден.")
    return False


async def main_cycle():
    bot_entity = await client.get_input_entity(BOT_USERNAME)

    logger.info("--- Новый цикл ---")
    await client.send_message(bot_entity, '/start')
    await asyncio.sleep(WAIT_AFTER_START)

    seen_ids = set()
    async for msg in client.iter_messages(bot_entity, limit=20):
        seen_ids.add(msg.id)

    if not await click_button(bot_entity, BTN_SEARCH):
        logger.info("Кнопка не найдена, отправляю /searchchat")
        await client.send_message(bot_entity, '/searchchat')
    await asyncio.sleep(WAIT_AFTER_SEARCH)

    if not await wait_for_partner(bot_entity, TIMEOUT_FIND, seen_ids):
        await click_button(bot_entity, 'Отменить поиск')
        return

    logger.info(f"Ожидание {WAIT_AFTER_FOUND} секунд перед отправкой сообщения...")
    await asyncio.sleep(WAIT_AFTER_FOUND)

    await client.send_message(bot_entity, MESSAGE_TO_SEND)
    logger.info("💬 Сообщение отправлено.")
    await asyncio.sleep(WAIT_BEFORE_END)

    if not await click_button(bot_entity, BTN_END):
        logger.info("Кнопка завершения не найдена, отправляю /chatend")
        await client.send_message(bot_entity, '/chatend')
    else:
        logger.info("🔚 Чат завершён.")

    logger.info(f"Пауза {WAIT_AFTER_END}с...")
    await asyncio.sleep(WAIT_AFTER_END)


async def run_forever():
    while True:
        try:
            await main_cycle()
            logger.info(f"Круг завершен. Спим {CYCLE_DELAY}с перед следующим...")
            await asyncio.sleep(CYCLE_DELAY)
        except RPCError as e:
            logger.error(f"Ошибка Telegram API: {e}")
            await asyncio.sleep(30)
        except Exception as e:
            logger.exception(f"Непредвиденная ошибка: {e}")
            await asyncio.sleep(15)


async def main():
    logger.info("Запуск клиента...")
    await client.start()
    logger.info("Авторизация успешна! Начинаем цикл.")
    await run_forever()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Остановлено пользователем.")
