from notifier import notify
from binance.client import Client
import pandas as pd
import time


#############
#   strategy
#############
def check_entry_signal(htf_data, ltf_data):
    """
    Перевіряє наявність сигналу для входу в межах поточного HTF часу.
    
    Параметри:
    - htf_data: pandas DataFrame із даними HTF
    - ltf_data: pandas DataFrame із даними LTF
    
    Повертає:
    - Словник із сигналом (або None, якщо сигналу немає)
    """
    required_columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']
    if not all(col in htf_data.columns for col in required_columns) or \
       not all(col in ltf_data.columns for col in required_columns):
        return None

    # Поточний HTF час
    current_htf_time = htf_data.iloc[-1]['datetime']

    # Виявлення OB зони на HTF
    ob_zones = detect_ob_zone(htf_data)
    if not ob_zones:
        return None

    # Виявлення CHOCH на LTF, але лише в межах поточного HTF часу
    choch_signals = check_choch(ltf_data[ltf_data['datetime'] <= current_htf_time])
    if not choch_signals:
        return None

    # Виявлення Liquidity Sweep на LTF у межах HTF часу
    liquidity_zones = detect_liquidity_sweep(ltf_data[ltf_data['datetime'] <= current_htf_time])
    if not liquidity_zones:
        return None

    # Вибираємо останню OB зону
    latest_ob_idx = ob_zones[-1]
    zone = {
        'high': htf_data.iloc[latest_ob_idx]['high'],
        'low': htf_data.iloc[latest_ob_idx]['low'],
        'datetime': htf_data.iloc[latest_ob_idx]['datetime']
    }

    # Вибираємо останній CHOCH, якщо він у межах HTF часу
    latest_choch_idx = choch_signals[-1]
    if ltf_data.iloc[latest_choch_idx]['datetime'] > current_htf_time:
        return None  # CHOCH пізніше за HTF час, сигналу немає

    entry_price = ltf_data.iloc[latest_choch_idx]['close']
    
    # Ігнорування нейтральних свічок (доджі)
    close = ltf_data.iloc[latest_choch_idx]['close']
    open_ = ltf_data.iloc[latest_choch_idx]['open']
    if abs(close - open_) < 0.001 * close:  # Різниця < 0.1% від ціни закриття
        return None

    # Визначення тренду на HTF (наприклад, за останні 10 свічок)
    trend_window = min(10, len(htf_data))  # Уникаємо помилки, якщо свічок < 10
    htf_trend = 'bullish' if htf_data['close'].iloc[-1] > htf_data['close'].iloc[-trend_window] else 'bearish'

    # Визначення типу угоди з урахуванням OB зони та тренду
    zone_low = zone['low']
    zone_high = zone['high']
    if entry_price > zone_high and htf_trend == 'bullish':
        trade_type = 'LONG'  # Ціна вище OB зони в бичачому тренді
    elif entry_price < zone_low and htf_trend == 'bearish':
        trade_type = 'SHORT'  # Ціна нижче OB зони в ведмежому тренді
    else:
        return None  # Якщо ціна не відповідає тренду та OB зоні, сигналу немає

    signal = {
        'type': trade_type,
        'entry_price': entry_price,
        'timestamp': ltf_data.iloc[latest_choch_idx]['datetime'],  # Час входу
        'trend': htf_trend,  # Додаємо тренд
        'ob_zone_high': zone_high,  # Верхня межа OB зони
        'ob_zone_low': zone_low,    # Нижня межа OB зони
        'ob_zone_time': zone['datetime'],  # Час OB зони
        'liquidity_sweep': len(liquidity_zones) > 0,  # Чи був Liquidity Sweep
        'choch_time': ltf_data.iloc[latest_choch_idx]['datetime']  # Час CHOCH
    }

    try:
        sl, tp = calculate_tp_sl(signal['entry_price'], zone, rr=2.0)
        signal['sl'] = sl
        signal['tp'] = tp
    except (KeyError, ValueError, TypeError) as e:
        return None

    return signal






#############
#   utils
#############
def calculate_tp_sl(entry, zone, rr=2.0):
    """
    Обчислює рівні стоп-лосс (SL) і тейк-профіт (TP).
    
    Параметри:
    - entry: Ціна входу (float)
    - zone: Словник із полями 'high' і 'low' (цінові рівні зони)
    - rr: Співвідношення ризик:прибуток (float, за замовчуванням 2.0)
    
    Повертає:
    - Кортеж (sl, tp), округлені до 2 знаків після коми
    """
    if not isinstance(zone, dict) or 'high' not in zone or 'low' not in zone:
        raise ValueError("Параметр 'zone' має бути словником із ключами 'high' і 'low'")
    
    sl = zone['low'] if entry > zone['high'] else zone['high']
    risk = abs(entry - sl)
    tp = entry + risk * rr if entry > sl else entry - risk * rr
    return round(sl, 5), round(tp, 5)





#############
#   zones
#############
def detect_ob_zone(df):
    """
    Визначає Order Block зони на основі історичних даних.
    
    Параметри:
    - df: pandas DataFrame із колонками ['open', 'close', 'high', 'low', 'volume']
    
    Повертає:
    - Список індексів, де виявлено OB зони
    """
    required_columns = ['open', 'close', 'high', 'low']
    if not all(col in df.columns for col in required_columns):
        raise ValueError(f"DataFrame має містити колонки: {required_columns}")

    ob_zones = []
    df = df.reset_index(drop=True)
    
    for i in range(1, len(df)):
        if df['close'][i] < df['open'][i - 1] and df['close'][i] < df['low'][i - 1]:
            ob_zones.append(i)
    
    return ob_zones

def check_choch(df):
    """
    Перевіряє Change of Character сигнали.
    
    Параметри:
    - df: pandas DataFrame із колонками ['open', 'close', 'high', 'low']
    
    Повертає:
    - Список індексів, де виявлено CHOCH сигнали
    """
    required_columns = ['open', 'close', 'high', 'low']
    if not all(col in df.columns for col in required_columns):
        raise ValueError(f"DataFrame має містити колонки: {required_columns}")

    choch_signals = []
    df = df.reset_index(drop=True)
    
    for i in range(2, len(df)):
        if df['close'][i] > df['close'][i - 1] and df['close'][i - 1] < df['close'][i - 2]:
            choch_signals.append(i)
    
    return choch_signals

def detect_liquidity_sweep(df):
    """
    Визначає зони Liquidity Sweep.
    
    Параметри:
    - df: pandas DataFrame із колонками ['open', 'close', 'high', 'low', 'volume']
    
    Повертає:
    - Список індексів, де виявлено зони ліквідності
    """
    required_columns = ['open', 'close', 'high', 'low', 'volume']
    if not all(col in df.columns for col in required_columns):
        raise ValueError(f"DataFrame має містити колонки: {required_columns}")

    liquidity_zones = []
    df = df.reset_index(drop=True)
    
    for i in range(2, len(df)):
        if df['volume'][i] > df['volume'][i - 1] and df['close'][i] > df['high'][i - 1]:
            liquidity_zones.append(i)
    
    return liquidity_zones


###########
# main.py
###########

client = Client()  # Додайте ключі API, якщо потрібно

# Список монет для перевірки
symbols = [
    'ONDOUSDT', 
    'ADAUSDT', 
    'BTCUSDT', 
    'ETHUSDT', 
    'JUPUSDT', 
    'LDOUSDT', 
    'AVAXUSDT', 
    'WIFUSDT', 
    'HBARUSDT', 
    'NEARUSDT', 
    'AAVEUSDT', 
    'ARBUSDT', 
    'RENDERUSDT'
] 

htf_interval = Client.KLINE_INTERVAL_1HOUR
ltf_interval = Client.KLINE_INTERVAL_5MINUTE

# Словник для зберігання останніх сигналів для кожної монети
last_signals = {symbol: None for symbol in symbols}

while True:
    try:
        for symbol in symbols:
            print(f"Перевірка сигналу для {symbol}...")
            
            # Отримання даних
            candles_htf_raw = client.get_historical_klines(symbol, htf_interval, "1 day ago UTC")
            candles_ltf_raw = client.get_historical_klines(symbol, ltf_interval, "1 day ago UTC")

            # Перевірка на порожні дані
            if not candles_htf_raw or not candles_ltf_raw:
                print(f"Помилка: Дані для {symbol} не отримано")
                continue

            # Перетворення в DataFrame
            columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 
                       'close_time', 'quote_asset_volume', 'trades', 'taker_buy_base', 
                       'taker_buy_quote', 'ignored']
            candles_htf = pd.DataFrame(candles_htf_raw, columns=columns)
            candles_ltf = pd.DataFrame(candles_ltf_raw, columns=columns)

            # Конвертація типів і формату
            candles_htf['datetime'] = pd.to_datetime(candles_htf['timestamp'], unit='ms')
            candles_ltf['datetime'] = pd.to_datetime(candles_ltf['timestamp'], unit='ms')
            candles_htf[['open', 'high', 'low', 'close', 'volume']] = candles_htf[['open', 'high', 'low', 'close', 'volume']].astype(float)
            candles_ltf[['open', 'high', 'low', 'close', 'volume']] = candles_ltf[['open', 'high', 'low', 'close', 'volume']].astype(float)

            # Залишаємо тільки потрібні колонки
            candles_htf = candles_htf[['datetime', 'open', 'high', 'low', 'close', 'volume']]
            candles_ltf = candles_ltf[['datetime', 'open', 'high', 'low', 'close', 'volume']]

            # Перевірка сигналу
            signal = check_entry_signal(candles_htf, candles_ltf)
            
            # Якщо є новий сигнал
            if signal and signal != last_signals[symbol]:
                notify(signal, symbol)  # Передаємо symbol у notify
                print(f"Новий сигнал {symbol}: {signal}")
                last_signals[symbol] = signal
            else:
                print(f"Сигналу немає або він не змінився для {symbol}")

        # Затримка перед наступною перевіркою всіх монет
        print("Очікування наступного циклу...")
        time.sleep(30)

    except Exception as e:
        print(f"Помилка: {e}")
        time.sleep(30)