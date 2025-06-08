#main.py
from flask import Flask, request
from bot import bot
import os
import telebot
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_SECRET_PATH = os.getenv("WEBHOOK_SECRET_PATH", "supersecret")

app = Flask(__name__)


@app.route(f"/{WEBHOOK_SECRET_PATH}", methods=['POST'])
def webhook():
    try:
        json_str = request.get_data().decode("utf-8")
        logger.info(f"Received webhook data: {json_str}")

        update = telebot.types.Update.de_json(json_str)
        logger.info(f"Parsed update: {update}")

        bot.process_new_updates([update])
        logger.info("Update processed successfully")

        return '', 200
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return str(e), 500


@app.route("/", methods=['GET'])
def index():
    return "Poker Bot is alive!", 200

@app.route("/health", methods=['GET'])
def health():
    return {"status": "ok", "webhook_path": WEBHOOK_SECRET_PATH}, 200


if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    logger.info(f"Starting bot on port {port}")
    logger.info(f"Webhook path: /{WEBHOOK_SECRET_PATH}")

    try:
        bot.remove_webhook()
        webhook_url = f'{os.getenv("WEBHOOK_URL")}/{WEBHOOK_SECRET_PATH}'
        bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook set to: {webhook_url}")
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")

    app.run(host='0.0.0.0', port=port)







