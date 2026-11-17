import os
import time
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from groq import AsyncGroq

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()

app_flask = Flask('')

@app_flask.route('/')
def home():
    return "Bot Groq AI đang hoạt động!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app_flask.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

client = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
user_histories = {}
cached_model = None

SYSTEM_PROMPT = {
    "role": "system",
    "content": "Bạn là trợ lý AI thông minh, trả lời bằng tiếng Việt tự nhiên, súc tích và đi thẳng vào trọng tâm."
}

async def get_best_groq_model():
    global cached_model
    if cached_model:
        return cached_model
    models_list = await client.models.list()
    excluded = ["whisper", "guard", "tts", "audio", "vision", "embed"]
    valid_models = [m.id for m in models_list.data if not any(kw in m.id.lower() for kw in excluded)]
    # Ưu tiên llama-3.1-8b và llama-3.3 trước vì hạn mức miễn phí rất cao và tốc độ cực nhanh
    for preferred in ["llama-3.1-8b", "llama-3.3", "llama-4", "llama", "qwen", "deepseek"]:
        for m_id in valid_models:
            if preferred in m_id.lower():
                cached_model = m_id
                return cached_model
    cached_model = valid_models[0]
    return cached_model

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_histories[update.effective_user.id] = [SYSTEM_PROMPT]
    await update.message.reply_text("Xin chào! Tôi đã sẵn sàng. Bạn cần giúp gì nào?")

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_histories[update.effective_user.id] = [SYSTEM_PROMPT]
    await update.message.reply_text("Đã xóa trí nhớ cũ. Mình bắt đầu chủ đề mới nhé!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global cached_model
    if not client:
        await update.message.reply_text("Lỗi: Thiếu GROQ_API_KEY trên Render!")
        return

    user_id = update.effective_user.id
    if user_id not in user_histories:
        user_histories[user_id] = [SYSTEM_PROMPT]

    user_histories[user_id].append({"role": "user", "content": update.message.text})
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    full_reply = ""
    sent_message = None
    last_edit_time = 0

    try:
        active_model = await get_best_groq_model()
        stream = await client.chat.completions.create(
            model=active_model,
            messages=user_histories[user_id],
            temperature=0.7,
            max_tokens=900,
            stream=True
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                full_reply += delta
                now = time.time()
                if sent_message is None and full_reply.strip():
                    sent_message = await update.message.reply_text(full_reply[:4000] + " ▌")
                    last_edit_time = now
                elif sent_message and (now - last_edit_time) >= 0.7 and len(full_reply) <= 4000:
                    try:
                        await sent_message.edit_text(full_reply + " ▌")
                        last_edit_time = now
                    except Exception:
                        pass

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
        cached_model = None
        user_histories[user_id].pop()
        await update.message.reply_text(f"Có lỗi kết nối: {str(e)}")

def main():
    keep_alive()
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot Groq đang chạy...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
