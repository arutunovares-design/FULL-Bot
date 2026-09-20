import asyncio
import logging
import os
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web

# Логирование
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ID Администраторов / Главы / Замов (замените на реальные Telegram ID)
ADMIN_IDS = [123456789]  # Добавьте свой Telegram ID сюда

# Инициализация Базы Данных SQLite
def init_db():
    conn = sqlite3.connect("clan_bot.db")
    cursor = conn.cursor()
    
    # Таблица заявок
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            nickname TEXT,
            game_id TEXT,
            rank TEXT,
            kd REAL,
            status TEXT DEFAULT 'pending'
        )
    """)
    
    # Таблица соклановцев
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS members (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            nickname TEXT,
            game_id TEXT,
            role TEXT DEFAULT 'Member'
        )
    """)
    
    conn.commit()
    conn.close()

init_db()

# Машина состояний для подачи заявки
class ApplicationForm(StatesGroup):
    nickname = State()
    game_id = State()
    rank = State()
    kd = State()

# Клавиатуры
def get_main_keyboard(user_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Подать заявку в FULL•SQUAD", callback_data="apply")
    builder.button(text="📜 Правила клана", callback_data="rules")
    
    if user_id in ADMIN_IDS:
        builder.button(text="👑 Панель Управления", callback_data="admin_panel")
        
    builder.adjust(1)
    return builder.as_markup()

def get_admin_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📥 Просмотр заявок", callback_data="view_apps")
    builder.button(text="👥 Список соклановцев", callback_data="view_members")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

# Хэндлеры команд
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        f"Привет, {message.from_user.first_name}!\n"
        f"Добро пожаловать в официальный бот клана **FULL•SQUAD** по Blood Strike!\n\n"
        f"Выбери нужное действие в меню ниже:",
        reply_markup=get_main_keyboard(message.from_user.id),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "main_menu")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Главное меню клана **FULL•SQUAD**:",
        reply_markup=get_main_keyboard(callback.from_user.id),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "rules")
async def show_rules(callback: types.CallbackQuery):
    rules_text = (
        "📜 **Правила клана FULL•SQUAD:**\n\n"
        "1. Уважение к соклановцам и руководству.\n"
        "2. Активный онлайн и участие в клановых турнирах/праках.\n"
        "3. Наличие микрофона и связи во время игры.\n"
        "4. Соблюдение дисциплины и адекватность.\n"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="main_menu")
    await callback.message.edit_text(rules_text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

# Процесс подачи заявки
@dp.callback_query(F.data == "apply")
async def start_application(callback: types.CallbackQuery, state: FSMContext):
    conn = sqlite3.connect("clan_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM applications WHERE user_id = ? AND status = 'pending'", (callback.from_user.id,))
    app = cursor.fetchone()
    conn.close()

    if app:
        await callback.answer("У вас уже есть активная заявка на рассмотрении!", show_alert=True)
        return

    await state.set_state(ApplicationForm.nickname)
    await callback.message.answer("Шаг 1/4: Введите ваш игровой никнейм в Blood Strike:")
    await callback.answer()

@dp.message(ApplicationForm.nickname)
async def process_nickname(message: types.Message, state: FSMContext):
    await state.update_data(nickname=message.text)
    await state.set_state(ApplicationForm.game_id)
    await message.answer("Шаг 2/4: Введите ваш игровой ID (User ID):")

@dp.message(ApplicationForm.game_id)
async def process_game_id(message: types.Message, state: FSMContext):
    await state.update_data(game_id=message.text)
    await state.set_state(ApplicationForm.rank)
    await message.answer("Шаг 3/4: Укажите ваш текущий ранг (например, Легенда / Мастер):")

@dp.message(ApplicationForm.rank)
async def process_rank(message: types.Message, state: FSMContext):
    await state.update_data(rank=message.text)
    await state.set_state(ApplicationForm.kd)
    await message.answer("Шаг 4/4: Укажите ваш K/D (Убийства/Смерти):")

@dp.message(ApplicationForm.kd)
async def process_kd(message: types.Message, state: FSMContext):
    try:
        kd_val = float(message.text.replace(',', '.'))
    except ValueError:
        await message.answer("Пожалуйста, введите корректное числовое значение K/D (например, 2.5):")
        return

    user_data = await state.get_data()
    nickname = user_data['nickname']
    game_id = user_data['game_id']
    rank = user_data['rank']

    # Сохраняем заявку в БД
    conn = sqlite3.connect("clan_bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO applications (user_id, username, nickname, game_id, rank, kd)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (message.from_user.id, message.from_user.username or "без_юзернейма", nickname, game_id, rank, kd_val))
    app_id = cursor.lastrowid
    conn.commit()
    conn.close()

    await state.clear()
    await message.answer(
        "✅ Ваша заявка успешно отправлена на рассмотрение руководству клана FULL•SQUAD!",
        reply_markup=get_main_keyboard(message.from_user.id)
    )

    # Уведомление администраторам
    admin_markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_{app_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{app_id}")
        ]
    ])
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"📥 **Новая заявка в клан!**\n\n"
                f"👤 Игрок: {message.from_user.full_name} (@{message.from_user.username})\n"
                f"🎮 Ник: `{nickname}`\n"
                f"🆔 ID: `{game_id}`\n"
                f"🏆 Ранг: {rank}\n"
                f"📊 K/D: {kd_val}",
                reply_markup=admin_markup,
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"Не удалось отправить сообщение админу {admin_id}: {e}")

# Панель администратора
@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("У вас нет прав доступа!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "👑 **Панель управления кланом FULL•SQUAD**",
        reply_markup=get_admin_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "view_apps")
async def view_applications(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return

    conn = sqlite3.connect("clan_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, nickname, game_id, rank, kd FROM applications WHERE status = 'pending'")
    apps = cursor.fetchall()
    conn.close()

    if not apps:
        await callback.answer("Активных заявок пока нет.", show_alert=True)
        return

    for app in apps:
        app_id, nickname, game_id, rank, kd = app
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_{app_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{app_id}")
            ]
        ])
        await callback.message.answer(
            f"Заявка #{app_id}\nНик: {nickname}\nID: {game_id}\nРанг: {rank}\nK/D: {kd}",
            reply_markup=markup
        )
    await callback.answer()

@dp.callback_query(F.data.startswith("accept_"))
async def accept_application(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return

    app_id = int(callback.data.split("_")[1])

    conn = sqlite3.connect("clan_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, nickname, game_id FROM applications WHERE id = ?", (app_id,))
    app = cursor.fetchone()

    if app:
        user_id, username, nickname, game_id = app
        cursor.execute("UPDATE applications SET status = 'accepted' WHERE id = ?", (app_id,))
        cursor.execute("INSERT OR REPLACE INTO members (user_id, username, nickname, game_id) VALUES (?, ?, ?, ?)",
                       (user_id, username, nickname, game_id))
        conn.commit()

        try:
            await bot.send_message(user_id, "🎉 Поздравляем! Ваша заявка в клан FULL•SQUAD была одобрена!")
        except Exception:
            pass

        await callback.message.edit_text(f"✅ Заявка #{app_id} одобрена, игрок добавлен в соклановцы.")
    conn.close()
    await callback.answer()

@dp.callback_query(F.data.startswith("reject_"))
async def reject_application(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return

    app_id = int(callback.data.split("_")[1])

    conn = sqlite3.connect("clan_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM applications WHERE id = ?", (app_id,))
    app = cursor.fetchone()

    if app:
        user_id = app[0]
        cursor.execute("UPDATE applications SET status = 'rejected' WHERE id = ?", (app_id,))
        conn.commit()

        try:
            await bot.send_message(user_id, "❌ Ваша заявка в клан FULL•SQUAD была отклонена.")
        except Exception:
            pass

        await callback.message.edit_text(f"❌ Заявка #{app_id} отклонена.")
    conn.close()
    await callback.answer()

@dp.callback_query(F.data == "view_members")
async def view_members(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return

    conn = sqlite3.connect("clan_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT nickname, game_id, role FROM members")
    members = cursor.fetchall()
    conn.close()

    if not members:
        await callback.answer("Список соклановцев пуст.", show_alert=True)
        return

    text = "👥 **Состав клана FULL•SQUAD:**\n\n"
    for m in members:
        text += f"• {m[0]} (ID: {m[1]}) — {m[2]}\n"

    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="admin_panel")
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

# Веб-сервер для поддержки активности на Render
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

# Главная функция запуска
async def main():
    # Запуск встроенного веб-сервера для удовлетворения проверок портов Render
    await start_web_server()
    logging.info("Web server started successfully.")

    # Запуск бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
