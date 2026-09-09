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
        send_telegram(f"🟢 BUY SIGNAL! BTC ${price:,.0f}\nEMA9 crossed above EMA21\nRSI: {last['RSI']:.1f}")
    elif prev['EMA9'] > prev['EMA21'] and last['EMA9'] < last['EMA21'] and last['RSI'] > 30:
        send_telegram(f"🔴 SELL SIGNAL! BTC ${price:,.0f}\nEMA9 crossed below EMA21\nRSI: {last['RSI']:.1f}")
    else:
        trend = "BULLISH 📈" if last['EMA9'] > last['EMA21'] else "BEARISH 📉"
        send_telegram(f"💓 Heartbeat - BTC ${price:,.0f} | {trend} | RSI {last['RSI']:.0f}")

# LISTEN FOR /price and /trend COMMANDS
def listen_commands():
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={offset}&timeout=20"
            r = requests.get(url, timeout=10).json()
            for update in r.get('result', []):
                offset = update['update_id'] + 1
                msg = update.get('message', {})
                text = msg.get('text', '').lower()
                chat_id = str(msg.get('chat', {}).get('id', ''))
                if chat_id != TELEGRAM_CHAT_ID: continue
                if '/price' in text or '/trend' in text or 'price' in text or 'trend' in text:
                    send_telegram(get_price_msg())
        except: time.sleep(0.5)
        time.sleep(1)

def loop():
    while True:
        try: check_trend()
        except: pass
        time.sleep(1800)

threading.Thread(target=loop, daemon=True).start()
threading.Thread(target=listen_commands, daemon=True).start()
send_telegram("🚀 BOT UPGRADED! Now send /price or /trend and I will reply instantly ✅")

@app.route('/')
def home():
    return "Bot Live with Commands!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
