import os, time, threading, requests
import telebot
from flask import Flask

BOT_TOKEN = os.environ.get("BOT_TOKEN","").strip()
CHAT_ID = os.environ.get("CHAT_ID","").strip()
print(f"BOT_TOKEN ok? {bool(BOT_TOKEN)}")

app = Flask(__name__)
@app.route('/')
def home():
    return "5M Trader Bot LIVE"

bot = telebot.TeleBot(BOT_TOKEN) if BOT_TOKEN else None

# --- Trading State ---
current_trade = None # {"entry_price": 0, "type": "BUY"}

def get_klines():
    try:
        url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=50"
        data = requests.get(url, timeout=10).json()
        closes = [float(c[4]) for c in data]
        return closes
    except Exception as e:
        print(f"kline error {e}")
        return None

def ema(data, period):
    if len(data) < period: return None
    k = 2 / (period + 1)
    ema_val = sum(data[:period]) / period
    for price in data[period:]:
        ema_val = price * k + ema_val * (1 - k)
    return ema_val

def get_price():
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=5).json()
        return float(r['price'])
    except:
        return None

def send(msg):
    if bot and CHAT_ID:
        try:
            bot.send_message(CHAT_ID, msg)
            print(f"Sent: {msg[:50]}")
        except Exception as e:
            print(f"Send error {e}")

def trading_loop():
    global current_trade
    print("5M Trader loop started")
    while True:
        try:
            closes = get_klines()
            price = get_price()
            if not closes or not price:
                time.sleep(10)
                continue

            ema9 = ema(closes, 9)
            ema21 = ema(closes, 21)
            prev_close = closes[-2]

            print(f"Price: {price} | EMA9: {ema9:.2f} EMA21: {ema21:.2f}")

            # --- NO OPEN TRADE: Look for ENTRY ---
            if current_trade is None:
                # BUY condition: EMA9 > EMA21 and price is trending up on 5m
                if ema9 and ema21 and ema9 > ema21 and price > ema9 and closes[-1] > prev_close:
                    current_trade = {"entry_price": price, "type": "BUY"}
                    tp = price * 1.015
                    sl = price * 0.992
                    send(f"🚀 **ENTER BUY NOW**\n\nEntry: ${price:,.2f}\n5m Trend: UP (EMA9 > EMA21)\n\n🎯 Take Profit: ${tp:,.2f} (+1.5%)\n🛑 Stop Loss: ${sl:,.2f} (-0.8%)\n\nI will watch price for you!")

            # --- HAVE OPEN TRADE: Watch for TP/SL ---
            else:
                entry = current_trade["entry_price"]
                pnl_percent = ((price - entry) / entry) * 100

                # Take Profit +1.5%
                if price >= entry * 1.015:
                    send(f"✅ **TAKE PROFIT NOW!**\n\nEntry: ${entry:,.2f}\nExit: ${price:,.2f}\nProfit: +{pnl_percent:.2f}%\n\nClose trade!")
                    current_trade = None

                # Cut Loss -0.8%
                elif price <= entry * 0.992:
                    send(f"🚨 **CUT LOSS NOW!**\n\nEntry: ${entry:,.2f}\nExit: ${price:,.2f}\nLoss: {pnl_percent:.2f}%\n\nClose to avoid bigger loss!")
                    current_trade = None

                # Update every 3% move
                elif abs(pnl_percent) > 0.5:
                    print(f"Holding: {pnl_percent:.2f}%")

            time.sleep(30) # check every 30 seconds

        except Exception as e:
            print(f"Loop error {e}")
            time.sleep(10)

# Start bot
if BOT_TOKEN:
    threading.Thread(target=trading_loop, daemon=True).start()
    threading.Thread(target=lambda: bot.infinity_polling(), daemon=True).start()

@bot.message_handler(commands=['start','status'])
def handle_start(m):
    if current_trade:
        entry = current_trade["entry_price"]
        price = get_price()
        pnl = ((price-entry)/entry*100) if price else 0
        bot.reply_to(m, f"📊 Open Trade:\nEntry: ${entry:,.2f}\nNow: ${price:,.2f}\nPnL: {pnl:.2f}%")
    else:
        bot.reply_to(m, "👋 5M Trader Bot Ready!\n\nI scan BTC 5-min chart.\nI will alert you: ENTER, TAKE PROFIT, CUT LOSS.\n\nWaiting for uptrend...")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
