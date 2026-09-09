import yfinance as yf
import time
import telebot

TOKEN = "7586608380:AAGmYdMJ2Uk30MShVRjh8sp0DtpPguaOB2Q"
CHAT_ID = "7484911407"
bot = telebot.TeleBot(TOKEN)

# This is the memory - bot will remember if trade open
open_trade = None
entry = 0

def get_data():
    data = yf.download("BTC-USD", period="2d", interval="5m", progress=False)
    data['EMA9'] = data['Close'].ewm(span=9).mean()
    data['EMA21'] = data['Close'].ewm(span=21).mean()
    delta = data['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rs = gain / loss
    data['RSI'] = 100 - (100 / (1 + rs))
    return data

print("Bot started...")

while True:
    try:
        data = get_data()
        last = data.iloc[-1]
        price = float(last['Close'])
        ema9 = float(last['EMA9'])
        ema21 = float(last['EMA21'])
        rsi = float(last['RSI'])

        # ---- IF WE ALREADY HAVE A TRADE ----
        if open_trade is not None:
            print(f"Holding {open_trade} | Entry {entry} | Now {price}")
            
            # Check if BUY still valid
            if open_trade == "BUY":
                if ema9 < ema21: # Trend changed
                    bot.send_message(CHAT_ID, f"⚠️ CANCEL BUY! Trend reversed. Was ${entry:.2f} now ${price:.2f}. Looking for new trade.")
                    open_trade = None
                elif price >= entry * 1.03:
                    bot.send_message(CHAT_ID, f"✅ TP3 DONE! +3%! Trade finished. Profit secured! 💰")
                    open_trade = None
                elif price <= entry * 0.985:
                    bot.send_message(CHAT_ID, f"❌ SL Hit -1.5%. Closed. Next hunt...")
                    open_trade = None
                else:
                    # Check TP1 TP2 for info only
                    if price >= entry * 1.01 and price < entry * 1.015:
                        bot.send_message(CHAT_ID, f"🎯 TP1 +1% hit! Sell 50% now! ${price:.2f}")

            # Check if SELL still valid
            if open_trade == "SELL":
                if ema9 > ema21:
                    bot.send_message(CHAT_ID, f"⚠️ CANCEL SELL! Trend reversed. Looking for new.")
                    open_trade = None
                elif price <= entry * 0.97:
                    bot.send_message(CHAT_ID, f"✅ SELL TP3 DONE! +3%! 💰")
                    open_trade = None

        # ---- IF NO TRADE, FIND NEW ONE ----
        else:
            if ema9 > ema21 and rsi > 40 and rsi < 68:
                entry = price
                open_trade = "BUY"
                bot.send_message(CHAT_ID, f"🟢 5M BUY! BTC ${price:.2f}\nRSI {rsi:.1f}\nTP1 {price*1.01:.2f} | TP2 {price*1.02:.2f} | TP3 {price*1.03:.2f}\nSL {price*0.985:.2f}\n\nI will HOLD this till done. No new signal until this closes or cancels.")
            
            elif ema9 < ema21 and rsi < 60 and rsi > 32:
                entry = price
                open_trade = "SELL"
                bot.send_message(CHAT_ID, f"🔴 5M SELL! BTC ${price:.2f}\nRSI {rsi:.1f}\n\nI will HOLD this till done.")

    except Exception as e:
        print(f"Error: {e}")

    time.sleep(60)
