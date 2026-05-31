import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
)
from database import Database

# ─── ВСТАВЬ СВОЙ ТОКЕН СЮДА ───────────────────────────────────────────
import os
BOT_TOKEN = os.environ.get("8936794059:AAEPQZi7XxGXAakHVwN1ynRy8JRy6DR6v9A")
# ──────────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
db = Database("chat.db")


# ── Все интересы ─────────────────────────────────────────────────────

INTERESTS = {
    "general": [
        ("🎵 Музыка",     "music"),
        ("🎮 Игры",       "games"),
        ("🎬 Кино",       "movies"),
        ("📚 Книги",      "books"),
        ("⚽ Спорт",      "sport"),
        ("✈️ Путешествия","travel"),
        ("🍕 Еда",        "food"),
        ("🎨 Творчество", "art"),
        ("💻 Технологии", "tech"),
        ("🐾 Животные",   "animals"),
    ],
    "fun": [
        ("😈 Шалости",    "mischief"),
        ("🔥 Флирт",      "flirt"),
        ("💋 Интим",      "intimate"),
        ("🎭 Ролевые игры","roleplay"),
    ]
}

ALL_INTERESTS = {v: l for l, v in INTERESTS["general"] + INTERESTS["fun"]}


# ── FSM ──────────────────────────────────────────────────────────────

class Registration(StatesGroup):
    gender = State()
    age = State()
    interests = State()

class SearchSettings(StatesGroup):
    search_gender = State()

class EditProfile(StatesGroup):
    interests = State()


# ── Клавиатуры ───────────────────────────────────────────────────────

def kb_main():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🔍 Найти собеседника")],
        [KeyboardButton(text="👤 Мой профиль"), KeyboardButton(text="⚙️ Настройки")],
        [KeyboardButton(text="📊 Статистика"),  KeyboardButton(text="👥 Реферальная ссылка")],
    ], resize_keyboard=True)

def kb_gender():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👦 Парень"), KeyboardButton(text="👧 Девушка")],
    ], resize_keyboard=True)

def kb_search_gender():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👦 Парня"),    KeyboardButton(text="👧 Девушку")],
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


# ── Inline клавиатура интересов ───────────────────────────────────────

def kb_interests(selected: list) -> InlineKeyboardMarkup:
    buttons = []

    # Обычные интересы
    row = []
    for label, key in INTERESTS["general"]:
        mark = "✅" if key in selected else ""
        row.append(InlineKeyboardButton(
            text=f"{mark}{label}" if not mark else f"{label} ✅",
            callback_data=f"interest_{key}"
        ))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # Разделитель
    buttons.append([InlineKeyboardButton(text="─── 🔞 Для взрослых ───", callback_data="noop")])

    # Интересы 18+
    row = []
    for label, key in INTERESTS["fun"]:
        mark = "✅" if key in selected else ""
        row.append(InlineKeyboardButton(
            text=f"{label} ✅" if mark else label,
            callback_data=f"interest_{key}"
        ))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # Кнопка готово
    buttons.append([InlineKeyboardButton(text="✅ Готово", callback_data="interests_done")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Helpers ──────────────────────────────────────────────────────────

def gender_emoji(g): return "👦" if g == "male" else "👧"
def gender_text(g):  return "Парень" if g == "male" else "Девушка"
def search_gender_text(sg):
    if sg == "male":   return "👦 Парней"
    if sg == "female": return "👧 Девушек"
    return "🎲 Всех"

def format_interests(keys: list) -> str:
    if not keys:
        return "не выбраны"
    return ", ".join(ALL_INTERESTS.get(k, k) for k in keys)


# ── Меню команд бота ─────────────────────────────────────────────────

async def set_bot_commands():
    commands = [
        BotCommand(command="start",   description="🏠 Главное меню"),
        BotCommand(command="search",  description="🔍 Найти собеседника"),
        BotCommand(command="next",    description="⏭ Следующий собеседник"),
        BotCommand(command="stop",    description="❌ Завершить чат"),
        BotCommand(command="profile", description="👤 Мой профиль"),
        BotCommand(command="edit",    description="✏️ Изменить интересы"),
        BotCommand(command="settings",description="⚙️ Настройки поиска"),
        BotCommand(command="stats",   description="📊 Статистика"),
        BotCommand(command="ref",     description="👥 Реферальная ссылка"),
    ]
    await bot.set_my_commands(commands)


# ── /start ───────────────────────────────────────────────────────────

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    uid = message.from_user.id
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
        await message.answer("👋 С возвращением! Выбери действие:", reply_markup=kb_main())
        return

    await state.set_state(Registration.gender)
    await message.answer(
        "🌟 *Добро пожаловать в анонимный чат!*\n\n"
        "Общайся анонимно с незнакомцами 🔒\n\n"
        "❓ *Кто ты?*",
        parse_mode="Markdown",
        reply_markup=kb_gender()
    )


# ── Регистрация ───────────────────────────────────────────────────────

@dp.message(Registration.gender)
async def reg_gender(message: types.Message, state: FSMContext):
    if message.text == "👦 Парень":      gender = "male"
    elif message.text == "👧 Девушка":   gender = "female"
    else:
        await message.answer("Выбери из вариантов 👇", reply_markup=kb_gender())
        return

    await state.update_data(gender=gender)
    await state.set_state(Registration.age)
    await message.answer(
        f"{gender_emoji(gender)} Отлично!\n\n❓ *Сколько тебе лет?*",
        parse_mode="Markdown",
        reply_markup=kb_skip()
    )

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
    await state.update_data(selected_interests=[])

    await message.answer(
        "🎯 *Выбери свои интересы*\n\n"
        "Нажимай на квадратики — выбранные отмечаются ✅\n"
        "Можно выбрать несколько!\n\n"
        "_Раздел 🔞 только для 18+_",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    await message.answer("👇 Выбери интересы:", reply_markup=kb_interests([]))

@dp.callback_query(F.data.startswith("interest_"), Registration.interests)
async def reg_toggle_interest(callback: types.CallbackQuery, state: FSMContext):
    key = callback.data.replace("interest_", "")
    data = await state.get_data()
    selected = data.get("selected_interests", [])

    if key in selected:
        selected.remove(key)
    else:
        selected.append(key)

    await state.update_data(selected_interests=selected)
    await callback.message.edit_reply_markup(reply_markup=kb_interests(selected))
    await callback.answer()

@dp.callback_query(F.data == "interests_done", Registration.interests)
async def reg_interests_done(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("selected_interests", [])

    await db.update_user(
        callback.from_user.id,
        gender=data["gender"],
        age=data.get("age"),
        interests=selected,
        search_gender="any"
    )
    await state.clear()

    age_str = f", {data['age']} лет" if data.get("age") else ""
    interests_str = format_interests(selected)

    await callback.message.edit_text(
        f"✅ *Анкета заполнена!*\n\n"
        f"{gender_emoji(data['gender'])} {gender_text(data['gender'])}{age_str}\n"
        f"🎯 Интересы: {interests_str}\n\n"
        f"Теперь ты можешь найти собеседника 🎉",
        parse_mode="Markdown"
    )
    await callback.message.answer("Выбери действие:", reply_markup=kb_main())
    await callback.answer()


# ── Редактирование интересов ──────────────────────────────────────────

@dp.message(Command("edit"))
async def cmd_edit(message: types.Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user or not user.get("gender"):
        await message.answer("Сначала заполни анкету — /start")
        return

    selected = user.get("interests", [])
    await state.set_state(EditProfile.interests)
    await state.update_data(selected_interests=selected)
    await message.answer(
        "✏️ *Редактирование интересов*\n\nНажимай на кнопки чтобы выбрать/убрать:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    await message.answer("👇", reply_markup=kb_interests(selected))

@dp.callback_query(F.data.startswith("interest_"), EditProfile.interests)
async def edit_toggle_interest(callback: types.CallbackQuery, state: FSMContext):
    key = callback.data.replace("interest_", "")
    data = await state.get_data()
    selected = data.get("selected_interests", [])

    if key in selected:
        selected.remove(key)
    else:
        selected.append(key)

    await state.update_data(selected_interests=selected)
    await callback.message.edit_reply_markup(reply_markup=kb_interests(selected))
    await callback.answer()

@dp.callback_query(F.data == "interests_done", EditProfile.interests)
async def edit_interests_done(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("selected_interests", [])
    await db.update_user(callback.from_user.id, interests=selected)
    await state.clear()
    await callback.message.edit_text(
        f"✅ Интересы обновлены!\n🎯 {format_interests(selected)}",
        parse_mode="Markdown"
    )
    await callback.message.answer("Главное меню:", reply_markup=kb_main())
    await callback.answer()

@dp.callback_query(F.data == "noop")
async def noop(callback: types.CallbackQuery):
    await callback.answer()


# ── Профиль ──────────────────────────────────────────────────────────

@dp.message(F.text == "👤 Мой профиль")
@dp.message(Command("profile"))
async def cmd_profile(message: types.Message):
    user = await db.get_user(message.from_user.id)
    if not user or not user.get("gender"):
        await message.answer("Сначала заполни анкету — /start")
        return

    age_str = f"{user['age']} лет" if user.get("age") else "не указан"
    gender = user.get("gender", "male")

    await message.answer(
        f"👤 *Твой профиль*\n\n"
        f"{gender_emoji(gender)} Пол: {gender_text(gender)}\n"
        f"🎂 Возраст: {age_str}\n"
        f"🎯 Интересы: {format_interests(user.get('interests', []))}\n\n"
        f"🔍 Ищу: {search_gender_text(user.get('search_gender', 'any'))}\n"
        f"💬 Чатов: {user.get('chats_count', 0)}\n"
        f"👥 Приглашено: {user.get('ref_count', 0)}\n\n"
        f"_/edit — изменить интересы_",
        parse_mode="Markdown",
        reply_markup=kb_main()
    )


# ── Настройки ─────────────────────────────────────────────────────────

@dp.message(F.text == "⚙️ Настройки")
@dp.message(Command("settings"))
async def cmd_settings(message: types.Message, state: FSMContext):
    await state.set_state(SearchSettings.search_gender)
    await message.answer(
        "⚙️ *Настройки поиска*\n\n❓ Кого хочешь найти?",
        parse_mode="Markdown",
        reply_markup=kb_search_gender()
    )

@dp.message(SearchSettings.search_gender)
async def set_search_gender(message: types.Message, state: FSMContext):
    if message.text == "👦 Парня":          sg = "male"
    elif message.text == "👧 Девушку":      sg = "female"
    elif message.text == "🎲 Без разницы":  sg = "any"
    else:
        await message.answer("Выбери из вариантов 👇", reply_markup=kb_search_gender())
        return

    await db.update_user(message.from_user.id, search_gender=sg)
    await state.clear()
    await message.answer(f"✅ Теперь ищу: {search_gender_text(sg)}", reply_markup=kb_main())


# ── Реферальная ───────────────────────────────────────────────────────

@dp.message(F.text == "👥 Реферальная ссылка")
@dp.message(Command("ref"))
async def cmd_referral(message: types.Message):
    uid = message.from_user.id
    user = await db.get_user(uid)
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=ref_{uid}"

    await message.answer(
        f"👥 *Реферальная программа*\n\n"
        f"Приглашай друзей по своей ссылке!\n\n"
        f"🔗 Твоя ссылка:\n`{link}`\n\n"
        f"👤 Приглашено: *{user.get('ref_count', 0)}* чел.",
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


# ── Поиск ────────────────────────────────────────────────────────────

async def do_search(uid: int, send_fn):
    if await db.is_banned(uid):
        await send_fn("🚫 Ты заблокирован в боте.")
        return

    if not await db.is_registered(uid):
        await send_fn("Сначала заполни анкету — /start")
        return

    partner = await db.get_partner(uid)
    if partner:
        await send_fn("💬 Ты уже в чате. Нажми ❌ Завершить чат чтобы выйти.")
        return

    if await db.in_queue(uid):
        await send_fn("⏳ Уже ищем... чуть подожди 😊")
        return

    user = await db.get_user(uid)
    gender = user.get("gender", "male")
    search_gender = user.get("search_gender", "any")
    interests = user.get("interests", [])

    waiting = await db.get_from_queue(uid, gender, search_gender, interests)
    if waiting:
        await db.create_pair(uid, waiting)
        partner_user = await db.get_user(waiting)
        p_interests = partner_user.get("interests", [])
        common = list(set(interests) & set(p_interests))

        def build_msg(pu, common_list):
            msg = (
                "✅ *Собеседник найден!*\n\n"
                f"{gender_emoji(pu.get('gender','male'))} {gender_text(pu.get('gender','male'))}"
            )
            if pu.get("age"):
                msg += f", {pu['age']} лет"
            if pu.get("interests"):
                msg += f"\n🎯 Интересы: {format_interests(pu.get('interests', []))}"
            if common_list:
                msg += f"\n🤝 Общие: {format_interests(common_list)}"
            msg += "\n\n💬 Начинай общаться!\n_/next — следующий  |  /stop — выйти_"
            return msg

        await send_fn(build_msg(partner_user, common), kb_chat())
        await bot.send_message(
            waiting,
            build_msg(user, common),
            parse_mode="Markdown",
            reply_markup=kb_chat()
        )
    else:
        await db.add_to_queue(uid, gender, search_gender, interests)
        await send_fn(
            f"🔍 *Ищем собеседника...*\n\n"
            f"Ищу: {search_gender_text(search_gender)}\n"
            f"Твои интересы: {format_interests(interests)}\n\n"
            f"Как только найдём — сразу напишем! 😊"
        )


@dp.message(F.text == "🔍 Найти собеседника")
@dp.message(Command("search"))
async def cmd_search(message: types.Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id

    async def send_fn(text, markup=None):
        await message.answer(
            text, parse_mode="Markdown",
            reply_markup=markup if markup else ReplyKeyboardRemove()
        )

    await do_search(uid, send_fn)


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
    interests = user.get("interests", [])

    waiting = await db.get_from_queue(uid, gender, search_gender, interests)
    if waiting:
        await db.create_pair(uid, waiting)
        partner_user = await db.get_user(waiting)
        common = list(set(interests) & set(partner_user.get("interests", [])))

        msg = (
            "✅ *Новый собеседник найден!*\n\n"
            f"{gender_emoji(partner_user.get('gender','male'))} {gender_text(partner_user.get('gender','male'))}"
        )
        if partner_user.get("age"):
            msg += f", {partner_user['age']} лет"
        if partner_user.get("interests"):
            msg += f"\n🎯 {format_interests(partner_user.get('interests', []))}"
        if common:
            msg += f"\n🤝 Общие: {format_interests(common)}"
        msg += "\n\n💬 Начинай общаться!"

        await message.answer(msg, parse_mode="Markdown", reply_markup=kb_chat())

        my_msg = (
            "✅ *Новый собеседник найден!*\n\n"
            f"{gender_emoji(gender)} {gender_text(gender)}"
        )
        if user.get("age"):
            my_msg += f", {user['age']} лет"
        if user.get("interests"):
            my_msg += f"\n🎯 {format_interests(interests)}"
        if common:
            my_msg += f"\n🤝 Общие: {format_interests(common)}"
        my_msg += "\n\n💬 Начинай общаться!"

        await bot.send_message(waiting, my_msg, parse_mode="Markdown", reply_markup=kb_chat())
    else:
        await db.add_to_queue(uid, gender, search_gender, interests)
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


# ── Пересылка ─────────────────────────────────────────────────────────

@dp.message()
async def relay_message(message: types.Message, state: FSMContext):
    uid = message.from_user.id
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
    await set_bot_commands()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
