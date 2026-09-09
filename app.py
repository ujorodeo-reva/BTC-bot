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
    url = f"https://www.okx.com/api/v5/market/candles?instId={instId}&bar=15m&limit=100"
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
    msg = "💰 LIVE PRICES:\n\n"
    for coin in COINS:
        try:
            df = get_candles(coin)
            last = df.iloc[-1]
            trend = "📈" if last['EMA9'] > last['EMA21'] else "📉"
            msg += f"{coin.split('-')[0]}: ${last['close']:,.2f} {trend} RSI {last['RSI']:.0f}\n"
        except: pass
    msg += "\nUse /buy BTC 65000 for TP/SL"
    return msg

def check_all_trends():
    for coin in COINS:
        try:
            df = get_candles(coin)
            last = df.iloc[-1]
            prev = df.iloc[-2]
            price = last['close']
            name = coin.split('-')[0]
            if prev['EMA9'] < prev['EMA21'] and last['EMA9'] > last['EMA21'] and last['RSI'] < 70:
                send_telegram(f"🟢 BUY SIGNAL! {name} ${price:,.2f}\nEMA9 crossed above EMA21 | RSI {last['RSI']:.0f}\nSend /buy {name} {price:.0f} for TP/SL")
            elif prev['EMA9'] > prev['EMA21'] and last['EMA9'] < last['EMA21'] and last['RSI'] > 30:
                send_telegram(f"🔴 SELL SIGNAL! {name} ${price:,.2f}\nEMA9 crossed below EMA21 | RSI {last['RSI']:.0f}")
        except: pass
    # Heartbeat summary
    try: send_telegram(get_all_prices_msg())
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

                if '/price' in low or '/trend' in low or '/prices' in low or low == 'price':
                    send_telegram(get_all_prices_msg())

                elif '/buy' in low:
                    try:
                        parts = text.split()
                        if len(parts) == 3: # /buy BTC 65000
                            coin = parts[1].upper()
                            entry = float(parts[2].replace(',','').replace('$',''))
                        else: # /buy 65000
                            coin = "BTC"
                            entry = float(parts[1].replace(',','').replace('$',''))
                        tp1 = entry * 1.02
                        tp2 = entry * 1.05
                        tp3 = entry * 1.10
                        sl = entry * 0.97
                        send_telegram(f"💰 {coin} TRADE PLAN for ${entry:,.2f}\n\n🟢 Entry: ${entry:,.2f}\n🎯 TP1 (2%): ${tp1:,.2f}\n🎯 TP2 (5%): ${tp2:,.2f}\n🎯 TP3 (10%): ${tp3:,.2f}\n🔴 SL (3%): ${sl:,.2f}\n\nRisk/Reward 1:3.3\nSell 50% at TP1, 30% at TP2, 20% at TP3")
                    except:
                        send_telegram("Use: /buy 65000 OR /buy BTC 65000 OR /buy ETH 3000")

                elif '/help' in low:
                    send_telegram("🤖 MONSTER BOT COMMANDS:\n/price - All 4 coins price\n/buy 65000 - BTC TP/SL\n/buy ETH 3000 - ETH TP/SL\n/buy SOL 150 - SOL TP/SL\n/help - Menu\n\nBot watches: BTC, ETH, SOL, BNB 24/7")
        except: time.sleep(0.5)
        time.sleep(1)

def loop():
    while True:
        try: check_all_trends()
        except: pass
        time.sleep(1800)

threading.Thread(target=loop, daemon=True).start()
threading.Thread(target=listen_commands, daemon=True).start()
send_telegram("👹 MONSTER BOT LIVE! Watching BTC, ETH, SOL, BNB 24/7\nTry /price and /buy ETH 3000 ✅")

@app.route('/')
def home():
    return "Monster Bot Live - 4 Coins!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
