import os
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai

# Lấy Token và API Key an toàn từ cài đặt trên Render
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# --- Phần tạo Web Server nhỏ giữ bot hoạt động trên Render ---
app_flask = Flask('')

@app_flask.route('/')
def home():
    return "Bot AI đang hoạt động bình thường!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app_flask.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()
# -------------------------------------------------------------

client = genai.Client(api_key=GEMINI_API_KEY)
user_chats = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_chats[user_id] = client.chats.create(model="gemini-2.5-flash")
    await update.message.reply_text("Xin chào! Tôi là bot AI chạy 24/7. Bạn cần giúp gì hôm nay?")

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_chats[user_id] = client.chats.create(model="gemini-2.5-flash")
    await update.message.reply_text("Đã làm mới cuộc trò chuyện!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_chats:
        user_chats[user_id] = client.chats.create(model="gemini-2.5-flash")

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response = user_chats[user_id].send_message(update.message.text)
        # Chia nhỏ tin nhắn nếu dài quá giới hạn 4096 ký tự của Telegram
        text = response.text
        for i in range(0, len(text), 4000):
            await update.message.reply_text(text[i:i+4000])
    except Exception as e:
        await update.message.reply_text(f"Có lỗi xảy ra: {str(e)}")

def main():
    keep_alive()  # Khởi chạy web server song song với bot
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot đang chạy...")
    app.run_polling()

if __name__ == "__main__":
    main()
