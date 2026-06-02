import aiosqlite
import logging

DB_PATH = "phoenix3_bot.db"
logger = logging.getLogger(__name__)

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                full_name   TEXT,
                minecraft_nick TEXT DEFAULT '',
                balance     INTEGER DEFAULT 0,
                task_done   INTEGER DEFAULT 0,
                lang        TEXT DEFAULT 'ru',
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS task_submissions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                photo_id    TEXT,
                task_id     INTEGER DEFAULT 1,
                status      TEXT DEFAULT 'pending',
                admin_comment TEXT DEFAULT '',
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS withdraw_requests (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER,
                amount          INTEGER,
                minecraft_nick  TEXT,
                status          TEXT DEFAULT 'pending',
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS support_tickets (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                message     TEXT,
                from_admin  INTEGER DEFAULT 0,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.commit()
    logger.info("Database initialized")
    await migrate_db()

async def migrate_db():
    """Добавляет новые столбцы если их нет"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("PRAGMA table_info(task_submissions)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "task_id" not in columns:
            await db.execute("ALTER TABLE task_submissions ADD COLUMN task_id INTEGER DEFAULT 1")
            await db.commit()
    # Заполняем bot_config значениями по умолчанию, если пусто
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT value FROM bot_config WHERE key = 'task2_text'")
        if not await cursor.fetchone():
            from config import TASK2_TEXT, TASK2_MEDIA_ID, TASK2_MEDIA_TYPE
            await db.execute("REPLACE INTO bot_config (key, value) VALUES (?, ?)", ("task2_text", TASK2_TEXT))
            await db.execute("REPLACE INTO bot_config (key, value) VALUES (?, ?)", ("task2_media_id", TASK2_MEDIA_ID or ""))
            await db.execute("REPLACE INTO bot_config (key, value) VALUES (?, ?)", ("task2_media_type", TASK2_MEDIA_TYPE or ""))
            await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return await cursor.fetchone()

async def create_user(user_id: int, username: str, full_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)",
            (user_id, username or "", full_name or "")
        )
        await db.commit()

async def update_user(user_id: int, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [user_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE users SET {sets} WHERE user_id = ?", values)
        await db.commit()

async def add_balance(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()

async def subtract_balance(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()

async def add_task_submission_with_task(user_id: int, photo_id: str, task_id: int = 1) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO task_submissions (user_id, photo_id, task_id) VALUES (?, ?, ?)",
            (user_id, photo_id, task_id)
        )
        await db.commit()
        return cursor.lastrowid

async def get_submission(submission_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM task_submissions WHERE id = ?", (submission_id,)
        )
        return await cursor.fetchone()

async def update_submission(submission_id: int, status: str, comment: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE task_submissions SET status = ?, admin_comment = ? WHERE id = ?",
            (status, comment, submission_id)
        )
        await db.commit()

async def is_task_done(user_id: int, task_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM task_submissions WHERE user_id = ? AND task_id = ? AND status = 'approved'",
            (user_id, task_id)
        )
        return await cursor.fetchone() is not None

async def get_completed_tasks(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT task_id FROM task_submissions WHERE user_id = ? AND status = 'approved'",
            (user_id,)
        )
        return [row[0] for row in await cursor.fetchall()]

async def add_withdraw_request(user_id: int, amount: int, minecraft_nick: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO withdraw_requests (user_id, amount, minecraft_nick) VALUES (?, ?, ?)",
            (user_id, amount, minecraft_nick)
        )
        await db.commit()
        return cursor.lastrowid

async def get_withdraw_request(req_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM withdraw_requests WHERE id = ?", (req_id,)
        )
        return await cursor.fetchone()

async def update_withdraw_request(req_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE withdraw_requests SET status = ? WHERE id = ?",
            (status, req_id)
        )
        await db.commit()

async def add_support_message(user_id: int, message: str, from_admin: bool = False):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO support_tickets (user_id, message, from_admin) VALUES (?, ?, ?)",
            (user_id, message, int(from_admin))
        )
        await db.commit()

async def get_user_support_history(user_id: int, limit: int = 10):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM support_tickets WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        )
        return await cursor.fetchall()

# --- Для задания #2 ---
async def get_task2_config():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT key, value FROM bot_config WHERE key LIKE 'task2_%'")
        rows = await cursor.fetchall()
        config = {"text": "", "media_id": None, "media_type": None}
        for row in rows:
            if row["key"] == "task2_text":
                config["text"] = row["value"]
            elif row["key"] == "task2_media_id":
                config["media_id"] = row["value"] if row["value"] else None
            elif row["key"] == "task2_media_type":
                config["media_type"] = row["value"] if row["value"] else None
        return config

async def set_task2_config(text: str = None, media_id: str = None, media_type: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if text is not None:
            await db.execute("REPLACE INTO bot_config (key, value) VALUES (?, ?)", ("task2_text", text))
        if media_id is not None:
            await db.execute("REPLACE INTO bot_config (key, value) VALUES (?, ?)", ("task2_media_id", media_id))
        if media_type is not None:
            await db.execute("REPLACE INTO bot_config (key, value) VALUES (?, ?)", ("task2_media_type", media_type))
        await db.commit()