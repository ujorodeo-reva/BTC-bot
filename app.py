import os, time, threading, requests
import telebot
from flask import Flask

BOT_TOKEN = os.environ.get("BOT_TOKEN","").strip()
CHAT_ID = os.environ.get("CHAT_ID","").strip()

app = Flask(__name__)
@app.route('/')
def home():
    return "PRO Confluence Bot LIVE - Anti-Chop Filters V3"

bot = telebot.TeleBot(BOT_TOKEN) if BOT_TOKEN else None

COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
trades = {coin: None for coin in COINS}
BASE_URL = "https://data-api.binance.vision"

# --- NEW FILTER CONFIG ---
VOL_MIN_MULT = 1.15
VOL_MAX_MULT = 1.6
MAX_DIST_PCT = 0.8
MAX_RSI_JUMP = 10.0

def get_klines_full(symbol):
    try:
        url = f"{BASE_URL}/api/v3/klines?symbol={symbol}&interval=5m&limit=250"
        r = requests.get(url, timeout=15)
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            closes = [float(c[4]) for c in data]
            volumes = [float(c[5]) for c in data]
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

    vol_ma20 = sma(volumes, 20)
    vol_now = volumes[-1]

    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    if not ema12 or not ema26: return

    ema12_prev = ema(closes[:-1], 12)
    ema26_prev = ema(closes[:-1], 26)
    macd_prev = ema12_prev - ema26_prev if ema12_prev and ema26_prev else 0
    macd_line = ema12 - ema26
    macd_hist_now = macd_line - macd_prev
    rsi_slope = rsi_val - rsi_prev if rsi_val and rsi_prev else 0

    coin_name = symbol.replace("USDT","")
    if not all([ema9, ema21, ema200, ema9_prev, ema21_prev, rsi_val, rsi_prev, vol_ma20]): return

    bullish_cross = ema9_prev <= ema21_prev and ema9 > ema21
    bearish_cross = ema9_prev >= ema21_prev and ema9 < ema21

    # --- UPGRADED FILTERS (INJECTED) ---
    vol_mult = vol_now / vol_ma20 if vol_ma20 else 0
    dist_pct = abs(price - ema200) / ema200 * 100
    rsi_jump = rsi_val - rsi_prev

    # Volume must be in early range, not exhausted top
    volume_early = VOL_MIN_MULT < vol_mult < VOL_MAX_MULT
    volume_exhausted = vol_mult >= VOL_MAX_MULT

    # Distance filter
    not_too_far = dist_pct <= MAX_DIST_PCT

    # RSI jump filter
    rsi_not_exhausted_long = rsi_jump <= MAX_RSI_JUMP
    rsi_not_exhausted_short = rsi_jump >= -MAX_RSI_JUMP

    momentum_buy = macd_line > 0 and macd_hist_now > 0 and rsi_slope > 0.3
    momentum_sell = macd_line < 0 and macd_hist_now < 0 and rsi_slope < -0.3

    if trades[symbol] is None:
        # LONG - instant signal only when all PASS
        if price > ema200 and bullish_cross and 55 < rsi_val < 70 and closes[-1] > closes[-2] and volume_early and not_too_far and rsi_not_exhausted_long and momentum_buy:
            trades[symbol] = {"entry": price, "side": "LONG"}
            tp = price * 1.02
            sl = price * 0.99
            send(f"🚀 **LONG {coin_name} [FILTERED V3]** 📈\n\nPrice: ${price:,.4f}\n✅ Price > EMA200 ({dist_pct:.2f}% away)\n✅ EMA9 CROSS UP\n✅ RSI: {rsi_val:.1f} (+{rsi_slope:.2f})\n✅ Vol: {vol_now:.0f} / Avg {vol_ma20:.0f} = {vol_mult:.2f}x early\n✅ MACD Bullish\n\n🎯 TP: ${tp:,.4f} (+2%)\n🛑 SL: ${sl:,.4f} (-1%)")
        # SHORT - instant signal only when all PASS
        elif price < ema200 and bearish_cross and 30 < rsi_val < 45 and closes[-1] < closes[-2] and volume_early and not_too_far and rsi_not_exhausted_short and momentum_sell:
            trades[symbol] = {"entry": price, "side": "SHORT"}
            tp = price * 0.98
            sl = price * 1.01
            send(f"🔻 **SHORT {coin_name} [FILTERED V3]** 📉\n\nPrice: ${price:,.4f}\n✅ Price < EMA200 ({dist_pct:.2f}% away)\n✅ EMA9 CROSS DOWN\n✅ RSI: {rsi_val:.1f} ({rsi_slope:.2f})\n✅ Vol: {vol_now:.0f} / Avg {vol_ma20:.0f} = {vol_mult:.2f}x early\n✅ MACD Bearish\n\n🎯 TP: ${tp:,.4f} (-2%)\n🛑 SL: ${sl:,.4f} (+1%)")
        else:
            if bullish_cross or bearish_cross:
                reasons = []
                if volume_exhausted: reasons.append(f"VOL EXHAUSTED {vol_mult:.2f}x > {VOL_MAX_MULT}x")
                elif not volume_early: reasons.append(f"Vol weak {vol_mult:.2f}x")
                if not not_too_far: reasons.append(f"Too far {dist_pct:.2f}%")
                if bullish_cross and not rsi_not_exhausted_long: reasons.append(f"RSI jump +{rsi_jump:.1f}")
                if bearish_cross and not rsi_not_exhausted_short: reasons.append(f"RSI drop {rsi_jump:.1f}")
                if reasons:
                    print(f"⏭️ {coin_name} SKIP: {', '.join(reasons)} | Price {price}")

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
    print(f"PRO Bot Watching {COINS} with Anti-Chop V3")
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
    msg = "👑 **PRO Bot V3 Anti-Chop**\nEMA200 + Cross + RSI + Vol(1.15-1.6x) + Dist<0.8% + RSI jump\n\n"
    for coin in COINS:
        name = coin.replace("USDT","")
        closes, volumes = get_klines_full(coin)
        price = get_price(coin)
        if closes and volumes and price and len(closes) >= 200:
            e200 = ema(closes, 200)
            r = rsi(closes, 14)
            vol_ma = sma(volumes, 20)
            vol_mult = volumes[-1]/vol_ma if vol_ma else 0
            trend = "Above 200" if price > e200 else "Below 200"
            vol_status = "✅ Early" if 1.15 < vol_mult < 1.6 else "⛔ Exhausted" if vol_mult >= 1.6 else "💤 Weak"
            msg += f"• {name}: ${price:,.2f} | {trend} | RSI {r:.0f} | Vol {vol_mult:.2f}x {vol_status}\n"
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
