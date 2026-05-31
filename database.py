import aiosqlite


class Database:
    def __init__(self, path: str):
        self.path = path

    async def init(self):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    gender TEXT DEFAULT NULL,
                    age INTEGER DEFAULT NULL,
                    interests TEXT DEFAULT NULL,
                    search_gender TEXT DEFAULT 'any',
                    ref_by INTEGER DEFAULT NULL,
                    ref_count INTEGER DEFAULT 0,
                    chats_count INTEGER DEFAULT 0,
                    is_banned INTEGER DEFAULT 0,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS pairs (
                    user1 INTEGER UNIQUE,
                    user2 INTEGER UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS queue (
                    user_id INTEGER PRIMARY KEY,
                    gender TEXT DEFAULT NULL,
                    search_gender TEXT DEFAULT 'any',
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

    # ── Пользователи ─────────────────────────────────────────────────────

    async def add_user(self, uid: int, ref_by: int = None):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO users (id, ref_by) VALUES (?, ?)",
                (uid, ref_by)
            )
            if ref_by:
                await db.execute(
                    "UPDATE users SET ref_count = ref_count + 1 WHERE id = ?",
                    (ref_by,)
                )
            await db.commit()

    async def get_user(self, uid: int) -> dict | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE id = ?", (uid,)) as cur:
                row = await cur.fetchone()
        return dict(row) if row else None

    async def update_user(self, uid: int, **kwargs):
        fields = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [uid]
        async with aiosqlite.connect(self.path) as db:
            await db.execute(f"UPDATE users SET {fields} WHERE id = ?", values)
            await db.commit()

    async def is_registered(self, uid: int) -> bool:
        user = await self.get_user(uid)
        return user is not None and user.get("gender") is not None

    async def is_banned(self, uid: int) -> bool:
        user = await self.get_user(uid)
        return bool(user and user.get("is_banned"))

    # ── Очередь ───────────────────────────────────────────────────────────

    async def add_to_queue(self, uid: int, gender: str, search_gender: str):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO queue (user_id, gender, search_gender) VALUES (?, ?, ?)",
                (uid, gender, search_gender)
            )
            await db.commit()

    async def remove_from_queue(self, uid: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM queue WHERE user_id = ?", (uid,))
            await db.commit()

    async def in_queue(self, uid: int) -> bool:
        async with aiosqlite.connect(self.path) as db:
            async with db.execute("SELECT 1 FROM queue WHERE user_id = ?", (uid,)) as cur:
                return await cur.fetchone() is not None

    async def get_from_queue(self, exclude_uid: int, my_gender: str, search_gender: str) -> int | None:
        """
        Ищем подходящего партнёра:
        - если search_gender != 'any' → партнёр должен быть нужного пола
        - партнёр должен искать нас (any или наш пол)
        """
        async with aiosqlite.connect(self.path) as db:
            if search_gender == "any":
                query = """
                    SELECT user_id FROM queue
                    WHERE user_id != ?
                      AND (search_gender = 'any' OR search_gender = ?)
                    ORDER BY added_at LIMIT 1
                """
                params = (exclude_uid, my_gender)
            else:
                query = """
                    SELECT user_id FROM queue
                    WHERE user_id != ?
                      AND gender = ?
                      AND (search_gender = 'any' OR search_gender = ?)
                    ORDER BY added_at LIMIT 1
                """
                params = (exclude_uid, search_gender, my_gender)

            async with db.execute(query, params) as cur:
                row = await cur.fetchone()

            if row:
                uid = row[0]
                await db.execute("DELETE FROM queue WHERE user_id = ?", (uid,))
                await db.commit()
                return uid
        return None

    # ── Пары ──────────────────────────────────────────────────────────────

    async def create_pair(self, uid1: int, uid2: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO pairs (user1, user2) VALUES (?, ?)",
                (uid1, uid2)
            )
            await db.execute(
                "UPDATE users SET chats_count = chats_count + 1 WHERE id IN (?, ?)",
                (uid1, uid2)
            )
            await db.commit()

    async def get_partner(self, uid: int) -> int | None:
        async with aiosqlite.connect(self.path) as db:
            async with db.execute(
                "SELECT user1, user2 FROM pairs WHERE user1 = ? OR user2 = ?",
                (uid, uid)
            ) as cur:
                row = await cur.fetchone()
        if row:
            return row[1] if row[0] == uid else row[0]
        return None

    async def remove_pair(self, uid: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "DELETE FROM pairs WHERE user1 = ? OR user2 = ?",
                (uid, uid)
            )
            await db.commit()

    # ── Статистика ────────────────────────────────────────────────────────

    async def get_stats(self) -> dict:
        async with aiosqlite.connect(self.path) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as cur:
                users = (await cur.fetchone())[0]
            async with db.execute("SELECT COUNT(*) FROM pairs") as cur:
                pairs = (await cur.fetchone())[0]
            async with db.execute("SELECT COUNT(*) FROM queue") as cur:
                queue = (await cur.fetchone())[0]
        return {"users": users, "pairs": pairs, "queue": queue}
