import asyncio
import math
import random
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# === НАСТРОЙКИ БОТА ===
BOT_TOKEN = "8504438550:AAH1kU2yVazCjTQXbQw2qkfupFXGNLhcTe4"
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# === НАСТРОЙКИ СЕРВЕРА ===
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

stats = {"orders": 0, "income": 0, "expenses": 0, "distance": 0.0, "lat": 53.195, "lon": 50.100, "last_order": 0}
zones = {
    "Центр": {"lat": 53.195, "lon": 50.100, "orders": 0},
    "Аврора": {"lat": 53.210, "lon": 50.120, "orders": 0},
    "Московское шоссе": {"lat": 53.180, "lon": 50.090, "orders": 0},
    "Южный": {"lat": 53.170, "lon": 50.150, "orders": 0}
}

class Location(BaseModel):
    lat: float
    lon: float

def calc_dist(lat1, lon1, lat2, lon2):
    R = 6371.0
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon / 2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

# --- РОУТЫ СЕРВЕРА (Для оверлея и телефона) ---
@app.get("/stats")
def get_stats(): return stats

@app.post("/location")
def update_location(loc: Location):
    if stats["lat"] != 53.195: 
        dist = calc_dist(stats["lat"], stats["lon"], loc.lat, loc.lon)
        if dist < 1.0: stats["distance"] += dist
    stats["lat"], stats["lon"] = loc.lat, loc.lon
    return {"ok": True}

@app.get("/best_zone")
def best_zone():
    best = max(zones.keys(), key=lambda z: zones[z]["orders"])
    return {"zone": best}

# --- ЛОГИКА БОТА ---
class Form(StatesGroup):
    waiting_for_order_price = State()
    waiting_for_expense_price = State()

menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📦 Добавить заказ"), KeyboardButton(text="💧 Добавить расход")],
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🔄 Новая смена")]
    ], resize_keyboard=True
)

@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer("🚗 Облачная панель активна!", reply_markup=menu_kb)

@dp.message(F.text == "📦 Добавить заказ")
async def add_order(msg: types.Message, state: FSMContext):
    await msg.answer("Сумма заказа:")
    await state.set_state(Form.waiting_for_order_price)

@dp.message(Form.waiting_for_order_price)
async def proc_order(msg: types.Message, state: FSMContext):
    if not msg.text.isdigit(): return await msg.answer("Только цифры!")
    price = int(msg.text)
    
    # Меняем стату напрямую в памяти! Никаких задержек.
    stats["orders"] += 1
    stats["income"] += price
    stats["last_order"] = price
    zones[random.choice(list(zones.keys()))]["orders"] += 1
    
    await msg.answer(f"✅ Заказ на {price} ₽ добавлен!")
    await state.clear()

@dp.message(F.text == "💧 Добавить расход")
async def add_exp(msg: types.Message, state: FSMContext):
    await msg.answer("Сумма расхода:")
    await state.set_state(Form.waiting_for_expense_price)

@dp.message(Form.waiting_for_expense_price)
async def proc_exp(msg: types.Message, state: FSMContext):
    if not msg.text.isdigit(): return await msg.answer("Только цифры!")
    stats["expenses"] += int(msg.text)
    await msg.answer(f"💸 Расход {msg.text} ₽ учтен!")
    await state.clear()

@dp.message(F.text == "📊 Статистика")
async def show_stats(msg: types.Message):
    pure = stats["income"] - stats["expenses"]
    await msg.answer(
        f"📊 <b>Статистика:</b>\n📦 Заказов: <b>{stats['orders']}</b>\n"
        f"📏 Пройдено: <b>{round(stats['distance'], 2)} км</b>\n💰 Доход: <b>{stats['income']} ₽</b>\n"
        f"💵 ЧИСТЫМИ: <b>{pure} ₽</b>", parse_mode="HTML"
    )

@dp.message(F.text == "🔄 Новая смена")
async def reset_shift(msg: types.Message):
    stats["orders"] = stats["income"] = stats["expenses"] = stats["distance"] = stats["last_order"] = 0
    for z in zones: zones[z]["orders"] = 0
    await msg.answer("✅ Статистика сброшена! Погнали! 🚀")

# --- ЗАПУСК БОТА И РАЗДАЧА ФАЙЛОВ ---
@app.on_event("startup")
async def on_startup():
    asyncio.create_task(dp.start_polling(bot))

app.mount("/", StaticFiles(directory=".", html=True), name="static")