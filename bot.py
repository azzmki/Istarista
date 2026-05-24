import logging
import sqlite3
import asyncio
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, LabeledPrice
from aiohttp import web

# Konfiguratsiya
BOT_TOKEN = "8949788569:AAGNahSae9Hyc_CHYnqE1qFd-xW84YDO_y8"
CLICK_TOKEN = "3828182:TEST:1234"  
ADMIN_ID = 7800449398

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# DB Sozlamalari
conn = sqlite3.connect("stars_bot.db")
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, uzs_balance REAL DEFAULT 0, stars_balance REAL DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('card_number', '8600 0000 0000 0000')")
conn.commit()

class BotStates(StatesGroup):
    input_topup_amount = State()      
    select_stars_amount = State()     
    input_target_username = State()   
    input_support_msg = State()       
    admin_change_card = State()       

def main_menu():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⭐ Stars olish"), KeyboardButton(text="💰 Balans")],[KeyboardButton(text="🎁 Gift"), KeyboardButton(text="✍️ Murojaat")]], resize_keyboard=True)

def stars_amount_menu():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="50 Stars", callback_data="buy_stars_50"), InlineKeyboardButton(text="100 Stars", callback_data="buy_stars_100")],[InlineKeyboardButton(text="150 Stars", callback_data="buy_stars_150"), InlineKeyboardButton(text="200 Stars", callback_data="buy_stars_200")]])

def gift_menu():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🧸 Ayiqcha (3,500 UZS)", callback_data="gift_ayiqcha_3500")],[InlineKeyboardButton(text="🌹 Atirgul (5,000 UZS)", callback_data="gift_atirgul_5000")],[InlineKeyboardButton(text="💎 Olmos (15,000 UZS)", callback_data="gift_olmos_15000")]])

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    welcome_text = "👋 Salom! Stars botiga xush kelibsiz."
    if user_id == ADMIN_ID: welcome_text += "\n\n👨‍✈️ Admin! Panel uchun /admin buyrug'ini bosing."
    await message.answer(welcome_text, reply_markup=main_menu())

@dp.message(F.text == "💰 Balans")
async def balance_cmd(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT uzs_balance, stars_balance FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    uzs, stars = res if res else (0, 0)
    text = f"💳 **Sizning hisobingiz:**\n\n💵 Balans: {uzs:,.0f} UZS\n⭐ Stars: {stars} Stars"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Hisobni to'ldirish (Click)", callback_data="topup_account")]])
    await message.answer(text, parse_mode="Markdown", reply_markup=kb)

@dp.callback_query(F.data == "topup_account")
async def topup_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("💸 To'ldirmoqchi bo'lgan summani kiriting (min: 2,000 UZS):")
    await state.set_state(BotStates.input_topup_amount)
    await callback.answer()

@dp.message(BotStates.input_topup_amount)
async def process_topup_amount(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text)
        if amount < 2000:
            await message.answer("❌ Minimal to'ldirish summasi 2,000 UZS.")
            return
        await state.clear()
        prices = [LabeledPrice(label="Balansni to'ldirish", amount=amount * 100)]
        await bot.send_invoice(chat_id=message.chat.id, title="Balansni to'ldirish", description=f"Bot balansingizni {amount:,} so'mga to'ldirish", provider_token=CLICK_TOKEN, currency="UZS", prices=prices, payload=f"topup_{message.from_user.id}_{amount}")
    except ValueError:
        await message.answer("🔢 Iltimos, faqat raqam kiriting:")

@dp.pre_checkout_query()
async def checkout_process(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment_handler(message: types.Message):
    payload = message.successful_payment.invoice_payload
    _, user_id, amount = payload.split("_")
    amount, user_id = int(amount), int(user_id)
    calculated_stars = amount // 5500
    cursor.execute("UPDATE users SET uzs_balance = uzs_balance + ?, stars_balance = stars_balance + ? WHERE user_id = ?", (amount, calculated_stars, user_id))
    conn.commit()
    await message.answer(f"✅ To'lov qabul qilindi!\n💰 +{amount:,} UZS\n⭐ +{calculated_stars} Stars!", reply_markup=main_menu())

@dp.message(F.text == "⭐ Stars olish")
async def get_stars_cmd(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT stars_balance FROM users WHERE user_id = ?", (user_id,))
    stars = cursor.fetchone()[0]
    if stars < 50:
        await message.answer(f"❌ Minimal 50 Stars bo'lishi kerak. Sizda: {stars} Stars bor.")
        return
    await message.answer("Qancha Stars yechib olmoqchisiz?", reply_markup=stars_amount_menu())

@dp.callback_query(F.data.startswith("buy_stars_"))
async def process_stars_selection(callback: types.CallbackQuery, state: FSMContext):
    chosen_stars = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    cursor.execute("SELECT stars_balance FROM users WHERE user_id = ?", (user_id,))
    if cursor.fetchone()[0] < chosen_stars:
        await callback.answer("❌ Mablag' yetarli emas!", show_alert=True)
        return
    await state.update_data(chosen_stars=chosen_stars)
    await callback.message.answer("📝 Telegram username kiriting (@username):")
    await state.set_state(BotStates.input_target_username)
    await callback.answer()

@dp.message(BotStates.input_target_username)
async def confirm_stars_transfer(message: types.Message, state: FSMContext):
    target_username = message.text.strip()
    if not target_username.startswith("@"):
        await message.answer("❌ Username xato. @ bilan boshlansin:")
        return
    data = await state.get_data()
    chosen_stars = data['chosen_stars']
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"confirm_send_{chosen_stars}_{target_username}")],[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_transfer")]])
    await message.answer(f"⚠️ **{chosen_stars} Stars** -> **{target_username}** profiliga o'tkazilsinmi?", parse_mode="Markdown", reply_markup=kb)
    await state.clear()

@dp.callback_query(F.data.startswith("confirm_send_"))
async def finalize_stars_transfer(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    chosen_stars, target_user = int(parts[2]), parts[3]
    user_id = callback.from_user.id
    cursor.execute("UPDATE users SET stars_balance = stars_balance - ? WHERE user_id = ?", (chosen_stars, user_id))
    conn.commit()
    await callback.message.edit_text(f"🚀 So'rov qabul qilindi!")
    await bot.send_message(ADMIN_ID, f"🔔 **Stars Buyurtmasi!**\nID: `{user_id}`\nStars: {chosen_stars}\nKimga: {target_user}")

@dp.callback_query(F.data == "cancel_transfer")
async def cancel_transfer(callback: types.CallbackQuery):
    await callback.message.edit_text("❌ Bekor qilindi.", reply_markup=main_menu())

@dp.message(F.text == "🎁 Gift")
async def gift_cmd(message: types.Message):
    await message.answer("🎁 Telegram sovg'alarini tanlang:", reply_markup=gift_menu())

@dp.callback_query(F.data.startswith("gift_"))
async def process_gift_purchase(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    gift_name, gift_price = parts[1], int(parts[2])
    user_id = callback.from_user.id
    cursor.execute("SELECT uzs_balance FROM users WHERE user_id = ?", (user_id,))
    if cursor.fetchone()[0] < gift_price:
        await callback.answer("❌ Mablag' yetarli emas!", show_alert=True)
        return
    cursor.execute("UPDATE users SET uzs_balance = uzs_balance - ? WHERE user_id = ?", (gift_price, user_id))
    conn.commit()
    await callback.message.answer(f"🎉 {gift_name.capitalize()} sotib olindi!")
    await bot.send_message(ADMIN_ID, f"🎁 **Gift Xarid qilindi!**\nID: `{user_id}`\nNomi: {gift_name}")
    await callback.answer()

@dp.message(F.text == "✍️ Murojaat")
async def support_cmd(message: types.Message, state: FSMContext):
    await message.answer("✍️ Taklif yoki shikoyatingizni yozing:")
    await state.set_state(BotStates.input_support_msg)

@dp.message(BotStates.input_support_msg)
async def process_support_msg(message: types.Message, state: FSMContext):
    await bot.send_message(ADMIN_ID, f"📩 **Murojaat!**\nID: `{message.from_user.id}`\nMatn: {message.text}")
    await state.clear()
    await message.answer("✅ Adminga yetkazildi!")

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    cursor.execute("SELECT COUNT(user_id) FROM users")
    total = cursor.fetchone()[0]
    await message.answer(f"👨‍✈️ **Admin Panel**\n📊 Jami userlar: {total} ta")

# --- SERVER QISMI (RENDER UCHUN) ---
async def handle(request):
    return web.Response(text="Bot is Live!")

async def main():
    import os
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render uchun portni dinamik olish (8080 o'rniga)
    port = int(os.environ.get("PORT", 10000)) 
    site = web.TCPSite(runner, "0.0.0.0", port)
    
    await site.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())