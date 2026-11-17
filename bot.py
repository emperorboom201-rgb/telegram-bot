import os
import asyncio
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai

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
user_histories = {}

def get_available_models():
    """Tự động lấy danh sách model hỗ trợ chat từ API, ưu tiên gemini-3.8-flash"""
    models = ["gemini-3.8-flash"]
    try:
        for m in client.models.list():
            name = m.name.replace("models/", "")
            if "gemini" in name and "embedding" not in name and "imagen" not in name and "veo" not in name:
                if name not in models:
                    models.append(name)
    except Exception:
        pass
    return models[:5]  # Lấy tối đa 5 model để dự phòng

async def generate_with_fallback(history):
    models = get_available_models()
    last_error = None
    for model_name in models:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=history
                )
                return response.text
            except Exception as e:
                last_error = e
                err_str = str(e)
                if "503" in err_str or "UNAVAILABLE" in err_str or "429" in err_str:
                    await asyncio.sleep(2)
                    continue
                if "404" in err_str or "NOT_FOUND" in err_str or "400" in err_str:
                    break  # Bỏ qua model không hỗ trợ và chuyển ngay sang model tiếp theo
                break
    raise last_error

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = []
    await update.message.reply_text("Xin chào! Tôi là bot AI chạy 24/7. Bạn cần giúp gì hôm nay?")

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = []
    await update.message.reply_text("Đã làm mới cuộc trò chuyện!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    if user_id not in user_histories:
        user_histories[user_id] = []

    user_histories[user_id].append({"role": "user", "parts": [{"text": user_text}]})
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        reply_text = await generate_with_fallback(user_histories[user_id])
        user_histories[user_id].append({"role": "model", "parts": [{"text": reply_text}]})

        if len(user_histories[user_id]) > 20:
            user_histories[user_id] = user_histories[user_id][-20:]

        for i in range(0, len(reply_text), 4000):
            await update.message.reply_text(reply_text[i:i+4000])

    except Exception as e:
        user_histories[user_id].pop()
        if "503" in str(e):
            await update.message.reply_text("Hệ thống AI đang quá tải tạm thời, bạn gửi lại tin nhắn sau vài giây nhé!")
        else:
            await update.message.reply_text(f"Có lỗi xảy ra: {str(e)}")

def main():
    keep_alive()
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot đang chạy...")
    app.run_polling()

if __name__ == "__main__":
    main()
