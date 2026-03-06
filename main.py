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

# === НАСТРОЙКИ ===
BOT_TOKEN = "8504438550:AAH1kU2yVazCjTQXbQw2qkfupFXGNLhcTe4"
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

stats = {"orders": 0, "income": 0, "expenses": 0, "distance": 0.0, "lat": 53.195, "lon": 50.100, "last_order": 0}
zones = {"Центр": 0, "Аврора": 0, "Московское": 0, "Южный": 0}

class Location(BaseModel):
    lat: float
    lon: float

# --- МАТЕМАТИКА ---
def calc_dist(lat1, lon1, lat2, lon2):
    R = 6371.0
    dLat, dLon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dLat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon / 2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

# --- API ---
@app.get("/")
async def home(): return {"status": "online", "service": "DELIVERY LIVE"}

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
    zone = max(zones, key=zones.get)
    return {"zone": zone}

# --- БОТ ---
class Form(StatesGroup):
    waiting_for_order_price = State()
    waiting_for_expense_price = State()

menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📦 Добавить заказ"), KeyboardButton(text="💧 Добавить расход")],
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🔄 Новая смена")]
    ], resize_keyboard=True
)

# ПРИОРИТЕТНЫЙ ОБРАБОТЧИК КНОПОК
@dp.message(F.text.in_({"📊 Статистика", "🔄 Новая смена", "📦 Добавить заказ", "💧 Добавить расход"}))
async def handle_menu(msg: types.Message, state: FSMContext):
    await state.clear() # Мгновенно забываем про ожидание цифр
    if msg.text == "📊 Статистика":
        pure = stats["income"] - stats["expenses"]
        await msg.answer(f"📊 <b>Статистика:</b>\n📦 Заказов: {stats['orders']}\n📏 Км: {round(stats['distance'], 2)}\n💰 Доход: {stats['income']} ₽\n💵 Чистыми: {pure} ₽", parse_mode="HTML")
    elif msg.text == "🔄 Новая смена":
        for k in stats: stats[k] = 0.0 if isinstance(stats[k], float) else 0
        stats["lat"], stats["lon"] = 53.195, 50.100
        await msg.answer("✅ Смена обнулена! Удачи, Ренат! 🚀")
    elif msg.text == "📦 Добавить заказ":
        await msg.answer("Введите сумму заказа:")
        await state.set_state(Form.waiting_for_order_price)
    elif msg.text == "💧 Добавить расход":
        await msg.answer("Введите сумму расхода:")
        await state.set_state(Form.waiting_for_expense_price)

@dp.message(Command("start"))
async def start(msg: types.Message, state: FSMContext):
    await state.clear()
    await msg.answer("🚗 Панель DELIVERY LIVE активна!", reply_markup=menu_kb)

@dp.message(Form.waiting_for_order_price, F.text.isdigit())
async def proc_order(msg: types.Message, state: FSMContext):
    price = int(msg.text)
    stats["orders"] += 1
    stats["income"] += price
    await msg.answer(f"✅ Заказ на {price} ₽ добавлен!")
    await state.clear()

@dp.message(Form.waiting_for_expense_price, F.text.isdigit())
async def proc_exp(msg: types.Message, state: FSMContext):
    stats["expenses"] += int(msg.text)
    await msg.answer(f"💸 Расход {msg.text} ₽ учтен!")
    await state.clear()

@dp.message(Form.waiting_for_order_price)
@dp.message(Form.waiting_for_expense_price)
async def failed_digits(msg: types.Message):
    await msg.answer("❌ Введи число цифрами или выбери действие в меню.")

@app.on_event("startup")
async def on_startup(): asyncio.create_task(dp.start_polling(bot))

app.mount("/", StaticFiles(directory=".", html=True), name="static")
