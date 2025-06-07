from flask import Flask, request
from bot import bot
import os
import telebot

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
app = Flask(__name__)

@app.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return '', 200

@app.route("/", methods=['GET'])
def index():
    return "Poker Bot is alive!", 200

if __name__ == '__main__':
    from os import getenv
    port = int(getenv("PORT", 8443))
    bot.remove_webhook()  # Удаляем старый вебхук, если есть
    bot.set_webhook(url=f'{getenv("WEBHOOK_URL")}/{TOKEN}')
    app.run(host='0.0.0.0', port=port)