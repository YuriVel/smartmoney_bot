import telebot
import os
from dotenv import load_dotenv

load_dotenv()
bot = telebot.TeleBot(os.getenv("TG_BOT_TOKEN"))

def notify(signal, symbol):
    if not isinstance(signal, dict):
        raise ValueError(f"Очікується словник, отримано: {type(signal)}")
    message = (
        f"Новий сигнал: {symbol}\n"
        f"Тип: {signal['type']}\n"
        f"Ціна входу: {signal['entry_price']}\n"
        f"SL: {signal['sl']}\n"
        f"TP: {signal['tp']}\n"
        f"Тренд на HTF: {signal['trend']}\n"
        f"OB зона: {signal['ob_zone_low']} - {signal['ob_zone_high']}\n"
        f"Час OB зони: {signal['ob_zone_time']}\n"
        f"CHOCH відбувся: {signal['choch_time']}\n"
        f"Liquidity Sweep: {'Так' if signal['liquidity_sweep'] else 'Ні'}"
    )
    chat_id = os.getenv("TG_CHAT_ID")
    if not chat_id:
        raise ValueError("TG_CHAT_ID не вказано в .env")
    bot.send_message(chat_id=chat_id, text=message)