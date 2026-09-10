import os, time, threading, requests
import telebot
from flask import Flask

BOT_TOKEN = os.environ.get("BOT_TOKEN","").strip()
CHAT_ID = os.environ.get("CHAT_ID","").strip()

app = Flask(__name__)
@app.route('/')
def home():
    return "PRO Confluence Bot LIVE"

bot = telebot.TeleBot(BOT_TOKEN) if BOT_TOKEN else None

COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
trades = {coin: None for coin in COINS}

def get_klines(symbol):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=5m&limit=250"
        r = requests.get(url, timeout=15)
        data = r.json()
        if isinstance(data, list):
            closes = [float(c[4]) for c in data]
            return closes
        else:
            print(f"Klines error {symbol}: {data}")
            return None
    except Exception as e:
        print(f"Klines exception {symbol}: {e}")
        return None

def ema(data, period):
    if len(data) < period: return None
    k = 2 / (period + 1)
    ema_val = sum(data[:period]) / period
    for price in data[period:]:
        ema_val = price * k + ema_val * (1 - k)
    return ema_val

def rsi(data, period=14):
    if len(data) < period + 1: return None
    gains = []
    losses = []
    for i in range(1, len(data)):
        change = data[i] - data[i-1]
        if change > 0: gains.append(change); losses.append(0)
        else: gains.append(0); losses.append(abs(change))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0: return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def get_price(symbol):
    try:
        r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}", timeout=10).json()
        return float(r['price'])
    except:
        return None

def send(msg):
    if bot and CHAT_ID:
        try: bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
        except Exception as e: print(f"Send error {e}")

def analyze_coin(symbol):
    closes = get_klines(symbol)
    price = get_price(symbol)
    if not closes or not price or len(closes) < 200: return

    ema9 = ema(closes, 9)
    ema21 = ema(closes, 21)
    ema200 = ema(closes, 200)
    ema9_prev = ema(closes[:-1], 9)
    ema21_prev = ema(closes[:-1], 21)
    rsi_val = rsi(closes, 14)
    coin_name = symbol.replace("USDT","")

    if not all([ema9, ema21, ema200, ema9_prev, ema21_prev, rsi_val]): return

    bullish_cross = ema9_prev <= ema21_prev and ema9 > ema21
    bearish_cross = ema9_prev >= ema21_prev and ema9 < ema21

    if trades[symbol] is None:
        if price > ema200 and bullish_cross and rsi_val > 50 and rsi_val < 70 and closes[-1] > closes[-2]:
            trades[symbol] = {"entry": price, "side": "LONG"}
            tp = price * 1.02
            sl = price * 0.99
            send(f"🚀 **HIGH CONFIDENCE LONG {coin_name}** 📈\n\nPrice: ${price:,.4f}\n✅ Price > EMA200 ({ema200:,.2f})\n✅ EMA9 CROSS UP EMA21\n✅ RSI: {rsi_val:.1f}\n\n🎯 TP: ${tp:,.4f} (+2%)\n🛑 SL: ${sl:,.4f} (-1%)")
        elif price < ema200 and bearish_cross and rsi_val < 50 and rsi_val > 30 and closes[-1] < closes[-2]:
            trades[symbol] = {"entry": price, "side": "SHORT"}
            tp = price * 0.98
            sl = price * 1.01
            send(f"🔻 **HIGH CONFIDENCE SHORT {coin_name}** 📉\n\nPrice: ${price:,.4f}\n✅ Price < EMA200 ({ema200:,.2f})\n✅ EMA9 CROSS DOWN EMA21\n✅ RSI: {rsi_val:.1f}\n\n🎯 TP: ${tp:,.4f} (-2%)\n🛑 SL: ${sl:,.4f} (+1%)")
    else:
        entry = trades[symbol]["entry"]
        side = trades[symbol]["side"]
        if side == "LONG":
            if price >= entry * 1.02:
                pnl = ((price-entry)/entry*100)
                send(f"✅ **TP HIT LONG {coin_name}! +{pnl:.2f}%**\nEntry: ${entry:,.4f} -> Exit: ${price:,.4f}")
                trades[symbol] = None
            elif price <= entry * 0.99:
                pnl = ((price-entry)/entry*100)
                send(f"🚨 **SL HIT LONG {coin_name}! {pnl:.2f}%**\nEntry: ${entry:,.4f} -> Exit: ${price:,.4f}")
                trades[symbol] = None
        else:
            if price <= entry * 0.98:
                pnl = ((entry-price)/entry*100)
                send(f"✅ **TP HIT SHORT {coin_name}! +{pnl:.2f}%**\nEntry: ${entry:,.4f} -> Exit: ${price:,.4f}")
                trades[symbol] = None
            elif price >= entry * 1.01:
                pnl = ((entry-price)/entry*100)
                send(f"🚨 **SL HIT SHORT {coin_name}! {pnl:.2f}%**\nEntry: ${entry:,.4f} -> Exit: ${price:,.4f}")
                trades[symbol] = None

def trading_loop():
    print(f"PRO Bot Watching {COINS}")
    while True:
        for coin in COINS:
            try:
                analyze_coin(coin)
                time.sleep(3)
            except Exception as e:
                print(f"{coin} error {e}")
        time.sleep(60)

if BOT_TOKEN:
    threading.Thread(target=trading_loop, daemon=True).start()
    threading.Thread(target=lambda: bot.infinity_polling(), daemon=True).start()

@bot.message_handler(commands=['start','status'])
def handle_start(m):
    msg = "👑 **PRO Confluence Bot**\nEMA200 + Cross + RSI\n\n"
    for coin in COINS:
        name = coin.replace("USDT","")
        closes = get_klines(coin)
        price = get_price(coin)
        if closes and price and len(closes) >= 200:
            e200 = ema(closes, 200)
            r = rsi(closes, 14)
            trend = "Above 200" if price > e200 else "Below 200"
            msg += f"• {name}: ${price:,.2f} | {trend} | RSI {r:.0f}\n"
            if trades[coin]:
                entry = trades[coin]["entry"]
                side = trades[coin]["side"]
                pnl = ((price-entry)/entry*100) if side=="LONG" else ((entry-price)/entry*100)
                msg += f" 📊 IN {side} {pnl:.2f}%\n"
        elif price:
            msg += f"• {name}: ${price:,.2f} | loading EMA...\n"
        else:
            msg += f"• {name}: loading...\n"
    bot.reply_to(m, msg, parse_mode="Markdown")

@bot.message_handler(commands=['price'])
def handle_price(m):
    txt = "💰 **Live Prices + EMA200**\n\n"
    for coin in COINS:
        try:
            p = get_price(coin)
            closes = get_klines(coin)
            name = coin.replace("USDT","")
            if p:
                txt += f"{name}: ${p:,.2f}\n"
            if closes and len(closes) >= 200:
                e200 = ema(closes, 200)
                r = rsi(closes, 14)
                txt += f"EMA200: ${e200:,.2f} | RSI: {r:.0f}\n\n"
            else:
                count = len(closes) if closes else 0
                txt += f"(loading EMA... {count} candles)\n\n"
        except Exception as e:
            txt += f"{coin}: error {e}\n\n"
    bot.reply_to(m, txt, parse_mode="Markdown")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
