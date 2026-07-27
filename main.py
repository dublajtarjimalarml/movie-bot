import os
import sqlite3
from threading import Thread
from flask import Flask
import telebot
from telebot import types

# --- SOZLAMALAR ---
BOT_TOKEN = "8895763314:AAGk8HVxRRiSMseyvh6dx672wvDfaZYklzY"
ADMIN_ID = 5736752273  # O'zingizning numeric Telegram ID'ingiz
MOVIE_CHANNEL_ID = -1004374661522  # Baza kanali ID'si
REQUIRED_CHANNEL_ID = -1003944114251  # Obuna kanali ID'si

bot = telebot.TeleBot(BOT_TOKEN)

# --- MA'LUMOTLAR BAZASI ---
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            message_id INTEGER
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- OBUNANI TEKSHIRISH ---
def check_subscription(user_id):
    try:
        member = bot.get_chat_member(REQUIRED_CHANNEL_ID, user_id)
        return member.status in ['creator', 'administrator', 'member']
    except Exception:
        return True

# --- START BUYRUG'I ---
@bot.message_handler(commands=['start'])
def start_cmd(message):
    if not check_subscription(message.from_user.id):
        bot.reply_to(message, "❌ Botdan foydalanish uchun avval kanalga obuna bo'ling!")
        return
    bot.reply_to(message, "Assalomu alaykum! Kinoni ko'rish uchun **kino kodini** (masalan: 1) yuboring.", parse_mode="Markdown")

# --- ADMIN BUYRUQLARI ---

# 1. Bittalab qo'shish: /add [kino_kodi] [message_id]
@bot.message_handler(commands=['add'])
def add_movie(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        args = message.text.split()
        if len(args) != 3:
            bot.reply_to(message, "❌ Namuna: `/add 1 122`", parse_mode="Markdown")
            return
        
        movie_code = args[1]
        msg_id = int(args[2])

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO movies (code, message_id) VALUES (?, ?)", (movie_code, msg_id))
        conn.commit()
        conn.close()

        bot.reply_to(message, f"✅ Saqlandi!\nKino kodi: `{movie_code}`\nMessage ID: `{msg_id}`", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}")

# 2. Ko'plab qismlarni birda qo'shish: /add_range [kino_kodi] [boshlang'ich_id] [oxirgi_id]
@bot.message_handler(commands=['add_range'])
def add_range_movie(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        args = message.text.split()
        if len(args) != 4:
            bot.reply_to(message, "❌ Namuna: `/add_range 1 122 130`", parse_mode="Markdown")
            return

        movie_code = args[1]
        start_id = int(args[2])
        end_id = int(args[3])

        if start_id > end_id:
            bot.reply_to(message, "❌ Boshlang'ich ID oxirgisidan katta bo'lishi mumkin emas!")
            return

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        added_count = 0
        for msg_id in range(start_id, end_id + 1):
            cursor.execute("INSERT INTO movies (code, message_id) VALUES (?, ?)", (movie_code, msg_id))
            added_count += 1

        conn.commit()
        conn.close()

        bot.reply_to(message, f"✅ Muvaffaqiyatli saqlandi!\n\n🎬 **Kino kodi:** `{movie_code}`\n📦 **Qo'shilgan qismlar:** {added_count} ta ({start_id} dan {end_id} gacha)")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}")

# 3. O'chirish: /del [kino_kodi]
@bot.message_handler(commands=['del'])
def del_movie(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        args = message.text.split()
        if len(args) != 2:
            bot.reply_to(message, "❌ Namuna: `/del 1`", parse_mode="Markdown")
            return

        movie_code = args[1]
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM movies WHERE code = ?", (movie_code,))
        conn.commit()
        conn.close()

        bot.reply_to(message, f"🗑 Kodi `{movie_code}` bo'lgan barcha qismlar o'chirildi!", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}")

# --- FOYDALANUVCHIDAN RAQAM KELGANDA KINONI YUBORISH ---
@bot.message_handler(func=lambda message: True)
def get_movie(message):
    if not check_subscription(message.from_user.id):
        bot.reply_to(message, "❌ Botdan foydalanish uchun avval kanalga obuna bo'ling!")
        return

    code = message.text.strip()
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT message_id FROM movies WHERE code = ?", (code,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        bot.reply_to(message, "Bunday raqamli kino yoki drama topilmadi. Qaytadan tekshirib ko'ring.")
        return

    ids_list = [r[0] for r in rows]

    # Agar bitta qism bo'lsa - to'g'ridan-to'g'ri yuboradi
    if len(ids_list) == 1:
        try:
            bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=MOVIE_CHANNEL_ID,
                message_id=int(ids_list[0])
            )
        except Exception:
            bot.send_message(message.chat.id, "Xatolik yuz berdi. Bot baza kanalida Admin ekanligini tekshiring.")
    else:
        # Agar ko'p qismli drama bo'lsa - tugmalar orqali chiqarib beradi
        markup = types.InlineKeyboardMarkup(row_width=3)
        buttons = []
        for idx, msg_id in enumerate(ids_list, start=1):
            buttons.append(
                types.InlineKeyboardButton(
                    text=f"{idx}-qism 🎬", callback_data=f"ep_{msg_id}"
                )
            )
        markup.add(*buttons)

        bot.send_message(
            message.chat.id,
            f"🎬 **{code}**-sonli Drama qismlari:\n\nKo'rmoqchi bo'lgan qismingizni tanlang 👇",
            parse_mode="Markdown",
            reply_markup=markup
        )

# --- TUGMA BOSILGANDA QISMNI YUBORISH ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("ep_"))
def send_episode(call):
    msg_id = call.data.split("_")[1]
    try:
        bot.copy_message(
            chat_id=call.message.chat.id,
            from_chat_id=MOVIE_CHANNEL_ID,
            message_id=int(msg_id)
        )
    except Exception:
        bot.send_message(call.message.chat.id, "Xatolik yuz berdi. Baza kanalini tekshiring.")

# --- FLASK WEB SERVER VA KEEP-ALIVE ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- ISHGA TUSHIRISH ---
if __name__ == "__main__":
    keep_alive()
    print("Bot ishga tushdi...")
    bot.infinity_polling()
import os
import sqlite3
from threading import Thread
from flask import Flask
import telebot
from telebot import types

# --- SOZLAMALAR ---
BOT_TOKEN = "YANGI_BOT_TOKENINGIZNI_YOZING"
ADMIN_ID = 123456789  # O'zingizning numeric Telegram ID'ingiz
MOVIE_CHANNEL_ID = -1004374661522  # Baza kanali ID'si
REQUIRED_CHANNEL_ID = -1003944114251  # Obuna kanali ID'si

bot = telebot.TeleBot(BOT_TOKEN)

# --- MA'LUMOTLAR BAZASI ---
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            message_id INTEGER
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- OBUNANI TEKSHIRISH ---
def check_subscription(user_id):
    try:
        member = bot.get_chat_member(REQUIRED_CHANNEL_ID, user_id)
        return member.status in ['creator', 'administrator', 'member']
    except Exception:
        return True

# --- START BUYRUG'I ---
@bot.message_handler(commands=['start'])
def start_cmd(message):
    if not check_subscription(message.from_user.id):
        bot.reply_to(message, "❌ Botdan foydalanish uchun avval kanalga obuna bo'ling!")
        return
    bot.reply_to(message, "Assalomu alaykum! Kinoni ko'rish uchun **kino kodini** (masalan: 1) yuboring.", parse_mode="Markdown")

# --- ADMIN BUYRUQLARI ---

# 1. Bittalab qo'shish: /add [kino_kodi] [message_id]
@bot.message_handler(commands=['add'])
def add_movie(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        args = message.text.split()
        if len(args) != 3:
            bot.reply_to(message, "❌ Namuna: `/add 1 122`", parse_mode="Markdown")
            return
        
        movie_code = args[1]
        msg_id = int(args[2])

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO movies (code, message_id) VALUES (?, ?)", (movie_code, msg_id))
        conn.commit()
        conn.close()

        bot.reply_to(message, f"✅ Saqlandi!\nKino kodi: `{movie_code}`\nMessage ID: `{msg_id}`", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {e}")

# 2. Ko'plab qismlarni birda qo'shish: /add_range [kino_kodi] [boshlang'ich_id] [oxirgi_id]
@bot.message_handler(commands=['add_range'])
def add_range_movie(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        args = message.text.split()
        if len(args) != 4:
            bot.reply_to(message, "❌ Namuna: `/add_range 1 122 130`", parse_mode="Markdown")
            return

        movie_code = args[1]
        start_id = int(args[2])
        end_id = int(args[3])

        if start_id > end_id:
            bot.reply_to(message, "❌ Boshlang'ich ID oxirgisidan katta bo'lishi mumkin emas!")
            return

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        added_count = 0
        for msg_id in range(start_id, end_id + 1):
            cursor.execute("INSERT INTO movies (code, message_id) VALUES (?, ?)", (movie_code, msg_id))
            added_count += 1

        conn.commit()
        conn.close()


