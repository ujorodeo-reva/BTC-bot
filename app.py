from flask import Flask
import requests, time, pandas as pd, threading

app = Flask(__name__)
TELEGRAM_TOKEN = "7586608380:AAGmYdMJ2Uk30MShVRjh8sp0DtpPguaOB2Q"
TELEGRAM_CHAT_ID = "7484911407"
COINS = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "BNB-USDT"]

# Store your active trades
active_trades = []

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

def get_price(instId):
    try:
        df = get_candles(instId)
        return float(df.iloc[-1]['close'])
    except: return None

def check_trades():
    global active_trades
    for trade in active_trades[:]:
        price = get_price(f"{trade['coin']}-USDT")
        if not price: continue
        entry = trade['entry']
        pnl = ((price-entry)/entry)*100
        if price >= trade['tp1'] and not trade['hit1']:
            trade['hit1']=True
            send_telegram(f"🎯 TP1 HIT! {trade['coin']} +1%!\nEntry ${entry:.2f} -> Now ${price:.2f} (+{pnl:.2f}%)\n💰 Take 50% profit & move SL to breakeven!")
        if price >= trade['tp2'] and not trade['hit2']:
            trade['hit2']=True
            send_telegram(f"🎯🎯 TP2 HIT! {trade['coin']} +2%!\nEntry ${entry:.2f} -> Now ${price:.2f} (+{pnl:.2f}%)\n🔥 Take another 30%!")
        if price >= trade['tp3'] and not trade['hit3']:
            trade['hit3']=True
            send_telegram(f"🚀 TP3 HIT! {trade['coin']} +3%! FULL TARGET!\nEntry ${entry:.2f} -> Now ${price:.2f} (+{pnl:.2f}%)\n🏆 CLOSE ALL & CELEBRATE!")
            active_trades.remove(trade)
        if price <= trade['sl']:
            send_telegram(f"🔴 SL HIT! {trade['coin']} -1.5%\nEntry ${entry:.2f} -> Now ${price:.2f} ({pnl:.2f}%)\nCut loss, next trade!")
            active_trades.remove(trade)

def get_all_prices_msg():
    msg = "⚡ 5M SCALPER LIVE:\n\n"
    for coin in COINS:
        try:
            df = get_candles(coin)
            last = df.iloc[-1]
            trend = "BULLISH 📈" if last['EMA9'] > last['EMA21'] else "BEARISH 📉"
            msg += f"{coin.split('-')[0]}: ${last['close']:,.2f} {trend} RSI {last['RSI']:.0f}\n"
        except: pass
    if active_trades:
        msg += f"\n📌 Active Trades: {len(active_trades)} watching..."
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
                send_telegram(f"🟢 5M BUY SIGNAL! {name} ${price:,.2f}\nEMA9 > EMA21 Uptrend\nRSI: {last['RSI']:.1f}\nSend /buy {name} {price:.0f} to track it!")
            elif prev['EMA9'] > prev['EMA21'] and last['EMA9'] < last['EMA21'] and last['RSI'] > 30:
                send_telegram(f"🔴 5M SELL SIGNAL! {name} ${price:,.2f}\nEMA9 < EMA21 Downtrend\nRSI: {last['RSI']:.1f}")
        except: pass

def listen_commands():
    global active_trades
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
                if '/price' in low:
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
                        active_trades.append({"coin":coin,"entry":entry,"tp1":tp1,"tp2":tp2,"tp3":tp3,"sl":sl,"hit1":False,"hit2":False,"hit3":False})
                        send_telegram(f"⚡ {coin} TRACKING STARTED ${entry:,.2f}\n\n🎯 TP1: ${tp1:,.2f} (+1%)\n🎯 TP2: ${tp2:,.2f} (+2%)\n🎯 TP3: ${tp3:,.2f} (+3%)\n🔴 SL: ${sl:,.2f} (-1.5%)\n\nI will alert you when TP/SL hits!")
                    except:
                        send_telegram("Use: /buy BTC 65000 or /buy SOL 180")
                elif '/trades' in low:
                    if not active_trades:
                        send_telegram("No active trades. Send /buy BTC 65000 to start tracking.")
                    else:
                        tmsg = f"📌 Active ({len(active_trades)}):\n"
                        for t in active_trades:
                            tmsg += f"{t['coin']} Entry ${t['entry']:.2f}\n"
                        send_telegram(tmsg)
                elif '/help' in low:
                    send_telegram("⚡ 5M MONSTER + AUTO TP:\n/price - trends\n/buy BTC 65000 - start auto TP alerts\n/trades - see tracked trades\n/help - menu")
        except: time.sleep(0.5)
        time.sleep(1)

def loop():
    while True:
        try:
            check_all_trends()
            check_trades()
        except: pass
        time.sleep(180)

threading.Thread(target=loop, daemon=True).start()
threading.Thread(target=listen_commands, daemon=True).start()
send_telegram("🔔 AUTO TP ALERTS LIVE! Now tracking TP1/TP2/TP3 hits! Send /buy BTC 65000 to test!")

@app.route('/')
def home():
    return "5M Monster + Auto TP Live!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
