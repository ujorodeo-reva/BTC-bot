import os, time, threading, requests
import telebot
from flask import Flask

BOT_TOKEN = os.environ.get("BOT_TOKEN","").strip()
CHAT_ID = os.environ.get("CHAT_ID","").strip()

app = Flask(__name__)
@app.route('/')
def home():
    return "PRO Confluence Bot LIVE - Volume + Momentum Upgraded"

bot = telebot.TeleBot(BOT_TOKEN) if BOT_TOKEN else None

COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
trades = {coin: None for coin in COINS}
BASE_URL = "https://data-api.binance.vision"

def get_klines_full(symbol):
    try:
        url = f"{BASE_URL}/api/v3/klines?symbol={symbol}&interval=5m&limit=250"
        r = requests.get(url, timeout=15)
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            closes = [float(c[4]) for c in data]
            volumes = [float(c[5]) for c in data] # NEW: Volume
            return closes, volumes
        else:
            print(f"Klines error {symbol}: {data}")
            return None, None
    except Exception as e:
        print(f"Klines exception {symbol}: {e}")
        return None, None

def ema(data, period):
    if len(data) < period: return None
    k = 2 / (period + 1)
    ema_val = sum(data[:period]) / period
    for price in data[period:]:
        ema_val = price * k + ema_val * (1 - k)
    return ema_val

def sma(data, period):
    if len(data) < period: return None
    return sum(data[-period:]) / period

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
        url = f"{BASE_URL}/api/v3/ticker/price?symbol={symbol}"
        r = requests.get(url, timeout=10).json()
        return float(r['price'])
    except:
        return None

def send(msg):
    if bot and CHAT_ID:
        try: bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
        except Exception as e: print(f"Send error {e}")

def analyze_coin(symbol):
    closes, volumes = get_klines_full(symbol)
    price = get_price(symbol)
    if not closes or not volumes or not price or len(closes) < 200: return

    ema9 = ema(closes, 9)
    ema21 = ema(closes, 21)
    ema200 = ema(closes, 200)
    ema9_prev = ema(closes[:-1], 9)
    ema21_prev = ema(closes[:-1], 21)
    rsi_val = rsi(closes, 14)
    rsi_prev = rsi(closes[:-1], 14)

    # --- NEW: VOLUME & MOMENTUM CALCULATIONS ---
    vol_ma20 = sma(volumes, 20)
    vol_now = volumes[-1]

    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    if not ema12 or not ema26: return
    macd_line = ema12 - ema26
    macd_signal = ema([ema(c[:i], 12) - ema(c[:i], 26) for i,c in enumerate([closes[:j] for j in range(27, len(closes)+1)], start=27)], 9) # simplified signal
    # Simple MACD hist: current MACD vs previous
    ema12_prev = ema(closes[:-1], 12)
    ema26_prev = ema(closes[:-1], 26)
    macd_prev = ema12_prev - ema26_prev if ema12_prev and ema26_prev else 0
    macd_hist_now = macd_line - macd_prev # momentum rising/falling
    rsi_slope = rsi_val - rsi_prev if rsi_val and rsi_prev else 0

    coin_name = symbol.replace("USDT","")
    if not all([ema9, ema21, ema200, ema9_prev, ema21_prev, rsi_val, vol_ma20]): return

    bullish_cross = ema9_prev <= ema21_prev and ema9 > ema21
    bearish_cross = ema9_prev >= ema21_prev and ema9 < ema21

    # NEW FILTERS
    volume_strong = vol_now > vol_ma20 * 1.2
    momentum_buy = macd_line > 0 and macd_hist_now > 0 and rsi_slope > 0.3
    momentum_sell = macd_line < 0 and macd_hist_now < 0 and rsi_slope < -0.3

    if trades[symbol] is None:
        if price > ema200 and bullish_cross and rsi_val > 55 and rsi_val < 70 and closes[-1] > closes[-2] and volume_strong and momentum_buy:
            trades[symbol] = {"entry": price, "side": "LONG"}
            tp = price * 1.02
            sl = price * 0.99
            send(f"🚀 **HIGH CONFIDENCE LONG {coin_name} [VOL+ MOM CONFIRMED]** 📈\n\nPrice: ${price:,.4f}\n✅ Price > EMA200\n✅ EMA9 CROSS UP EMA21\n✅ RSI: {rsi_val:.1f} rising (+{rsi_slope:.2f})\n✅ Volume: {vol_now:.0f} > Avg {vol_ma20:.0f} (Strong)\n✅ MACD Momentum: Bullish\n\n🎯 TP: ${tp:,.4f} (+2%)\n🛑 SL: ${sl:,.4f} (-1%)")
        elif price < ema200 and bearish_cross and rsi_val < 45 and rsi_val > 30 and closes[-1] < closes[-2] and volume_strong and momentum_sell:
            trades[symbol] = {"entry": price, "side": "SHORT"}
            tp = price * 0.98
            sl = price * 1.01
            send(f"🔻 **HIGH CONFIDENCE SHORT {coin_name} [VOL+ MOM CONFIRMED]** 📉\n\nPrice: ${price:,.4f}\n✅ Price < EMA200\n✅ EMA9 CROSS DOWN EMA21\n✅ RSI: {rsi_val:.1f} falling ({rsi_slope:.2f})\n✅ Volume: {vol_now:.0f} > Avg {vol_ma20:.0f} (Strong)\n✅ MACD Momentum: Bearish\n\n🎯 TP: ${tp:,.4f} (-2%)\n🛑 SL: ${sl:,.4f} (+1%)")
        else:
            # Debug why no trade - helps you see filter working
            if (bullish_cross or bearish_cross):
                reason = []
                if not volume_strong: reason.append("Low Volume")
                if bullish_cross and not momentum_buy: reason.append("Weak Buy Momentum")
                if bearish_cross and not momentum_sell: reason.append("Weak Sell Momentum")
                if reason:
                    print(f"{coin_name} cross but filtered: {', '.join(reason)} | Vol {vol_now:.0f} vs {vol_ma20:.0f}")

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
    print(f"PRO Bot Watching {COINS} with Volume+Momentum")
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
    msg = "👑 **PRO Confluence Bot V2 [Volume + Momentum]**\nEMA200 + Cross + RSI + Vol + MACD\n\n"
    for coin in COINS:
        name = coin.replace("USDT","")
        closes, volumes = get_klines_full(coin)
        price = get_price(coin)
        if closes and volumes and price and len(closes) >= 200:
            e200 = ema(closes, 200)
            r = rsi(closes, 14)
            vol_ma = sma(volumes, 20)
            trend = "Above 200" if price > e200 else "Below 200"
            vol_status = "🔥 Strong" if volumes[-1] > vol_ma*1.2 else "💤 Weak"
            msg += f"• {name}: ${price:,.2f} | {trend} | RSI {r:.0f} | Vol {vol_status}\n"
            if trades[coin]:
                entry = trades[coin]["entry"]
                side = trades[coin]["side"]
                pnl = ((price-entry)/entry*100) if side=="LONG" else ((entry-price)/entry*100)
                msg += f" 📊 IN {side} {pnl:.2f}%\n"
        elif price:
            msg += f"• {name}: ${price:,.2f} | loading...\n"
        else:
            msg += f"• {name}: loading...\n"
    bot.reply_to(m, msg, parse_mode="Markdown")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
