import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
import database as db
import texts
from config import ADMIN_ID, ADMIN_CHAT_ID, TASK_REWARD, MIN_WITHDRAW, TASK_BOT_LINK, SERVER_NAME
from keyboards import (
    main_menu_kb, task_kb, support_kb, cancel_kb,
    admin_submission_kb, admin_withdraw_kb, verify_nick_kb
)
from states import RegistrationFSM, TaskFSM, WithdrawFSM, SupportFSM, AdminFSM

logger = logging.getLogger(__name__)
main_router = Router()
admin_router = Router()

def get_notify_target():
    return ADMIN_CHAT_ID if ADMIN_CHAT_ID else ADMIN_ID

# ------------------------------------------------------------
# СТАРТ / РЕГИСТРАЦИЯ
# ------------------------------------------------------------
@main_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user:
        await db.create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
        await state.clear()
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
        InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en"),
    )
    await message.answer(texts.WELCOME, reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.set_state(RegistrationFSM.choosing_lang)

@main_router.callback_query(F.data.in_(["lang_ru", "lang_en"]), RegistrationFSM.choosing_lang)
async def choose_language(call: CallbackQuery, state: FSMContext):
    lang = "ru" if call.data == "lang_ru" else "en"
    await db.update_user(call.from_user.id, lang=lang)
    user = await db.get_user(call.from_user.id)
    if user and user["minecraft_nick"]:
        await call.message.edit_text(texts.MAIN_MENU.format(server_name=SERVER_NAME.upper()), parse_mode="HTML")
        await call.message.answer("👇", reply_markup=main_menu_kb())
        await state.clear()
    else:
        await call.message.edit_text(texts.WELCOME_RU.format(server_name=SERVER_NAME), parse_mode="HTML")
        await state.set_state(RegistrationFSM.entering_minecraft_nick)
    await call.answer()

@main_router.message(RegistrationFSM.entering_minecraft_nick)
async def enter_minecraft_nick(message: Message, state: FSMContext):
    nick = message.text.strip()
    if len(nick) < 3 or len(nick) > 16 or not nick.replace("_", "").isalnum():
        await message.answer("❌ Неверный ник. Ник должен быть от 3 до 16 символов (буквы, цифры, _).\nПопробуй ещё раз:")
        return
    await db.update_user(message.from_user.id, minecraft_nick=nick)
    await message.answer(
        f"✅ Отлично, <b>{nick}</b>! Ты зарегистрирован.\n\n" + texts.MAIN_MENU.format(server_name=SERVER_NAME.upper()),
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )
    await state.clear()

# ------------------------------------------------------------
# ГЛАВНОЕ МЕНЮ
# ------------------------------------------------------------
@main_router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(texts.MAIN_MENU.format(server_name=SERVER_NAME.upper()), reply_markup=main_menu_kb())

async def ensure_registered(message: Message) -> bool:
    user = await db.get_user(message.from_user.id)
    if not user or not user["minecraft_nick"]:
        await message.answer("❗ Сначала зарегистрируйся — напиши /start", reply_markup=main_menu_kb())
        return False
    return True

# ------------------------------------------------------------
# ЗАДАНИЯ
# ------------------------------------------------------------
@main_router.message(F.text == "📋 Задания")
async def show_tasks(message: Message):
    if not await ensure_registered(message):
        return
    user = await db.get_user(message.from_user.id)
    task1_done = await db.is_task_done(message.from_user.id, 1)
    task2_config = await db.get_task2_config()
    task2_done = await db.is_task_done(message.from_user.id, 2)

    text = f"""
<b>📋 ДОСТУПНЫЕ ЗАДАНИЯ</b>

<blockquote><b>🎯 ЗАДАНИЕ #1</b>
├ Подпишись на партнёра
├ Награда: <code>{TASK_REWARD:,} 🪙</code>
└ Статус: {'✅ Выполнено' if task1_done else '❌ Ожидает'}</blockquote>

<blockquote><b>🎯 ЗАДАНИЕ #2</b>
{task2_config['text'][:200]}
├ Награда: <code>{TASK_REWARD:,} 🪙</code>
└ Статус: {'✅ Выполнено' if task2_done else '❌ Ожидает'}</blockquote>

<blockquote>💰 <b>Ваш текущий баланс:</b> <code>{user['balance']:,} 🪙</code></blockquote>
"""
    builder = InlineKeyboardBuilder()
    if not task1_done:
        builder.row(InlineKeyboardButton(text="📌 Задание #1", callback_data="task_1"))
    if not task2_done and task2_config['text'] and "не настроено" not in task2_config['text']:
        builder.row(InlineKeyboardButton(text="📌 Задание #2", callback_data="task_2"))
    if builder.buttons:
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    else:
        await message.answer(text + "\n\n✅ Все задания выполнены!", parse_mode="HTML")

@main_router.callback_query(F.data == "copy_link")
async def copy_link(call: CallbackQuery):
    await call.answer(f"Ссылка: {TASK_BOT_LINK}", show_alert=True)

@main_router.callback_query(F.data.in_(["task_1", "task_2"]))
async def choose_task(call: CallbackQuery, state: FSMContext):
    task_id = int(call.data.split("_")[1])
    await state.update_data(current_task=task_id)
    if task_id == 1:
        text = f"🔗 <b>Задание #1</b>\n\nПерейди по ссылке, подпишись и пришли скриншот:\n{TASK_BOT_LINK}"
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="🔗 Перейти", url=TASK_BOT_LINK))
        kb.row(InlineKeyboardButton(text="📸 Отправить скрин", callback_data="send_screenshot"))
        await call.message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    else:
        config = await db.get_task2_config()
        text = f"📌 <b>Задание #2</b>\n\n{config['text']}"
        if config['media_id'] and config['media_type']:
            if config['media_type'] == 'photo':
                await call.message.answer_photo(photo=config['media_id'], caption=text, parse_mode="HTML")
            elif config['media_type'] == 'video':
                await call.message.answer_video(video=config['media_id'], caption=text, parse_mode="HTML")
            else:
                await call.message.answer(text, parse_mode="HTML")
        else:
            await call.message.answer(text, parse_mode="HTML")
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="📸 Отправить скрин", callback_data="send_screenshot"))
        await call.message.answer("👇 Пришли скриншот выполнения задания:", reply_markup=kb.as_markup())
    await state.set_state(TaskFSM.waiting_screenshot)
    await call.answer()

@main_router.callback_query(F.data == "send_screenshot", TaskFSM.waiting_screenshot)
async def ask_screenshot(call: CallbackQuery):
    await call.message.answer("📸 <b>Отправь скриншот</b> (фото, не файл)", reply_markup=cancel_kb(), parse_mode="HTML")
    await call.answer()

@main_router.message(TaskFSM.waiting_screenshot, F.photo)
async def receive_screenshot(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    task_id = data.get("current_task", 1)
    photo_id = message.photo[-1].file_id
    user = await db.get_user(message.from_user.id)
    submission_id = await db.add_task_submission_with_task(message.from_user.id, photo_id, task_id)
    await message.answer("✅ <b>Скриншот получен!</b>\n\nОжидай проверки.", reply_markup=main_menu_kb(), parse_mode="HTML")
    await state.clear()
    target = get_notify_target()
    uname = f"@{message.from_user.username}" if message.from_user.username else "без юзернейма"
    
    # === ВСТАВЛЯТЬ СЮДА ===
    caption = (
        f"<b>📸 Новый отчёт на проверку #{submission_id}</b>\n"
        f"<blockquote>Задание #{task_id}</blockquote>\n\n"
        f"<blockquote><b>Информация об игроке:</b>\n"
        f"├ 👤 Имя: {message.from_user.full_name} ({uname})\n"
        f"├ 🆔 ID: <code>{message.from_user.id}</code>\n"
        f"├ ⛏ Ник: <code>{user['minecraft_nick'] if user else 'не указан'}</code>\n"
        f"└ 💰 Баланс: <code>{user['balance']:,} 🪙</code></blockquote>"
    )
    # ======================

    await bot.send_photo(
        chat_id=target,
        photo=photo_id,
        caption=caption,
        reply_markup=admin_submission_kb(submission_id, message.from_user.id, task_id),
        parse_mode="HTML"
    )

@main_router.message(TaskFSM.waiting_screenshot)
async def wrong_screenshot_format(message: Message, state: FSMContext):
    # Список кнопок нашего меню
    menu_buttons = ["📋 Задания", "👤 Профиль", "💸 Вывод", "🆘 Тех. поддержка"]
    
    # Если юзер нажал на кнопку меню — сбрасываем состояние и перенаправляем
    if message.text in menu_buttons:
        await state.clear()
        
        if message.text == "📋 Задания":
            await show_tasks(message)
        elif message.text == "👤 Профиль":
            await show_profile(message)
        elif message.text == "💸 Вывод":
            await show_withdraw(message)
        elif message.text == "🆘 Тех. поддержка":
            await show_support(message)
        return

    # Если это просто левый текст, а не фотка:
    await message.answer("❌ <b>Ошибка!</b>\nПожалуйста, пришли именно <b>фото/скриншот</b>, а не файл или текст. 📸", parse_mode="HTML")

# ------------------------------------------------------------
# ВЫВОД
# ------------------------------------------------------------

# ------------------------------------------------------------
# ПРОФИЛЬ ИГРОКА
# ------------------------------------------------------------
@main_router.message(F.text == "👤 Профиль")
async def cmd_profile(message: Message):
    await show_profile(message)

async def show_profile(message: Message):
    if not await ensure_registered(message):
        return
    
    user = await db.get_user(message.from_user.id)
    uname = f"@{message.from_user.username}" if message.from_user.username else "не указан"
    
    text = f"""
<b>👤 ТВОЙ ПРОФИЛЬ | 💎 {SERVER_NAME.upper()}</b>

<blockquote><b>📊 Статистика аккаунта:</b>
├ 🆔 Твой Telegram ID: <code>{message.from_user.id}</code>
├ 👤 Юзернейм: {uname}
├ ⛏ Ник в Minecraft: <code>{user['minecraft_nick']}</code>
└ 💰 Текущий баланс: <code>{user['balance']:,} 🪙</code></blockquote>

💸 Накопленные монеты можно вывести на сервере через вкладку меню <b>«💸 Вывод»</b>!
"""
    await message.answer(text, reply_markup=main_menu_kb(), parse_mode="HTML")
@main_router.message(F.text == "💸 Вывод")
async def show_withdraw(message: Message, state: FSMContext = None):
    if state:
        await state.clear() # Сбрасываем любые зависшие состояния
        
    if not await ensure_registered(message):
        return
    
    user = await db.get_user(message.from_user.id)
    balance = user["balance"]
    
    # 💎 Обновленный красивый дизайн
    text = f"""
<b>💳 ВЫВОД СРЕДСТВ | 💎 {SERVER_NAME.upper()}</b>

<blockquote><b>🌟 Условия вывода:</b>
🔸 Минимальная сумма: <code>{MIN_WITHDRAW:,} 🪙</code></blockquote>

<blockquote><b>📋 Инструкция (как получить монеты):</b>
1️⃣ Проверь правильность своего никнейма.
2️⃣ Выставь <b>1 блок земли</b> на аукцион за <b>100$</b>.
3️⃣ Нажми кнопку <i>«💸 Подать заявку»</i>.
4️⃣ Ожидай выкупа лота администратором.

⚠️ <i>Важно: Не отменяй лот до завершения сделки!</i></blockquote>

<b>📊 Состояние твоего счёта:</b>
├ 💰 Баланс: <code>{balance:,} 🪙</code>
└ {'✅' if balance >= MIN_WITHDRAW else '❌'} Статус: <b>{'Доступно к выводу!' if balance >= MIN_WITHDRAW else f'Нужно еще {MIN_WITHDRAW - balance:,} 🪙'}</b>

👤 <b>Твой текущий ник:</b> <code>{user['minecraft_nick']}</code>
"""

    builder = InlineKeyboardBuilder()
    
    # Логика кнопок: если денег хватает — активна, если нет — заглушка
    if balance >= MIN_WITHDRAW:
        builder.row(InlineKeyboardButton(text="💸 Подать заявку", callback_data="start_withdraw"))
    else:
        builder.row(InlineKeyboardButton(text="🔒 Недостаточно монет", callback_data="no_funds"))
        
    # Кнопка смены ника теперь доступна ВСЕГДА
    builder.row(InlineKeyboardButton(text="📝 Изменить ник", callback_data="change_withdraw_nick"))

    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")

# Добавь этот хэндлер сразу после show_withdraw, чтобы кнопка-заглушка работала
@main_router.callback_query(F.data == "no_funds")
async def no_funds_alert(call: CallbackQuery):
    await call.answer("❌ На балансе недостаточно монет для вывода!", show_alert=True)
@main_router.message(WithdrawFSM.changing_nick)
async def process_nick_change(message: Message, state: FSMContext):
    nick = message.text.strip()
    if 3 <= len(nick) <= 16 and nick.replace("_", "").isalnum():
        await db.update_user(message.from_user.id, minecraft_nick=nick)
        await message.answer(f"✅ Ник изменён на <b>{nick}</b>", parse_mode="HTML")
        await state.clear()
        await show_withdraw(message)
    else:
        await message.answer("❌ Неверный формат. Ник 3-16 символов (буквы, цифры, _). Попробуй снова:")

@main_router.callback_query(F.data == "start_withdraw")
async def start_withdraw(call: CallbackQuery, state: FSMContext):
    user = await db.get_user(call.from_user.id)
    if not user or user["balance"] < MIN_WITHDRAW:
        await call.answer("❌ Недостаточно монет", show_alert=True)
        return
    await state.set_state(WithdrawFSM.confirming)
    await state.update_data(withdraw_amount=user["balance"])
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, всё верно", callback_data="confirm_withdraw"),
        InlineKeyboardButton(text="📝 Изменить ник", callback_data="change_withdraw_nick")
    )
    await call.message.answer(
        f"💸 <b>ПОДТВЕРЖДЕНИЕ ВЫВОДА</b>\n\n"
        f"⛏ <b>Ник в Minecraft:</b> <code>{user['minecraft_nick']}</code>\n"
        f"💰 <b>Сумма вывода:</b> <code>{user['balance']:,} 🪙</code>\n\n"
        f"<i>Если ник верный, нажми «Да». Если нет – измени.</i>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await call.answer()

@main_router.callback_query(F.data == "confirm_withdraw", WithdrawFSM.confirming)
async def confirm_withdraw(call: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    amount = data.get("withdraw_amount")
    user = await db.get_user(call.from_user.id)
    if not user or user["balance"] < MIN_WITHDRAW:
        await call.answer("❌ Баланс изменился, повторите попытку", show_alert=True)
        await state.clear()
        return
    req_id = await db.add_withdraw_request(call.from_user.id, amount, user["minecraft_nick"])
    await db.subtract_balance(call.from_user.id, amount)
    await call.message.answer("✅ <b>Заявка отправлена!</b>\n\nОжидайте, админ купит ваш блок земли.", reply_markup=main_menu_kb())
    await state.clear()
    target = get_notify_target()
    uname = f"@{call.from_user.username}" if call.from_user.username else "без юзернейма"
    await bot.send_message(
        target,
        f"💸 <b>Заявка на вывод #{req_id}</b>\n\n"
        f"👤 {call.from_user.full_name} ({uname})\n🆔 <code>{call.from_user.id}</code>\n"
        f"⛏ <code>{user['minecraft_nick']}</code>\n💰 <code>{amount:,} 🪙</code>\n\n"
        f"❗ Купите блок земли у игрока на аукционе за 100$",
        reply_markup=admin_withdraw_kb(req_id, call.from_user.id),
        parse_mode="HTML"
    )
    await call.answer()

# ------------------------------------------------------------
# ТЕХПОДДЕРЖКА
# ------------------------------------------------------------
@main_router.message(F.text == "🆘 Тех. поддержка")
async def show_support(message: Message):
    await message.answer(texts.SUPPORT_WELCOME, reply_markup=support_kb(), parse_mode="HTML")

@main_router.callback_query(F.data == "open_support")
async def open_support_chat(call: CallbackQuery, state: FSMContext):
    await call.message.answer("💬 <b>Напиши свой вопрос:</b>\n<i>(Для выхода — /menu или ❌ Отмена)</i>", reply_markup=cancel_kb(), parse_mode="HTML")
    await state.set_state(SupportFSM.chatting)
    await call.answer()

@main_router.message(SupportFSM.chatting, F.text == "❌ Отмена")
async def cancel_support(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(texts.MAIN_MENU.format(server_name=SERVER_NAME.upper()), reply_markup=main_menu_kb())

@main_router.message(SupportFSM.chatting)
async def support_message(message: Message, bot: Bot):
    user = await db.get_user(message.from_user.id)
    await db.add_support_message(message.from_user.id, message.text)
    await message.answer("✅ <b>Сообщение отправлено в поддержку!</b>\n\nОжидай ответа.", parse_mode="HTML")
    target = get_notify_target()
    uname = f"@{message.from_user.username}" if message.from_user.username else "без юзернейма"
    nick = user["minecraft_nick"] if user else "не указан"
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💬 Ответить", callback_data=f"reply_support:{message.from_user.id}"))
    await bot.send_message(
        chat_id=target,
        text=(
            f"🆘 <b>Сообщение в поддержку</b>\n\n"
            f"👤 <b>{message.from_user.full_name}</b> ({uname})\n"
            f"🆔 <b>ID:</b> <code>{message.from_user.id}</code>\n"
            f"⛏ <b>Ник:</b> <code>{nick}</code>\n\n"
            f"📝 <b>Сообщение:</b>\n{message.text}"
        ),
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

# ------------------------------------------------------------
# ADMIN HANDLERS
# ------------------------------------------------------------
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

@admin_router.callback_query(F.data.startswith("approve_task:"))
async def approve_task(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return
    _, sub_id, user_id, task_id = call.data.split(":")
    sub_id, user_id, task_id = int(sub_id), int(user_id), int(task_id)
    sub = await db.get_submission(sub_id)
    if not sub or sub["status"] != "pending":
        await call.answer("Заявка уже обработана", show_alert=True)
        return
    await db.update_submission(sub_id, "approved")
    await db.add_balance(user_id, TASK_REWARD)
    await call.message.edit_caption(
        call.message.caption + f"\n\n✅ <b>ОДОБРЕНО</b> — начислено {TASK_REWARD:,} 🪙",
        parse_mode="HTML"
    )
    await call.answer("✅ Одобрено!")
    try:
        await bot.send_message(user_id, f"✅ <b>Задание #{task_id} выполнено!</b>\n\nНачислено {TASK_REWARD:,} 🪙", parse_mode="HTML")
    except:
        pass

@admin_router.callback_query(F.data.startswith("reject_task:"))
async def reject_task(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return
    _, sub_id, user_id, task_id = call.data.split(":")
    sub_id, user_id = int(sub_id), int(user_id)
    sub = await db.get_submission(sub_id)
    if not sub or sub["status"] != "pending":
        await call.answer("Заявка уже обработана", show_alert=True)
        return
    await db.update_submission(sub_id, "rejected")
    await call.message.edit_caption(call.message.caption + "\n\n❌ <b>ОТКЛОНЕНО</b>", parse_mode="HTML")
    await call.answer("❌ Отклонено")
    try:
        await bot.send_message(user_id, "❌ <b>Задание отклонено.</b>\n\nСкрин не прошёл проверку. Попробуй снова.")
    except:
        pass

@admin_router.callback_query(F.data.startswith("comment_task:"))
async def comment_task(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return
    _, sub_id, user_id, task_id = call.data.split(":")
    await state.set_state(AdminFSM.commenting)
    await state.update_data(commenting_sub_id=int(sub_id), commenting_user_id=int(user_id))
    await call.message.answer("✏️ Напиши комментарий для игрока:")
    await call.answer()

@admin_router.message(AdminFSM.commenting)
async def send_comment(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    sub_id = data.get("commenting_sub_id")
    user_id = data.get("commenting_user_id")
    await db.update_submission(sub_id, "commented", message.text)
    await state.clear()
    await message.answer("✅ Комментарий сохранён и отправлен игроку.")
    try:
        await bot.send_message(user_id, f"💬 <b>Комментарий от администратора</b> по заявке #{sub_id}:\n\n{message.text}", parse_mode="HTML")
    except:
        pass

@admin_router.callback_query(F.data.startswith("approve_withdraw:"))
async def approve_withdraw(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return
    _, req_id, user_id = call.data.split(":")
    req_id, user_id = int(req_id), int(user_id)
    req = await db.get_withdraw_request(req_id)
    if not req or req["status"] != "pending":
        await call.answer("Заявка уже обработана", show_alert=True)
        return
    await db.update_withdraw_request(req_id, "approved")
    await call.message.edit_text(call.message.text + "\n\n✅ <b>ВЫВОД ПОДТВЕРЖДЁН</b>", parse_mode="HTML")
    await call.answer("✅ Вывод подтверждён!")
    try:
        await bot.send_message(user_id, f"✅ <b>Вывод подтверждён!</b>\n\nАдминистратор купил твой блок земли.\nСпасибо за использование сервера {SERVER_NAME}!", parse_mode="HTML")
    except:
        pass

@admin_router.callback_query(F.data.startswith("reject_withdraw:"))
async def reject_withdraw(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return
    _, req_id, user_id = call.data.split(":")
    req_id, user_id = int(req_id), int(user_id)
    req = await db.get_withdraw_request(req_id)
    if not req or req["status"] != "pending":
        await call.answer("Заявка уже обработана", show_alert=True)
        return
    await db.add_balance(user_id, req["amount"])
    await db.update_withdraw_request(req_id, "rejected")
    await call.message.edit_text(call.message.text + "\n\n❌ <b>ВЫВОД ОТКЛОНЁН</b> — монеты возвращены", parse_mode="HTML")
    await call.answer("❌ Отклонено, монеты возвращены")
    try:
        await bot.send_message(user_id, "❌ <b>Заявка на вывод отклонена.</b>\n\nМонеты возвращены на твой баланс.")
    except:
        pass

@admin_router.callback_query(F.data.startswith("reply_support:"))
async def reply_support_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return
    user_id = int(call.data.split(":")[1])
    await state.set_state(AdminFSM.replying_support)
    await state.update_data(reply_to_user=user_id)
    await call.message.answer(f"✏️ Пиши ответ пользователю <code>{user_id}</code>:", parse_mode="HTML")
    await call.answer()

@admin_router.message(AdminFSM.replying_support)
async def send_support_reply(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    user_id = data.get("reply_to_user")
    await state.clear()
    await db.add_support_message(user_id, message.text, from_admin=True)
    await message.answer("✅ Ответ отправлен!")
    try:
        await bot.send_message(user_id, f"📩 <b>Ответ от поддержки:</b>\n\n{message.text}", parse_mode="HTML")
    except:
        await message.answer("⚠️ Не удалось отправить — пользователь заблокировал бота.")

@admin_router.message(Command("set_task2"))
async def admin_set_task2(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminFSM.setting_task2_text)
    await message.answer("✏️ Отправьте текст для задания #2 (можно с HTML-разметкой):")

@admin_router.message(AdminFSM.setting_task2_text)
async def set_task2_text(message: Message, state: FSMContext):
    await state.update_data(task2_text=message.text)
    await state.set_state(AdminFSM.setting_task2_media)
    await message.answer("📎 Теперь пришлите фото или видео (или нажмите /skip, чтобы оставить без медиа):")

@admin_router.message(AdminFSM.setting_task2_media, F.photo)
async def set_task2_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    text = data.get("task2_text")
    photo_id = message.photo[-1].file_id
    await db.set_task2_config(text=text, media_id=photo_id, media_type="photo")
    await state.clear()
    await message.answer("✅ Задание #2 обновлено с фото!")

@admin_router.message(AdminFSM.setting_task2_media, F.video)
async def set_task2_video(message: Message, state: FSMContext):
    data = await state.get_data()
    text = data.get("task2_text")
    video_id = message.video.file_id
    await db.set_task2_config(text=text, media_id=video_id, media_type="video")
    await state.clear()
    await message.answer("✅ Задание #2 обновлено с видео!")

@admin_router.message(AdminFSM.setting_task2_media, Command("skip"))
async def skip_media(message: Message, state: FSMContext):
    data = await state.get_data()
    text = data.get("task2_text")
    await db.set_task2_config(text=text, media_id=None, media_type=None)
    await state.clear()
    await message.answer("✅ Задание #2 обновлено без медиа.")

# ------------------------------------------------------------
# НЕИЗВЕСТНЫЕ КОМАНДЫ (СТАВИТЬ В САМЫЙ КОНЕЦ!)
# ------------------------------------------------------------
@main_router.message()
async def unknown_message(message: Message):
    # Если это случайное сообщение (не кнопка и не команда), вежливо просим юзать меню
    await message.answer(
        "🤷‍♂️ <b>Я не понимаю эту команду или сообщение.</b>\n\n"
        "Пожалуйста, воспользуйся кнопками меню ниже 👇", 
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )

@main_router.callback_query()
async def unknown_callback(call: CallbackQuery):
    # Если нажата устаревшая или неизвестная кнопка
    await call.answer("⏳ Эта кнопка больше не работает или устарела.", show_alert=True)