import os
import time
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai
from google.genai import types

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# --- Web Server giữ bot thức 24/7 trên Render ---
app_flask = Flask('')

@app_flask.route('/')
def home():
    return "Bot AI đang hoạt động siêu tốc!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app_flask.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()
# ------------------------------------------------

client = genai.Client(api_key=GEMINI_API_KEY)
user_histories = {}

# Chỉ dùng các model chat tốc độ cao nhất, không dùng model ảnh/thử nghiệm
FAST_MODELS = ["gemini-3.8-flash", "gemini-2.5-pro"]

SYSTEM_PROMPT = (
    "Bạn là một trợ lý AI thông minh, thân thiện và trả lời bằng tiếng Việt tự nhiên, "
    "súc tích, đi thẳng vào trọng tâm."
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = []
    await update.message.reply_text("Xin chào! Tôi đã sẵn sàng. Bạn cần hỗ trợ gì nào?")

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = []
    await update.message.reply_text("Đã xóa trí nhớ cũ. Mình bắt đầu chủ đề mới nhé!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    if user_id not in user_histories:
        user_histories[user_id] = []

    user_histories[user_id].append({"role": "user", "parts": [{"text": user_text}]})
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    full_reply = ""
    sent_message = None
    last_edit_time = 0
    success = False
    last_error = None

    for model_name in FAST_MODELS:
        try:
            # Dùng generate_content_stream để nhận chữ ngay lập tức như ChatGPT/Gemini
            response_stream = client.models.generate_content_stream(
                model=model_name,
                contents=user_histories[user_id],
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.7,
                )
            )

            for chunk in response_stream:
                if chunk.text:
                    full_reply += chunk.text
                    now = time.time()
                    # Gửi tin nhắn đầu tiên ngay khi có chữ, sau đó cập nhật mượt mỗi 0.8 giây
                    if sent_message is None and len(full_reply.strip()) > 0:
                        sent_message = await update.message.reply_text(full_reply[:4000] + " ▌")
                        last_edit_time = now
                    elif sent_message is not None and (now - last_edit_time) >= 0.8:
                        if len(full_reply) <= 4000:
                            try:
                                await sent_message.edit_text(full_reply + " ▌")
                                last_edit_time = now
                            except Exception:
                                pass

            success = True
            break  # Thành công thì thoát vòng lặp ngay

        except Exception as e:
            last_error = e
            full_reply = ""
            continue  # Nếu model 1 lỗi (503/429), lập tức chuyển sang model 2 không chờ đợi

    if success and full_reply:
        # Hoàn thiện tin nhắn cuối cùng (bỏ dấu nháy ▌)
        if len(full_reply) <= 4000:
            if sent_message:
                try:
                    await sent_message.edit_text(full_reply)
                except Exception:
                    pass
            else:
                await update.message.reply_text(full_reply)
        else:
            # Nếu câu trả lời quá dài (>4000 ký tự), chia làm nhiều tin nhắn
            if sent_message:
                try:
                    await sent_message.edit_text(full_reply[:4000])
                except Exception:
                    pass
            for i in range(4000, len(full_reply), 4000):
                await update.message.reply_text(full_reply[i:i+4000])

        user_histories[user_id].append({"role": "model", "parts": [{"text": full_reply}]})
        if len(user_histories[user_id]) > 20:
            user_histories[user_id] = user_histories[user_id][-20:]
    else:
        user_histories[user_id].pop()
        await update.message.reply_text(
            "Máy chủ AI đang bận nhẹ, bạn gửi lại câu vừa rồi giúp mình nhé!"
        )

def main():
    keep_alive()
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot siêu tốc đang chạy...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
