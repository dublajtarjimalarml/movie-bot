from flask import Flask
from threading import Thread
import telebot
import psycopg2
from psycopg2.extras import RealDictCursor

# --- SOZLAMALAR ---
BOT_TOKEN = "8895763314:AAGXgZI3TzvU2O7dDPjveKbUZ6FAEj_NCyA"
# Supabase parolingizni moslang:
DB_URL = "postgresql://postgres:minlienferuza@db.traxqticwscihsnargez.supabase.co:5432/postgres"

ADMIN_ID = 5736752273  # Sizning Telegram ID ingiz

# Kanallar ro'yxati (ID raqami va taklif havolasi)
CHANNELS = [
    {"id": -1003944114251, "link": "https://t.me/+YSnX_ktYFEoxNzAy"}, # Shaxsiy kanal
    {"id": "@MLdublaj", "link": "https://t.me/MLdublaj"}              # Ommaviy kanal
]

bot = telebot.TeleBot(BOT_TOKEN)

# --- POSTGRESQL DATABASE FUNKSIYALARI ---
def get_db_connection():
    return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS movies (
            code INTEGER PRIMARY KEY,
            file_id TEXT NOT NULL,
            caption TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

init_db()

def add_user(user_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"User add error: {e}")

# --- KANALGA A'ZOLIKNI TEKSHIRISH ---
def check_sub(user_id):
    for ch in CHANNELS:
        try:
            member = bot.get_chat_member(ch["id"], user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception as e:
            print(f"Check sub error: {e}")
            return False
    return True

def sub_markup():
    markup = telebot.types.InlineKeyboardMarkup()
    for i, ch in enumerate(CHANNELS, 1):
        markup.add(telebot.types.InlineKeyboardButton(text=f"{i}-kanalga a'zo bo'lish ➕", url=ch["link"]))
    markup.add(telebot.types.InlineKeyboardButton(text="Tekshirish 🔄", callback_data="check"))
    return markup

# --- HANDLERLAR ---
@bot.message_handler(commands=['start'])
def start_cmd(message):
    add_user(message.from_user.id)
    if not check_sub(message.from_user.id):
        bot.send_message(
            message.chat.id, 
            "Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:", 
            reply_markup=sub_markup()
        )
        return
    bot.send_message(message.chat.id, "Xush kelibsiz! Kino kodini yuboring:")

@bot.callback_query_handler(func=lambda call: call.data == "check")
def check_callback(call):
    if check_sub(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Rahmat! Endi kino kodini yuborishingiz mumkin.")
    else:
        bot.answer_callback_query(call.id, "Barcha kanallarga a'zo bo'lmadingiz!", show_alert=True)

# --- ADMIN BUYRUQLARI ---
@bot.message_handler(commands=['stat'])
def stat_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    u_count = cur.fetchone()['count']
    cur.execute("SELECT COUNT(*) FROM movies")
    m_count = cur.fetchone()['count']
    cur.close()
    conn.close()
    bot.send_message(message.chat.id, f"📊 Statistika:\n\nFoydalanuvchilar: {u_count}\nKinolar: {m_count}")

@bot.message_handler(commands=['add_range'])
def add_range_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    bot.send_message(message.chat.id, "Kinolarni birma-bir video shaklida yuboring. Bot ularga avtomatik ravishda tartib kodi biriktirib boradi.")

@bot.message_handler(commands=['del_range'])
def del_range_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split()
        start_code = int(parts[1])
        end_code = int(parts[2])
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM movies WHERE code >= %s AND code <= %s", (start_code, end_code))
        conn.commit()
        cur.close()
        conn.close()
        bot.send_message(message.chat.id, f"✅ {start_code}-{end_code} oralig'idagi kinolar o'chirildi.")
    except Exception:
        bot.send_message(message.chat.id, "Xatolik! Buyruq formati: /del_range 10 20")

# --- KINO KODINI QIDIRISH ---
@bot.message_handler(func=lambda m: m.text and m.text.isdigit())
def get_movie(message):
    if not check_sub(message.from_user.id):
        bot.send_message(message.chat.id, "Kino ko'rish uchun avval kanallarga a'zo bo'ling:", reply_markup=sub_markup())
        return
    
    code = int(message.text)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM movies WHERE code = %s", (code,))
    movie = cur.fetchone()
    cur.close()
    conn.close()
    
    if movie:
        bot.send_video(message.chat.id, movie['file_id'], caption=movie['caption'])
    else:
        bot.send_message(message.chat.id, "❌ Bunday kodli kino topilmadi.")

# --- KINO QO'SHISH (ADMIN VIDEO YUBORGANIDA) ---
@bot.message_handler(content_types=['video'])
def handle_video(message):
    if message.from_user.id != ADMIN_ID:
        return
    file_id = message.video.file_id
    caption = message.caption or ""
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT MAX(code) FROM movies")
    res = cur.fetchone()
    max_code = res['max'] if res and res['max'] is not None else 0
    new_code = max_code + 1
    
    cur.execute("INSERT INTO movies (code, file_id, caption) VALUES (%s, %s, %s)", (new_code, file_id, caption))
    conn.commit()
    cur.close()
    conn.close()
    
    bot.send_message(message.chat.id, f"✅ Kino saqlandi!\n🎬 KODI: {new_code}")

# --- FLASK KEEP-ALIVE SERVER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot ishlayapti!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

if __name__ == '__main__':
    Thread(target=run_flask).start()
    bot.infinity_polling()

