#main.py
from flask import Flask, request
from bot import bot
import os
import telebot

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_SECRET_PATH = os.getenv("WEBHOOK_SECRET_PATH", "supersecret")

app = Flask(__name__)


@app.route(f"/{WEBHOOK_SECRET_PATH}", methods=['POST'])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return '', 200


@app.route("/", methods=['GET'])
def index():
    return "Poker Bot is alive!", 200


if __name__ == '__main__':
    port = int(os.getenv("PORT", 8443))
    bot.remove_webhook()
    bot.set_webhook(url=f'{os.getenv("WEBHOOK_URL")}/{WEBHOOK_SECRET_PATH}')
    app.run(host='0.0.0.0', port=port)






