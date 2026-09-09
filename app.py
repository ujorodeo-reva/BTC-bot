from flask import Flask
import requests, time, pandas as pd, threading

app = Flask(__name__)
TELEGRAM_TOKEN = "7586608380:AAGmYdMJ2Uk30MShVRjh8sp0DtpPguaOB2Q"
TELEGRAM_CHAT_ID = "7484911407"

def send_telegram(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
    except: pass

def get_candles():
    url = "https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=5m&limit=300"
    r = requests.get(url, timeout=10).json()
    data = r['data'][::-1]
    df = pd.DataFrame(data, columns=['time','open','high','low','close','vol','volCcy','volCcyQuote','confirm'])
    df['close'] = df['close'].astype(float)
    df['EMA9'] = df['close'].ewm(span=9).mean()
    df['EMA21'] = df['close'].ewm(span=21).mean()
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + gain/loss))
    return df

def bot_loop():
    position = None
    entry_price = 0
    last_heartbeat = 0
    send_telegram("🚀 RENDER 24/7 BOT LIVE! EMA 9/21 + 30min Heartbeat. Will never sleep ✅")
    while True:
        try:
            df = get_candles()
            curr, prev = df.iloc[-1], df.iloc[-2]
            price, rsi = curr['close'], curr['RSI']
            long_signal = prev['EMA9'] < prev['EMA21'] and curr['EMA9'] > curr['EMA21']
            short_signal = prev['EMA9'] > prev['EMA21'] and curr['EMA9'] < curr['EMA21']
            if time.time() - last_heartbeat > 1800:
                send_telegram(f"💓 Render Alive | BTC ${price:.0f} | RSI {rsi:.0f} | Pos: {position or 'WAITING'}")
                last_heartbeat = time.time()
            if position:
                pnl = (price-entry_price)/entry_price*100 if position=='LONG' else (entry_price-price)/entry_price*100
                if pnl <= -0.8:
                    send_telegram(f"🛑 CLOSE {position} SL {pnl:.2f}% at ${price:.0f}")
                    position = None
                elif pnl >= 1.2:
                    send_telegram(f"✅ CLOSE {position} TP +{pnl:.2f}% at ${price:.0f}!")
                    position = None
            if not position:
                if long_signal:
                    position='LONG'; entry_price=price
                    send_telegram(f"🟢 BUY LONG ${price:.0f} RSI {rsi:.0f}\nAction: $5 Long 2x | SL {price*0.992:.0f} TP {price*1.012:.0f}")
                elif short_signal:
                    position='SHORT'; entry_price=price
                    send_telegram(f"🔴 SELL SHORT ${price:.0f} RSI {rsi:.0f}\nAction: $5 Short 2x | SL {price*1.008:.0f} TP {price*0.988:.0f}")
            time.sleep(60)
        except Exception as e:
            print(e); time.sleep(30)

@app.route('/')
def home():
    return "Bot is running 24/7"

threading.Thread(target=bot_loop, daemon=True).start()
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
