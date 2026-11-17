import os
import time
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from groq import AsyncGroq

# Lấy Token và Key tự động từ Render (không dán trực tiếp vào đây để tránh lỗi đỏ GitHub)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# --- Web Server giữ bot thức 24/7 trên Render ---
app_flask = Flask('')

@app_flask.route('/')
def home():
    return "Bot Groq AI siêu tốc đang chạy!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app_flask.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()
# ------------------------------------------------

client = AsyncGroq(api_key=GROQ_API_KEY)
user_histories = {}

SYSTEM_PROMPT = {
    "role": "system",
    "content": "Bạn là một trợ lý AI thông minh, thân thiện, trả lời bằng tiếng Việt tự nhiên, súc tích và đi thẳng vào trọng tâm."
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = [SYSTEM_PROMPT]
    await update.message.reply_text("Xin chào! Tôi đã được nâng cấp tốc độ. Bạn cần giúp gì nào?")

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = [SYSTEM_PROMPT]
    await update.message.reply_text("Đã xóa trí nhớ cũ. Mình bắt đầu chủ đề mới nhé!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    if user_id not in user_histories:
        user_histories[user_id] = [SYSTEM_PROMPT]

    user_histories[user_id].append({"role": "user", "content": user_text})
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    full_reply = ""
    sent_message = None
    last_edit_time = 0

    try:
        stream = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=user_histories[user_id],
            temperature=0.7,
            max_tokens=2048,
            stream=True
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                full_reply += delta
                now = time.time()
                if sent_message is None and len(full_reply.strip()) > 0:
                    sent_message = await update.message.reply_text(full_reply[:4000] + " ▌")
                    last_edit_time = now
                elif sent_message is not None and (now - last_edit_time) >= 0.7:
                    if len(full_reply) <= 4000:
                        try:
                            await sent_message.edit_text(full_reply + " ▌")
                            last_edit_time = now
                        except Exception:
                            pass

        # Hoàn tất tin nhắn cuối cùng
        if len(full_reply) <= 4000:
            if sent_message:
                try:
                    await sent_message.edit_text(full_reply)
                except Exception:
                    pass
            else:
                await update.message.reply_text(full_reply)
        else:
            if sent_message:
                try:
                    await sent_message.edit_text(full_reply[:4000])
                except Exception:
                    pass
            for i in range(4000, len(full_reply), 4000):
                await update.message.reply_text(full_reply[i:i+4000])

        user_histories[user_id].append({"role": "assistant", "content": full_reply})
        if len(user_histories[user_id]) > 21:
            user_histories[user_id] = [SYSTEM_PROMPT] + user_histories[user_id][-20:]

    except Exception as e:
        user_histories[user_id].pop()
        await update.message.reply_text(f"Có lỗi kết nối: {str(e)}")

def main():
    keep_alive()
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot Groq siêu tốc đang chạy...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
