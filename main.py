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
zones = {
    "Центр": {"lat": 53.195, "lon": 50.100, "orders": 0},
    "Аврора": {"lat": 53.210, "lon": 50.120, "orders": 0},
    "Московское шоссе": {"lat": 53.180, "lon": 50.090, "orders": 0},
    "Южный": {"lat": 53.170, "lon": 50.150, "orders": 0}
}

class Location(BaseModel):
    lat: float
    lon: float

# --- МАТЕМАТИКА ---
def calc_dist(lat1, lon1, lat2, lon2):
    R = 6371.0
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    # Формула гаверсинуса для расчета расстояния
    a = math.sin(dLat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon / 2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

# --- API СЕРВЕРА ---
@app.get("/")
async def home():
    return {"status": "online", "owner": "RENATKO", "message": "BMW M5 F90 is on the map!"}

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
async def start(msg: types.Message, state: FSMContext):
    await state.clear()
    await msg.answer("🚗 Панель управления стримом Самары активна!", reply_markup=menu_kb)

# Сброс состояния, если нажата любая кнопка вместо ввода цифр
@dp.message(F.text.in_({"📊 Статистика", "🔄 Новая смена", "📦 Добавить заказ", "💧 Добавить расход"}))
async def menu_interruption(msg: types.Message, state: FSMContext):
    await state.clear()
    if msg.text == "📊 Статистика":
        await show_stats(msg, state)
    elif msg.text == "🔄 Новая смена":
        await reset_shift(msg, state)
    elif msg.text == "📦 Добавить заказ":
        await add_order(msg, state)
    elif msg.text == "💧 Добавить расход":
        await add_exp(msg, state)

@dp.message(F.text == "📦 Добавить заказ")
async def add_order(msg: types.Message, state: FSMContext):
    await msg.answer("Введите сумму заказа (только цифры):")
    await state.set_state(Form.waiting_for_order_price)

@dp.message(Form.waiting_for_order_price, F.text.isdigit())
async def proc_order(msg: types.Message, state: FSMContext):
    price = int(msg.text)
    stats["orders"] += 1
    stats["income"] += price
    stats["last_order"] = price
    zones[random.choice(list(zones.keys()))]["orders"] += 1
    await msg.answer(f"✅ Заказ на {price} ₽ добавлен!")
    await state.clear()

@dp.message(F.text == "💧 Добавить расход")
async def add_exp(msg: types.Message, state: FSMContext):
    await msg.answer("Введите сумму расхода (только цифры):")
    await state.set_state(Form.waiting_for_expense_price)

@dp.message(Form.waiting_for_expense_price, F.text.isdigit())
async def proc_exp(msg: types.Message, state: FSMContext):
    stats["expenses"] += int(msg.text)
    await msg.answer(f"💸 Расход {msg.text} ₽ учтен!")
    await state.clear()

@dp.message(F.text == "📊 Статистика")
async def show_stats(msg: types.Message, state: FSMContext):
    await state.clear()
    pure = stats["income"] - stats["expenses"]
    await msg.answer(
        f"📊 <b>Статистика:</b>\n📦 Заказов: <b>{stats['orders']}</b>\n"
        f"📏 Пройдено: <b>{round(stats['distance'], 2)} км</b>\n💰 Доход: <b>{stats['income']} ₽</b>\n"
        f"💵 ЧИСТЫМИ: <b>{pure} ₽</b>", parse_mode="HTML"
    )

@dp.message(F.text == "🔄 Новая смена")
async def reset_shift(msg: types.Message, state: FSMContext):
    await state.clear()
    stats["orders"] = stats["income"] = stats["expenses"] = stats["distance"] = stats["last_order"] = 0
    for z in zones: zones[z]["orders"] = 0
    await msg.answer("✅ Смена обнулена! Удачи на дорогах Самары! 🚀")

@dp.message(Form.waiting_for_order_price)
@dp.message(Form.waiting_for_expense_price)
async def failed_digits(msg: types.Message):
    await msg.answer("❌ Нужно ввести число. Попробуй еще раз или нажми другую кнопку.")

# --- ЗАПУСК ---
@app.on_event("startup")
async def on_startup():
    asyncio.create_task(dp.start_polling(bot))

app.mount("/", StaticFiles(directory=".", html=True), name="static")
