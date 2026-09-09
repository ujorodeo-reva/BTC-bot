import os
import time
import threading
import requests
import telebot
from flask import Flask

# --- GET TOKEN - Fixed ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

print(f"DEBUG: BOT_TOKEN exists? {bool(BOT_TOKEN)}")
print(f"DEBUG: CHAT_ID exists? {bool(CHAT_ID)}")

if not BOT_TOKEN:
    print("ERROR: BOT_TOKEN is missing in Render Environment!")
    # Don't crash, keep Flask alive so you can see logs
else:
    BOT_TOKEN = BOT_TOKEN.strip()

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running! If you see this, Flask works."

def get_btc_data():
    try:
        url = "https://api.coingecko.com/api/v3/coins/bitcoin"
        r = requests.get(url, timeout=10).json()
        price = r['market_data']['current_price']['usd']
        change = r['market_data']['price_change_percentage_24h']
        return price, change
    except:
        return None, None

def check_and_send():
    if not BOT_TOKEN or not CHAT_ID:
        print("Skipping Telegram send - token/chat_id missing")
        return
    try:
        bot = telebot.TeleBot(BOT_TOKEN)
        price, change = get_btc_data()
        if price and change is not None and change > 0:
            msg = f"🚀 BUY SIGNAL\nBTC: ${price:,.2f}\n24h: +{change:.2f}%\nTrend is UP!"
            bot.send_message(CHAT_ID, msg)
            print("Sent BUY signal")
    except Exception as e:
        print(f"Telegram error: {e}")

def loop():
    while True:
        check_and_send()
        time.sleep(60)

if BOT_TOKEN:
    threading.Thread(target=loop, daemon=True).start()
    threading.Thread(target=lambda: telebot.TeleBot(BOT_TOKEN).infinity_polling(), daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
