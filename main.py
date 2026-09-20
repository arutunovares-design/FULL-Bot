import asyncio
import logging
import os
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = -5230412814

LEADER_IDS = [8588786035]
CO_LEADER_IDS = [5881764705]
FAN_IDS = [1812755802]

ADMIN_IDS = LEADER_IDS + CO_LEADER_IDS + FAN_IDS

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ======== 1. БАЗА ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect("clan_members.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        nickname_id TEXT,
        level TEXT,
        rank TEXT,
        target_rank TEXT,
        kd TEXT,
        fav_gun TEXT,
        join_date TEXT,
        trust_level INTEGER DEFAULT 1,
        status TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()


# ======== 2. FSM (СОСТОЯНИЯ) ==========
class MemberCardForm(StatesGroup):
    waiting_for_nick_id = State()
    waiting_for_join_date = State()
    waiting_for_current_rank = State()
    waiting_for_target_rank = State()
    waiting_for_kd = State()
    waiting_for_fav_gun = State()

class JoinClanForm(StatesGroup):
    waiting_for_photo = State()
    waiting_for_level = State()
    waiting_for_rank = State()
    waiting_for_kd = State()
    waiting_for_fav_gun = State()
    waiting_for_activity = State()
    waiting_for_about = State()


# ======== 3. ГЛАВНОЕ МЕНЮ И START ==========
def get_main_keyboard(user_id: int):
    buttons = [
        [
            InlineKeyboardButton(text="⚔️ Состав / Моя карточка", callback_data="btn_inside"),
            InlineKeyboardButton(text="📊 Статистика", callback_data="btn_player_stats")
        ],
        [
            InlineKeyboardButton(text="📝 Вступить в клан", callback_data="btn_join_clan")
        ]
    ]
    
    if user_id in ADMIN_IDS:
        buttons.append([InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="btn_admin_panel")])
        
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@dp.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 <b>Приветствуем в официальном боте клана FULL•SQUAD!</b>\n\n"
        "Выбери нужный раздел в меню ниже:",
        reply_markup=get_main_keyboard(message.from_user.id),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "btn_join_clan")
async def start_join_clan(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(JoinClanForm.waiting_for_photo)
    await callback.message.answer(
        "<b>Шаг 1/7:</b> Отправь скриншот своего профиля из игры Blood Strike:",
        parse_mode="HTML"
    )


# ======== 4. ХЭНДЛЕРЫ JOINCLANFORM (Заявка в клан) ==========
@dp.message(JoinClanForm.waiting_for_photo, F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo=photo_id)
    await state.set_state(JoinClanForm.waiting_for_level)
    await message.answer("<b>Шаг 2/7:</b> Укажи свой уровень в игре:", parse_mode="HTML")

@dp.message(JoinClanForm.waiting_for_level)
async def process_level(message: types.Message, state: FSMContext):
    await state.update_data(level=message.text)
    await state.set_state(JoinClanForm.waiting_for_rank)
    await message.answer("<b>Шаг 3/7:</b> Укажи свой текущий ранг (КБ):", parse_mode="HTML")

@dp.message(JoinClanForm.waiting_for_rank)
async def process_rank(message: types.Message, state: FSMContext):
    await state.update_data(rank=message.text)
    await state.set_state(JoinClanForm.waiting_for_kd)
    await message.answer("<b>Шаг 4/7:</b> Укажи свой K/D:", parse_mode="HTML")

@dp.message(JoinClanForm.waiting_for_kd)
async def process_kd_join(message: types.Message, state: FSMContext):
    await state.update_data(kd=message.text)
    await state.set_state(JoinClanForm.waiting_for_fav_gun)
    await message.answer("<b>Шаг 5/7:</b> Назови свое любимое оружие:", parse_mode="HTML")

@dp.message(JoinClanForm.waiting_for_fav_gun)
async def process_fav_gun_join(message: types.Message, state: FSMContext):
    await state.update_data(fav_gun=message.text)
    await state.set_state(JoinClanForm.waiting_for_activity)
    await message.answer("<b>Шаг 6/7:</b> Сколько часов в день/в какое время играешь?", parse_mode="HTML")

@dp.message(JoinClanForm.waiting_for_activity)
async def process_activity(message: types.Message, state: FSMContext):
    await state.update_data(activity=message.text)
    await state.set_state(JoinClanForm.waiting_for_about)
    await message.answer("<b>Шаг 7/7:</b> Напиши пару слов о себе:", parse_mode="HTML")

@dp.message(JoinClanForm.waiting_for_about)
async def process_about(message: types.Message, state: FSMContext):
    await state.update_data(about=message.text)
    user_data = await state.get_data()
    applicant = message.from_user

    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_{applicant.id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{applicant.id}")
        ]
    ])

    caption_text = (
        f"📩 <b>НОВАЯ ЗАЯВКА В КЛАН FULL•SQUAD!</b>\n\n"
        f"👤 <b>Кандидат:</b> @{applicant.username or 'без_юзернейма'} ({applicant.first_name})\n"
        f"🆔 <b>TG ID:</b> <code>{applicant.id}</code>\n"
        f"📊 <b>Уровень:</b> {user_data['level']}\n"
        f"🏆 <b>Ранг:</b> {user_data['rank']}\n"
        f"🎯 <b>K/D:</b> {user_data['kd']}\n"
        f"🔫 <b>Любимый ган:</b> {user_data['fav_gun']}\n"
        f"⏰ <b>Актив:</b> {user_data['activity']}\n"
        f"📝 <b>О себе:</b> {user_data['about']}"
    )

    try:
        await message.bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=user_data['photo'],
            caption=caption_text,
            reply_markup=admin_kb,
            parse_mode="HTML"
        )
        await message.answer("🚀 <b>Твоя заявка отправлена руководству клана!</b> Ожидай решения.", parse_mode="HTML")
    except Exception as e:
        logging.error(f"Ошибка отправки заявки админу: {e}")
        await message.answer("❌ Произошла ошибка при отправке заявки. Попробуй позже.")

    await state.clear()


# ======== 5. ОБРАБОТКА РЕШЕНИЙ АДМИНА ==========
@dp.callback_query(F.data.startswith("accept_"))
async def accept_member(callback: types.CallbackQuery):
    applicant_id = int(callback.data.split("_")[1])
    await callback.answer("Заявка принята!")
    await callback.message.edit_caption(
        caption=callback.message.caption + "\n\n✅ <b>ПРИНЯТ В КЛАН</b>",
        parse_mode="HTML"
    )
    try:
        await bot.send_message(applicant_id, "🎉 <b>Поздравляем! Твоя заявка в FULL•SQUAD одобрена!</b> Добро пожаловать в строй!", parse_mode="HTML")
    except Exception:
        pass

@dp.callback_query(F.data.startswith("reject_"))
async def reject_member(callback: types.CallbackQuery):
    applicant_id = int(callback.data.split("_")[1])
    await callback.answer("Заявка отклонена.")
    await callback.message.edit_caption(
        caption=callback.message.caption + "\n\n❌ <b>ОТКЛОНЕН</b>",
        parse_mode="HTML"
    )
    try:
        await bot.send_message(applicant_id, "😔 К сожалению, твоя заявка в FULL•SQUAD была отклонена.", parse_mode="HTML")
    except Exception:
        pass


# ======== 6. КНОПКИ МЕНЮ ==========
@dp.callback_query(F.data == "btn_player_stats")
async def process_statistic(callback: types.CallbackQuery):
    await callback.answer("Сверяюсь с архивами...")
    await callback.message.answer("<i>Раздел статистики находится в разработке...</i>", parse_mode="HTML")

@dp.callback_query(F.data == "btn_inside")
async def process_inside(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    await callback.answer("Кто ты, воин?")

    if user_id in LEADER_IDS:
        await callback.message.answer(
            "<b>👑 ЛИЧНАЯ КАРТОЧКА ОСНОВАТЕЛЯ 👑</b>\n\n"
            "👤 <b>Статус:</b> Глава FULL•SQUAD\n"
            "📆 <b>В клане:</b> С момента основания 21.07.2026\n"
            "⭐️ <b>Уровень Доверия:</b> 5/5 (Основатель)\n"
            "🎯 <b>Цель:</b> Топ-1 Клан в Blood Strike\n\n"
            "<i>«Лидер ведет за собой!»</i> 👑",
            parse_mode="HTML"
        )
        return

    elif user_id in CO_LEADER_IDS:
        await callback.message.answer(
            "<b>⚔️ КАРТОЧКА ЗАМЕСТИТЕЛЯ ЛИДЕРА ⚔️</b>\n\n"
            "👤 <b>Статус:</b> Заместитель (Зам)\n"
            "📆 <b>В клане:</b> С 23.08.2026\n"
            "⭐️ <b>Уровень Доверия:</b> 5/5 (Бро Лидера)\n"
            "🔰 <b>Доступ:</b> Управление составом\n\n"
            "<i>«Правая рука и опора клана!»</i> 🫡",
            parse_mode="HTML"
        )
        return

    elif user_id in FAN_IDS:
        await callback.message.answer(
            "<b>🔥 КАРТОЧКА БОЛЕЛЬЩИКА 🔥</b>\n\n"
            "👤 <b>Статус:</b> Талисман клана FULL•SQUAD\n"
            "📆 <b>В клане:</b> С 01.08.2026\n"
            "❤️ <b>Поддержка:</b> На максимум!\n\n"
            "<i>Спасибо, что ты с нами!</i> 🎉",
            parse_mode="HTML"
        )
        return

    conn = sqlite3.connect("clan_members.db")
    cursor = conn.cursor()
    cursor.execute("SELECT nickname_id, join_date, rank, target_rank, trust_level FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()
    conn.close()

    if user_data:
        nick_id, join_date, rank, target_rank, trust = user_data
        await callback.message.answer(
            f"<b>Твоя Личная Карточка Бойца:</b>\n\n"
            f"👤 <b>Ник и UID:</b> {nick_id}\n"
            f"📆 <b>В клане с:</b> {join_date}\n"
            f"🏆 <b>Текущий ранг:</b> {rank}\n"
            f"🎯 <b>Целевой ранг:</b> {target_rank}\n"
            f"⭐️ <b>Уровень Доверия:</b> {trust}/5\n"
            f"🔰 <b>Статус:</b> Участник FULL•SQUAD",
            parse_mode="HTML"
        )
    else:
        await state.set_state(MemberCardForm.waiting_for_nick_id)
        await callback.message.answer(
            "<i>Мы рады видеть тебя с нами! Давай заполним твою личную карточку🫠</i>\n\n"
            "<b>Шаг 1/6:</b> Напиши свой игровой ник и UID:",
            parse_mode="HTML"
        )


# ======== 7. ХЭНДЛЕРЫ MEMBERCARDFORM (Уже в клане) ==========
@dp.message(MemberCardForm.waiting_for_nick_id)
async def process_nick_id(message: types.Message, state: FSMContext):
    await state.update_data(nick_id=message.text)
    await state.set_state(MemberCardForm.waiting_for_join_date)
    await message.answer("<b>Шаг 2/6:</b> Укажи дату, когда ты вступил в клан:", parse_mode="HTML")

@dp.message(MemberCardForm.waiting_for_join_date)
async def process_join_date(message: types.Message, state: FSMContext):
    await state.update_data(join_date=message.text)
    await state.set_state(MemberCardForm.waiting_for_current_rank)
    await message.answer("<b>Шаг 3/6:</b> Укажи свой текущий ранг в игре:", parse_mode="HTML")

@dp.message(MemberCardForm.waiting_for_current_rank)
async def process_current_rank(message: types.Message, state: FSMContext):
    await state.update_data(current_rank=message.text)
    await state.set_state(MemberCardForm.waiting_for_target_rank)
    await message.answer("<b>Шаг 4/6:</b> По желанию укажи желаемый ранг:", parse_mode="HTML")

@dp.message(MemberCardForm.waiting_for_target_rank)
async def process_target_rank(message: types.Message, state: FSMContext):
    await state.update_data(target_rank=message.text)
    await state.set_state(MemberCardForm.waiting_for_kd)
    await message.answer("<b>Шаг 5/6:</b> Укажи свой K/D в игре:", parse_mode="HTML")

@dp.message(MemberCardForm.waiting_for_kd)
async def process_kd(message: types.Message, state: FSMContext):
    await state.update_data(kd=message.text)
    await state.set_state(MemberCardForm.waiting_for_fav_gun)
    await message.answer("<b>Шаг 6/6:</b> Назови свое любимое оружие:", parse_mode="HTML")

@dp.message(MemberCardForm.waiting_for_fav_gun)
async def process_fav_gun(message: types.Message, state: FSMContext):
    await state.update_data(fav_gun=message.text)
    user_data = await state.get_data()
    
    conn = sqlite3.connect("clan_members.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO users 
        (user_id, username, nickname_id, join_date, rank, target_rank, kd, fav_gun, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        message.from_user.id,
        message.from_user.username,
        user_data['nick_id'],
        user_data['join_date'],
        user_data['current_rank'],
        user_data['target_rank'],
        user_data['kd'],
        user_data['fav_gun'],
        'member'
    ))
    conn.commit()
    conn.close()

    await state.clear()
    await message.answer("✅ <b>Твоя карточка успешно сохранена в базе FULL•SQUAD!</b>", parse_mode="HTML")


# ======== 8. АДМИН-ПАНЕЛЬ И КОМАНДЫ ==========

async def send_admin_info(message_or_callback):
    conn = sqlite3.connect("clan_members.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT user_id, nickname_id, trust_level FROM users LIMIT 10")
    members = cursor.fetchall()
    conn.close()

    text = f"⚙️ <b>АДМИН-ПАНЕЛЬ FULL•SQUAD</b>\n\n👥 Всего в базе: <b>{total_users}</b>\n\n<b>Последние записи:</b>\n"
    for m in members:
        text += f"• ID: <code>{m[0]}</code> | Ник: {m[1]} | Доверие: {m[2]}/5\n"
    text += (
        "\n<b>Доступные команды:</b>\n"
        "1️⃣ Изменить доверие:\n<code>/set_trust TG_ID LEVEL</code> (Пример: <code>/set_trust 8588786035 5</code>)\n\n"
        "2️⃣ Сделать рассылку всем:\n<code>/broadcast ТЕКСТ</code> (Пример: <code>/broadcast Важное объявление!</code>)"
    )

    if isinstance(message_or_callback, types.CallbackQuery):
        await message_or_callback.message.answer(text, parse_mode="HTML")
    else:
        await message_or_callback.answer(text, parse_mode="HTML")

@dp.callback_query(F.data == "btn_admin_panel")
async def process_admin_callback(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return
    await callback.answer()
    await send_admin_info(callback)

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У тебя нет доступа к админ-панели.")
        return
    await send_admin_info(message)

@dp.message(Command("set_trust"))
async def set_trust_level(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У тебя нет прав для изменения уровня доверия.")
        return

    try:
        args = message.text.split()
        target_id = int(args[1])
        new_trust = int(args[2])

        conn = sqlite3.connect("clan_members.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET trust_level = ? WHERE user_id = ?", (new_trust, target_id))
        conn.commit()
        conn.close()

        await message.answer(f"✔️ Уровень доверия пользователя <code>{target_id}</code> изменен на <b>{new_trust}/5</b>!", parse_mode="HTML")
    except Exception:
        await message.answer("⚠️ Использование: <code>/set_trust TG_ID LEVEL</code>", parse_mode="HTML")

@dp.message(Command("broadcast"))
async def broadcast_message(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У тебя нет прав для создания рассылки.")
        return

    text_to_send = message.text.replace("/broadcast", "").strip()
    if not text_to_send:
        await message.answer("⚠️ Введи текст для рассылки после команды!")
        return

    conn = sqlite3.connect("clan_members.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()

    success, failed = 0, 0
    for u in users:
        try:
            await bot.send_message(u[0], f"📢 <b>ОБЪЯВЛЕНИЕ РУКОВОДСТВА FULL•SQUAD:</b>\n\n{text_to_send}", parse_mode="HTML")
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1

    await message.answer(f"📊 <b>Рассылка завершена!</b>\n✔️ Успешно: {success}\n❌ Не доставлено: {failed}", parse_mode="HTML")


# ======== 9. ОБЩИЙ ЭХО-ХЭНДЛЕР ==========
@dp.message()
async def echo_handler(message: types.Message):
    await message.answer(f"Принято! Твой текст: {message.text}")


# ======== 10. ВЕБ-СЕРВЕР ДЛЯ RENDER ==========
async def handle(request):
    return web.Response(text="FULL SQUAD Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()


# ======== 11. СТАРТ ==========
async def main():
    logging.basicConfig(level=logging.INFO)
    print("Чем займемся, командир?")
    
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
