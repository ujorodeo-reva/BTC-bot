from flask import Flask
import requests, time, pandas as pd, threading

app = Flask(__name__)
TELEGRAM_TOKEN = "7586608380:AAGmYdMJ2Uk30MShVRjh8sp0DtpPguaOB2Q"
TELEGRAM_CHAT_ID = "7484911407"

COINS = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "BNB-USDT"]

def send_telegram(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
    except: pass

def get_candles(instId):
    url = f"https://www.okx.com/api/v5/market/candles?instId={instId}&bar=5m&limit=100"
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

def get_all_prices_msg():
    msg = "⚡ 5M SCALPER LIVE PRICES:\n\n"
    for coin in COINS:
        try:
            df = get_candles(coin)
            last = df.iloc[-1]
            trend = "BULLISH 📈" if last['EMA9'] > last['EMA21'] else "BEARISH 📉"
            msg += f"{coin.split('-')[0]}: ${last['close']:,.2f} {trend} RSI {last['RSI']:.0f}\n"
        except: pass
    return msg

def check_all_trends():
    for coin in COINS:
        try:
            df = get_candles(coin)
            last = df.iloc[-1]
            prev = df.iloc[-2]
            price = last['close']
            name = coin.split('-')[0]
            # Trend following on 5m
            if prev['EMA9'] < prev['EMA21'] and last['EMA9'] > last['EMA21'] and last['RSI'] < 70:
                send_telegram(f"🟢 5M BUY SIGNAL! {name} ${price:,.2f}\nTrend: EMA9 > EMA21 (UpTrend)\nRSI: {last['RSI']:.1f}\nScalp Targets: +1% +2%\nSend /buy {name} {price:.0f}")
            elif prev['EMA9'] > prev['EMA21'] and last['EMA9'] < last['EMA21'] and last['RSI'] > 30:
                send_telegram(f"🔴 5M SELL SIGNAL! {name} ${price:,.2f}\nTrend: EMA9 < EMA21 (DownTrend)\nRSI: {last['RSI']:.1f}")
        except: pass

def listen_commands():
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={offset}&timeout=5"
            r = requests.get(url, timeout=10).json()
            for update in r.get('result', []):
                offset = update['update_id'] + 1
                msg = update.get('message', {})
                text = msg.get('text', '').strip()
                low = text.lower()
                chat_id = str(msg.get('chat', {}).get('id', ''))
                if chat_id!= TELEGRAM_CHAT_ID: continue
                if '/price' in low or '/prices' in low:
                    send_telegram(get_all_prices_msg())
                elif '/buy' in low:
                    try:
                        parts = text.split()
                        if len(parts) == 3:
                            coin = parts[1].upper()
                            entry = float(parts[2].replace(',','').replace('$',''))
                        else:
                            coin = "BTC"
                            entry = float(parts[1].replace(',','').replace('$',''))
                        tp1 = entry * 1.01
                        tp2 = entry * 1.02
                        tp3 = entry * 1.03
                        sl = entry * 0.985
                        send_telegram(f"⚡ {coin} 5M SCALP PLAN ${entry:,.2f}\n\n🟢 Entry: ${entry:,.2f}\n🎯 TP1 (1%): ${tp1:,.2f}\n🎯 TP2 (2%): ${tp2:,.2f}\n🎯 TP3 (3%): ${tp3:,.2f}\n🔴 SL (1.5%): ${sl:,.2f}\n\nFor 5M scalping, take profit FAST!")
                    except:
                        send_telegram("Use: /buy BTC 65000")
                elif '/help' in low:
                    send_telegram("⚡ 5M SCALPER BOT:\n/price - 4 coins trend (5m)\n/buy BTC 65000 - Scalp TP/SL (1%,2%,3%)\nWatching: BTC, ETH, SOL, BNB on 5M timeframe 24/7")
        except: time.sleep(0.5)
        time.sleep(1)

def loop():
    while True:
        try: check_all_trends()
        except: pass
        time.sleep(300) # Check every 5 minutes = matches timeframe!

threading.Thread(target=loop, daemon=True).start()
threading.Thread(target=listen_commands, daemon=True).start()
send_telegram("⚡ 5M SCALPER MONSTER LIVE! Watching BTC,ETH,SOL,BNB on 5M timeframe - Trend Following Trades ACTIVE!")

@app.route('/')
def home():
    return "5M Scalper Monster Live!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
