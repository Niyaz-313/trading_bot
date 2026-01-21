"""
Конфигурационный файл для торгового бота
"""
import os
from dotenv import load_dotenv

# Загружаем .env файл (пробуем разные варианты имени)
if os.path.exists('.env'):
    load_dotenv('.env')
elif os.path.exists('.env.txt'):
    load_dotenv('.env.txt')
    print("⚠ ВНИМАНИЕ: Используется файл .env.txt. Рекомендуется переименовать в .env")
else:
    load_dotenv()  # Пробуем загрузить по умолчанию

# Telegram настройки
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# Брокерские настройки - T-Invest API (Т-Инвестиции)
TINVEST_TOKEN = os.getenv('TINVEST_TOKEN', '')  # Токен T-Invest API
TINVEST_SANDBOX = os.getenv('TINVEST_SANDBOX', 'true').lower() == 'true'  # Использовать песочницу
TINVEST_ACCOUNT_ID = os.getenv('TINVEST_ACCOUNT_ID', '')  # ID счета (опционально, если не указан - используется первый доступный)
# (опционально) gRPC target для SDK. Если пусто — используем стандартный sandbox target из SDK или fallback.
TINVEST_GRPC_TARGET = os.getenv("TINVEST_GRPC_TARGET", "").strip()

# Брокерские настройки - Alpaca API (старая поддержка, опционально)
ALPACA_API_KEY = os.getenv('ALPACA_API_KEY', '')
ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET_KEY', '')
ALPACA_BASE_URL = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')

# Выбор брокера (в этой сборке поддерживается tinvest; alpaca оставлен как legacy-параметр)
BROKER = os.getenv('BROKER', 'tinvest').lower()  # По умолчанию T-Invest

# Торговые настройки
# Для T-Invest используйте российские тикеры (SBER, GAZP, YNDX и т.д.)
# В этом проекте исторические данные для РФ берутся через T-Invest API (Yahoo/yfinance не используется).
SYMBOLS_RAW = os.getenv(
    'SYMBOLS',
    # База ликвидных акций РФ + доп. “сырьевые” (нефть/металлы) + валютные инструменты/ETF
    # Примечание по валюте: в sandbox список инструментов может отличаться от “привычных” тикеров.
    # Мы включаем те, что реально находятся через instruments.currencies() в песочнице.
    'SBER,GAZP,YNDX,VTBR,MOEX,LKOH,ROSN,NVTK,GMKN,TATN,MGNT,AFLT,SNGS,SNGSP,CHMF,NLMK,MAGN,MTSS,IRAO,ALRS,PHOR,PLZL,RUAL,AFKS,TRNFP,SIBN,FLOT,BANE,BANEP,RNFT,TATNP,SELG,UGLD,LNZL,USD000UTSTOM,CNYRUB_TOM,GLDRUB_TOM,SLVRUB_TOM,PLTRUB_TOM,PLDRUB_TOM',
)
SYMBOLS = [s.strip() for s in SYMBOLS_RAW.split(',')] if SYMBOLS_RAW else ['SBER', 'GAZP', 'YNDX']
INITIAL_CAPITAL = float(os.getenv('INITIAL_CAPITAL', '10000'))  # Начальный капитал
MAX_POSITION_SIZE = float(os.getenv('MAX_POSITION_SIZE', '0.20'))  # Максимальный размер позиции (20% от капитала)
STOP_LOSS_PERCENT = float(os.getenv('STOP_LOSS_PERCENT', '0.03'))  # Стоп-лосс 3% - увеличен для снижения ложных срабатываний
TAKE_PROFIT_PERCENT = float(os.getenv('TAKE_PROFIT_PERCENT', '0.06'))  # Тейк-профит 6% - увеличен для большей прибыли
# Риск на сделку (доля капитала). Используется для ATR/стоп-ориентированного позиционирования.
# ОПТИМИЗИРОВАНО (2026-01-16): увеличено с 0.005 (0.5%) до 0.01 (1%) для компенсации комиссий при активной торговле
RISK_PER_TRADE = float(os.getenv('RISK_PER_TRADE', '0.01'))  # 1% по умолчанию

# Backtest настройки (используются в backtest.py и диагностике)
BACKTEST_PERIOD = os.getenv("BACKTEST_PERIOD", "2y").strip()
BACKTEST_STRATEGY = os.getenv("BACKTEST_STRATEGY", "best").strip().lower()
COOLDOWN_DAYS = int(os.getenv("COOLDOWN_DAYS", "10"))

# Настройки стратегии (оптимизированы для прибыльности)
RSI_PERIOD = int(os.getenv('RSI_PERIOD', '14'))
RSI_OVERSOLD = int(os.getenv('RSI_OVERSOLD', '30'))  # Оптимальный уровень для покупки
RSI_OVERBOUGHT = int(os.getenv('RSI_OVERBOUGHT', '70'))  # Оптимальный уровень для продажи
MA_SHORT_PERIOD = int(os.getenv('MA_SHORT_PERIOD', '20'))
MA_LONG_PERIOD = int(os.getenv('MA_LONG_PERIOD', '50'))
MACD_FAST = int(os.getenv('MACD_FAST', '12'))
MACD_SLOW = int(os.getenv('MACD_SLOW', '26'))
MACD_SIGNAL = int(os.getenv('MACD_SIGNAL', '9'))

# Настройки обновления
UPDATE_INTERVAL = int(os.getenv('UPDATE_INTERVAL', '300'))  # Интервал обновления в секундах (5 минут для стабильности)
ENABLE_TRADING = os.getenv('ENABLE_TRADING', 'true').lower() == 'true'

# Live-торговля (реальное время / песочница)
BAR_INTERVAL = os.getenv("BAR_INTERVAL", "5m")  # интервал свечей для стратегии
HISTORY_LOOKBACK = os.getenv("HISTORY_LOOKBACK", "5d")  # сколько истории брать каждый цикл
# ОПТИМИЗИРОВАНО (2026-01-19): снижено до 0.42 для увеличения количества сделок с сохранением качества
# При 1 сигнале требуется confidence >= 0.55, при 2+ сигналах >= 0.42
MIN_CONF_BUY = float(os.getenv("MIN_CONF_BUY", "0.42"))
MIN_CONF_SELL = float(os.getenv("MIN_CONF_SELL", "0.50"))
# Для SELL по сигналу: “сильный” порог уверенности (уменьшает churn/комиссии).
MIN_CONF_SELL_STRONG = float(os.getenv("MIN_CONF_SELL_STRONG", "0.65"))
# Требуем N подряд подтверждений sell-сигнала, прежде чем закрывать позицию “по сигналу”.
SELL_CONFIRM_BARS = int(os.getenv("SELL_CONFIRM_BARS", "2"))
MAX_TRADES_PER_DAY = int(os.getenv("MAX_TRADES_PER_DAY", "50"))  # Увеличено до 50 для достижения 10+ сделок в день

# Глобальные фильтры качества BUY (для режима "качество входов"):
# если включены, резко уменьшают число входов, но повышают шанс "плюса" (меньше входов против рынка).
REQUIRE_TREND_UP_BUY = os.getenv("REQUIRE_TREND_UP_BUY", "false").lower() == "true"
MIN_VOLUME_RATIO_BUY = float(os.getenv("MIN_VOLUME_RATIO_BUY", "0.0"))  # volume/volume_ma, 0 = не проверять
REQUIRE_MACD_RISING_BUY = os.getenv("REQUIRE_MACD_RISING_BUY", "false").lower() == "true"

# Логику стопа/тейка в live можно привязать к ATR (меньше “ложных” стопов и лучше контроль риска).
ATR_STOP_MULT = float(os.getenv("ATR_STOP_MULT", "2.0"))
ATR_TAKE_MULT = float(os.getenv("ATR_TAKE_MULT", "3.0"))
ATR_TRAIL_MULT = float(os.getenv("ATR_TRAIL_MULT", "2.0"))
LIVE_POSITION_SIZING = os.getenv("LIVE_POSITION_SIZING", "risk").strip().lower()  # "risk" | "max_position"

# Фильтр качества входа для шумных/дешёвых бумаг (Recommendation D)
NOISY_SYMBOLS_RAW = os.getenv("NOISY_SYMBOLS", "VTBR").strip()
NOISY_SYMBOLS = [s.strip().upper() for s in NOISY_SYMBOLS_RAW.split(",") if s.strip()] if NOISY_SYMBOLS_RAW else []
# ОПТИМИЗИРОВАНО (2026-01-16): ослаблены фильтры для шумных символов, чтобы не блокировать 19+ сигналов
NOISY_REQUIRE_TREND_UP = os.getenv("NOISY_REQUIRE_TREND_UP", "false").lower() == "true"  # Отключено по умолчанию
NOISY_VOLUME_RATIO_MIN = float(os.getenv("NOISY_VOLUME_RATIO_MIN", "1.0"))  # Снижено с 1.2 до 1.0
NOISY_MACD_HIST_MIN = float(os.getenv("NOISY_MACD_HIST_MIN", "0.0"))  # >0 = только положительный импульс
NOISY_REQUIRE_MACD_RISING = os.getenv("NOISY_REQUIRE_MACD_RISING", "false").lower() == "true"  # Отключено по умолчанию
NOISY_MIN_CONF_BUY = float(os.getenv("NOISY_MIN_CONF_BUY", "0.60"))  # Снижено с 0.70 до 0.60

# Ранжирование BUY-кандидатов: сколько лучших входов можно совершить за один цикл.
# ОПТИМИЗИРОВАНО (2026-01-17): увеличено до 5 для достижения 10+ сделок в день
MAX_BUYS_PER_CYCLE = int(os.getenv("MAX_BUYS_PER_CYCLE", "5"))

# Расширенное audit-логирование (для последующей оптимизации стратегии)
AUDIT_DECISIONS = os.getenv("AUDIT_DECISIONS", "true").lower() == "true"
AUDIT_MARKET = os.getenv("AUDIT_MARKET", "true").lower() == "true"
AUDIT_DECISION_EVERY_N = int(os.getenv("AUDIT_DECISION_EVERY_N", "1"))  # 1 = каждый цикл, 2 = через цикл, ...

def _parse_percent(value: str, default: float) -> float:
    try:
        v = str(value).strip()
        if v.endswith("%"):
            return float(v[:-1].strip()) / 100.0
        return float(v)
    except Exception:
        return float(default)

DAILY_LOSS_LIMIT_PCT = _parse_percent(os.getenv("DAILY_LOSS_LIMIT_PCT", "0.02"), 0.02)  # 2% дневной лимит убытка
MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", "10"))  # Увеличено до 10 для достижения 10+ сделок в день
SYMBOL_COOLDOWN_MIN = int(os.getenv("SYMBOL_COOLDOWN_MIN", "10"))  # Снижено до 10 минут для большей активности
AUTO_START = os.getenv("AUTO_START", "true").lower() == "true"

# Если внутри дня equity "скачет" слишком сильно (например, из-за sandbox_pay_in),
# дневную базу корректнее брать ПОСЛЕ последнего такого скачка.
# Это защищает статистику и дневной риск-лимит от искажения пополнениями.
DAILY_CASHFLOW_JUMP_PCT = _parse_percent(os.getenv("DAILY_CASHFLOW_JUMP_PCT", "30%"), 0.30)

# Минимальная “дистанция” для ATR-трейлинга (чтобы стоп не становился слишком плотным при маленьком ATR,
# что приводит к частым stop_loss и падению прибыльности).
# Можно задавать как долю (0.0075) или процент ("0.75%").
_DEFAULT_TRAIL_MIN_PCT = max(0.005, float(STOP_LOSS_PERCENT) / 4.0)  # минимум 0.5%, по умолчанию ~0.75% при SL=3%
TRAIL_MIN_PCT = _parse_percent(os.getenv("TRAIL_MIN_PCT", str(_DEFAULT_TRAIL_MIN_PCT)), _DEFAULT_TRAIL_MIN_PCT)

# Минимальный тейк-профит (чтобы take_profit не был “слишком близко” и не проигрывал комиссиям/спреду).
# Можно задавать как долю (0.0075) или процент ("0.75%").
TAKE_MIN_PCT = _parse_percent(os.getenv("TAKE_MIN_PCT", "0.75%"), 0.0075)

# Логирование
# ОПТИМИЗИРОВАНО (2026-01-19): логи в поддиректорию для удобства на сервере
LOG_FILE = os.getenv("LOG_FILE", "logs/trading_bot.log")
AUDIT_LOG_PATH = os.getenv("AUDIT_LOG_PATH", "audit_logs/trades_audit.jsonl")
AUDIT_CSV_PATH = os.getenv("AUDIT_CSV_PATH", "audit_logs/trades_audit.csv")

# Временная зона для дневной статистики (используется в /day и дневной просадке)
LOCAL_TIMEZONE = os.getenv("LOCAL_TIMEZONE", "Europe/Moscow")

# Файл состояния (чтобы дневные метрики не сбрасывались после перезапуска)
DAILY_STATE_PATH = os.getenv("DAILY_STATE_PATH", "state/daily_state.json")

# Время "старта торгового дня" в локальной TZ (для метрик Поднятие/Просадка и дневных лимитов).
# Для MOEX обычно удобно считать день от открытия (10:00 МСК), а не от полуночи, чтобы ночные гэпы
# не раздували "Просадка за день".
DAILY_RESET_HOUR_LOCAL = int(os.getenv("DAILY_RESET_HOUR_LOCAL", "10"))

# Доп. защита: отключать новые входы, если просадка от дневного ПИКА превышает порог.
# 0 или пусто = выключено.
DAILY_PEAK_DRAWDOWN_LIMIT_PCT = _parse_percent(os.getenv("DAILY_PEAK_DRAWDOWN_LIMIT_PCT", "5%"), 0.05)

# Перевод стопа в безубыток: когда позиция ушла в плюс на N%, подтягиваем stop_loss до entry+(lock%).
BREAKEVEN_TRIGGER_PCT = _parse_percent(os.getenv("BREAKEVEN_TRIGGER_PCT", "0.0"), 0.0)
BREAKEVEN_LOCK_PCT = _parse_percent(os.getenv("BREAKEVEN_LOCK_PCT", "0.0"), 0.0)

# После рестарта in-memory positions_tracking пустой → стоп/тейк могут не работать.
# Включаем восстановление трекинга по текущим позициям и audit-логу.
RESTORE_TRACKING_FROM_AUDIT = os.getenv("RESTORE_TRACKING_FROM_AUDIT", "true").lower() == "true"

# ============================================
# ЗАЩИТА ОТ РИСКОВ НА НИЗКОВОЛАТИЛЬНЫХ И ВЫСОКОЛОТНЫХ ИНСТРУМЕНТАХ
# ============================================

# Минимальный ATR как доля от цены. Если ATR/price < этого значения — не входим (защита от "шумовых" стопов).
# ИСПРАВЛЕНО (2026-01-16): снижено с 0.4% до 0.15% для разрешения большего количества сигналов
# Многие хорошие инструменты имеют ATR < 0.4%, что блокировало 125+ сигналов
MIN_ATR_PCT = _parse_percent(os.getenv("MIN_ATR_PCT", "0.15%"), 0.0015)

# Минимальная дистанция стопа от цены входа (защита от слишком "плотных" стопов).
# Если рассчитанный стоп ближе этого — отодвигаем его.
MIN_STOP_DISTANCE_PCT = _parse_percent(os.getenv("MIN_STOP_DISTANCE_PCT", "1.2%"), 0.012)

# Порог "высокого лота" — если lot >= этого значения, применяем дополнительные ограничения.
HIGH_LOT_THRESHOLD = int(os.getenv("HIGH_LOT_THRESHOLD", "100"))

# Коэффициент уменьшения размера для высоколотных инструментов (0.5 = половина от расчётного).
HIGH_LOT_SIZE_FACTOR = float(os.getenv("HIGH_LOT_SIZE_FACTOR", "0.5"))

# Жёсткий лимит на СТОИМОСТЬ одной позиции (% от equity). Применяется ПОСЛЕ округления до лотов.
# Если итоговая стоимость > этого — уменьшаем qty_lots.
MAX_POSITION_VALUE_PCT = _parse_percent(os.getenv("MAX_POSITION_VALUE_PCT", "20%"), 0.20)

# RSI порог "сильной перекупленности" — при RSI > этого значения, sell_confidence повышается автоматически.
# Это фиксирует успешный паттерн: лучшие продажи были при RSI > 75-85.
RSI_STRONG_OVERBOUGHT = int(os.getenv("RSI_STRONG_OVERBOUGHT", "80"))

# ============================================
# ФИЛЬТРЫ КАЧЕСТВА BUY (по анализу ошибочных решений)
# ============================================

# Максимальный RSI для BUY: если RSI выше этого — не покупаем (если MACD_hist не сильно положительный).
# ОПТИМИЗИРОВАНО (2026-01-17): увеличено до 75 для достижения 10+ сделок в день (баланс между активностью и качеством)
# RSI 68-75 часто дает хорошие входы при сильном положительном MACD
RSI_MAX_BUY = int(os.getenv("RSI_MAX_BUY", "75"))

# Требовать положительный или нейтральный MACD_hist для BUY.
# Анализ: ВСЕ убыточные BUY (UGLD, RUAL, PLDRUB) имели отрицательный macd_hist.
# Если true — не покупаем при macd_hist < 0 (падающий импульс).
REQUIRE_MACD_HIST_POSITIVE_BUY = os.getenv("REQUIRE_MACD_HIST_POSITIVE_BUY", "false").lower() == "true"

# Минимальное значение MACD_hist/ATR для BUY (нормализованный порог).
# Если macd_hist/atr < этого — скорее всего падающий импульс. Пропускаем.
# ОПТИМИЗИРОВАНО (2026-01-17): снижено до -0.4 для достижения 10+ сделок в день
# 0 = выключено, -0.4 = разрешаем умеренный отрицательный импульс, -0.5 = строже.
# По умолчанию -0.4 (более активная торговля при слабом отрицательном импульсе).
MIN_MACD_HIST_ATR_RATIO_BUY = float(os.getenv("MIN_MACD_HIST_ATR_RATIO_BUY", "-0.4"))

# Если RSI > RSI_MAX_BUY, требуем СИЛЬНЫЙ положительный MACD_hist для входа.
# ОПТИМИЗИРОВАНО (2026-01-16): снижено с 0.3 до 0.2 для разрешения большего количества входов при высоком RSI
# Порог: macd_hist/atr >= этого значения. При RSI 68-75 разрешаем вход если MACD импульс достаточно сильный.
MACD_OVERRIDE_FOR_HIGH_RSI = float(os.getenv("MACD_OVERRIDE_FOR_HIGH_RSI", "0.2"))

# ОПТИМИЗИРОВАНО (2026-01-16): отключено по умолчанию для большей активности
# Комбинация "sideways + отрицательный MACD" может быть опасна, но при сильной перепроданности (RSI <= 35) может быть прибыльной
# Если trend=sideways и macd_hist < 0 — пропускаем BUY (но есть исключения в trading_strategy.py).
BLOCK_SIDEWAYS_NEGATIVE_MACD = os.getenv("BLOCK_SIDEWAYS_NEGATIVE_MACD", "false").lower() == "true"

# ============================================
# ГЛОБАЛЬНЫЕ МОДУЛИ ПОВЫШЕНИЯ ДОХОДНОСТИ
# ============================================

# Symbol Tracker: адаптивный трекинг производительности символов
ENABLE_SYMBOL_TRACKER = os.getenv("ENABLE_SYMBOL_TRACKER", "true").lower() == "true"
# Путь к файлу состояния трекера
SYMBOL_TRACKER_STATE_PATH = os.getenv("SYMBOL_TRACKER_STATE_PATH", "state/symbol_performance.json")
# Сколько дней истории учитывать
SYMBOL_TRACKER_LOOKBACK_DAYS = int(os.getenv("SYMBOL_TRACKER_LOOKBACK_DAYS", "14"))

# Market Regime: детектор режима рынка (BULL/BEAR/SIDEWAYS)
ENABLE_MARKET_REGIME = os.getenv("ENABLE_MARKET_REGIME", "true").lower() == "true"

# Correlation Guard: защита от коррелированных позиций
ENABLE_CORRELATION_GUARD = os.getenv("ENABLE_CORRELATION_GUARD", "true").lower() == "true"
# Максимум позиций в одной коррелированной группе (нефтегаз, металлы, etc.)
MAX_POSITIONS_PER_CORRELATION_GROUP = int(os.getenv("MAX_POSITIONS_PER_CORRELATION_GROUP", "2"))

# Time Filter: фильтр оптимальных торговых часов
ENABLE_TIME_FILTER = os.getenv("ENABLE_TIME_FILTER", "false").lower() == "true"
# Блокировать торговлю в рискованные часы (первый час после открытия, последний час)
BLOCK_RISKY_HOURS = os.getenv("BLOCK_RISKY_HOURS", "false").lower() == "true"

# Автоматическая блокировка символов с плохой статистикой
AUTO_BLOCK_BAD_SYMBOLS = os.getenv("AUTO_BLOCK_BAD_SYMBOLS", "false").lower() == "true"
# Минимум сделок для оценки
AUTO_BLOCK_MIN_TRADES = int(os.getenv("AUTO_BLOCK_MIN_TRADES", "5"))
# Если loss_rate > этого, блокируем символ
AUTO_BLOCK_MAX_LOSS_RATE = float(os.getenv("AUTO_BLOCK_MAX_LOSS_RATE", "0.75"))
