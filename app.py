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

def check_trend():
    df = get_candles()
    last = df.iloc[-1]
    prev = df.iloc[-2]
    price = last['close']
    
    # BUY/SELL Logic
    if prev['EMA9'] < prev['EMA21'] and last['EMA9'] > last['EMA21'] and last['RSI'] < 70:
        send_telegram(f"🟢 BUY SIGNAL! BTC ${price:,.0f}\nEMA9 crossed above EMA21\nRSI: {last['RSI']:.1f} - Uptrend starting!")
    elif prev['EMA9'] > prev['EMA21'] and last['EMA9'] < last['EMA21'] and last['RSI'] > 30:
        send_telegram(f"🔴 SELL SIGNAL! BTC ${price:,.0f}\nEMA9 crossed below EMA21\nRSI: {last['RSI']:.1f} - Downtrend starting!")
    else:
        trend = "BULLISH 📈" if last['EMA9'] > last['EMA21'] else "BEARISH 📉"
        send_telegram(f"💓 Heartbeat - BTC ${price:,.0f} | {trend} | RSI {last['RSI']:.0f}")

def loop():
    while True:
        try:
            check_trend()
        except: pass
        time.sleep(1800) # 30 mins

threading.Thread(target=loop, daemon=True).start()
send_telegram("🚀 RENDER 24/7 BOT LIVE! BUY/SELL Alerts ON ✅")

@app.route('/')
def home():
    return "Bot is Live with BUY/SELL!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
