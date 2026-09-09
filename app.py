import os, time, threading
import yfinance as yf
import telebot
from flask import Flask

TOKEN = os.getenv("BOT_TOKEN") or "7586608380:AAGmYdMJ2Uk30MShVRjh8sp0DtpPguaOB2Q"
CHAT_ID = os.getenv("CHAT_ID") or "7484911407"
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

open_trade = None
entry = 0

@app.route('/')
def home():
    return f"Bot is running! Trade: {open_trade} Entry: {entry}"

def get_data():
    data = yf.download("BTC-USD", period="2d", interval="5m", progress=False)
    data['EMA9'] = data['Close'].ewm(span=9).mean()
    data['EMA21'] = data['Close'].ewm(span=21).mean()
    delta = data['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rs = gain / loss
    data['RSI'] = 100 - (100 / (1 + rs))
    return data

def trading_loop():
    global open_trade, entry
    print("Trading loop started")
    while True:
        try:
            data = get_data()
            last = data.iloc[-1]
            price = float(last['Close'])
            ema9 = float(last['EMA9'])
            ema21 = float(last['EMA21'])
            rsi = float(last['RSI'])

            # HOLD LOGIC
            if open_trade is not None:
                print(f"Holding {open_trade} Entry {entry} Now {price}")
                if open_trade == "BUY":
                    if ema9 < ema21:
                        bot.send_message(CHAT_ID, f"⚠️ CANCEL BUY! Trend flipped. Entry ${entry:.2f} -> Now ${price:.2f}")
                        open_trade = None
                    elif price >= entry * 1.03:
                        bot.send_message(CHAT_ID, f"✅ TP3 +3% DONE! 💰 BTC ${price:.2f}")
                        open_trade = None
                    elif price <= entry * 0.985:
                        bot.send_message(CHAT_ID, f"❌ SL -1.5% Hit. Closed.")
                        open_trade = None
                elif open_trade == "SELL":
                    if ema9 > ema21:
                        bot.send_message(CHAT_ID, f"⚠️ CANCEL SELL! Trend flipped.")
                        open_trade = None
                continue

            # NEW SIGNAL (only if no open trade)
            if ema9 > ema21 and 40 < rsi < 68:
                entry = price
                open_trade = "BUY"
                bot.send_message(CHAT_ID, f"🟢 5M BUY! ${price:.2f} RSI {rsi:.1f}\nTP1 {price*1.01:.2f} TP2 {price*1.02:.2f} TP3 {price*1.03:.2f} SL {price*0.985:.2f}\nHolding till TP/SL or Cancel")
            elif ema9 < ema21 and 32 < rsi < 60:
                entry = price
                open_trade = "SELL"
                bot.send_message(CHAT_ID, f"🔴 5M SELL! ${price:.2f} RSI {rsi:.1f}\nHolding till done")

        except Exception as e:
            print(f"Error: {e}")
        time.sleep(60)

# Start trading in background
threading.Thread(target=trading_loop, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
