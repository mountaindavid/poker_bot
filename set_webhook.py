import requests
import os
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
RAILWAY_URL = "https://your-app-name.up.railway.app"  # без слэша в конце

url = f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={RAILWAY_URL}/{TOKEN}"
print(requests.get(url).json())