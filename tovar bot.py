import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums.parse_mode import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest
import aiosqlite
import datetime

# Bot tokeningizni kiriting
TOKEN = "token"

# Bot ishga tushgan vaqtni saqlash uchun global o'zgaruvchi
start_time = None

# Qidiruv holatlari uchun klass
class SearchStates(StatesGroup):
    waiting_for_query = State()

dp = Dispatcher()

# Ma'lumotlar bazasi fayli
DB_FILE = 'documents.db'

async def init_db():
    """Ma'lumotlar bazasini yaratish yoki ulanganish."""
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                file_id TEXT PRIMARY KEY,
                file_name TEXT,
                date_sent TEXT,
                message_id INTEGER,
                chat_id INTEGER,
                caption TEXT
            )
        ''')
        await db.commit()

# Bot buyruqlarini oʻrnatish
async def set_commands(bot: Bot):
    commands = [
        types.BotCommand(command="izlash", description="Hujjatni izlash")
    ]
    await bot.set_my_commands(commands)

# /start buyrug'ini qabul qilish
@dp.message(F.text == '/start')
async def start_command(message: types.Message):
    global start_time
    formatted_start_time = start_time.strftime("%Y-yil %m-%d-kun, soat %H:%M:%S")
    response = (
        f"Salom, **{message.from_user.full_name}**!\n\n"
        f"Men hujjatlarni saqlovchi va qidiruvchi botman.\n"
        f"Menga **PDF** fayllarni izoh bilan yuboring.\n"
        f"Hujjatni qidirish uchun **`/izlash@hujjat_izla_bot`** buyrug'ini bering.\n\n"
        f"Bot **{formatted_start_time}** dan boshlab ishlamoqda."
    )
    await message.reply(response)

# Hujjatlarni qabul qilish va saqlash
@dp.message(F.document)
async def handle_document(message: types.Message):
    if message.document and message.document.file_name.lower().endswith('.pdf'):
        file_id = message.document.file_id
        file_name = message.document.file_name
        date_sent = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message_id = message.message_id
        chat_id = message.chat.id
        caption = message.caption if message.caption else ""
        async with aiosqlite.connect(DB_FILE) as db:
            try:
                await db.execute(
                    "INSERT INTO documents (file_id, file_name, date_sent, message_id, chat_id, caption) VALUES (?, ?, ?, ?, ?, ?)",
                    (file_id, file_name, date_sent, message_id, chat_id, caption)
                )
                await db.commit()
                print(f"PDF hujjat saqlandi: {file_name}")
            except aiosqlite.IntegrityError:
                print(f"Hujjat allaqachon mavjud: {file_name}")

# /izlash@hujjat_izla_bot buyrug'ini qabul qilish
@dp.message(F.text == '/izlash@hujjat_izla_bot')
async def start_search(message: types.Message, state: FSMContext):
    await state.set_state(SearchStates.waiting_for_query)
    await message.reply("Hujjat nomi yoki uning bir qismini kiriting 📑.")

# Hujjat nomini qabul qilish va qidirish
@dp.message(SearchStates.waiting_for_query)
async def process_search_query(message: types.Message, state: FSMContext):
    query = message.text.strip().lower()
    if not query:
        await message.reply("Qidirish uchun matn kiritilmadi. Iltimos, qaytadan urinib ko'ring.")
        await state.clear()
        return

    one_week_ago = datetime.datetime.now() - datetime.timedelta(days=7)
    one_week_ago_str = one_week_ago.strftime("%Y-%m-%d %H:%M:%S")

    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(
            "SELECT file_id, file_name, message_id, chat_id, caption FROM documents WHERE (file_name LIKE ? OR caption LIKE ?) AND date_sent >= ?",
            ('%' + query + '%', '%' + query + '%', one_week_ago_str)
        )
        results = await cursor.fetchall()

    if results:
        await message.reply(f"Topildi ✅, **'{query}'** so'zini o'z ichiga olgan hujjatlar (so'nggi 7 kun ichida).")

        for file_id, file_name, reply_id, chat_id, caption in results:
            text_to_send = f"**{file_name}**"
            if caption:
                text_to_send += f"\n\n**Hujjatdagi kamchilik 📑 ❗️**: {caption}"

            try:
                await message.bot.send_message(
                    chat_id=chat_id,
                    text=text_to_send,
                    reply_to_message_id=reply_id,
                    parse_mode=ParseMode.MARKDOWN
                )
            except TelegramBadRequest as e:
                print(f"Hujjatga javob yuborishda xato: {e}")

    else:
        await message.reply(f"'{query}' bo'yicha so'nggi 7 kun ichida hujjat topilmadi.")

    await state.clear()

async def main():
    global start_time
    start_time = datetime.datetime.now()
    await init_db()
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
    await set_commands(bot) # Buyruqlarni oʻrnatish funksiyasi chaqirildi
    await dp.start_polling(bot)

if __name__ == "__main__":

    asyncio.run(main())
