import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
)
from database import Database

# ─── ВСТАВЬ СВОЙ ТОКЕН СЮДА ───────────────────────────────────────────
BOT_TOKEN = "8936794059:AAEPQZi7XxGXAakHVwN1ynRy8JRy6DR6v9A"
# ──────────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
db = Database("chat.db")


# ── FSM состояния (анкета) ────────────────────────────────────────────

class Registration(StatesGroup):
    gender = State()
    age = State()
    interests = State()

class SearchSettings(StatesGroup):
    search_gender = State()


# ── Клавиатуры ───────────────────────────────────────────────────────

def kb_main():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🔍 Найти собеседника")],
        [KeyboardButton(text="👤 Мой профиль"), KeyboardButton(text="⚙️ Настройки")],
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="👥 Реферальная ссылка")],
    ], resize_keyboard=True)

def kb_gender():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👦 Парень"), KeyboardButton(text="👧 Девушка")],
    ], resize_keyboard=True)

def kb_search_gender():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👦 Парня"), KeyboardButton(text="👧 Девушку")],
        [KeyboardButton(text="🎲 Без разницы")],
    ], resize_keyboard=True)

def kb_chat():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="⏭ Следующий"), KeyboardButton(text="❌ Завершить чат")],
    ], resize_keyboard=True)

def kb_skip():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="⏩ Пропустить")],
    ], resize_keyboard=True)


# ── Helpers ──────────────────────────────────────────────────────────

def gender_emoji(gender: str) -> str:
    return "👦" if gender == "male" else "👧"

def gender_text(gender: str) -> str:
    return "Парень" if gender == "male" else "Девушка"

def search_gender_text(sg: str) -> str:
    if sg == "male": return "👦 Парней"
    if sg == "female": return "👧 Девушек"
    return "🎲 Всех"


# ── /start ───────────────────────────────────────────────────────────

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    uid = message.from_user.id

    # Реферальная ссылка
    args = message.text.split()
    ref_by = None
    if len(args) > 1:
        try:
            ref_id = int(args[1].replace("ref_", ""))
            if ref_id != uid:
                ref_by = ref_id
        except:
            pass

    await db.add_user(uid, ref_by=ref_by)
    user = await db.get_user(uid)

    if user.get("gender"):
        await message.answer(
            "👋 С возвращением!\n\nВыбери действие:",
            reply_markup=kb_main()
        )
        return

    # Новый пользователь — анкета
    await state.set_state(Registration.gender)
    await message.answer(
        "🌟 *Добро пожаловать в анонимный чат!*\n\n"
        "Здесь ты можешь общаться с незнакомцами анонимно 🔒\n\n"
        "Давай заполним небольшую анкету.\n"
        "❓ *Кто ты?*",
        parse_mode="Markdown",
        reply_markup=kb_gender()
    )


# ── Регистрация: пол ─────────────────────────────────────────────────

@dp.message(Registration.gender)
async def reg_gender(message: types.Message, state: FSMContext):
    text = message.text
    if text == "👦 Парень":
        gender = "male"
    elif text == "👧 Девушка":
        gender = "female"
    else:
        await message.answer("Пожалуйста, выбери один из вариантов 👇", reply_markup=kb_gender())
        return

    await state.update_data(gender=gender)
    await state.set_state(Registration.age)
    await message.answer(
        f"{gender_emoji(gender)} Отлично!\n\n❓ *Сколько тебе лет?*\n_(напиши число, например: 18)_",
        parse_mode="Markdown",
        reply_markup=kb_skip()
    )


# ── Регистрация: возраст ─────────────────────────────────────────────

@dp.message(Registration.age)
async def reg_age(message: types.Message, state: FSMContext):
    age = None
    if message.text != "⏩ Пропустить":
        try:
            age = int(message.text)
            if not (10 <= age <= 99):
                await message.answer("⚠️ Введи реальный возраст (10–99):", reply_markup=kb_skip())
                return
        except:
            await message.answer("⚠️ Введи число, например *18*", parse_mode="Markdown", reply_markup=kb_skip())
            return

    await state.update_data(age=age)
    await state.set_state(Registration.interests)
    await message.answer(
        "✨ *Твои интересы*\n\n"
        "Напиши пару слов о себе или своих интересах.\n"
        "_(например: музыка, игры, кино)_\n\n"
        "Это поможет найти интересного собеседника 😊",
        parse_mode="Markdown",
        reply_markup=kb_skip()
    )


# ── Регистрация: интересы ────────────────────────────────────────────

@dp.message(Registration.interests)
async def reg_interests(message: types.Message, state: FSMContext):
    interests = None if message.text == "⏩ Пропустить" else message.text[:100]
    data = await state.get_data()

    await db.update_user(
        message.from_user.id,
        gender=data["gender"],
        age=data.get("age"),
        interests=interests,
        search_gender="any"
    )
    await state.clear()

    gender = data["gender"]
    age_str = f", {data['age']} лет" if data.get("age") else ""
    interests_str = f"\n🎯 Интересы: {interests}" if interests else ""

    await message.answer(
        f"✅ *Анкета заполнена!*\n\n"
        f"{gender_emoji(gender)} {gender_text(gender)}{age_str}"
        f"{interests_str}\n\n"
        f"Теперь ты можешь найти собеседника 🎉",
        parse_mode="Markdown",
        reply_markup=kb_main()
    )


# ── Профиль ──────────────────────────────────────────────────────────

@dp.message(F.text == "👤 Мой профиль")
async def cmd_profile(message: types.Message):
    user = await db.get_user(message.from_user.id)
    if not user or not user.get("gender"):
        await message.answer("Сначала заполни анкету — нажми /start")
        return

    age_str = f"{user['age']} лет" if user.get("age") else "не указан"
    interests_str = user.get("interests") or "не указаны"
    search_str = search_gender_text(user.get("search_gender", "any"))
    gender = user.get("gender", "male")

    await message.answer(
        f"👤 *Твой профиль*\n\n"
        f"{gender_emoji(gender)} Пол: {gender_text(gender)}\n"
        f"🎂 Возраст: {age_str}\n"
        f"🎯 Интересы: {interests_str}\n\n"
        f"🔍 Ищу: {search_str}\n"
        f"💬 Чатов проведено: {user.get('chats_count', 0)}\n"
        f"👥 Приглашено друзей: {user.get('ref_count', 0)}",
        parse_mode="Markdown",
        reply_markup=kb_main()
    )


# ── Настройки поиска ─────────────────────────────────────────────────

@dp.message(F.text == "⚙️ Настройки")
async def cmd_settings(message: types.Message, state: FSMContext):
    await state.set_state(SearchSettings.search_gender)
    await message.answer(
        "⚙️ *Настройки поиска*\n\n"
        "❓ Кого хочешь найти?",
        parse_mode="Markdown",
        reply_markup=kb_search_gender()
    )

@dp.message(SearchSettings.search_gender)
async def set_search_gender(message: types.Message, state: FSMContext):
    text = message.text
    if text == "👦 Парня":
        sg = "male"
    elif text == "👧 Девушку":
        sg = "female"
    elif text == "🎲 Без разницы":
        sg = "any"
    else:
        await message.answer("Выбери из вариантов 👇", reply_markup=kb_search_gender())
        return

    await db.update_user(message.from_user.id, search_gender=sg)
    await state.clear()
    await message.answer(
        f"✅ Настройки сохранены!\nТеперь ищу: {search_gender_text(sg)}",
        reply_markup=kb_main()
    )


# ── Реферальная ссылка ───────────────────────────────────────────────

@dp.message(F.text == "👥 Реферальная ссылка")
async def cmd_referral(message: types.Message):
    uid = message.from_user.id
    user = await db.get_user(uid)
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=ref_{uid}"
    ref_count = user.get("ref_count", 0) if user else 0

    await message.answer(
        f"👥 *Реферальная программа*\n\n"
        f"Приглашай друзей по своей ссылке!\n\n"
        f"🔗 Твоя ссылка:\n`{link}`\n\n"
        f"👤 Приглашено: *{ref_count}* чел.",
        parse_mode="Markdown",
        reply_markup=kb_main()
    )


# ── Статистика ────────────────────────────────────────────────────────

@dp.message(F.text == "📊 Статистика")
@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    stats = await db.get_stats()
    await message.answer(
        f"📊 *Статистика бота*\n\n"
        f"👥 Пользователей: *{stats['users']}*\n"
        f"💬 Активных чатов: *{stats['pairs']}*\n"
        f"⏳ В очереди: *{stats['queue']}*",
        parse_mode="Markdown",
        reply_markup=kb_main()
    )


# ── Поиск собеседника ────────────────────────────────────────────────

@dp.message(F.text == "🔍 Найти собеседника")
@dp.message(Command("search"))
async def cmd_search(message: types.Message, state: FSMContext):
    uid = message.from_user.id

    if await db.is_banned(uid):
        await message.answer("🚫 Ты заблокирован в боте.")
        return

    if not await db.is_registered(uid):
        await message.answer("Сначала заполни анкету — нажми /start")
        return

    await state.clear()

    partner = await db.get_partner(uid)
    if partner:
        await message.answer("💬 Ты уже в чате. Нажми ❌ Завершить чат чтобы выйти.", reply_markup=kb_chat())
        return

    if await db.in_queue(uid):
        await message.answer("⏳ Уже ищем... чуть подожди 😊", reply_markup=ReplyKeyboardRemove())
        return

    user = await db.get_user(uid)
    gender = user.get("gender", "male")
    search_gender = user.get("search_gender", "any")

    waiting = await db.get_from_queue(uid, gender, search_gender)
    if waiting:
        await db.create_pair(uid, waiting)
        partner_user = await db.get_user(waiting)

        msg = (
            "✅ *Собеседник найден!*\n\n"
            f"{gender_emoji(partner_user.get('gender', 'male'))} "
            f"{gender_text(partner_user.get('gender', 'male'))}"
        )
        if partner_user.get("age"):
            msg += f", {partner_user['age']} лет"
        if partner_user.get("interests"):
            msg += f"\n🎯 {partner_user['interests']}"
        msg += "\n\n💬 Начинай общаться!\n_/next — следующий  |  /stop — выйти_"

        await message.answer(msg, parse_mode="Markdown", reply_markup=kb_chat())

        my_msg = (
            "✅ *Собеседник найден!*\n\n"
            f"{gender_emoji(gender)} {gender_text(gender)}"
        )
        if user.get("age"):
            my_msg += f", {user['age']} лет"
        if user.get("interests"):
            my_msg += f"\n🎯 {user['interests']}"
        my_msg += "\n\n💬 Начинай общаться!\n_/next — следующий  |  /stop — выйти_"

        await bot.send_message(waiting, my_msg, parse_mode="Markdown", reply_markup=kb_chat())
    else:
        await db.add_to_queue(uid, gender, search_gender)
        search_str = search_gender_text(search_gender)
        await message.answer(
            f"🔍 *Ищем собеседника...*\n\n"
            f"Ищу: {search_str}\n\n"
            f"Как только найдём — сразу напишем! 😊",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove()
        )


# ── Следующий ────────────────────────────────────────────────────────

@dp.message(F.text == "⏭ Следующий")
@dp.message(Command("next"))
async def cmd_next(message: types.Message):
    uid = message.from_user.id
    partner = await db.get_partner(uid)

    if partner:
        await db.remove_pair(uid)
        await bot.send_message(
            partner,
            "👋 Собеседник ищет нового партнёра...",
            reply_markup=kb_main()
        )

    user = await db.get_user(uid)
    gender = user.get("gender", "male")
    search_gender = user.get("search_gender", "any")

    waiting = await db.get_from_queue(uid, gender, search_gender)
    if waiting:
        await db.create_pair(uid, waiting)
        partner_user = await db.get_user(waiting)

        msg = (
            "✅ *Новый собеседник найден!*\n\n"
            f"{gender_emoji(partner_user.get('gender', 'male'))} "
            f"{gender_text(partner_user.get('gender', 'male'))}"
        )
        if partner_user.get("age"):
            msg += f", {partner_user['age']} лет"
        if partner_user.get("interests"):
            msg += f"\n🎯 {partner_user['interests']}"
        msg += "\n\n💬 Начинай общаться!"

        await message.answer(msg, parse_mode="Markdown", reply_markup=kb_chat())

        my_msg = (
            "✅ *Новый собеседник найден!*\n\n"
            f"{gender_emoji(gender)} {gender_text(gender)}"
        )
        if user.get("age"):
            my_msg += f", {user['age']} лет"
        if user.get("interests"):
            my_msg += f"\n🎯 {user['interests']}"
        my_msg += "\n\n💬 Начинай общаться!"

        await bot.send_message(waiting, my_msg, parse_mode="Markdown", reply_markup=kb_chat())
    else:
        await db.add_to_queue(uid, gender, search_gender)
        await message.answer(
            "🔍 *Ищем нового собеседника...*\n\nКак только найдём — сразу напишем! 😊",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove()
        )


# ── Стоп ─────────────────────────────────────────────────────────────

@dp.message(F.text == "❌ Завершить чат")
@dp.message(Command("stop"))
async def cmd_stop(message: types.Message):
    uid = message.from_user.id
    partner = await db.get_partner(uid)

    if partner:
        await db.remove_pair(uid)
        await bot.send_message(
            partner,
            "❌ *Собеседник покинул чат.*\n\nНажми 🔍 чтобы найти нового!",
            parse_mode="Markdown",
            reply_markup=kb_main()
        )
        await message.answer(
            "✅ *Чат завершён.*\n\nНажми 🔍 чтобы найти нового собеседника!",
            parse_mode="Markdown",
            reply_markup=kb_main()
        )
    elif await db.in_queue(uid):
        await db.remove_from_queue(uid)
        await message.answer("🔍 Поиск отменён.", reply_markup=kb_main())
    else:
        await message.answer("Ты не в чате.", reply_markup=kb_main())


# ── Пересылка сообщений ───────────────────────────────────────────────

@dp.message()
async def relay_message(message: types.Message, state: FSMContext):
    uid = message.from_user.id

    # Если в FSM состоянии — не мешаем
    current_state = await state.get_state()
    if current_state:
        return

    if await db.is_banned(uid):
        await message.answer("🚫 Ты заблокирован.")
        return

    partner = await db.get_partner(uid)

    if not partner:
        if await db.in_queue(uid):
            await message.answer("⏳ Ещё ищем собеседника... подожди 😊")
        else:
            await message.answer(
                "💬 Ты не в чате.\nНажми *🔍 Найти собеседника* чтобы начать!",
                parse_mode="Markdown",
                reply_markup=kb_main()
            )
        return

    try:
        await bot.copy_message(
            chat_id=partner,
            from_chat_id=uid,
            message_id=message.message_id
        )
    except Exception as e:
        logging.error(f"Relay error: {e}")
        await message.answer("⚠️ Не удалось отправить сообщение.")


# ── Запуск ────────────────────────────────────────────────────────────

async def main():
    await db.init()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
