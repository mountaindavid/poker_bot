#set_webhook.py
import requests
import os
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
RAILWAY_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_SECRET_PATH = os.getenv("WEBHOOK_SECRET_PATH", "supersecret")

url = f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={RAILWAY_URL}/{WEBHOOK_SECRET_PATH}"
print(requests.get(url).json())