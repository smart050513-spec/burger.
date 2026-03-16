import sqlite3
import random
import time
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Вставь сюда токен своего бота
TOKEN = "PASTE_YOUR_TOKEN_HERE"

conn = sqlite3.connect("burger.db", check_same_thread=False)
cursor = conn.cursor()

# Таблицы
cursor.execute("""
CREATE TABLE IF NOT EXISTS chats(
chat_id INTEGER PRIMARY KEY,
weight INTEGER DEFAULT 0,
level INTEGER DEFAULT 1,
feeds INTEGER DEFAULT 0
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS players(
user_id INTEGER,
chat_id INTEGER,
name TEXT,
fed INTEGER DEFAULT 0,
weight INTEGER DEFAULT 0,
last_time INTEGER,
PRIMARY KEY(user_id,chat_id)
)
""")
conn.commit()

# Эволюции
EVOLUTIONS = [
    (5_000_000_000_000_000_000_000_000, "Пожиратель планет", 5_000_000_000_000_000_000_000_000),
    (50_000_000_000_000_000_000_000, "Пожиратель Лун", 2_500_000_000_000_000_000),
    (5_000_000_000_000_000_000, "Мировая угроза", 10_000_000_000_000_000),
    (500_000_000_000_000, "Пожиратель Островов", 10_000_000_000),
    (3_000_000_000_000, "Пожиратель Гор", 5_000_000),
    (10_000_000_000, "Пожиратель городов", 25_000),
    (100_000_000, "Угроза для города", 500),
    (10_000_000, "Пожиратель зданий", 100),
    (1_000_000, "Пожиратель сельских домов", 50),
    (100_000, "Сильнейшее существо", 25),
    (10_000, "Супер-Хищник", 15),
    (1_000, "Альфа Хищник", 7),
    (500, "Хищник", 5),
    (100, "Пожиратель людишек", 2),
    (10, "Микро Монстр", 1.5),
]

def get_evolution(weight):
    for req, name, multi in EVOLUTIONS:
        if weight >= req:
            return name, multi
    return "Обычный бургер", 1

def rare_burger_bonus():
    chance = random.randint(1, 100)
    if chance == 1:
        return random.choice([10,50,100,500,1000])
    return 1

def level_from_weight(weight):
    return weight // 1000 + 1

# Команды
async def eatburger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    user_id = user.id
    chat_id = chat.id
    name = user.first_name
    now = int(time.time())

    # 10 минут антиспам
    cursor.execute("SELECT last_time FROM players WHERE user_id=? AND chat_id=?", (user_id, chat_id))
    row = cursor.fetchone()
    if row and row[0] and now - row[0] < 600:
        remain = 600 - (now - row[0])
        minutes = remain // 60
        await update.message.reply_text(f"⏳ {name}, ты уже кормил Бургера! Подожди ещё {minutes} минут.")
        return

    base_gain = random.randint(1,30)
    cursor.execute("INSERT OR IGNORE INTO chats(chat_id,weight) VALUES(?,0)", (chat_id,))
    cursor.execute("SELECT weight FROM chats WHERE chat_id=?", (chat_id,))
    row = cursor.fetchone()
    current_weight = row[0] if row else 0

    evo_name, evo_multiplier = get_evolution(current_weight)
    rare_multiplier = rare_burger_bonus()
    gain = int(base_gain * evo_multiplier * rare_multiplier)

    cursor.execute("UPDATE chats SET weight=weight+?, feeds=feeds+1 WHERE chat_id=?", (gain, chat_id))
    cursor.execute("""
        INSERT INTO players(user_id,chat_id,name,fed,weight,last_time)
        VALUES(?,?,?,?,?,?)
        ON CONFLICT(user_id,chat_id) DO UPDATE SET
        fed=fed+1,
        weight=weight+?,
        last_time=?
    """, (user_id,chat_id,name,1,gain,now,gain,now))
    conn.commit()

    cursor.execute("SELECT weight,level FROM chats WHERE chat_id=?", (chat_id,))
    weight, level = cursor.fetchone()
    new_level = level_from_weight(weight)

    rare_text = f"\n✨ РЕДКИЙ БУРГЕР! x{rare_multiplier} бонус!" if rare_multiplier>1 else ""
    message = (
        f"🍔 {name} накормил Бургера!\n\n"
        f"⚖ Базовый вес: {base_gain} кг\n"
        f"🔥 Множитель эволюции: x{evo_multiplier}{rare_text}\n\n"
        f"+{gain} кг\n\n"
        f"🐷 Вес: {weight} кг\n"
        f"⭐ Уровень: {new_level}\n"
        f"🧬 Эволюция: {evo_name}"
    )
    await update.message.reply_text(message)

    if new_level > level:
        cursor.execute("UPDATE chats SET level=? WHERE chat_id=?", (new_level, chat_id))
        conn.commit()
        await update.message.reply_text(f"🎉 Бургер вырос до уровня {new_level}!")

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    cursor.execute("SELECT weight FROM chats WHERE chat_id=?", (chat_id,))
    row = cursor.fetchone()
    weight = row[0] if row else 0
    await update.message.reply_text(f"🏆 Общий вес бургера:\n\n🍔 {weight} кг")

async def players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    cursor.execute("SELECT name,fed FROM players WHERE chat_id=? ORDER BY fed DESC LIMIT 10", (chat_id,))
    rows = cursor.fetchall()
    if not rows:
        await update.message.reply_text("Пока никто не кормил бургер.")
        return
    text = "🏆 Топ игроков чата:\n\n"
    for i,(name,fed) in enumerate(rows,start=1):
        text+=f"{i}. {name} — {fed} 🍔\n"
    await update.message.reply_text(text)

async def globalplayerskg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT name,SUM(weight) FROM players GROUP BY user_id ORDER BY SUM(weight) DESC LIMIT 10")
    rows = cursor.fetchall()
    text="🌍 Топ игроков по кг:\n\n"
    for i,(name,kg) in enumerate(rows,start=1):
        text+=f"{i}. {name} — {kg} кг\n"
    await update.message.reply_text(text)

async def globalplayersfed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT name,SUM(fed) FROM players GROUP BY user_id ORDER BY SUM(fed) DESC LIMIT 10")
    rows = cursor.fetchall()
    text="🌍 Топ игроков по кормлениям:\n\n"
    for i,(name,fed) in enumerate(rows,start=1):
        text+=f"{i}. {name} — {fed} 🍔\n"
    await update.message.reply_text(text)

async def globalchatskg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT chat_id,weight FROM chats ORDER BY weight DESC LIMIT 10")
    rows = cursor.fetchall()
    text="🌍 Топ чатов по кг:\n\n"
    for i,(chat,kg) in enumerate(rows,start=1):
        text+=f"{i}. Чат {chat} — {kg} кг\n"
    await update.message.reply_text(text)

async def globalchatsfed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT chat_id,feeds FROM chats ORDER BY feeds DESC LIMIT 10")
    rows = cursor.fetchall()
    text="🌍 Топ чатов по кормлениям:\n\n"
    for i,(chat,fed) in enumerate(rows,start=1):
        text+=f"{i}. Чат {chat} — {fed} 🍔\n"
    await update.message.reply_text(text)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🍔 Бургер Пожиратель!\n\n"
        "Команды:\n"
        "/eatburger — накормить бургером\n"
        "/top — вес бургера\n"
        "/players — топ игроков чата\n\n"
        "🌍 Глобальные рейтинги:\n"
        "/globalplayerskg\n"
        "/globalplayersfed\n"
        "/globalchatskg\n"
        "/globalchatsfed"
    )

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("eatburger", eatburger))
app.add_handler(CommandHandler("top", top))
app.add_handler(CommandHandler("players", players))
app.add_handler(CommandHandler("globalplayerskg", globalplayerskg))
app.add_handler(CommandHandler("globalplayersfed", globalplayersfed))
app.add_handler(CommandHandler("globalchatskg", globalchatskg))
app.add_handler(CommandHandler("globalchatsfed", globalchatsfed))

print("🍔 Burger Bot запущен!")
app.run_polling()
