from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from config import TASK_BOT_LINK

# ─── Главное меню ──────────────────────────────────────
def main_menu_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📋 Задания"), KeyboardButton(text="👤 Профиль"))
    builder.row(KeyboardButton(text="💸 Вывод"), KeyboardButton(text="🆘 Тех. поддержка"))
    return builder.as_markup(resize_keyboard=True)

def main_menu_inline_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu"))
    return builder.as_markup()

def back_to_menu_kb() -> InlineKeyboardMarkup:
    return main_menu_inline_kb()

# ─── Задания ──────────────────────────────────────────
def task_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔗 Перейти по ссылке", url=TASK_BOT_LINK))
    builder.row(InlineKeyboardButton(text="📋 Скопировать ссылку", callback_data="copy_link"))
    builder.row(InlineKeyboardButton(text="📸 Отправить скрин", callback_data="send_screenshot"))
    return builder.as_markup()

# ─── Вывод (раньше была withdraw_kb, теперь не используется, но оставим для совместимости) ───
def withdraw_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💸 Подать заявку на вывод", callback_data="start_withdraw"))
    return builder.as_markup()

# ─── Поддержка ────────────────────────────────────────
def support_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💬 Написать в поддержку", callback_data="open_support"))
    return builder.as_markup()

# ─── Верификация ника (используется в старом коде вывода) ───
def verify_nick_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Ник верный", callback_data="confirm_withdraw_nick"),
        InlineKeyboardButton(text="📝 Изменить ник", callback_data="change_withdraw_nick")
    )
    return builder.as_markup()

# ─── Кнопка отмены (FSM) ──────────────────────────────
def cancel_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="❌ Отмена"))
    return builder.as_markup(resize_keyboard=True)

# ─── Админ: проверка скрина (с task_id) ───────────────
def admin_submission_kb(submission_id: int, user_id: int, task_id: int = 1) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Оплатить", callback_data=f"approve_task:{submission_id}:{user_id}:{task_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_task:{submission_id}:{user_id}:{task_id}")
    )
    builder.row(InlineKeyboardButton(text="💬 Комментарий", callback_data=f"comment_task:{submission_id}:{user_id}:{task_id}"))
    return builder.as_markup()

# ─── Админ: заявка на вывод ───────────────────────────
def admin_withdraw_kb(req_id: int, user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить вывод", callback_data=f"approve_withdraw:{req_id}:{user_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_withdraw:{req_id}:{user_id}")
    )
    return builder.as_markup()