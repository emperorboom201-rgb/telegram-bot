import os
import time
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from groq import AsyncGroq

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

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

client = AsyncGroq(api_key=GROQ_API_KEY)
user_histories = {}
cached_model = None

SYSTEM_PROMPT = {
    "role": "system",
    "content": "Bạn là một trợ lý AI thông minh, thân thiện, trả lời bằng tiếng Việt tự nhiên, súc tích và đi thẳng vào trọng tâm."
}

async def get_best_groq_model():
    """Tự động tìm model chat đang hoạt động trên tài khoản Groq của bạn"""
    global cached_model
    if cached_model:
        return cached_model

    models_list = await client.models.list()
    excluded = ["whisper", "guard", "tts", "audio", "vision", "embed"]
    valid_models = [
        m.id for m in models_list.data
        if not any(kw in m.id.lower() for kw in excluded)
    ]

    # Ưu tiên các dòng model lớn và nhanh nhất hiện có
    for preferred in ["llama-4", "llama-3.3", "qwen", "deepseek", "llama-3.1-8b", "llama"]:
        for m_id in valid_models:
            if preferred in m_id.lower():
                cached_model = m_id
                return cached_model

    cached_model = valid_models[0]
    return cached_model

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = [SYSTEM_PROMPT]
    await update.message.reply_text("Xin chào! Tôi đã sẵn sàng. Bạn cần giúp gì nào?")

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = [SYSTEM_PROMPT]
    await update.message.reply_text("Đã xóa trí nhớ cũ. Mình bắt đầu chủ đề mới nhé!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global cached_model
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
        active_model = await get_best_groq_model()
        stream = await client.chat.completions.create(
            model=active_model,
            messages=
