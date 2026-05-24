import io
import os
import logging
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    BufferedInputFile
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from PIL import Image

# Опциональная поддержка HEIC/HEIF (с iPhone)
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIC_SUPPORT = True
except ImportError:
    HEIC_SUPPORT = False

# ==================== КОНФИГ ====================
BOT_TOKEN = "8291094837:AAGOrcprhQDUJlHzpAVnPF8YChSb4I_EVxg"
MAX_FILE_SIZE_MB = 20
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)


# ==================== FSM СОСТОЯНИЯ ====================
class States(StatesGroup):
    main = State()
    conv_wait_file = State()
    create_wait_content = State()
    create_wait_name = State()
    rename_wait_file = State()
    rename_wait_name = State()
    code_wait_code = State()
    code_wait_name = State()


# ==================== ДАННЫЕ ====================
IMAGE_FORMATS = ["JPG", "PNG", "WEBP", "BMP", "TIFF", "GIF", "ICO"]

FILE_CATEGORIES = {
    "📝 Текст": ["TXT", "MD", "CSV", "LOG"],
    "📦 Данные": ["JSON", "XML", "YAML", "TOML", "INI"],
    "🌐 Веб": ["HTML", "CSS", "JS", "TS", "PHP"],
    "💻 Код": ["PY", "JAVA", "C", "CPP", "H", "GO", "RS", "SQL"],
    "⚙️ Скрипты": ["SH", "BAT", "PS1"],
}


# ==================== КЛАВИАТУРЫ ====================
def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖼 Конвертация изображений", callback_data="menu:convert")],
        [InlineKeyboardButton(text="📄 Создать файл", callback_data="menu:create")],
        [InlineKeyboardButton(text="✏️ Изменить имя/расширение", callback_data="menu:rename")],
        [InlineKeyboardButton(text="💻 Код в файл", callback_data="menu:code")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="menu:help")],
    ])


def back_kb(to: str = "main") -> InlineKeyboardMarkup:
    text = "🏠 Главное меню" if to == "main" else "◀️ Назад"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=f"back:{to}")]
    ])


def back_with_cancel_kb(to: str = "main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"back:{to}"),
            InlineKeyboardButton(text="🏠 В меню", callback_data="back:main"),
        ]
    ])


def image_format_kb() -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for i, fmt in enumerate(IMAGE_FORMATS):
        row.append(InlineKeyboardButton(text=fmt, callback_data=f"conv_fmt:{fmt}"))
        if (i + 1) % 4 == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="back:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def file_category_kb() -> InlineKeyboardMarkup:
    buttons = []
    for cat_name in FILE_CATEGORIES.keys():
        buttons.append([InlineKeyboardButton(text=cat_name, callback_data=f"cat:{cat_name}")])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="back:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def file_ext_kb(category: str) -> InlineKeyboardMarkup:
    exts = FILE_CATEGORIES[category]
    buttons = []
    row = []
    for i, ext in enumerate(exts):
        row.append(InlineKeyboardButton(text=ext, callback_data=f"create_ext:{ext}"))
        if (i + 1) % 4 == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:create"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="back:main"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def code_lang_kb() -> InlineKeyboardMarkup:
    code_exts = ["PY", "JS", "TS", "JAVA", "C", "CPP", "H", "GO", "RS",
                 "HTML", "CSS", "PHP", "SQL", "SH", "BAT", "JSON", "XML", "YAML", "TXT", "MD"]
    buttons = []
    row = []
    for i, ext in enumerate(code_exts):
        row.append(InlineKeyboardButton(text=ext, callback_data=f"code_ext:{ext}"))
        if (i + 1) % 5 == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="back:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==================== УТИЛИТЫ ====================
def sanitize_filename(name: str) -> str:
    forbidden = r'\/:*?"<>|'
    for ch in forbidden:
        name = name.replace(ch, "_")
    name = name.strip(". ")
    return name or "file"


def convert_image(image_bytes: bytes, target_fmt: str) -> tuple:
    img = Image.open(io.BytesIO(image_bytes))

    if target_fmt in ("JPG", "BMP") and img.mode in ("RGBA", "P", "LA"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        bg.paste(img, mask=img.split()[-1] if "A" in img.mode else None)
        img = bg
    elif target_fmt in ("JPG", "BMP") and img.mode != "RGB":
        img = img.convert("RGB")

    out = io.BytesIO()
    save_kwargs = {}

    if target_fmt == "JPG":
        pil_fmt, mime = "JPEG", "image/jpeg"
        save_kwargs["quality"] = 95
    elif target_fmt == "PNG":
        pil_fmt, mime = "PNG", "image/png"
    elif target_fmt == "WEBP":
        pil_fmt, mime = "WEBP", "image/webp"
        save_kwargs["quality"] = 90
    elif target_fmt == "BMP":
        pil_fmt, mime = "BMP", "image/bmp"
    elif target_fmt == "TIFF":
        pil_fmt, mime = "TIFF", "image/tiff"
    elif target_fmt == "GIF":
        pil_fmt, mime = "GIF", "image/gif"
    elif target_fmt == "ICO":
        pil_fmt, mime = "ICO", "image/x-icon"
        save_kwargs["sizes"] = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    else:
        raise ValueError(f"Неизвестный формат: {target_fmt}")

    img.save(out, format=pil_fmt, **save_kwargs)
    return out.getvalue(), mime


# ==================== ГЛАВНОЕ МЕНЮ ====================
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    heic_note = "✅ Поддержка HEIC/HEIF активна\n" if HEIC_SUPPORT else ""
    text = (
        f"👋 <b>Привет, {message.from_user.first_name}!</b>\n\n"
        f"Я — универсальный комбайн для работы с файлами.\n\n"
        f"🎯 <b>Возможности:</b>\n"
        f"• 🖼 Конвертация изображений (7+ форматов)\n"
        f"• 📄 Создание файлов 20+ типов\n"
        f"• ✏️ Переименование любых файлов\n"
        f"• 💻 Превращение кода в файлы\n\n"
        f"{heic_note}"
        f"📏 Лимит размера файла: <b>{MAX_FILE_SIZE_MB} МБ</b>\n\n"
        f"👇 Выбери действие:"
    )
    await message.answer(text, reply_markup=main_menu_kb())


@router.callback_query(F.data == "back:main")
async def back_to_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await call.message.edit_text(
            "🏠 <b>Главное меню</b>\n\nВыбери действие:",
            reply_markup=main_menu_kb()
        )
    except Exception:
        await call.message.answer("🏠 <b>Главное меню</b>\n\nВыбери действие:", reply_markup=main_menu_kb())
    await call.answer()


@router.callback_query(F.data == "menu:help")
async def show_help(call: CallbackQuery):
    text = (
        "ℹ️ <b>Как пользоваться ботом</b>\n\n"
        "🖼 <b>Конвертация:</b> отправь фото или файл-картинку → выбери формат → получи результат.\n\n"
        "📄 <b>Создание файла:</b> выбери категорию → расширение → отправь содержимое → укажи имя.\n\n"
        "✏️ <b>Переименование:</b> отправь любой файл → введи новое имя с расширением (например, <code>photo.png</code>).\n\n"
        "💻 <b>Код в файл:</b> выбери язык → отправь код сообщением → укажи имя файла.\n\n"
        "💡 <b>Совет:</b> для лучшего качества картинок отправляй их как <b>документ</b>, а не как фото."
    )
    await call.message.edit_text(text, reply_markup=back_kb("main"))
    await call.answer()


# ==================== КОНВЕРТАЦИЯ ИЗОБРАЖЕНИЙ ====================
@router.callback_query(F.data == "menu:convert")
async def conv_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(States.conv_wait_file)
    text = (
        "🖼 <b>Конвертация изображений</b>\n\n"
        "Отправь мне изображение:\n"
        "• Как <b>фото</b> 📷\n"
        "• Или как <b>документ</b> 📎 (рекомендуется для качества)\n\n"
        "Поддерживаются: JPG, PNG, WEBP, BMP, TIFF, GIF, ICO"
        + (", HEIC/HEIF" if HEIC_SUPPORT else "")
    )
    await call.message.edit_text(text, reply_markup=back_with_cancel_kb("main"))
    await call.answer()


@router.message(States.conv_wait_file, F.photo)
async def conv_get_photo(message: Message, state: FSMContext):
    photo = message.photo[-1]
    if photo.file_size and photo.file_size > MAX_FILE_SIZE:
        await message.answer(f"❌ Файл слишком большой (лимит {MAX_FILE_SIZE_MB} МБ).")
        return
    file = await bot.get_file(photo.file_id)
    data = await bot.download_file(file.file_path)
    await state.update_data(image_bytes=data.read(), source_name="photo")
    await message.answer("🎨 Выбери целевой формат:", reply_markup=image_format_kb())


@router.message(States.conv_wait_file, F.document)
async def conv_get_document(message: Message, state: FSMContext):
    doc = message.document
    if doc.file_size and doc.file_size > MAX_FILE_SIZE:
        await message.answer(f"❌ Файл слишком большой (лимит {MAX_FILE_SIZE_MB} МБ).")
        return
    file = await bot.get_file(doc.file_id)
    data = await bot.download_file(file.file_path)
    name = doc.file_name or "image"
    await state.update_data(image_bytes=data.read(), source_name=name.rsplit(".", 1)[0])
    await message.answer("🎨 Выбери целевой формат:", reply_markup=image_format_kb())


@router.callback_query(F.data.startswith("conv_fmt:"))
async def conv_do_convert(call: CallbackQuery, state: FSMContext):
    target_fmt = call.data.split(":")[1]
    data = await state.get_data()
    image_bytes = data.get("image_bytes")
    source_name = data.get("source_name", "image")

    if not image_bytes:
        await call.answer("❌ Нет изображения", show_alert=True)
        return

    await call.answer("⏳ Конвертирую...")
    progress = await call.message.answer("⏳ Обрабатываю изображение...")

    try:
        result_bytes, mime = convert_image(image_bytes, target_fmt)
        ext = "jpg" if target_fmt == "JPG" else target_fmt.lower()
        filename = f"{sanitize_filename(source_name)}.{ext}"

        await progress.delete()
        await call.message.answer_document(
            document=BufferedInputFile(result_bytes, filename=filename),
            caption=f"✅ Готово! Формат: <b>{target_fmt}</b> | Размер: <b>{len(result_bytes) / 1024:.1f} КБ</b>"
        )
        await state.clear()
        await call.message.answer("🏠 Возвращаю в главное меню:", reply_markup=main_menu_kb())
    except Exception as e:
        logging.exception("Ошибка конвертации")
        await progress.edit_text(f"❌ Не удалось конвертировать: <code>{e}</code>", reply_markup=back_kb("main"))


# ==================== СОЗДАНИЕ ФАЙЛОВ ====================
@router.callback_query(F.data == "menu:create")
async def create_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "📄 <b>Создание файла</b>\n\nВыбери категорию:",
        reply_markup=file_category_kb()
    )
    await call.answer()


@router.callback_query(F.data.startswith("cat:"))
async def create_show_exts(call: CallbackQuery, state: FSMContext):
    category = call.data.split(":", 1)[1]
    await state.update_data(category=category)
    await call.message.edit_text(
        f"📁 <b>Категория:</b> {category}\n\nВыбери расширение:",
        reply_markup=file_ext_kb(category)
    )
    await call.answer()


@router.callback_query(F.data.startswith("create_ext:"))
async def create_ask_content(call: CallbackQuery, state: FSMContext):
    ext = call.data.split(":")[1]
    await state.update_data(extension=ext)
    await state.set_state(States.create_wait_content)
    await call.message.edit_text(
        f"📝 <b>Формат:</b> {ext}\n\n"
        f"Теперь отправь содержимое файла текстовым сообщением.\n"
        f"Можно отправлять большой текст — всё будет сохранено.",
        reply_markup=back_with_cancel_kb("main")
    )
    await call.answer()


@router.message(States.create_wait_content, F.text)
async def create_save_content(message: Message, state: FSMContext):
    await state.update_data(content=message.text)
    await state.set_state(States.create_wait_name)
    data = await state.get_data()
    ext = data.get("extension", "txt")
    await message.answer(
        f"📝 Содержимое принято ({len(message.text)} символов).\n\n"
        f"Введи имя файла <b>без расширения</b> (оно будет <code>.{ext.lower()}</code>):",
        reply_markup=back_with_cancel_kb("main")
    )


@router.message(States.create_wait_name, F.text)
async def create_final(message: Message, state: FSMContext):
    data = await state.get_data()
    ext = data.get("extension", "txt").lower()
    content = data.get("content", "")
    name = sanitize_filename(message.text.strip())
    filename = f"{name}.{ext}"

    file_bytes = content.encode("utf-8")
    await message.answer_document(
        document=BufferedInputFile(file_bytes, filename=filename),
        caption=f"✅ Файл <b>{filename}</b> создан! Размер: {len(file_bytes)} байт."
    )
    await state.clear()
    await message.answer("🏠 Главное меню:", reply_markup=main_menu_kb())


# ==================== ПЕРЕИМЕНОВАНИЕ ====================
@router.callback_query(F.data == "menu:rename")
async def rename_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(States.rename_wait_file)
    await call.message.edit_text(
        "✏️ <b>Изменение имени/расширения</b>\n\n"
        "Отправь мне любой файл (документ).",
        reply_markup=back_with_cancel_kb("main")
    )
    await call.answer()


@router.message(States.rename_wait_file, F.document)
async def rename_get_file(message: Message, state: FSMContext):
    doc = message.document
    if doc.file_size and doc.file_size > MAX_FILE_SIZE:
        await message.answer(f"❌ Файл слишком большой (лимит {MAX_FILE_SIZE_MB} МБ).")
        return
    file = await bot.get_file(doc.file_id)
    data = await bot.download_file(file.file_path)
    await state.update_data(
        file_bytes=data.read(),
        mime=doc.mime_type or "application/octet-stream",
        old_name=doc.file_name or "file"
    )
    await state.set_state(States.rename_wait_name)
    await message.answer(
        f"📎 Файл <b>{doc.file_name}</b> получен.\n\n"
        f"Введи <b>новое имя с расширением</b>:\n"
        f"Например: <code>отчёт_2024.pdf</code>",
        reply_markup=back_with_cancel_kb("main")
    )


@router.message(States.rename_wait_name, F.text)
async def rename_apply(message: Message, state: FSMContext):
    data = await state.get_data()
    new_name = message.text.strip()
    if "." not in new_name:
        await message.answer("❌ Имя должно содержать расширение (например, <code>file.txt</code>). Попробуй ещё раз:")
        return

    safe_name = sanitize_filename(new_name.rsplit(".", 1)[0]) + "." + new_name.rsplit(".", 1)[1].strip()
    file_bytes = data["file_bytes"]

    await message.answer_document(
        document=BufferedInputFile(file_bytes, filename=safe_name),
        caption=f"✅ Готово! Было: <b>{data['old_name']}</b> → Стало: <b>{safe_name}</b>"
    )
    await state.clear()
    await message.answer("🏠 Главное меню:", reply_markup=main_menu_kb())


# ==================== КОД В ФАЙЛ ====================
@router.callback_query(F.data == "menu:code")
async def code_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "💻 <b>Код → Файл</b>\n\nВыбери язык/расширение:",
        reply_markup=code_lang_kb()
    )
    await call.answer()


@router.callback_query(F.data.startswith("code_ext:"))
async def code_ask_code(call: CallbackQuery, state: FSMContext):
    ext = call.data.split(":")[1]
    await state.update_data(extension=ext)
    await state.set_state(States.code_wait_code)
    await call.message.edit_text(
        f"💻 <b>Расширение:</b> .{ext.lower()}\n\n"
        f"Отправь код сообщением. Можно <b>большой объём</b> — всё сохранится в файл.\n\n"
        f"💡 Совет: используй моноширинный формат (тройные кавычки), чтобы сохранить отступы.",
        reply_markup=back_with_cancel_kb("main")
    )
    await call.answer()


@router.message(States.code_wait_code, F.text)
async def code_save(message: Message, state: FSMContext):
    code = message.text or ""
    
    # Снимаем обёртку markdown (
```code
```), если она есть.
    # Используем конкатенацию, чтобы избежать багов парсинга Markdown при копировании!
    backticks = "`" * 3
    if code.startswith(backticks) and code.endswith(backticks):
        lines = code.split("\n")
        if len(lines) >= 2:
            code = "\n".join(lines[1:-1])

    await state.update_data(code=code)
    await state.set_state(States.code_wait_name)
    data = await state.get_data()
    ext = data.get("extension", "txt")
    
    await message.answer(
        f"📥 Код принят ({len(code)} символов, ~{len(code.encode('utf-8'))} байт).\n\n"
        f"Введи имя файла <b>без расширения</b> (.{ext.lower()} добавится автоматически):",
        reply_markup=back_with_cancel_kb("main")
    )


@router.message(States.code_wait_name, F.text)
async def code_final(message: Message, state: FSMContext):
    data = await state.get_data()
    ext = data.get("extension", "txt").lower()
    code = data.get("code", "")
    name = sanitize_filename(message.text.strip())
    filename = f"{name}.{ext}"

    file_bytes = code.encode("utf-8")
    await message.answer_document(
        document=BufferedInputFile(file_bytes, filename=filename),
        caption=f"✅ Файл <b>{filename}</b> создан!\n"
                f"📏 Строк: {code.count(chr(10)) + 1} | Размер: {len(file_bytes) / 1024:.1f} КБ"
    )
    await state.clear()
    await message.answer("🏠 Главное меню:", reply_markup=main_menu_kb())


# ==================== ЗАПУСК ====================
async def main():
    logging.info("🚀 Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

