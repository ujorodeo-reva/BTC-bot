import os, time, threading, requests
import telebot
from flask import Flask

BOT_TOKEN = os.environ.get("BOT_TOKEN","").strip()
CHAT_ID = os.environ.get("CHAT_ID","").strip()

app = Flask(__name__)
@app.route('/')
def home():
    return "4-Coin 5M Trader LIVE"

bot = telebot.TeleBot(BOT_TOKEN) if BOT_TOKEN else None

# --- CONFIG: Your 4 coins ---
COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
# You can change to any: e.g. ["BTCUSDT", "PEPEUSDT", "DOGEUSDT", "XRPUSDT"]

trades = {coin: None for coin in COINS} # Track each coin

def get_klines(symbol):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=5m&limit=50"
        data = requests.get(url, timeout=10).json()
        closes = [float(c[4]) for c in data]
        return closes
    except:
        return None

def ema(data, period):
    if len(data) < period: return None
    k = 2 / (period + 1)
    ema_val = sum(data[:period]) / period
    for price in data[period:]:
        ema_val = price * k + ema_val * (1 - k)
    return ema_val

def get_price(symbol):
    try:
        r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}", timeout=5).json()
        return float(r['price'])
    except:
        return None

def send(msg):
    if bot and CHAT_ID:
        try: bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
        except Exception as e: print(f"Send error {e}")

def analyze_coin(symbol):
    global trades
    closes = get_klines(symbol)
    price = get_price(symbol)
    if not closes or not price: return

    ema9 = ema(closes, 9)
    ema21 = ema(closes, 21)
    coin_name = symbol.replace("USDT","")

    # No open trade - Look for ENTRY
    if trades[symbol] is None:
        if ema9 and ema21 and ema9 > ema21 and price > ema9 and closes[-1] > closes[-2]:
            trades[symbol] = {"entry": price}
            tp = price * 1.015
            sl = price * 0.992
            send(f"🚀 **ENTER BUY {coin_name} NOW**\n\nEntry: ${price:,.4f}\n5m Trend: UP (EMA9 > EMA21)\n\n🎯 TP: ${tp:,.4f} (+1.5%)\n🛑 SL: ${sl:,.4f} (-0.8%)")
    else:
        # Have trade - Watch TP/SL
        entry = trades[symbol]["entry"]
        if price >= entry * 1.015:
            pnl = ((price-entry)/entry*100)
            send(f"✅ **TAKE PROFIT {coin_name}!**\n\nEntry: ${entry:,.4f}\nExit: ${price:,.4f}\nProfit: +{pnl:.2f}%")
            trades[symbol] = None
        elif price <= entry * 0.992:
            pnl = ((price-entry)/entry*100)
            send(f"🚨 **CUT LOSS {coin_name}!**\n\nEntry: ${entry:,.4f}\nExit: ${price:,.4f}\nLoss: {pnl:.2f}%")
            trades[symbol] = None

def trading_loop():
    print(f"Watching {COINS}")
    while True:
        for coin in COINS:
            try:
                analyze_coin(coin)
                time.sleep(2) # small delay between coins
            except Exception as e:
                print(f"{coin} error {e}")
        time.sleep(30) # scan all 4 coins every 30 sec

if BOT_TOKEN:
    threading.Thread(target=trading_loop, daemon=True).start()
    threading.Thread(target=lambda: bot.infinity_polling(), daemon=True).start()

@bot.message_handler(commands=['start','status'])
def handle_start(m):
    msg = "👋 **4-Coin 5M Trader Ready**\n\n"
    for coin in COINS:
        name = coin.replace("USDT","")
        if trades[coin]:
            entry = trades[coin]["entry"]
            price = get_price(coin)
            pnl = ((price-entry)/entry*100) if price else 0
            msg += f"📊 {name}: IN TRADE {pnl:.2f}%\n"
        else:
            msg += f"⏳ {name}: Waiting for uptrend\n"
    msg += f"\nScanning every 30s."
    bot.reply_to(m, msg, parse_mode="Markdown")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
