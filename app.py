from flask import Flask
import requests, time, pandas as pd, threading

app = Flask(__name__)
TELEGRAM_TOKEN = "7586608380:AAGmYdMJ2Uk30MShVRjh8sp0DtpPguaOB2Q"
TELEGRAM_CHAT_ID = "7484911407"

def send_telegram(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
    except: pass

def get_candles():
    url = "https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=15m&limit=100"
    r = requests.get(url, timeout=10).json()
    data = r['data'][::-1]
    df = pd.DataFrame(data, columns=['time','open','high','low','close','vol','volCcy','volCcyQuote','confirm'])
    df['close'] = df['close'].astype(float)
    df['EMA9'] = df['close'].ewm(span=9).mean()
    df['EMA21'] = df['close'].ewm(span=21).mean()
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rs = gain/loss
    df['RSI'] = 100 - (100/(1+rs))
    return df

def get_price_msg():
    df = get_candles()
    last = df.iloc[-1]
    price = last['close']
    trend = "BULLISH 📈" if last['EMA9'] > last['EMA21'] else "BEARISH 📉"
    return f"₿ BTC Price: ${price:,.2f}\nTrend: {trend}\nEMA9: ${last['EMA9']:,.0f} | EMA21: ${last['EMA21']:,.0f}\nRSI: {last['RSI']:.1f}"

def check_trend():
    df = get_candles()
    last = df.iloc[-1]
    prev = df.iloc[-2]
    price = last['close']
    if prev['EMA9'] < prev['EMA21'] and last['EMA9'] > last['EMA21'] and last['RSI'] < 70:
        send_telegram(f"🟢 BUY SIGNAL! BTC ${price:,.0f}\nEMA9 crossed above EMA21\nRSI: {last['RSI']:.1f}\nTip: Send /buy {price:,.0f} for TP/SL")
    elif prev['EMA9'] > prev['EMA21'] and last['EMA9'] < last['EMA21'] and last['RSI'] > 30:
        send_telegram(f"🔴 SELL SIGNAL! BTC ${price:,.0f}\nEMA9 crossed below EMA21\nRSI: {last['RSI']:.1f}")
    else:
        trend = "BULLISH 📈" if last['EMA9'] > last['EMA21'] else "BEARISH 📉"
        send_telegram(f"💓 Heartbeat - BTC ${price:,.0f} | {trend} | RSI {last['RSI']:.0f}")

def listen_commands():
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={offset}&timeout=5"
            r = requests.get(url, timeout=10).json()
            for update in r.get('result', []):
                offset = update['update_id'] + 1
                msg = update.get('message', {})
                text = msg.get('text', '').lower()
                chat_id = str(msg.get('chat', {}).get('id', ''))
                if chat_id!= TELEGRAM_CHAT_ID: continue

                # /price /trend
                if '/price' in text or '/trend' in text or text.strip() == 'price' or text.strip() == 'trend':
                    send_telegram(get_price_msg())

                # /buy PRICE -> TP/SL CALCULATOR
                elif '/buy' in text:
                    try:
                        parts = text.split()
                        entry = float(parts[1].replace(',', '').replace('$',''))
                        tp1 = entry * 1.02
                        tp2 = entry * 1.05
                        tp3 = entry * 1.10
                        sl = entry * 0.97
                        send_telegram(f"💰 TRADE PLAN for ${entry:,.2f}\n\n🟢 Entry: ${entry:,.2f}\n🎯 TP1 (2%): ${tp1:,.2f}\n🎯 TP2 (5%): ${tp2:,.2f}\n🎯 TP3 (10%): ${tp3:,.2f}\n🔴 Stop Loss (3%): ${sl:,.2f}\n\nRisk/Reward: 1:3.3\nStrategy: Sell 50% at TP1, 30% at TP2, 20% at TP3")
                    except:
                        send_telegram("Use like: /buy 65000 or /buy 114500")

                elif '/help' in text:
                    send_telegram("🤖 COMMANDS:\n/price - Current BTC price & trend\n/trend - Same as price\n/buy 65000 - TP/SL calculator\n/help - This menu")
        except: time.sleep(0.5)
        time.sleep(1)

def loop():
    while True:
        try: check_trend()
        except: pass
        time.sleep(1800)

threading.Thread(target=loop, daemon=True).start()
threading.Thread(target=listen_commands, daemon=True).start()
send_telegram("🚀 ELITE BOT LIVE! Try:\n/price - Price\n/buy 65000 - TP/SL Calculator\n/help - Menu ✅")

@app.route('/')
def home():
    return "Elite Bot Live!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
