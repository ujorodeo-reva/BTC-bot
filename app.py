import os, time, threading, requests
from flask import Flask
import telebot

BOT_TOKEN = os.getenv("7586608380:AAGmYdMJ2Uk30MShVRjh8sp0DtpPguaOB2Q")
CHAT_ID = os.getenv("7484911407") # Add this in Render ENV!
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return "BUY-ONLY bot LIVE"

# --- STATE ---
in_trade = False
buy_price = 0
tp1 = 0
saved_chat_id = None

def get_btc_data():
    # Get BTC 5m candles from Binance (no API key needed)
    url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=30"
    data = requests.get(url).json()
    closes = [float(c[4]) for c in data]

    # Simple EMA9 and EMA21
    ema9 = sum(closes[-9:]) / 9
    ema21 = sum(closes[-21:]) / 21
    price = closes[-1]
    return price, ema9, ema21

@bot.message_handler(commands=['start','buy','status'])
def handle(m):
    global saved_chat_id, in_trade, buy_price, tp1
    saved_chat_id = m.chat.id
    if m.text.startswith('/buy'):
        try:
            buy_price = float(m.text.split()[1])
        except:
            price, _, _ = get_btc_data()
            buy_price = price
        tp1 = buy_price * 1.02
        in_trade = True
        bot.reply_to(m, f"✅ BUY at ${buy_price:.2f}\nTP1: ${tp1:.2f}\nNow HOLDING. I will alert you.")
    else:
        bot.reply_to(m, f"In trade: {in_trade} at ${buy_price}. Send /buy 80000 to test")

def trading_loop():
    global in_trade, buy_price, tp1
    while True:
        try:
            price, ema9, ema21 = get_btc_data()
            is_buy = ema9 > ema21 # BUY ONLY signal

            # If not in trade and BUY appears -> send 1 signal
            if not in_trade and is_buy:
                if saved_chat_id or CHAT_ID:
                    target = CHAT_ID or saved_chat_id
                    bot.send_message(target, f"🟢 BUY SIGNAL! BTC ${price:.2f}\nEMA9 {ema9:.2f} > EMA21 {ema21:.2f}\n\nNow HOLDING. TP1 ${price*1.02:.2f}")
                buy_price = price
                tp1 = price * 1.02
                in_trade = True
                print(f"BUY signal sent at {price}")

            # If in trade
            if in_trade:
                # 1. Check if trend flipped BEFORE TP1
                if price < tp1 and ema9 < ema21:
                    if saved_chat_id or CHAT_ID:
                        target = CHAT_ID or saved_chat_id
                        bot.send_message(target, f"❌ CLOSE TRADE! Trend changed before TP1\nBought at ${buy_price:.2f}, now ${price:.2f}\nWait for next BUY signal.")
                    in_trade = False
                    print("Closed - trend flipped")
                # 2. Check TP1 hit
                elif price >= tp1:
                    if saved_chat_id or CHAT_ID:
                        target = CHAT_ID or saved_chat_id
                        bot.send_message(target, f"🎯 TP1 HIT! ${price:.2f}\nBought at ${buy_price:.2f} - Profit! Close trade.")
                    in_trade = False
                    print("TP1 hit")

            time.sleep(60)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    threading.Thread(target=lambda: bot.infinity_polling(), daemon=True).start()
    threading.Thread(target=trading_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
