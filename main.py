import os
import sqlite3
from threading import Thread
from flask import Flask
import telebot
from telebot import types

# --- SOZLAMALAR ---
BOT_TOKEN = "8895763314:AAGk8HVxRRiSMseyvh6dx672wvDfaZYklzY"
bot = telebot.TeleBot(BOT_TOKEN)

ADMIN_ID = 0  # Shu yerga o'zingizning Telegram ID'ingizni yozing

CHANNELS = [{"id": -1003944114251, "link": "https://t.me/+YSnX_ktYFEoxMzAy"}]

MOVIE_CHANNEL_ID = -1004374661522


# --- BAZA BILAN ISHLASH (SQLite) ---
def init_db():
  conn = sqlite3.connect("movies.db")
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            code TEXT PRIMARY KEY,
            msg_ids TEXT
        )
    """)
  conn.commit()
  conn.close()


init_db()


def get_movie(code):
  conn = sqlite3.connect("movies.db")
  cursor = conn.cursor()
  cursor.execute("SELECT msg_ids FROM movies WHERE code = ?", (code,))
  row = cursor.fetchone()
  conn.close()
  return row[0] if row else None


def save_movie(code, msg_ids):
  conn = sqlite3.connect("movies.db")
  cursor = conn.cursor()
  cursor.execute(
      "INSERT OR REPLACE INTO movies (code, msg_ids) VALUES (?, ?)",
      (code, msg_ids),
  )
  conn.commit()
  conn.close()


def delete_movie(code):
  conn = sqlite3.connect("movies.db")
  cursor = conn.cursor()
  cursor.execute("DELETE FROM movies WHERE code = ?", (code,))
  conn.commit()
  conn.close()


# --- OBUNANI TEKSHIRISH ---
def check_sub(user_id):
  for ch in CHANNELS:
    try:
      member = bot.get_chat_member(chat_id=ch["id"], user_id=user_id)
      if member.status in ["left", "kicked"]:
        return False
    except Exception:
      return False
  return True


def get_sub_keyboard():
  markup = types.InlineKeyboardMarkup()
  for ch in CHANNELS:
    markup.add(
        types.InlineKeyboardButton(
            text="Kanalga a'zo bo'lish ➕", url=ch["link"]
        )
    )
  markup.add(
      types.InlineKeyboardButton(
          text="Tekshirish 🔄", callback_data="check"
      )
  )
  return markup


# --- BUYRUKLAR (HANDLERS) ---
@bot.message_handler(commands=["start"])
def start_cmd(message):
  bot.reply_to(
      message,
      "Xush kelibsiz! Kino yoki drama kodini yuboring.",
  )


@bot.callback_query_handler(func=lambda call: call.data == "check")
def check_callback(call):
  if check_sub(call.from_user.id):
    bot.answer_callback_query(
        call.id, "Rahmat! Endi kod yuborishingiz mumkin."
    )
    bot.send_message(call.message.chat.id, "Kino kodini yuboring:")
  else:
    bot.answer_callback_query(
        call.id, "Siz hali kanalga a'zo bo'lmadingiz!", show_alert=True
    )


# Admin: Kino qo'shish: /add <kod> <ID1,ID2...>
@bot.message_handler(commands=["add"])
def add_movie_cmd(message):
  if message.from_user.id != ADMIN_ID and ADMIN_ID != 0:
    return
  try:
    args = message.text.split(maxsplit=2)
    code = args[1].strip()
    ids = args[2].strip()
    save_movie(code, ids)
    bot.reply_to(
        message,
        f"✅ Muvaffaqiyatli saqlandi!\nKod: {code}\nID(lar): {ids}",
    )
  except Exception:
    bot.reply_to(
        message,
        "❌ Xato format!\nIshlatish: `/add <kod> <ID1,ID2...>`\nMasalan:"
        " `/add 1 15`\nDramalar: `/add 2 15,16,17`",
        parse_mode="Markdown",
    )


# Admin: Kino o'chirish: /del <kod>
@bot.message_handler(commands=["del"])
def del_movie_cmd(message):
  if message.from_user.id != ADMIN_ID and ADMIN_ID != 0:
    return
  try:
    code = message.text.split()[1].strip()
    delete_movie(code)
    bot.reply_to(message, f"🗑️ Kod `{code}` bazadan o'chirildi.")
  except Exception:
    bot.reply_to(
        message, "Ishlatish: `/del <kod>`", parse_mode="Markdown"
    )


# FOYDALANUVCHIDAN RAQAM KELGANDA
@bot.message_handler(func=lambda message: True)
def send_movie(message):
  if not check_sub(message.from_user.id):
    bot.send_message(
        message.chat.id,
        "Kino ko'rish uchun avval kanalga obuna bo'ling!",
        reply_markup=get_sub_keyboard(),
    )
    return

  code = message.text.strip()
  msg_ids_str = get_movie(code)

  if msg_ids_str:
    ids_list = [
        i.strip() for i in msg_ids_str.split(",") if i.strip()
    ]

    # Agar bitta qism bo'lsa - to'g'ridan-to'g'ri yuboradi
    if len(ids_list) == 1:
      try:
        bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=MOVIE_CHANNEL_ID,
            message_id=int(ids_list[0]),
        )
      except Exception:
        bot.send_message(
            message.chat.id,
            "Xatolik yuz berdi. Bot baza kanalida Admin ekanligini"
            " tekshiring.",
        )
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
          f"🎬 **{code}**-sonli Drama qismlari:\n\nKo'rmoqchi bo'lgan"
          " qismingizni tanlang 👇",
          parse_mode="Markdown",
          reply_markup=markup,
      )
  else:
    bot.send_message(
        message.chat.id,
        "Bunday raqamli kino yoki drama topilmadi. Qaytadan tekshirib"
        " ko'ring.",
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("ep_"))
def send_episode(call):
  msg_id = call.data.split("_")[1]
  try:
    bot.copy_message(
        chat_id=call.message.chat.id,
        from_chat_id=MOVIE_CHANNEL_ID,
        message_id=int(msg_id),
    )
  except Exception:
    bot.send_message(
        call.message.chat.id,
        "Xatolik yuz berdi. Baza kanalini tekshiring.",
    )


# --- FLASK VEB SERVER VA UYQUGA KETMASLIK (KEEP-ALIVE) ---
app = Flask("")


@app.route("/")
def home():
  return "Bot is running!"


def run():
  port = int(os.environ.get("PORT", 8080))
  app.run(host="0.0.0.0", port=port)


def keep_alive():
  t = Thread(target=run)
  t.start()


if __name__ == "__main__":
  keep_alive()
  print("Bot ishga tushdi...")
  bot.infinity_polling()

