import telebot
import os
from dotenv import load_dotenv

load_dotenv()
bot = telebot.TeleBot(os.getenv("TG_BOT_TOKEN"), parse_mode="MarkdownV2")


def escape_md(text):
    escape_chars = r'\_*[]()~`>#+-=|{}.!'
    text = str(text)
    return ''.join(f'\\{c}' if c in escape_chars else c for c in text)

def notify(signal, symbol):
    if not isinstance(signal, dict):
        raise ValueError(f"Очікується словник, отримано: {type(signal)}")

    chat_id = os.getenv("TG_CHAT_ID")
    if not chat_id:
        raise ValueError("TG_CHAT_ID не вказано в .env")


    # Формування повідомлення
    message = (
        f"\\#{escape_md(symbol)} — {'🟢' if signal['type'].lower() == 'long' else '🔴'} {escape_md(signal['type'])}\n"
        f"🚪 Enter: {escape_md(signal['entry_price'])} \\| ⛔ SL: {escape_md(signal['sl'])} \\| 🎯 TP: {escape_md(signal['tp'])}\n"
        f"\n"
        f"HTF Trend: {'📈' if signal['trend'].lower() == 'bearish' else '📉'} {escape_md(signal['trend'])} \\| 🟨 OB: {escape_md(signal['ob_zone_low'])}–{escape_md(signal['ob_zone_high'])}\n"
        f"⏱ {escape_md(signal['ob_zone_time'])} \\| ⚡ CHOCH: {escape_md(signal['choch_time'])}\n"
        f"💧 Sweep: {escape_md('✅' if signal['liquidity_sweep'] else '❌')}"
    )


    bot.send_message(chat_id=chat_id, text=message)
