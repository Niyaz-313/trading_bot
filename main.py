"""
Главный файл торгового бота
Автоматическая торговля акциями с интеграцией Telegram и T-Invest API
"""
import logging
import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List
import pandas as pd
from zoneinfo import ZoneInfo

from config import (
    SYMBOLS, UPDATE_INTERVAL, ENABLE_TRADING,
    LOG_FILE, AUDIT_LOG_PATH, AUDIT_CSV_PATH, STOP_LOSS_PERCENT, TAKE_PROFIT_PERCENT, TINVEST_SANDBOX, BROKER,
    BAR_INTERVAL, HISTORY_LOOKBACK, MIN_CONF_BUY, MIN_CONF_SELL, MAX_TRADES_PER_DAY,
    DAILY_LOSS_LIMIT_PCT, MAX_OPEN_POSITIONS, SYMBOL_COOLDOWN_MIN, AUTO_START, DAILY_CASHFLOW_JUMP_PCT,
    LOCAL_TIMEZONE, DAILY_STATE_PATH,
    DAILY_RESET_HOUR_LOCAL, DAILY_PEAK_DRAWDOWN_LIMIT_PCT, BREAKEVEN_TRIGGER_PCT, BREAKEVEN_LOCK_PCT, RESTORE_TRACKING_FROM_AUDIT,
    AUDIT_DECISIONS, AUDIT_MARKET, AUDIT_DECISION_EVERY_N,
    ATR_STOP_MULT, ATR_TAKE_MULT, ATR_TRAIL_MULT, LIVE_POSITION_SIZING, TRAIL_MIN_PCT,
    TAKE_MIN_PCT, MIN_CONF_SELL_STRONG, SELL_CONFIRM_BARS,
    REQUIRE_TREND_UP_BUY, MIN_VOLUME_RATIO_BUY, REQUIRE_MACD_RISING_BUY,
    NOISY_SYMBOLS, NOISY_REQUIRE_TREND_UP, NOISY_VOLUME_RATIO_MIN, NOISY_MACD_HIST_MIN, NOISY_REQUIRE_MACD_RISING, NOISY_MIN_CONF_BUY, MAX_BUYS_PER_CYCLE,
    MIN_ATR_PCT, MIN_STOP_DISTANCE_PCT, HIGH_LOT_THRESHOLD, HIGH_LOT_SIZE_FACTOR, MAX_POSITION_VALUE_PCT, RSI_STRONG_OVERBOUGHT,
    RSI_MAX_BUY, REQUIRE_MACD_HIST_POSITIVE_BUY, MIN_MACD_HIST_ATR_RATIO_BUY, MACD_OVERRIDE_FOR_HIGH_RSI, BLOCK_SIDEWAYS_NEGATIVE_MACD,
    ENABLE_SYMBOL_TRACKER, SYMBOL_TRACKER_STATE_PATH, SYMBOL_TRACKER_LOOKBACK_DAYS,
    ENABLE_MARKET_REGIME, ENABLE_CORRELATION_GUARD, MAX_POSITIONS_PER_CORRELATION_GROUP,
    ENABLE_TIME_FILTER, BLOCK_RISKY_HOURS,
    AUTO_BLOCK_BAD_SYMBOLS, AUTO_BLOCK_MIN_TRADES, AUTO_BLOCK_MAX_LOSS_RATE
)
from broker_api import BrokerAPI
from trading_strategy import TradingStrategy
from risk_manager import RiskManager
from telegram_bot import TelegramBot, TelegramControlPanel
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from audit_logger import AuditLogger, CsvAuditLogger
from audit_logger import read_last_jsonl_events, compute_avg_cost_from_audit
from state_store import load_json, save_json_atomic

# Глобальные модули для повышения доходности
try:
    from symbol_tracker import get_symbol_tracker, SymbolTracker
except ImportError:
    get_symbol_tracker = None
    SymbolTracker = None

try:
    from market_regime import get_market_regime_detector, get_correlation_guard, MarketRegimeDetector, CorrelationGuard
except ImportError:
    get_market_regime_detector = None
    get_correlation_guard = None
    MarketRegimeDetector = None
    CorrelationGuard = None

# Канонизация тикеров (чтобы не дублировать позиции из-за алиасов, например YDEX↔YNDX)
try:
    from tinvest_api import TICKER_CANONICAL_MAP  # type: ignore
except Exception:
    TICKER_CANONICAL_MAP = {}

def _canon_symbol(sym: str) -> str:
    s = str(sym or "").strip().upper()
    if not s:
        return s
    try:
        # Если это FIGI (начинается с BBG), пытаемся извлечь тикер из него
        # Например: BBGPLDRUBTOM -> PLDRUBTOM -> PLDRUB_TOM
        if s.startswith("BBG") and len(s) > 10:
            # Убираем префикс BBG для поиска в маппинге
            s_without_bbg = s[3:] if s.startswith("BBG") else s
            # Проверяем маппинг для варианта без BBG
            if s_without_bbg in {
                "PLTRUBTOM": "PLTRUB_TOM",
                "PLDRUBTOM": "PLDRUB_TOM",
                "CNYRUBTOM": "CNYRUB_TOM",
                "GLDRUBTOM": "GLDRUB_TOM",
                "SLVRUBTOM": "SLVRUB_TOM",
            }:
                currency_map = {
                    "PLTRUBTOM": "PLTRUB_TOM",
                    "PLDRUBTOM": "PLDRUB_TOM",
                    "CNYRUBTOM": "CNYRUB_TOM",
                    "GLDRUBTOM": "GLDRUB_TOM",
                    "SLVRUBTOM": "SLVRUB_TOM",
                }
                return currency_map[s_without_bbg]
        
        # Сначала проверяем стандартный маппинг
        result = str(TICKER_CANONICAL_MAP.get(s, s)).strip().upper()
        # Дополнительная нормализация для валютных пар: PLTRUBTOM -> PLTRUB_TOM
        # В позициях может быть без подчеркивания, в SYMBOLS - с подчеркиванием
        currency_map = {
            "PLTRUBTOM": "PLTRUB_TOM",
            "PLDRUBTOM": "PLDRUB_TOM",
            "CNYRUBTOM": "CNYRUB_TOM",
            "GLDRUBTOM": "GLDRUB_TOM",
            "SLVRUBTOM": "SLVRUB_TOM",
        }
        if result in currency_map:
            result = currency_map[result]
        return result
    except Exception:
        return s

def _is_trading_session_open() -> tuple[bool, str]:
    """
    Проверяет, открыта ли торговая сессия MOEX.
    
    Returns:
        tuple[bool, str]: (is_open, reason)
        - is_open: True если сессия открыта, False иначе
        - reason: причина (для логирования)
    """
    try:
        # Получаем текущее время в MSK
        msk_tz = ZoneInfo("Europe/Moscow")
        now_msk = datetime.now(msk_tz)
        current_time = now_msk.time()
        current_weekday = now_msk.weekday()  # 0 = Monday, 6 = Sunday
        
        # MOEX работает: пн-пт, 10:00-18:45 MSK (основная сессия)
        # Также есть вечерняя сессия 19:00-23:50, но для большинства инструментов основная сессия важнее
        session_start = datetime.strptime("10:00", "%H:%M").time()
        session_end = datetime.strptime("18:45", "%H:%M").time()
        
        # Проверка дня недели (0-4 = пн-пт)
        if current_weekday >= 5:  # Суббота или воскресенье
            return False, f"выходной день (weekday={current_weekday})"
        
        # Проверка времени
        if current_time < session_start:
            return False, f"до начала сессии (текущее время: {current_time.strftime('%H:%M')} MSK, сессия: {session_start.strftime('%H:%M')}-{session_end.strftime('%H:%M')} MSK)"
        
        if current_time > session_end:
            return False, f"после окончания сессии (текущее время: {current_time.strftime('%H:%M')} MSK, сессия: {session_start.strftime('%H:%M')}-{session_end.strftime('%H:%M')} MSK)"
        
        return True, "сессия открыта"
    except Exception as e:
        logger.warning(f"Ошибка при проверке торговой сессии: {e}")
        # В случае ошибки считаем, что сессия открыта (не блокируем торговлю)
        return True, f"ошибка проверки (разрешаем торговлю): {e}"


def _ensure_ticker_not_figi(symbol: str, broker_api) -> str:
    """
    Убедиться, что symbol является тикером, а не FIGI.
    Если это FIGI (начинается с BBG и длинный), пытается найти тикер через API.
    
    Args:
        symbol: Тикер или FIGI
        broker_api: Экземпляр BrokerAPI для доступа к API
    
    Returns:
        Тикер (если удалось найти) или исходный symbol (если это не FIGI или не удалось найти)
    """
    if not symbol:
        return symbol
    
    symbol_u = str(symbol).strip().upper()
    
    # Если это не FIGI (не начинается с BBG или слишком короткий), возвращаем как есть
    if not symbol_u.startswith("BBG") or len(symbol_u) <= 10:
        return symbol_u
    
    # Это похоже на FIGI, пытаемся найти тикер
    try:
        instrument = broker_api.get_instrument_by_figi(symbol_u) if hasattr(broker_api, 'get_instrument_by_figi') else None
        if instrument and instrument.get('ticker'):
            ticker = str(instrument.get('ticker')).strip().upper()
            logger.debug(f"Преобразовано FIGI {symbol_u} -> тикер {ticker}")
            return _canon_symbol(ticker)
    except Exception as e:
        logger.debug(f"Не удалось найти тикер для FIGI {symbol_u}: {e}")
    
    # Если не удалось найти тикер, возвращаем исходный symbol (FIGI)
    # Это может быть проблемой, но лучше вернуть что-то, чем None
    return symbol_u

# Настройка логирования
# Создаем директорию для логов, если её нет
log_dir = os.path.dirname(LOG_FILE) if os.path.dirname(LOG_FILE) else 'logs'
if log_dir and not os.path.exists(log_dir):
    os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Убираем лишний шум от внутренних HTTP/gRPC логгеров
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.INFO)
logging.getLogger("tinkoff.invest.logging").setLevel(logging.WARNING)


class TradingBot:
    """Главный класс торгового бота"""
    
    def __init__(self):
        """Инициализация бота"""
        # Для T-Invest используем sandbox, для Alpaca - paper_trading
        paper_trading = TINVEST_SANDBOX if BROKER == 'tinvest' else True
        self.broker = BrokerAPI(paper_trading=paper_trading)
        self.strategy = TradingStrategy()
        self.risk_manager = RiskManager()
        self.telegram = TelegramBot()
        self.running = False
        self.positions_tracking = {}  # Отслеживание позиций для стоп-лоссов и тейк-профитов
        # Для “SELL по сигналу” используем подтверждение, чтобы снизить churn/комиссии.
        self._sell_confirm = {}  # symbol -> consecutive sell-signal count
        self.trades_today = 0
        self.cycle_no = 0
        # Дневная статистика: используем локальную временную зону
        try:
            self.tz = ZoneInfo(LOCAL_TIMEZONE)
        except Exception:
            self.tz = timezone.utc

        self.trades_day = self._trading_day(datetime.now(self.tz))
        self.day_start_equity = None  # будет восстановлено из state/audit
        self.day_peak_equity = None   # пик equity за день (для просадки от пика), будет восстановлено из state/audit
        self.allow_entries = AUTO_START  # включать/выключать входы через Telegram
        self.cooldown_until = {}  # symbol -> datetime
        self.trade_history = []  # последние действия
        self.telegram_control = None
        self.audit = AuditLogger(AUDIT_LOG_PATH)
        self.audit_csv = CsvAuditLogger(
            AUDIT_CSV_PATH,
            fieldnames=[
                "ts_utc",
                "event",
                "symbol",
                "action",
                "qty_lots",
                "lot",
                "price",
                "reason",
                "skip_reason",
                "confidence",
                "buy_signals",
                "sell_signals",
                "rsi",
                "trend",
                "atr",
                "macd",
                "macd_signal",
                "macd_hist",
                "equity",
                "cash",
                "open_positions",
                "trades_today_buy",
                "order_id",
                "status",
                "figi",
                "details",
            ],
        )
        
        logger.info(f"Торговый бот инициализирован (брокер: {BROKER})")

        # Восстанавливаем day_start_equity после перезапуска (если есть).
        self._restore_daily_state()
        # Восстанавливаем счётчик BUY за сегодня из audit-лога (чтобы лимиты/статус были корректны после перезапуска).
        try:
            self.trades_today = self._count_buys_for_date(datetime.now(self.tz).date())
        except Exception:
            pass

        # Восстановление трекинга позиций после рестарта:
        # positions_tracking живёт в памяти и сбрасывается при перезапуске, из-за чего стоп/тейк могут "не работать".
        if RESTORE_TRACKING_FROM_AUDIT:
            try:
                self._bootstrap_tracking_from_positions()
            except Exception:
                pass

        # ============================================
        # Инициализация глобальных модулей повышения доходности
        # ============================================
        self.symbol_tracker = None
        self.market_regime_detector = None
        self.correlation_guard = None

        if ENABLE_SYMBOL_TRACKER and get_symbol_tracker is not None:
            try:
                self.symbol_tracker = get_symbol_tracker(SYMBOL_TRACKER_STATE_PATH)
                logger.info("Symbol Tracker инициализирован")
            except Exception as e:
                logger.warning(f"Не удалось инициализировать Symbol Tracker: {e}")

        if ENABLE_MARKET_REGIME and get_market_regime_detector is not None:
            try:
                self.market_regime_detector = get_market_regime_detector(LOCAL_TIMEZONE)
                logger.info("Market Regime Detector инициализирован")
            except Exception as e:
                logger.warning(f"Не удалось инициализировать Market Regime Detector: {e}")

        if ENABLE_CORRELATION_GUARD and get_correlation_guard is not None:
            try:
                self.correlation_guard = get_correlation_guard(MAX_POSITIONS_PER_CORRELATION_GROUP)
                logger.info(f"Correlation Guard инициализирован (max {MAX_POSITIONS_PER_CORRELATION_GROUP} в группе)")
            except Exception as e:
                logger.warning(f"Не удалось инициализировать Correlation Guard: {e}")

    def _trading_day(self, dt_loc: datetime | None = None) -> datetime.date:
        """
        Дата торгового дня в локальной TZ. Если reset_hour=10, то период 00:00..09:59 относится к предыдущему дню.
        Это делает метрики “за день” более осмысленными для MOEX.
        """
        d = dt_loc or datetime.now(self.tz)
        try:
            h = int(DAILY_RESET_HOUR_LOCAL)
        except Exception:
            h = 0
        h = max(0, min(23, h))
        day = d.date()
        if h > 0 and int(d.hour) < h:
            return day - timedelta(days=1)
        return day

    def _bootstrap_tracking_from_positions(self) -> None:
        """
        Создаёт positions_tracking для уже открытых позиций (например, после рестарта).
        Источник entry_price: позиция брокера (avg_entry_price), иначе audit-лог (compute_avg_cost_from_audit),
        иначе fallback на текущую цену.
        """
        try:
            positions = self.broker.get_positions() or []
        except Exception:
            positions = []
        if not positions:
            return

        try:
            cost_map = compute_avg_cost_from_audit(AUDIT_LOG_PATH)
        except Exception:
            cost_map = {}

        for p in positions:
            sym = _canon_symbol(p.get("symbol") or p.get("ticker") or "")
            if not sym:
                continue
            if sym in self.positions_tracking:
                continue
            try:
                qty_lots = int(p.get("qty_lots", p.get("qty", 0)) or 0)
            except Exception:
                qty_lots = 0
            if qty_lots <= 0:
                continue
            try:
                lot = int(p.get("lot", 1) or 1)
            except Exception:
                lot = 1
            lot = max(1, lot)

            entry = None
            try:
                if p.get("avg_entry_price") is not None:
                    entry = float(p.get("avg_entry_price"))
            except Exception:
                entry = None
            if entry is None:
                try:
                    cm = cost_map.get(sym) or {}
                    if cm.get("avg_price") is not None:
                        entry = float(cm.get("avg_price"))
                except Exception:
                    entry = None
            if entry is None:
                try:
                    entry = float(p.get("current_price", 0) or 0)
                except Exception:
                    entry = None
            if not entry or float(entry) <= 0:
                continue

            stop = float(entry) * (1.0 - float(STOP_LOSS_PERCENT))
            take = float(entry) * (1.0 + max(float(TAKE_PROFIT_PERCENT), float(TAKE_MIN_PCT)))
            self.positions_tracking[sym] = {
                "entry_price": float(entry),
                "qty_lots": int(qty_lots),
                "lot": int(lot),
                "stop_loss": float(stop),
                "take_profit": float(take),
                "entry_ts_utc": "",
                "restored_from": "audit_or_position",
            }

    def _restore_daily_state(self):
        today = self._trading_day(datetime.now(self.tz)).isoformat()
        st = load_json(DAILY_STATE_PATH) or {}
        if st.get("date") == today and isinstance(st.get("day_start_equity"), (int, float)):
            self.day_start_equity = float(st["day_start_equity"])
            if isinstance(st.get("day_peak_equity"), (int, float)):
                self.day_peak_equity = float(st["day_peak_equity"])
            else:
                self.day_peak_equity = float(self.day_start_equity)
            return

        # Fallback: берём метрики дня из audit-лога (учитывает прошлые запуски).
        start, peak = self._day_metrics_from_audit(today)
        if isinstance(start, (int, float)) and start > 0:
            self.day_start_equity = float(start)
            self.day_peak_equity = float(peak) if isinstance(peak, (int, float)) and peak > 0 else float(start)
            save_json_atomic(DAILY_STATE_PATH, {"date": today, "day_start_equity": float(self.day_start_equity), "day_peak_equity": float(self.day_peak_equity)})

    def _day_metrics_from_audit(self, day_iso: str) -> tuple[float | None, float | None]:
        """
        Восстановить start/peak equity за день (локальная TZ) по audit-логу.

        Берём любые события, где есть поле equity (cycle/trade/skip/decision),
        чтобы переживать рестарты и редкие циклы.
        """
        try:
            import json
            series: List[tuple[datetime, float]] = []
            with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                    except Exception:
                        continue
                    ts = e.get("ts_utc")
                    if not ts:
                        continue
                    try:
                        dt_utc = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        dt_loc = dt_utc.astimezone(self.tz)
                    except Exception:
                        continue
                    if dt_loc.date().isoformat() != day_iso:
                        continue
                    eq = e.get("equity")
                    if not isinstance(eq, (int, float)):
                        continue
                    v = float(eq)
                    if v <= 0:
                        continue
                    series.append((dt_loc, v))

            if not series:
                return None, None

            series.sort(key=lambda x: x[0])

            # Сегментация по "скачкам" equity (обычно это пополнение песочницы/смена базы).
            # Берём метрики ПОСЛЕ последнего сильного скачка, чтобы дневная статистика отражала торговлю,
            # а не пополнения.
            jump_pct = float(DAILY_CASHFLOW_JUMP_PCT) if isinstance(DAILY_CASHFLOW_JUMP_PCT, (int, float)) else 0.30
            jump_pct = max(0.05, min(0.95, jump_pct))

            seg_start_idx = 0
            prev = series[0][1]
            for i in range(1, len(series)):
                cur = series[i][1]
                if prev > 0:
                    rel = abs(cur - prev) / prev
                    if rel >= jump_pct:
                        seg_start_idx = i
                prev = cur

            seg = [v for _, v in series[seg_start_idx:]]
            if not seg:
                return None, None

            # ВАЖНО: start_eq должен быть минимальным значением equity за день (начало дня),
            # а не первым значением после скачка. Это гарантирует правильный расчет поднятия/просадки.
            # Но если есть скачок, то берем первое значение после скачка как начало торговли.
            start_eq = float(seg[0])  # Первое значение после последнего скачка (начало торговли)
            peak_eq = float(max(seg)) if seg else start_eq
            # Также находим минимальное значение для правильного расчета просадки
            min_eq = float(min(seg)) if seg else start_eq
            # Если минимальное значение меньше стартового, значит были убытки
            # В этом случае используем минимальное как базовое для расчета просадки
            return start_eq, peak_eq
        except Exception:
            return None, None

    def _passes_noisy_entry_filter(self, symbol: str, analysis: Dict) -> tuple[bool, Dict]:
        """
        Recommendation D: для "шумных/дешёвых" бумаг требуем более качественный вход,
        чтобы уменьшить долю stop_loss из-за шума.

        Возвращает: (ok, details) где details содержит причины отказа.
        """
        sym = str(symbol or "").strip().upper()
        if not sym or sym not in (NOISY_SYMBOLS or []):
            return True, {}

        fails: Dict[str, object] = {}

        # Для шумных бумаг повышаем требования к уверенности, чтобы уменьшить стоп-ауты.
        try:
            conf = float(analysis.get("confidence", 0) or 0)
        except Exception:
            conf = 0.0
        if float(conf) < float(NOISY_MIN_CONF_BUY):
            fails["min_confidence"] = {"need_gte": float(NOISY_MIN_CONF_BUY), "got": float(conf)}

        trend = str(analysis.get("trend") or "").strip().lower()
        if NOISY_REQUIRE_TREND_UP and trend and trend != "up":
            fails["trend"] = {"need": "up", "got": trend}

        # volume_ratio = volume / volume_ma (см. trading_strategy.analyze)
        vr = analysis.get("volume_ratio")
        try:
            vr_f = float(vr) if vr is not None else 1.0
        except Exception:
            vr_f = 1.0
        if NOISY_VOLUME_RATIO_MIN > 0 and vr_f < float(NOISY_VOLUME_RATIO_MIN):
            fails["volume_ratio"] = {"need_gte": float(NOISY_VOLUME_RATIO_MIN), "got": float(vr_f)}

        # MACD histogram: хотим хотя бы не-отрицательный импульс
        mh = analysis.get("macd_hist")
        try:
            mh_f = float(mh) if mh is not None else 0.0
        except Exception:
            mh_f = 0.0
        if mh_f < float(NOISY_MACD_HIST_MIN):
            fails["macd_hist"] = {"need_gte": float(NOISY_MACD_HIST_MIN), "got": float(mh_f)}

        if NOISY_REQUIRE_MACD_RISING:
            prev = analysis.get("macd_hist_prev")
            try:
                prev_f = float(prev) if prev is not None else None
            except Exception:
                prev_f = None
            if prev_f is not None and mh_f < float(prev_f):
                fails["macd_hist_rising"] = {"need_gte_prev": float(prev_f), "got": float(mh_f)}

        return (len(fails) == 0), fails

    def _buy_score(self, symbol: str, analysis: Dict) -> float:
        """
        Score для ранжирования BUY-кандидатов в текущем цикле.
        Идея: выбирать не “первый по списку”, а лучший по качеству сигнала/риску.
        """
        try:
            conf = float(analysis.get("confidence", 0) or 0.0)
        except Exception:
            conf = 0.0
        try:
            buy_signals = float(analysis.get("buy_signals", 0) or 0.0)
        except Exception:
            buy_signals = 0.0
        try:
            vr = float(analysis.get("volume_ratio", 1.0) or 1.0)
        except Exception:
            vr = 1.0
        trend = str(analysis.get("trend") or "").strip().lower()
        try:
            atr = float(analysis.get("atr") or 0.0)
        except Exception:
            atr = 0.0
        try:
            price = float(analysis.get("price") or 0.0)
        except Exception:
            price = 0.0
        atr_pct = (atr / price) if price > 0 and atr > 0 else 0.0
        # penalty 0..1 for atr_pct up to 2% (0.02)
        atr_pen = min(1.0, max(0.0, atr_pct / 0.02)) if atr_pct > 0 else 0.0

        # Сборка score (0..~1.5)
        score = 0.0
        score += conf * 1.0
        score += min(0.25, (buy_signals / 10.0))  # 0..0.25
        score += min(0.15, max(0.0, (vr - 1.0)) * 0.15)  # 0..0.15
        score += 0.05 if trend == "up" else (-0.05 if trend == "down" else 0.0)
        score -= 0.15 * atr_pen

        # Небольшая поправка для noisy-тикеров: даже хороший сигнал должен быть “лучше остальных”
        sym = str(symbol or "").strip().upper()
        if sym in (NOISY_SYMBOLS or []):
            score -= 0.03

        return float(score)

    async def _execute_buy(self, symbol: str, account_info: Dict, open_positions: Dict, analysis: Dict, rank: int = 1, score: float = 0.0):
        """
        Выполняет BUY по уже отранжированному кандидату.
        ВАЖНО: qty для T-Invest трактуем как ЛОТЫ.
        """
        current_price = float(analysis.get("price", 0) or 0)
        if current_price <= 0:
            return

        # Глобальные фильтры качества BUY (включаются через .env)
        try:
            trend = str(analysis.get("trend") or "").strip().lower()
        except Exception:
            trend = ""
        if REQUIRE_TREND_UP_BUY and trend and trend != "up":
            self._audit_event({
                "event": "skip",
                "symbol": symbol,
                "skip_reason": "quality_filter",
                "price": float(current_price),
                "confidence": float(analysis.get("confidence", 0) or 0),
                "details": {"rule": "require_trend_up_buy", "trend": trend, "rank": int(rank), "score": float(score)},
            })
            return
        try:
            vr = float(analysis.get("volume_ratio", 1.0) or 1.0)
        except Exception:
            vr = 1.0
        if float(MIN_VOLUME_RATIO_BUY or 0.0) > 0 and float(vr) < float(MIN_VOLUME_RATIO_BUY):
            self._audit_event({
                "event": "skip",
                "symbol": symbol,
                "skip_reason": "quality_filter",
                "price": float(current_price),
                "confidence": float(analysis.get("confidence", 0) or 0),
                "details": {"rule": "min_volume_ratio_buy", "need_gte": float(MIN_VOLUME_RATIO_BUY), "got": float(vr), "rank": int(rank), "score": float(score)},
            })
            return
        if REQUIRE_MACD_RISING_BUY:
            try:
                mh = float(analysis.get("macd_hist")) if analysis.get("macd_hist") is not None else None
                mh_prev = float(analysis.get("macd_hist_prev")) if analysis.get("macd_hist_prev") is not None else None
            except Exception:
                mh = None
                mh_prev = None
            if mh is not None and mh_prev is not None and float(mh) < float(mh_prev):
                self._audit_event({
                    "event": "skip",
                    "symbol": symbol,
                    "skip_reason": "quality_filter",
                    "price": float(current_price),
                    "confidence": float(analysis.get("confidence", 0) or 0),
                    "details": {"rule": "require_macd_rising_buy", "macd_hist": float(mh), "macd_hist_prev": float(mh_prev), "rank": int(rank), "score": float(score)},
                })
                return

        # ============================================
        # ФИЛЬТРЫ КАЧЕСТВА BUY (по анализу ошибочных решений 2026-01-14)
        # ============================================
        try:
            rsi_val = float(analysis.get("rsi", 50) or 50)
        except Exception:
            rsi_val = 50.0
        try:
            macd_hist_val = float(analysis.get("macd_hist", 0) or 0)
        except Exception:
            macd_hist_val = 0.0
        try:
            atr_val = float(analysis.get("atr", 1) or 1)
        except Exception:
            atr_val = 1.0
        # Нормализованный MACD_hist (относительно ATR)
        macd_hist_atr_ratio = macd_hist_val / atr_val if atr_val > 0 else 0.0

        # Фильтр 1: Блокируем BUY при sideways + отрицательный MACD (опасная комбинация: RUAL, PLDRUB)
        if BLOCK_SIDEWAYS_NEGATIVE_MACD and trend == "sideways" and macd_hist_val < 0:
            self._audit_event({
                "event": "skip",
                "symbol": symbol,
                "skip_reason": "sideways_negative_macd",
                "price": float(current_price),
                "confidence": float(analysis.get("confidence", 0) or 0),
                "details": {
                    "rule": "block_sideways_negative_macd",
                    "trend": trend,
                    "macd_hist": macd_hist_val,
                    "rank": int(rank),
                    "score": float(score),
                },
            })
            return

        # Фильтр 2: Требуем положительный MACD_hist (если включено)
        if REQUIRE_MACD_HIST_POSITIVE_BUY and macd_hist_val < 0:
            self._audit_event({
                "event": "skip",
                "symbol": symbol,
                "skip_reason": "negative_macd_hist",
                "price": float(current_price),
                "confidence": float(analysis.get("confidence", 0) or 0),
                "details": {
                    "rule": "require_macd_hist_positive_buy",
                    "macd_hist": macd_hist_val,
                    "rank": int(rank),
                    "score": float(score),
                },
            })
            return

        # Фильтр 3: Минимальный MACD_hist/ATR ratio (защита от сильного падающего импульса)
        if float(MIN_MACD_HIST_ATR_RATIO_BUY) != 0 and macd_hist_atr_ratio < float(MIN_MACD_HIST_ATR_RATIO_BUY):
            self._audit_event({
                "event": "skip",
                "symbol": symbol,
                "skip_reason": "low_macd_hist_atr_ratio",
                "price": float(current_price),
                "confidence": float(analysis.get("confidence", 0) or 0),
                "details": {
                    "rule": "min_macd_hist_atr_ratio_buy",
                    "macd_hist": macd_hist_val,
                    "atr": atr_val,
                    "ratio": macd_hist_atr_ratio,
                    "min_ratio": float(MIN_MACD_HIST_ATR_RATIO_BUY),
                    "rank": int(rank),
                    "score": float(score),
                },
            })
            return

        # Фильтр 4: RSI слишком высокий для BUY (кроме случая сильного положительного MACD)
        if rsi_val > float(RSI_MAX_BUY):
            # Разрешаем вход при высоком RSI ТОЛЬКО если MACD_hist очень сильный (как TRNFP)
            if macd_hist_atr_ratio < float(MACD_OVERRIDE_FOR_HIGH_RSI):
                self._audit_event({
                    "event": "skip",
                    "symbol": symbol,
                    "skip_reason": "rsi_too_high_for_buy",
                    "price": float(current_price),
                    "confidence": float(analysis.get("confidence", 0) or 0),
                    "details": {
                        "rule": "rsi_max_buy",
                        "rsi": rsi_val,
                        "rsi_max": float(RSI_MAX_BUY),
                        "macd_hist_atr_ratio": macd_hist_atr_ratio,
                        "override_threshold": float(MACD_OVERRIDE_FOR_HIGH_RSI),
                        "rank": int(rank),
                        "score": float(score),
                    },
                })
                return

        # ============================================
        # ГЛОБАЛЬНЫЕ МОДУЛИ ПОВЫШЕНИЯ ДОХОДНОСТИ
        # ============================================

        # 1. Correlation Guard: проверяем, нет ли уже позиций в этой коррелированной группе
        if self.correlation_guard is not None:
            try:
                can_open, reason = self.correlation_guard.can_open_position(symbol, open_positions or {})
                if not can_open:
                    self._audit_event({
                        "event": "skip",
                        "symbol": symbol,
                        "skip_reason": "correlation_guard",
                        "price": float(current_price),
                        "confidence": float(analysis.get("confidence", 0) or 0),
                        "details": {"reason": reason, "rank": int(rank), "score": float(score)},
                    })
                    return
            except Exception:
                pass

        # 2. Symbol Tracker: проверяем, не заблокирован ли символ и корректируем размер
        position_size_mult = 1.0
        if self.symbol_tracker is not None:
            try:
                # Автоблокировка плохих символов
                if AUTO_BLOCK_BAD_SYMBOLS and self.symbol_tracker.is_symbol_blocked(
                    symbol, min_trades=AUTO_BLOCK_MIN_TRADES, max_loss_rate=AUTO_BLOCK_MAX_LOSS_RATE
                ):
                    self._audit_event({
                        "event": "skip",
                        "symbol": symbol,
                        "skip_reason": "symbol_auto_blocked",
                        "price": float(current_price),
                        "confidence": float(analysis.get("confidence", 0) or 0),
                        "details": {
                            "stats": self.symbol_tracker.get_symbol_stats(symbol),
                            "rank": int(rank),
                            "score": float(score),
                        },
                    })
                    return
                # Получаем множитель размера позиции на основе истории символа
                position_size_mult = self.symbol_tracker.get_position_size_multiplier(symbol)
            except Exception:
                pass

        # 3. Market Regime: корректируем параметры под режим рынка
        regime_position_mult = 1.0
        if self.market_regime_detector is not None:
            try:
                # Time filter: проверяем оптимальное время
                if BLOCK_RISKY_HOURS:
                    is_optimal, time_reason = self.market_regime_detector.is_optimal_trading_time()
                    if not is_optimal:
                        self._audit_event({
                            "event": "skip",
                            "symbol": symbol,
                            "skip_reason": "risky_trading_hour",
                            "price": float(current_price),
                            "confidence": float(analysis.get("confidence", 0) or 0),
                            "details": {"reason": time_reason, "rank": int(rank), "score": float(score)},
                        })
                        return
                # Множитель по времени
                if ENABLE_TIME_FILTER:
                    regime_position_mult *= self.market_regime_detector.get_time_based_position_mult()
            except Exception:
                pass

        # Для T-Invest торгуем лотами, поэтому получаем lot
        # Убеждаемся, что symbol является тикером, а не FIGI
        symbol_for_api = _ensure_ticker_not_figi(symbol, self.broker)
        instrument = self.broker.get_instrument_details(symbol_for_api)
        # ВАЖНО: В sandbox флаги trading_status могут быть False даже когда торговля возможна (особенно в ночное время)
        # Не блокируем покупки по этой проверке - полагаемся на реальную ошибку API (30079)
        # Логируем информацию для диагностики, но продолжаем попытку размещения ордера
        if instrument:
            st = str(instrument.get("trading_status") or "").upper()
            api_ok = instrument.get("api_trade_available_flag")
            buy_ok = instrument.get("buy_available_flag")
            # Только логируем, но не блокируем
            if ("NOT_AVAILABLE" in st) or (api_ok is False) or (buy_ok is False):
                logger.debug(f"Инструмент {symbol} имеет флаги: trading_status={st}, api_ok={api_ok}, buy_ok={buy_ok} - продолжим попытку размещения ордера")
        lot = int(instrument.get("lot", 1)) if instrument else 1
        lot = max(1, lot)

        # Рассчитываем stop/take (ATR если доступен, иначе проценты) и размер позиции
        atr = analysis.get("atr")

        # ЗАЩИТА #1: Проверяем минимальный ATR как % от цены (защита от "шумовых" инструментов типа UGLD)
        if atr is not None and float(MIN_ATR_PCT) > 0:
            try:
                atr_pct = float(atr) / float(current_price) if float(current_price) > 0 else 0
                if atr_pct < float(MIN_ATR_PCT):
                    self._audit_event({
                        "event": "skip",
                        "symbol": symbol,
                        "skip_reason": "low_atr_pct",
                        "price": float(current_price),
                        "confidence": float(analysis.get("confidence", 0) or 0),
                        "details": {"atr": float(atr), "atr_pct": atr_pct, "min_atr_pct": float(MIN_ATR_PCT), "rank": int(rank), "score": float(score)},
                    })
                    return
            except Exception:
                pass
        stop_price = None
        take_price = None
        try:
            if atr is not None:
                stop_price = float(current_price) - float(ATR_STOP_MULT) * float(atr)
                take_price = float(current_price) + float(ATR_TAKE_MULT) * float(atr)
        except Exception:
            stop_price = None
            take_price = None
        if stop_price is None:
            stop_price = self.risk_manager.calculate_stop_loss(float(current_price))
        if take_price is None:
            take_price = self.risk_manager.calculate_take_profit(float(current_price))

        # Guard-rails:
        # - стоп не уже, чем процентный STOP_LOSS_PERCENT (защита от “плотного” ATR-стопа на малом ATR)
        # - тейк не дальше, чем TAKE_PROFIT_PERCENT (кап)
        # - тейк не ближе, чем TAKE_MIN_PCT (иначе прибыль часто “съедается” комиссиями/спредом)
        try:
            pct_stop = float(current_price) * (1 - float(STOP_LOSS_PERCENT))
            stop_price = min(float(stop_price), float(pct_stop))
        except Exception:
            pass
        try:
            pct_take = float(current_price) * (1 + float(TAKE_PROFIT_PERCENT))
            take_price = min(float(take_price), float(pct_take))
        except Exception:
            pass
        try:
            pct_take_min = float(current_price) * (1 + float(TAKE_MIN_PCT))
            take_price = max(float(take_price), float(pct_take_min))
        except Exception:
            pass

        # ЗАЩИТА #2: Минимальная дистанция стопа (защита от слишком "плотных" стопов)
        try:
            min_stop = float(current_price) * (1 - float(MIN_STOP_DISTANCE_PCT))
            if float(stop_price) > float(min_stop):
                stop_price = float(min_stop)
        except Exception:
            pass

        if str(LIVE_POSITION_SIZING).lower() == "risk":
            qty_shares = self.risk_manager.calculate_position_size_by_risk(
                float(account_info.get("equity", 10000) or 10000),
                float(current_price),
                float(stop_price),
                confidence=float(analysis.get("confidence", 1.0) or 1.0),
            )
        else:
            qty_shares = self.risk_manager.calculate_position_size(
                float(account_info.get("equity", 10000) or 10000),
                float(current_price),
                float(analysis.get("confidence", 1.0) or 1.0),
            )
        qty_lots = max(1, int(float(qty_shares) // float(lot)))

        # ЗАЩИТА #3: Уменьшаем размер для высоколотных инструментов (lot >= HIGH_LOT_THRESHOLD)
        if int(lot) >= int(HIGH_LOT_THRESHOLD) and float(HIGH_LOT_SIZE_FACTOR) < 1.0:
            qty_lots = max(1, int(float(qty_lots) * float(HIGH_LOT_SIZE_FACTOR)))

        # Применяем множители от Symbol Tracker и Market Regime
        total_position_mult = float(position_size_mult) * float(regime_position_mult)
        if total_position_mult != 1.0 and total_position_mult > 0:
            qty_lots = max(1, int(float(qty_lots) * total_position_mult))

        # ЗАЩИТА #4: Жёсткий лимит на СТОИМОСТЬ позиции (% от equity)
        equity = float(account_info.get("equity", 10000) or 10000)
        max_position_value = float(equity) * float(MAX_POSITION_VALUE_PCT)
        position_value = float(qty_lots) * float(lot) * float(current_price)
        if position_value > max_position_value and float(current_price) > 0 and int(lot) > 0:
            # Уменьшаем qty_lots, чтобы уложиться в лимит
            max_qty_lots = int(max_position_value / (float(lot) * float(current_price)))
            if max_qty_lots < 1:
                self._audit_event({
                    "event": "skip",
                    "symbol": symbol,
                    "skip_reason": "position_too_expensive",
                    "price": float(current_price),
                    "confidence": float(analysis.get("confidence", 0) or 0),
                    "details": {
                        "lot": int(lot),
                        "min_position_value": float(lot) * float(current_price),
                        "max_position_value": max_position_value,
                        "equity": equity,
                        "rank": int(rank),
                        "score": float(score),
                    },
                })
                return
            qty_lots = max(1, max_qty_lots)

        if not ENABLE_TRADING:
            return

        # Проверка торговой сессии перед размещением ордера
        is_session_open, session_reason = _is_trading_session_open()
        if not is_session_open:
            logger.warning(f"⚠️ Пропуск размещения ордера на покупку {symbol}: {session_reason}")
            self._audit_event({
                "event": "skip",
                "symbol": symbol,
                "skip_reason": "trading_session_closed",
                "price": float(current_price),
                "confidence": float(analysis.get("confidence", 0) or 0),
                "equity": float(account_info.get("equity", 0) or 0),
                "cash": float(account_info.get("cash", 0) or 0),
                "open_positions": int(len({id(v) for v in (open_positions or {}).values()})) if open_positions is not None else 0,
                "trades_today_buy": int(self.trades_today),
                "details": {
                    "reason": session_reason,
                    "qty_lots": int(qty_lots),
                    "lot": int(lot),
                    "rank": int(rank),
                    "score": float(score),
                },
            })
            return

        order = self.broker.place_market_order(symbol, qty_lots, 'buy')
        if not order:
            # Получаем детальную информацию об ошибке
            error_details = {}
            if hasattr(self.broker, 'client') and hasattr(self.broker.client, '_last_order_error'):
                error_details = self.broker.client._last_order_error.copy() if self.broker.client._last_order_error else {}
            
            # Формируем детальное сообщение об ошибке
            error_reason = error_details.get('reason', 'unknown')
            error_code = error_details.get('error_code', 'N/A')
            error_description = error_details.get('description', 'place_market_order returned None')
            
            logger.error(f"❌ НЕ УДАЛОСЬ РАЗМЕСТИТЬ ЗАЯВКУ НА ПОКУПКУ: {symbol} | "
                        f"Причина: {error_reason} | Код ошибки: {error_code} | "
                        f"Описание: {error_description} | "
                        f"Параметры: qty_lots={qty_lots}, price={current_price:.2f}, lot={lot}, "
                        f"figi={instrument.get('figi') if instrument else 'N/A'}, "
                        f"instrument_ok={instrument is not None}")
            
            # Дополнительное логирование в зависимости от типа ошибки
            if error_reason == 'instrument_not_available':
                from datetime import datetime
                current_time_msk = datetime.now().strftime('%H:%M:%S MSK')
                logger.warning(f"   Время: {current_time_msk} | MOEX работает 10:00-18:45 MSK (основная сессия)")
            elif error_reason == 'insufficient_balance':
                logger.warning(f"   Баланс: cash={account_info.get('cash', 0):.2f}, equity={account_info.get('equity', 0):.2f}")
            
            self._audit_event({
                "event": "skip",
                "symbol": symbol,
                "skip_reason": "order_placement_failed",
                "price": float(current_price),
                "confidence": float(analysis.get("confidence", 0) or 0),
                "equity": float(account_info.get("equity", 0) or 0),
                "cash": float(account_info.get("cash", 0) or 0),
                "open_positions": int(len({id(v) for v in (open_positions or {}).values()})) if open_positions is not None else 0,
                "trades_today_buy": int(self.trades_today),
                "details": {
                    "reason": error_reason,
                    "error_code": error_code,
                    "error_description": error_description,
                    "error_type": error_details.get('error_type', 'unknown'),
                    "qty_lots": int(qty_lots),
                    "lot": int(lot),
                    "rank": int(rank),
                    "score": float(score),
                    "instrument_ok": instrument is not None,
                    "figi": instrument.get("figi") if instrument else None,
                    **{k: v for k, v in error_details.items() if k not in ['reason', 'error_code', 'error_description', 'error_type']}
                },
            })
            return

        # Telegram уведомление
        # Преобразуем FIGI в тикер для корректного отображения в Telegram
        symbol_for_telegram = _ensure_ticker_not_figi(symbol, self.broker)
        symbol_for_telegram = _canon_symbol(symbol_for_telegram)
        
        currency = (account_info.get("currency") or "RUB")
        currency_symbol = {"RUB": "₽", "USD": "$", "EUR": "€"}.get(str(currency).upper(), str(currency).upper() + " ")
        qty_shares_total = float(qty_lots) * float(lot)
        reason = f"BUY (rank={rank}, score={score:.3f}) уверенность: {float(analysis.get('confidence',0) or 0)*100:.1f}%"
        message = self.telegram.format_trade_notification(
            symbol_for_telegram, "BUY", qty_lots, current_price,
            current_price * qty_lots * lot, reason,
            currency=currency,
            currency_symbol=currency_symbol,
            lot=lot,
            qty_shares=qty_shares_total,
        )
        await self.telegram.send_message(message, parse_mode='Markdown')

        # Локальные счётчики/лимиты
        self.trades_today += 1
        self.cooldown_until[symbol] = datetime.now() + timedelta(minutes=SYMBOL_COOLDOWN_MIN)

        # Обновляем локальную "позицию", чтобы лимит позиций работал в текущем цикле при MAX_BUYS_PER_CYCLE>1
        sym_can = _canon_symbol(symbol)
        try:
            open_positions[sym_can] = {
                "symbol": sym_can,
                "ticker": sym_can,
                "figi": (instrument.get("figi") if instrument else ""),
                "qty_lots": int(qty_lots),
                "lot": int(lot),
                "qty_shares": float(qty_shares_total),
            }
        except Exception:
            pass

        # Трекинг стоп/тейк для check_positions()
        self.positions_tracking[sym_can] = {
            "entry_price": float(current_price),
            "stop_loss": float(stop_price),
            "take_profit": float(take_price),
            "lot": int(lot),
            "qty_lots": int(qty_lots),
        }

        # Аудит
        self._audit_event({
            "event": "trade",
            "symbol": symbol,
            "action": "BUY",
            "qty_lots": int(qty_lots),
            "lot": int(lot),
            "price": float(current_price),
            "reason": "ranked_buy",
            "confidence": float(analysis.get("confidence", 0) or 0),
            "buy_signals": analysis.get("buy_signals"),
            "sell_signals": analysis.get("sell_signals"),
            "rsi": analysis.get("rsi"),
            "trend": analysis.get("trend"),
            "atr": analysis.get("atr"),
            "macd": analysis.get("macd"),
            "macd_signal": analysis.get("macd_signal"),
            "macd_hist": analysis.get("macd_hist"),
            "order": order,
            "equity": float(account_info.get("equity", 0) or 0),
            "cash": float(account_info.get("cash", 0) or 0),
            "open_positions": int(len({id(v) for v in (open_positions or {}).values()})) if open_positions is not None else 0,
            "trades_today_buy": int(self.trades_today),
            "details": {
                "rank": int(rank),
                "score": float(score),
                "stop_loss": float(stop_price),
                "take_profit": float(take_price),
                "qty_shares": float(qty_shares_total),
            },
        })

    def _day_start_equity_from_audit(self, day_iso: str) -> float | None:
        # day_iso: YYYY-MM-DD in local timezone
        try:
            with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
                first_eq = None
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        import json
                        e = json.loads(line)
                    except Exception:
                        continue
                    if e.get("event") != "cycle":
                        continue
                    ts = e.get("ts_utc")
                    if not ts:
                        continue
                    try:
                        dt_utc = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        dt_loc = dt_utc.astimezone(self.tz)
                    except Exception:
                        continue
                    if dt_loc.date().isoformat() != day_iso:
                        continue
                    eq = e.get("equity")
                    if isinstance(eq, (int, float)):
                        first_eq = float(eq)
                        break
                return first_eq
        except Exception:
            return None

    def _count_buys_for_date(self, target_date) -> int:
        """Подсчитать количество BUY (trade events) за дату (в локальной TZ) по audit-логу."""
        try:
            import json
            cnt = 0
            with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                    except Exception:
                        continue
                    if e.get("event") != "trade":
                        continue
                    if str(e.get("action", "")).upper() != "BUY":
                        continue
                    ts = e.get("ts_utc")
                    if not ts:
                        continue
                    try:
                        dt_utc = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        dt_loc = dt_utc.astimezone(self.tz)
                    except Exception:
                        continue
                    if dt_loc.date() == target_date:
                        cnt += 1
            return cnt
        except Exception:
            return 0

    def get_day_report_text(self, day_str: str) -> str:
        """
        /day YYYY-MM-DD — дневной отчёт.

        ВАЖНО: абсолютно точные метрики возможны только там, где у нас есть данные (cycle/trade/skip) в audit-логе.
        Если бот был выключен — будет "нет данных за период".
        """
        day_str = (day_str or "").strip()

        # Режим диапазона, приходит из callback: "YYYY-MM-DD..YYYY-MM-DD|<mode>"
        # mode: D (по дням), A (среднее), B (оба)
        if ".." in day_str and "|" in day_str:
            try:
                range_part, mode = day_str.split("|", 1)
                start_s, end_s = range_part.split("..", 1)
                start_d = datetime.fromisoformat(start_s.strip()).date()
                end_d = datetime.fromisoformat(end_s.strip()).date()
                mode = mode.strip().upper()[:1]
            except Exception:
                return "Неверный формат периода. Использование: /day YYYY-MM-DD YYYY-MM-DD"

            if end_d < start_d:
                start_d, end_d = end_d, start_d

            return self._format_period_report(start_d, end_d, mode=mode)

        # Обычный режим одного дня
        try:
            target_date = datetime.fromisoformat(day_str).date()
        except Exception:
            return "Неверный формат. Использование: /day YYYY-MM-DD"

        # Собираем события за день по локальной TZ
        cycles = []
        trades = []
        skips = []
        equity_points = []  # (dt_loc, equity) по любым событиям, где есть equity
        report_currency = "RUB"
        try:
            with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
                import json
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                    except Exception:
                        continue
                    ts = e.get("ts_utc")
                    if not ts:
                        continue
                    try:
                        dt_utc = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        dt_loc = dt_utc.astimezone(self.tz)
                    except Exception:
                        continue
                    if dt_loc.date() != target_date:
                        continue
                    ev = e.get("event")
                    if ev == "cycle":
                        cycles.append((dt_loc, e))
                        # валюта отчёта — берем из cycle, если есть
                        cur = e.get("currency")
                        if isinstance(cur, str) and cur.strip():
                            report_currency = cur.strip().upper()
                    elif ev == "trade":
                        trades.append((dt_loc, e))
                    elif ev == "skip":
                        skips.append((dt_loc, e))

                    # equity-снимки: берём из любых событий (cycle/market/decision/trade/skip),
                    # чтобы отчёт корректно работал даже если cycle пишется редко/не пишется.
                    eq = e.get("equity")
                    if isinstance(eq, (int, float)) and float(eq) > 0:
                        equity_points.append((dt_loc, float(eq)))
        except Exception:
            pass

        if not cycles and not trades and not skips:
            return f"📅 *Отчёт за {target_date.isoformat()}*\n\nНет данных в audit-логе за этот день (бот мог быть выключен)."

        cycles.sort(key=lambda x: x[0])
        trades.sort(key=lambda x: x[0])
        skips.sort(key=lambda x: x[0])

        # Equity метрики (по всем событиям, где есть equity)
        start_eq = None
        end_eq = None
        eq_series = [v for _, v in sorted(equity_points, key=lambda x: x[0])]

        # Сегментация по скачкам (пополнение/смена базы) — чтобы отчёт отражал торговлю за день.
        # Берем ПОСЛЕ последнего большого скачка equity в рамках дня.
        seg_series = list(eq_series)
        try:
            jump_pct = float(DAILY_CASHFLOW_JUMP_PCT) if isinstance(DAILY_CASHFLOW_JUMP_PCT, (int, float)) else 0.30
            jump_pct = max(0.05, min(0.95, jump_pct))
            if len(seg_series) >= 2:
                seg_start_idx = 0
                prev = seg_series[0]
                for i in range(1, len(seg_series)):
                    cur = seg_series[i]
                    if prev > 0:
                        rel = abs(cur - prev) / prev
                        if rel >= jump_pct:
                            seg_start_idx = i
                    prev = cur
                seg_series = seg_series[seg_start_idx:] if seg_start_idx < len(seg_series) else seg_series
        except Exception:
            seg_series = list(eq_series)

        if seg_series:
            start_eq = seg_series[0]
            end_eq = seg_series[-1]

        max_dd = 0.0
        if seg_series:
            peak = seg_series[0]
            trough_dd = 0.0
            for v in seg_series:
                if v > peak:
                    peak = v
                dd = (v - peak) / peak if peak > 0 else 0.0
                trough_dd = min(trough_dd, dd)
            max_dd = trough_dd

        # Реализованный P/L по trade событиям за день (по average-cost в пределах лога)
        # Для точности мы считаем базу по всем сделкам до конца дня, но суммируем realized только внутри дня.
        realized = 0.0
        realized_profit = 0.0
        realized_loss = 0.0
        buy_count = 0
        sell_count = 0
        positions = {}  # sym -> {shares, cost}
        try:
            with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
                import json
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                    except Exception:
                        continue
                    if e.get("event") != "trade":
                        continue
                    ts = e.get("ts_utc")
                    if not ts:
                        continue
                    try:
                        dt_utc = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        dt_loc = dt_utc.astimezone(self.tz)
                    except Exception:
                        continue

                    sym = str(e.get("symbol") or "").upper().strip()
                    if not sym:
                        continue
                    action = str(e.get("action") or "").upper().strip()
                    if action not in ("BUY", "SELL"):
                        continue
                    price = float(e.get("price") or 0.0)
                    qty_lots = e.get("qty_lots")
                    lot = e.get("lot")
                    shares = 0.0
                    try:
                        if isinstance(qty_lots, (int, float)) and isinstance(lot, (int, float)) and float(lot) > 0:
                            shares = float(qty_lots) * float(lot)
                        elif isinstance(qty_lots, (int, float)):
                            shares = float(qty_lots)
                    except Exception:
                        shares = 0.0
                    if shares <= 0:
                        continue

                    p = positions.setdefault(sym, {"shares": 0.0, "cost": 0.0})
                    cur_sh = float(p["shares"])
                    cur_cost = float(p["cost"])
                    avg = (cur_cost / cur_sh) if cur_sh > 0 else 0.0

                    if action == "BUY":
                        cur_sh += shares
                        cur_cost += shares * price
                        if dt_loc.date() == target_date:
                            buy_count += 1
                    else:
                        # realized P/L vs avg cost
                        sell_sh = min(shares, cur_sh) if cur_sh > 0 else 0.0
                        if sell_sh > 0:
                            pnl = sell_sh * (price - avg)
                            if dt_loc.date() == target_date:
                                realized += pnl
                                sell_count += 1
                                if pnl >= 0:
                                    realized_profit += pnl
                                else:
                                    realized_loss += pnl
                            cur_sh -= sell_sh
                            cur_cost -= sell_sh * avg
                            if cur_sh <= 1e-9:
                                cur_sh = 0.0
                                cur_cost = 0.0

                    p["shares"] = cur_sh
                    p["cost"] = cur_cost
        except Exception:
            pass

        # Текст
        lines = [f"📅 *Отчёт за {target_date.isoformat()}*"]
        lines.append(f"Валюта отчёта: *{report_currency}* — все денежные значения ниже в этой валюте.")
        if start_eq and end_eq:
            day_ret = (end_eq - start_eq) / start_eq if start_eq > 0 else 0.0
            delta_eq = (end_eq - start_eq)
            lines.append("")
            lines.append(f"Equity старт: *{start_eq:.2f} {report_currency}* — стоимость портфеля на первом снимке дня.")
            lines.append(f"Equity конец: *{end_eq:.2f} {report_currency}* — стоимость портфеля на последнем снимке дня.")
            lines.append(
                f"Δ equity: *{delta_eq:.2f} {report_currency}* — изменение стоимости портфеля за день (Equity конец − Equity старт)."
            )
            lines.append(f"Доходность дня: *{day_ret*100:.2f}%* — Δ / Equity старт.")
            lines.append(f"Макс. просадка (intraday): *{max_dd*100:.2f}%* — максимум падения от внутридневного пика equity.")
        else:
            lines.append("\nEquity: недостаточно cycle‑снимков за день для расчёта просадки.")

        lines.append("")
        lines.append(f"Сделок (по audit): BUY={buy_count}, SELL={sell_count} — количество событий trade в audit‑логе за день.")
        lines.append(
            f"Реализованный P/L: *{realized:.2f} {report_currency}* — прибыль/убыток только по закрытым сделкам (SELL), оценка по avg-cost. "
            f"(profit={realized_profit:.2f} {report_currency}, loss={realized_loss:.2f} {report_currency})"
        )

        # Нереализованный P/L напрямую без цен по позициям не восстановить, если бот не логировал цены на каждом цикле.
        # Поэтому показываем "остаток" от изменения equity после вычитания realized.
        if start_eq and end_eq:
            residual = (end_eq - start_eq) - realized
            lines.append(
                f"Нереализованный P/L + комиссии (остаток): *{residual:.2f} {report_currency}* — то, что осталось в Δ equity после вычитания реализованного P/L. "
                f"Обычно это изменение оценки открытых позиций + комиссии/округления."
            )
            total_pl = realized + residual
            lines.append(
                f"Итоговый P/L (сверка): *{total_pl:.2f} {report_currency}* — реализованный + остаток. Должен совпадать с Δ equity."
            )

        lines.append(f"Пропусков (skip): {len(skips)} — сколько раз бот решил НЕ входить/не выполнять действие.")

        if start_eq and end_eq:
            lines.append("")
            lines.append("*Сверка (чтобы “дебет с кредитом” сошёлся):*")
            lines.append("Δ equity = Реализованный P/L + (Нереализованный P/L + комиссии/прочее).")
            lines.append(
                f"{(end_eq-start_eq):.2f} {report_currency} = {realized:.2f} {report_currency} + {((end_eq-start_eq)-realized):.2f} {report_currency}"
            )

        lines.append("")
        lines.append(
            "Примечание про “упущенные сделки”: корректно считать можно только если логировать цены/сигналы и правило выхода. "
            "Если хотите — добавлю расширенное логирование сигналов, и тогда /day сможет оценивать “упущенную прибыль/убыток”."
        )
        return "\n".join(lines)

    def _format_period_report(self, start_d, end_d, mode: str) -> str:
        """
        mode:
          D - по дням
          A - среднее по дням (и суммарно)
          B - и по дням, и среднее
        """
        # собираем отчёты по каждому дню, используя уже готовую функцию одного дня
        days = []
        cur = start_d
        while cur <= end_d:
            days.append(cur)
            cur = cur + timedelta(days=1)

        # Берём метрики из текста (мы не переписываем весь пайплайн), но аккуратно считаем средние по тем дням,
        # где есть cycle‑снимки (Equity старт/конец присутствуют).
        per_day_texts = []
        day_returns = []
        day_dds = []
        deltas = []
        realized_list = []
        missing = 0

        for d in days:
            txt = self.get_day_report_text(d.isoformat())
            per_day_texts.append((d, txt))
            if "Нет данных" in txt or "недостаточно cycle" in txt.lower():
                missing += 1
            # вытаскиваем из текста численные значения best-effort
            try:
                import re
                # Δ equity (новый формат) или старый "Изменение equity (Δ)"
                m = re.search(r"Δ equity: \*([-\d\.]+)", txt)
                if not m:
                    m = re.search(r"Изменение equity \(Δ\): \*([-\d\.]+)\*", txt)
                if m:
                    deltas.append(float(m.group(1)))
                m = re.search(r"Доходность дня: \*([-\d\.]+)%\*", txt)
                if m:
                    day_returns.append(float(m.group(1)))
                m = re.search(r"Макс\. просадка \(intraday\): \*([-\d\.]+)%\*", txt)
                if m:
                    day_dds.append(float(m.group(1)))
                m = re.search(r"Реализованный P/L: \*([-\d\.]+)", txt)
                if m:
                    realized_list.append(float(m.group(1)))
            except Exception:
                pass

        avg_ret = sum(day_returns) / len(day_returns) if day_returns else 0.0
        avg_dd = sum(day_dds) / len(day_dds) if day_dds else 0.0
        sum_delta = sum(deltas) if deltas else 0.0
        sum_realized = sum(realized_list) if realized_list else 0.0

        header = f"📅 *Отчёт за период {start_d.isoformat()} → {end_d.isoformat()}*"
        lines = [header]
        # Валюта: берём из первого дня с данными (обычно RUB для T‑Invest). Если данных нет — RUB.
        report_currency = "RUB"
        for _, txt in per_day_texts:
            if "Валюта отчёта:" in txt:
                try:
                    for ln in txt.splitlines():
                        if ln.startswith("Валюта отчёта:"):
                            report_currency = ln.split("*")[1].strip()
                            break
                except Exception:
                    pass
                break
        lines.append(f"Валюта отчёта: *{report_currency}* — все денежные значения ниже в этой валюте.")
        lines.append(f"Дней в периоде: {len(days)} (с данными: {len(days)-missing}, без данных: {missing})")

        if mode in ("D", "B"):
            lines.append("\n*Разбивка по дням:*")
            for d, txt in per_day_texts:
                # короткая шапка + ключевые строки (чтобы не было простыни)
                lines.append(f"\n— *{d.isoformat()}* —")
                for ln in txt.splitlines():
                    if ln.startswith("Equity старт") or ln.startswith("Equity конец") or ln.startswith("Изменение equity") or ln.startswith("Доходность дня") or ln.startswith("Макс. просадка") or ln.startswith("Реализованный P/L") or ln.startswith("Нереализованный P/L") or ln.startswith("Итоговый P/L"):
                        lines.append(ln)
                    if "Нет данных" in ln:
                        lines.append(ln)

        if mode in ("A", "B"):
            lines.append("\n*Среднее/итоги за период:*")
            lines.append(f"Средняя дневная доходность: *{avg_ret:.2f}%* — среднее по дням, где она была рассчитана.")
            lines.append(f"Средняя макс. просадка дня: *{avg_dd:.2f}%* — среднее intraday DD по дням.")
            lines.append(f"Суммарное Δ equity (по доступным дням): *{sum_delta:.2f} {report_currency}*")
            lines.append(f"Суммарный реализованный P/L: *{sum_realized:.2f} {report_currency}*")
            lines.append("\n*Сверка:*")
            lines.append("Итоги по периоду складываются из дневных Δ equity; средние — это среднее по дневным процентам/просадкам.")

        return "\n".join(lines)

    def _audit_event(self, payload: Dict):
        """
        Запись в аудит-логи (JSONL + CSV), append-only.

        - payload: dict с данными события (trade/skip/cycle).
        """
        try:
            event = dict(payload or {})
            # Единый timestamp для обоих логов
            if "ts_utc" not in event or not event.get("ts_utc"):
                event["ts_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

            # JSONL (полная структура)
            self.audit.append(event)

            # CSV (удобно для Excel). Сложные поля складываем в details.
            order = event.get("order")
            order_id = ""
            status = ""
            figi = ""
            if isinstance(order, dict):
                order_id = order.get("order_id") or order.get("id") or ""
                status = order.get("status") or ""
                figi = order.get("figi") or ""

            self.audit_csv.append({
                "ts_utc": event.get("ts_utc", ""),
                "event": event.get("event", ""),
                "symbol": event.get("symbol", ""),
                "action": event.get("action", ""),
                "qty_lots": event.get("qty_lots", ""),
                "lot": event.get("lot", ""),
                "price": event.get("price", ""),
                "reason": event.get("reason", ""),
                "skip_reason": event.get("skip_reason", ""),
                "confidence": event.get("confidence", ""),
                "buy_signals": event.get("buy_signals", ""),
                "sell_signals": event.get("sell_signals", ""),
                "rsi": event.get("rsi", ""),
                "trend": event.get("trend", ""),
                "atr": event.get("atr", ""),
                "macd": event.get("macd", ""),
                "macd_signal": event.get("macd_signal", ""),
                "macd_hist": event.get("macd_hist", ""),
                "equity": event.get("equity", ""),
                "cash": event.get("cash", ""),
                "open_positions": event.get("open_positions", ""),
                "trades_today_buy": event.get("trades_today_buy", ""),
                "order_id": order_id,
                "status": status,
                "figi": figi,
                "details": event.get("details", ""),
            })
        except Exception:
            # Никогда не ломаем торговый цикл из-за логов
            pass

    def _escape_markdown(self, text: str) -> str:
        """Экранировать специальные символы Markdown для Telegram (кроме уже используемых для разметки)"""
        if not text:
            return ""
        # Экранируем только символы, которые могут конфликтовать с разметкой
        # НЕ экранируем символы, которые мы используем для разметки (* для жирного)
        # Список всех специальных символов Markdown V2: _ * [ ] ( ) ~ ` > # + - = | { } . !
        special_chars = ['[', ']', '(', ')', '~', '`', '>', '#', '+', '=', '|', '{', '}', '.', '!', '-']
        result = str(text)
        for char in special_chars:
            result = result.replace(char, f'\\{char}')
        return result
    
    def get_status_text(self) -> str:
        mode = "✅ ВКЛ" if self.allow_entries else "⛔ ВЫКЛ"
        dd_txt = ""
        hb_txt = ""
        try:
            ai = self.broker.get_account_info()
            eq = float(ai.get("equity", 0) or 0)
            # Обновляем trades_today из audit-лога (на случай перезапуска/рассинхронизации)
            try:
                today = datetime.now(self.tz).date()
                self.trades_today = max(int(self.trades_today or 0), self._count_buys_for_date(today))
            except Exception:
                pass
            # ВАЖНО: после рестарта state может быть "устаревшим" (например, пик был до рестарта).
            # Поэтому для статуса всегда сверяем start/peak по audit-логу за сегодня.
            if eq > 0:
                try:
                    today_iso = self._trading_day(datetime.now(self.tz)).isoformat()
                    a_start, a_peak = self._day_metrics_from_audit(today_iso)
                    if isinstance(a_start, (int, float)) and a_start > 0:
                        # start дня — это первое observed equity за дату (по всем запускам)
                        self.day_start_equity = float(a_start)
                    if isinstance(a_peak, (int, float)) and a_peak > 0:
                        # peak дня — максимум equity за дату (по всем запускам)
                        self.day_peak_equity = float(a_peak)
                    if self.day_start_equity and self.day_peak_equity:
                        save_json_atomic(
                            DAILY_STATE_PATH,
                            {
                                "date": today_iso,
                                "day_start_equity": float(self.day_start_equity),
                                "day_peak_equity": float(self.day_peak_equity),
                            },
                        )
                except Exception:
                    # fallback: попробуем восстановить хотя бы из state
                    try:
                        self._restore_daily_state()
                    except Exception:
                        pass
                if self.day_peak_equity is None and self.day_start_equity:
                    self.day_peak_equity = float(self.day_start_equity)

            if self.day_start_equity and self.day_start_equity > 0 and eq > 0:
                day_change = (eq - self.day_start_equity) / self.day_start_equity

                # Если equity резко выросла без явной причины (обычно это sandbox пополнение),
                # чтобы “статистика была чистой” — сбрасываем базу дня на текущее значение.
                # Порог 30% выбран как безопасный (для нормальной торговли за день редко).
                try:
                    if float(day_change) > 0.30 and int(self.trades_today or 0) == 0:
                        self.day_start_equity = float(eq)
                        today_iso = self._trading_day(datetime.now(self.tz)).isoformat()
                        save_json_atomic(DAILY_STATE_PATH, {"date": today_iso, "day_start_equity": float(self.day_start_equity), "day_peak_equity": float(eq)})
                        self._audit_event({
                            "event": "cycle",
                            "skip_reason": "day_start_equity_reset_after_cashflow",
                            "equity": float(eq),
                            "cash": float(ai.get("cash", 0) or 0),
                            "details": {"day_change_pct": float(day_change) * 100.0},
                        })
                        day_change = 0.0
                except Exception:
                    pass

                # “Поднятие/Просадка” — правильный расчет:
                # ВАЖНО: пересчитываем от актуального day_start_equity, даже если day_change был сброшен
                # Поднятие = только если equity выросла от старта дня (положительное изменение)
                # Просадка = только если equity упала от старта дня (отрицательное изменение)
                # Также просадка от пика = максимальная просадка от дневного пика
                
                # Пересчитываем day_change от актуального day_start_equity (на случай, если он был сброшен)
                actual_day_change = (eq - float(self.day_start_equity)) / float(self.day_start_equity) if float(self.day_start_equity) > 0 else 0.0
                
                uplift = max(0.0, float(actual_day_change)) if float(actual_day_change) > 0 else 0.0
                drawdown_from_start = max(0.0, -float(actual_day_change)) if float(actual_day_change) < 0 else 0.0

                # Просадка от дневного пика (максимальная просадка за день)
                try:
                    peak = float(self.day_peak_equity) if self.day_peak_equity else float(self.day_start_equity)
                    if peak > 0 and eq > peak:
                        peak = eq
                        self.day_peak_equity = float(peak)
                        today_iso = self._trading_day(datetime.now(self.tz)).isoformat()
                        save_json_atomic(DAILY_STATE_PATH, {"date": today_iso, "day_start_equity": float(self.day_start_equity), "day_peak_equity": float(self.day_peak_equity)})
                    day_drawdown_from_peak = max(0.0, (peak - eq) / peak) if peak > 0 else 0.0
                    # Используем максимальную из двух просадок: от старта или от пика
                    day_drawdown = max(drawdown_from_start, day_drawdown_from_peak)
                except Exception:
                    day_drawdown = drawdown_from_start

                # Безопасное форматирование с экранированием
                # Используем actual_day_change для отображения, чтобы показывать реальное изменение
                day_change_val = f"{actual_day_change*100:.2f}"
                uplift_val = f"{uplift*100:.2f}"
                drawdown_val = f"{day_drawdown*100:.2f}"
                limit_val = f"{abs(float(DAILY_LOSS_LIMIT_PCT))*100:.2f}"
                dd_txt = (
                    f"\nΔ equity за день: *{day_change_val}%*"
                    f"\nПоднятие за день: *{uplift_val}%*"
                    f"\nПросадка за день: *{drawdown_val}%* (лимит {limit_val}%)"
                )

            # Heartbeat: показываем, что бот реально пишет market/decision/cycle в audit-лог.
            try:
                now_loc = datetime.now(self.tz)

                def _age_min(ts_utc: str) -> float | None:
                    if not ts_utc:
                        return None
                    try:
                        dt_utc = datetime.fromisoformat(ts_utc.replace("Z", "+00:00"))
                        dt_loc = dt_utc.astimezone(self.tz)
                        return (now_loc - dt_loc).total_seconds() / 60.0
                    except Exception:
                        return None

                last_cycle = read_last_jsonl_events(AUDIT_LOG_PATH, limit=1, predicate=lambda e: e.get("event") == "cycle")
                last_dec = read_last_jsonl_events(AUDIT_LOG_PATH, limit=1, predicate=lambda e: e.get("event") == "decision")

                lc = last_cycle[0] if last_cycle else None
                ld = last_dec[0] if last_dec else None

                lc_ts = (lc or {}).get("ts_utc", "")
                ld_ts = (ld or {}).get("ts_utc", "")
                lc_age = _age_min(lc_ts)
                ld_age = _age_min(ld_ts)

                lc_no = (lc or {}).get("cycle_no", None)
                ld_sym = (ld or {}).get("symbol", None)

                parts = []
                if lc_ts:
                    parts.append(f"последний cycle: {str(lc_ts).replace('T', ' ').replace('Z', ' UTC')}")
                    if lc_no is not None:
                        # Экранируем скобки для Markdown
                        parts[-1] += f" \\(№{lc_no}\\)"
                    if isinstance(lc_age, (int, float)):
                        parts[-1] += f" — {lc_age:.1f} мин назад"
                if ld_ts:
                    sfx = f", {ld_sym}" if ld_sym else ""
                    parts.append(f"последнее decision{sfx}: {str(ld_ts).replace('T', ' ').replace('Z', ' UTC')}")
                    if isinstance(ld_age, (int, float)):
                        parts[-1] += f" — {ld_age:.1f} мин назад"

                # Простейший алерт: если последний цикл сильно старше UPDATE_INTERVAL*2 — возможно завис/остановлен.
                warn = ""
                try:
                    if isinstance(lc_age, (int, float)) and lc_age * 60.0 > float(UPDATE_INTERVAL) * 2.2:
                        # Экранируем обратные кавычки для Markdown
                        warn = "\n⚠️ Похоже, цикл давно не обновлялся — проверьте, что \\`python main.py\\` ещё запущен."
                except Exception:
                    pass

                if parts:
                    # Экранируем все части heartbeat для безопасности
                    # Используем _escape_markdown для правильного экранирования всех специальных символов
                    safe_parts = []
                    for p in parts:
                        # Экранируем все специальные символы Markdown
                        safe_p = self._escape_markdown(str(p))
                        safe_parts.append(safe_p)
                    # Экранируем также warn, если он есть
                    warn_safe = self._escape_markdown(warn) if warn else ""
                    hb_txt = "\n\n🫀 *Heartbeat*\n" + "\n".join(f"- {p}" for p in safe_parts) + warn_safe
            except Exception:
                hb_txt = ""
        except Exception:
            pass
        
        # Безопасное форматирование всех значений для Markdown
        # Экранируем значения, которые могут содержать специальные символы
        broker_safe = self._escape_markdown(str(BROKER))
        sandbox_safe = self._escape_markdown(str(TINVEST_SANDBOX))
        interval_safe = self._escape_markdown(str(BAR_INTERVAL))
        history_safe = self._escape_markdown(str(HISTORY_LOOKBACK))
        trades_safe = str(self.trades_today or 0)
        max_trades_safe = str(MAX_TRADES_PER_DAY)
        max_pos_safe = str(MAX_OPEN_POSITIONS)
        cooldown_safe = str(SYMBOL_COOLDOWN_MIN)
        
        return (
            "ℹ️ *Статус бота*\n\n"
            f"Брокер: *{broker_safe}* (sandbox={sandbox_safe})\n"
            f"Входы (BUY): {mode}\n"
            f"Интервал: *{interval_safe}* / история: *{history_safe}*\n"
            f"Ограничения: max_trades/day={max_trades_safe}, max_positions={max_pos_safe}, cooldown={cooldown_safe}m\n"
            f"Сделок сегодня (BUY): *{trades_safe}*\n"
            + (dd_txt if dd_txt else "")
            + (hb_txt if hb_txt else "")
        )

    def get_portfolio_text(self) -> str:
        ai = self.broker.get_account_info()
        pos = self.broker.get_positions() or []
        orders = []
        try:
            orders = self.broker.get_open_orders() or []
        except Exception:
            orders = []
        try:
            logger.info(f"Telegram PORTFOLIO: positions={len(pos)}, open_orders={len(orders)}")
        except Exception:
            pass
        # Обогащаем позиции покупной ценой из audit-лога (фактические BUY цены).
        try:
            cost_map = compute_avg_cost_from_audit(AUDIT_LOG_PATH)
        except Exception:
            cost_map = {}

        for p in pos:
            sym = str(p.get("symbol", "") or "").upper().strip()
            if not sym:
                continue
            cm = cost_map.get(sym)
            if not cm:
                continue
            # avg_price по audit-логу в "цене за акцию"
            p["avg_entry_price"] = float(cm.get("avg_price", 0.0) or 0.0)
            p["entry_price_source"] = "audit"
            p["entry_last_buy_ts_utc"] = cm.get("last_buy_ts_utc", "")

        return self.telegram.format_account_status(ai, pos, open_orders=orders, recent_operations=None, last_order_state=None)

    def get_trades_text(self) -> str:
        # 1) Предпочтительно показываем сделки/операции из T‑Invest API (истина брокера).
        ops = []
        try:
            ops = self.broker.get_recent_operations(limit=10) or []
        except Exception:
            ops = []

        if ops:
            lines = ["🧾 *Последние сделки (до 10)*\n_Источник: T‑Invest API (операции)_\n"]
            for op in ops:
                dt = op.get("date", "")
                ticker = op.get("ticker", "") or op.get("figi", "")
                typ = op.get("type", "")
                state = op.get("state", "")
                qty = op.get("quantity", None)
                price = op.get("price", None)
                pay = op.get("payment", 0.0)
                cur = op.get("currency", "RUB")
                qty_s = f"x{qty}" if isinstance(qty, int) else ""
                price_s = f"@ {price:.2f} {cur}" if isinstance(price, (int, float)) else ""
                lines.append(f"- {dt}: {ticker} {qty_s} {price_s} | {typ} {state} | {pay:.2f} {cur}")
            return "\n".join(lines)

        # 2) Fallback: если API временно не отдаёт операции — показываем из audit-лога.
        events = read_last_jsonl_events(AUDIT_LOG_PATH, limit=10, predicate=lambda e: e.get("event") == "trade")
        if not events:
            return "🧾 *Последние сделки*\n\nПока нет записей."

        lines = ["🧾 *Последние сделки (до 10)*\n_Источник: локальный audit‑лог_\n"]
        for e in events:
            ts = e.get("ts_utc", "")
            action = e.get("action", "?")
            sym = e.get("symbol", "?")
            ql = e.get("qty_lots", "")
            lot = e.get("lot", None)
            try:
                shares = int(ql) * int(lot) if (isinstance(ql, int) and isinstance(lot, int) and lot > 0) else None
            except Exception:
                shares = None
            qty_s = f"{ql} лот" + (f" ({shares} акций)" if shares is not None else "")
            price = e.get("price", 0)
            reason = e.get("reason", "")
            oid = ""
            try:
                if isinstance(e.get("order"), dict):
                    oid = e["order"].get("order_id", "") or ""
            except Exception:
                oid = ""
            oid_s = f", id={oid}" if oid else ""
            lines.append(f"- {ts}: *{action}* {sym} {qty_s} @ {price:.2f} ({reason}){oid_s}")
        return "\n".join(lines)

    async def tg_start_entries(self):
        self.allow_entries = True

    async def tg_stop_entries(self):
        self.allow_entries = False
    
    async def start(self):
        """Запустить бота"""
        self.running = True
        logger.info("Торговый бот запущен")
        
        # Отправляем уведомление о запуске
        start_mode = "ВКЛ" if self.allow_entries else "ВЫКЛ"
        await self.telegram.send_message(
            f"🤖 *Торговый бот запущен*\n\n"
            f"Режим входов (BUY): *{start_mode}*\n"
            f"Песочница: *{TINVEST_SANDBOX}*\n"
            f"Интервал: *{BAR_INTERVAL}*, история: *{HISTORY_LOOKBACK}*",
            parse_mode="Markdown"
        )

        # Telegram панель управления (polling в фоне)
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            try:
                self.telegram_control = TelegramControlPanel(
                    token=TELEGRAM_BOT_TOKEN,
                    chat_id=TELEGRAM_CHAT_ID,
                    keyboard_factory=self.telegram.build_control_keyboard,
                    on_start=self.tg_start_entries,
                    on_stop=self.tg_stop_entries,
                    get_status_text=self.get_status_text,
                    get_portfolio_text=self.get_portfolio_text,
                    get_trades_text=self.get_trades_text,
                    get_day_report_text=self.get_day_report_text,
                )
                asyncio.create_task(self.telegram_control.start())
                await self.telegram.send_message(
                    "Панель управления: отправьте команду `/menu`",
                    parse_mode="Markdown",
                    reply_markup=self.telegram.build_control_keyboard(),
                )
            except Exception as e:
                logger.error(f"Не удалось запустить Telegram панель: {e}", exc_info=True)
        
        # Основной цикл
        while self.running:
            try:
                # Сброс дневного счетчика сделок
                today = self._trading_day(datetime.now(self.tz))
                if today != self.trades_day:
                    self.trades_day = today
                    self.trades_today = 0
                    self.day_start_equity = None
                    try:
                        save_json_atomic(DAILY_STATE_PATH, {"date": today.isoformat(), "day_start_equity": None, "day_peak_equity": None})
                    except Exception:
                        pass

                await self.process_symbols()
                await self.check_positions()
                await asyncio.sleep(UPDATE_INTERVAL)
            except KeyboardInterrupt:
                logger.info("Получен сигнал остановки")
                break
            except asyncio.CancelledError:
                # Нормально при Ctrl+C в asyncio.run — выходим без traceback
                logger.info("Отмена задач (CancelledError). Останавливаемся...")
                break
            except Exception as e:
                logger.error(f"Ошибка в основном цикле: {e}", exc_info=True)
                await asyncio.sleep(UPDATE_INTERVAL)
        
        await self.stop()
    
    async def process_symbols(self):
        """Обработать все символы"""
        self.cycle_no += 1
        account_info = self.broker.get_account_info()
        positions = self.broker.get_positions() or []

        # Реальное число открытых позиций (уникальные позиции), а не число ключей в open_symbols.
        # open_symbols индексируется по нескольким ключам (symbol/ticker/figi/alias), поэтому len(open_symbols)
        # может быть больше и ошибочно блокировать входы по MAX_OPEN_POSITIONS.
        open_positions_count = 0
        try:
            uniq = set()
            for pos in positions:
                qty_lots = pos.get("qty_lots", pos.get("qty", 0)) or 0
                try:
                    if float(qty_lots) <= 0:
                        continue
                except Exception:
                    pass

                figi = pos.get("figi")
                if figi:
                    uniq.add(str(figi).strip().upper())
                    continue

                sym = pos.get("symbol") or pos.get("ticker")
                sym = _canon_symbol(sym) if sym else ""
                if sym:
                    uniq.add(str(sym).strip().upper())
            open_positions_count = len(uniq)
        except Exception:
            open_positions_count = len(positions)
        # Важно: позиции могут приходить как ticker или figi (а также с разными алиасами).
        # Чтобы стопы/логика "есть позиция" работали устойчиво, индексируем по нескольким ключам.
        open_symbols: Dict[str, Dict] = {}
        for pos in positions:
            keys = []
            for k in (pos.get("symbol"), pos.get("ticker"), pos.get("figi")):
                if k:
                    keys.append(str(k).strip().upper())
            for k in keys:
                open_symbols[k] = pos
                # Также индексируем по каноническому тикеру (если есть алиасы)
                ck = _canon_symbol(k)
                if ck:
                    open_symbols[ck] = pos

        # Пишем "heartbeat" (нечасто) в аудит-лог: факт цикла + основные параметры.
        # Это помогает расследовать "почему не было сделок" без просмотра консоли.
        self._audit_event({
            "event": "cycle",
            "cycle_no": int(self.cycle_no),
            "broker": BROKER,
            "sandbox": bool(TINVEST_SANDBOX),
            "allow_entries": bool(self.allow_entries),
            "symbols_count": len(SYMBOLS),
            "open_positions": int(open_positions_count),
            "equity": float(account_info.get("equity", 0) or 0),
            "cash": float(account_info.get("cash", 0) or 0),
            "currency": str(account_info.get("currency", "RUB") or "RUB"),
            "trades_today_buy": int(self.trades_today),
        })

        # дневной лимит убытка (по equity)
        eq = float(account_info.get("equity", 0) or 0)
        # ВАЖНО: старт дня не должен сбрасываться при перезапуске.
        # 1) если уже восстановлен — используем
        # 2) если нет — пытаемся взять из audit (первый cycle за сегодня)
        # 3) если и там нет — фиксируем текущий equity как старт дня и сохраняем
        if self.day_start_equity is None and eq > 0:
            today_iso = self._trading_day(datetime.now(self.tz)).isoformat()
            start, peak = self._day_metrics_from_audit(today_iso)
            if isinstance(start, (int, float)) and start > 0:
                self.day_start_equity = float(start)
                self.day_peak_equity = float(peak) if isinstance(peak, (int, float)) and peak > 0 else float(self.day_start_equity)
            else:
                # Если в audit за сегодня нет данных (бот был выключен), фиксируем текущую equity как старт дня.
                self.day_start_equity = eq
                self.day_peak_equity = eq
            try:
                save_json_atomic(DAILY_STATE_PATH, {"date": today_iso, "day_start_equity": float(self.day_start_equity), "day_peak_equity": float(self.day_peak_equity or self.day_start_equity)})
            except Exception:
                pass

        # Обновляем дневной пик equity и сохраняем, чтобы рестарт не обнулял просадку.
        if self.day_start_equity and self.day_start_equity > 0 and eq > 0:
            if self.day_peak_equity is None or float(eq) > float(self.day_peak_equity):
                self.day_peak_equity = float(eq)
                try:
                    today_iso = self._trading_day(datetime.now(self.tz)).isoformat()
                    save_json_atomic(DAILY_STATE_PATH, {"date": today_iso, "day_start_equity": float(self.day_start_equity), "day_peak_equity": float(self.day_peak_equity)})
                except Exception:
                    pass
        if self.day_start_equity and self.day_start_equity > 0:
            dd = (eq - self.day_start_equity) / self.day_start_equity
            if dd <= -abs(float(DAILY_LOSS_LIMIT_PCT)):
                if self.allow_entries:
                    self.allow_entries = False
                    # Логируем причину отключения входов
                    self._audit_event({
                        "event": "skip",
                        "skip_reason": "daily_loss_limit_reached",
                        "equity": float(eq),
                        "cash": float(account_info.get("cash", 0) or 0),
                        "open_positions": int(open_positions_count),
                        "trades_today_buy": int(self.trades_today),
                        "details": {
                            "day_start_equity": float(self.day_start_equity),
                            "daily_drawdown": float(dd),
                            "daily_loss_limit_pct": float(DAILY_LOSS_LIMIT_PCT),
                        }
                    })
                    await self.telegram.send_message(
                        f"🛑 *Дневной лимит убытка достигнут*\n\n"
                        f"Старт дня: {self.day_start_equity:.2f}\n"
                        f"Текущая equity: {eq:.2f}\n"
                        f"Просадка: {dd*100:.2f}%\n\n"
                        f"Новые входы (BUY) отключены до конца дня.",
                        parse_mode="Markdown"
                    )

        # Доп. лимит: просадка от ПИКА за торговый день (если включено)
        try:
            peak_lim = float(DAILY_PEAK_DRAWDOWN_LIMIT_PCT or 0.0)
        except Exception:
            peak_lim = 0.0
        if peak_lim and self.day_peak_equity and float(self.day_peak_equity) > 0 and eq > 0:
            dd_peak = (eq - float(self.day_peak_equity)) / float(self.day_peak_equity)
            # Логирование для диагностики блокировки покупок
            logger.info(f"Проверка просадки от пика: пик={float(self.day_peak_equity):.2f}, текущая={eq:.2f}, просадка={dd_peak*100:.2f}%, лимит={peak_lim*100:.2f}%, allow_entries={self.allow_entries}")
            if dd_peak <= -abs(float(peak_lim)) and self.allow_entries:
                logger.warning(f"БЛОКИРОВКА ПОКУПОК: просадка от пика {dd_peak*100:.2f}% достигла лимита {peak_lim*100:.2f}%")
                self.allow_entries = False
                self._audit_event({
                    "event": "skip",
                    "skip_reason": "daily_peak_drawdown_limit_reached",
                    "equity": float(eq),
                    "cash": float(account_info.get("cash", 0) or 0),
                    "open_positions": int(open_positions_count),
                    "trades_today_buy": int(self.trades_today),
                    "details": {
                        "day_peak_equity": float(self.day_peak_equity),
                        "daily_drawdown_from_peak": float(dd_peak),
                        "daily_peak_drawdown_limit_pct": float(peak_lim),
                    },
                })
                await self.telegram.send_message(
                    f"🛑 *Просадка от дневного пика достигла лимита*\n\n"
                    f"Пик дня: {float(self.day_peak_equity):.2f}\n"
                    f"Текущая equity: {eq:.2f}\n"
                    f"Просадка от пика: {dd_peak*100:.2f}%\n\n"
                    f"Новые входы (BUY) отключены до конца торгового дня.",
                    parse_mode="Markdown",
                )
        
        # --- PASS 1: анализируем все символы и собираем BUY-кандидатов (SELL обрабатываем сразу) ---
        buy_candidates: List[Dict] = []
        for symbol in SYMBOLS:
            try:
                sym_key = str(symbol).strip().upper()
                sym_key = _canon_symbol(sym_key)
                has_position = bool(open_symbols.get(sym_key) or open_symbols.get(sym_key.lower()))
                if has_position:
                    # SELL-логика и обновление трейлинг-стопов — только для открытых позиций
                    await self.process_symbol(symbol, account_info, open_symbols)
                    continue

                data = self.broker.get_historical_data(symbol, period=HISTORY_LOOKBACK, interval=BAR_INTERVAL)
                if data is None or getattr(data, "empty", True):
                    continue
                analysis = self.strategy.analyze(data)
                current_price = analysis.get("price", 0)
                if not current_price:
                    continue

                # Базовые гейты входа (включая дневной лимит, позиции, cooldown, лимиты)
                gates = {
                    "has_position": False,
                    "allow_entries": bool(self.allow_entries),
                    "max_open_positions_ok": not (MAX_OPEN_POSITIONS > 0 and int(open_positions_count) >= int(MAX_OPEN_POSITIONS)),
                    "cooldown_ok": not (self.cooldown_until.get(symbol) and datetime.now() < self.cooldown_until.get(symbol)),
                    "max_trades_ok": not (self.trades_today >= MAX_TRADES_PER_DAY),
                    "enable_trading": bool(ENABLE_TRADING),
                }

                # Логируем decision (чтобы понимать “почему не купил” даже после ранжирования)
                sampled = True
                try:
                    sample_n = max(1, int(AUDIT_DECISION_EVERY_N or 1))
                    sampled = (int(self.cycle_no) % sample_n) == 0
                except Exception:
                    sampled = True
                if AUDIT_DECISIONS and sampled:
                    sig_buy = bool(self.strategy.should_buy(analysis, min_confidence=MIN_CONF_BUY))
                    sig_sell = bool(self.strategy.should_sell(analysis, min_confidence=MIN_CONF_SELL))
                    self._audit_event({
                        "event": "decision",
                        "cycle_no": int(self.cycle_no),
                        "symbol": symbol,
                        "price": float(current_price),
                        "signal": str(analysis.get("signal", "")),
                        "confidence": float(analysis.get("confidence", 0) or 0),
                        "buy_signals": analysis.get("buy_signals"),
                        "sell_signals": analysis.get("sell_signals"),
                        "rsi": analysis.get("rsi"),
                        "trend": analysis.get("trend"),
                        "atr": analysis.get("atr"),
                        "macd": analysis.get("macd"),
                        "macd_signal": analysis.get("macd_signal"),
                        "macd_hist": analysis.get("macd_hist"),
                        "details": {
                            "strategy_should_buy": sig_buy,
                            "strategy_should_sell": sig_sell,
                            "gates": gates,
                            "min_conf_buy": float(MIN_CONF_BUY),
                            "min_conf_sell": float(MIN_CONF_SELL),
                        },
                        "equity": float(account_info.get("equity", 0) or 0),
                        "cash": float(account_info.get("cash", 0) or 0),
                        "open_positions": int(open_positions_count),
                        "trades_today_buy": int(self.trades_today),
                    })

                # Если гейты уже запрещают — не добавляем кандидата (и пусть skip пишется там, где гейт сработал)
                if not gates["allow_entries"]:
                    self._audit_event({
                        "event": "skip",
                        "symbol": symbol,
                        "skip_reason": "entries_disabled",
                        "price": float(current_price),
                        "confidence": float(analysis.get("confidence", 0) or 0),
                        "equity": float(account_info.get("equity", 0) or 0),
                        "cash": float(account_info.get("cash", 0) or 0),
                        "open_positions": int(open_positions_count),
                        "trades_today_buy": int(self.trades_today),
                    })
                    continue
                if not gates["max_open_positions_ok"]:
                    self._audit_event({
                        "event": "skip",
                        "symbol": symbol,
                        "skip_reason": "max_open_positions",
                        "open_positions": int(open_positions_count),
                        "price": float(current_price),
                        "confidence": float(analysis.get("confidence", 0) or 0),
                        "equity": float(account_info.get("equity", 0) or 0),
                        "cash": float(account_info.get("cash", 0) or 0),
                    })
                    continue
                if not gates["cooldown_ok"]:
                    cd_until = self.cooldown_until.get(symbol)
                    self._audit_event({
                        "event": "skip",
                        "symbol": symbol,
                        "skip_reason": "cooldown",
                        "price": float(current_price),
                        "confidence": float(analysis.get("confidence", 0) or 0),
                        "details": {"cooldown_until": cd_until.isoformat() if cd_until else ""},
                    })
                    continue
                if not gates["max_trades_ok"]:
                    self._audit_event({
                        "event": "skip",
                        "symbol": symbol,
                        "skip_reason": "max_trades_per_day",
                        "price": float(current_price),
                        "trades_today_buy": int(self.trades_today),
                        "details": {"max_trades_per_day": int(MAX_TRADES_PER_DAY)},
                    })
                    continue

                # Стратегия + фильтр noisy
                strategy_should_buy_result = self.strategy.should_buy(analysis, min_confidence=MIN_CONF_BUY)
                if not strategy_should_buy_result:
                    # Определяем причину блокировки для логирования
                    skip_reason = "strategy_should_buy_false"
                    skip_details = {}
                    
                    # Анализируем почему should_buy вернул False
                    rsi = analysis.get("rsi")
                    trend = analysis.get("trend", "")
                    macd_hist = analysis.get("macd_hist")
                    macd_hist_prev = analysis.get("macd_hist_prev")
                    signal = analysis.get("signal", "")
                    conf = float(analysis.get("confidence", 0) or 0)
                    
                    # Причины блокировки (в порядке приоритета проверки в should_buy)
                    if rsi is not None and not pd.isna(rsi) and float(rsi) > 68:
                        skip_reason = "strategy_blocked_rsi_too_high"
                        skip_details = {"rsi": float(rsi), "threshold": 68}
                    elif trend == 'sideways' and macd_hist is not None:
                        try:
                            if float(macd_hist) < 0:
                                rsi_val = float(rsi) if rsi is not None and not pd.isna(rsi) else None
                                conf_val = float(conf)
                                # Проверяем разрешен ли вход при перепроданности или высоком confidence
                                if rsi_val is not None and rsi_val <= 30:
                                    # Разрешено при перепроданности, значит другая причина
                                    skip_reason = "strategy_blocked_sideways_negative_macd_but_rsi_ok"
                                    skip_details = {"trend": trend, "macd_hist": float(macd_hist), "rsi": rsi_val, "confidence": conf_val}
                                elif conf_val > 0.8:
                                    # Разрешено при высоком confidence, значит другая причина
                                    skip_reason = "strategy_blocked_sideways_negative_macd_but_conf_ok"
                                    skip_details = {"trend": trend, "macd_hist": float(macd_hist), "rsi": rsi_val, "confidence": conf_val}
                                else:
                                    skip_reason = "strategy_blocked_sideways_negative_macd"
                                    skip_details = {"trend": trend, "macd_hist": float(macd_hist), "rsi": rsi_val, "confidence": conf_val}
                        except Exception:
                            skip_reason = "strategy_blocked_sideways_negative_macd"
                            skip_details = {"trend": trend, "macd_hist": macd_hist}
                    elif macd_hist is not None and macd_hist_prev is not None:
                        try:
                            if float(macd_hist) < 0 and float(macd_hist) < float(macd_hist_prev):
                                skip_reason = "strategy_blocked_falling_knife"
                                skip_details = {"macd_hist": float(macd_hist), "macd_hist_prev": float(macd_hist_prev)}
                        except Exception:
                            pass
                    elif signal != 'buy':
                        skip_reason = "strategy_blocked_signal_not_buy"
                        skip_details = {"signal": signal}
                    elif conf < float(MIN_CONF_BUY):
                        skip_reason = "strategy_blocked_low_confidence"
                        skip_details = {"confidence": conf, "min_confidence": float(MIN_CONF_BUY)}
                    else:
                        # Общая причина если не удалось определить конкретную
                        skip_reason = "strategy_should_buy_false"
                        skip_details = {"signal": signal, "confidence": conf, "trend": trend, "rsi": rsi, "macd_hist": macd_hist}
                    
                    # Логируем skip event с детальной причиной блокировки
                    self._audit_event({
                        "event": "skip",
                        "symbol": symbol,
                        "skip_reason": skip_reason,
                        "price": float(current_price),
                        "confidence": float(conf),
                        "buy_signals": analysis.get("buy_signals"),
                        "sell_signals": analysis.get("sell_signals"),
                        "rsi": rsi,
                        "trend": trend,
                        "atr": analysis.get("atr"),
                        "macd_hist": macd_hist,
                        "equity": float(account_info.get("equity", 0) or 0),
                        "cash": float(account_info.get("cash", 0) or 0),
                        "open_positions": int(open_positions_count),
                        "trades_today_buy": int(self.trades_today),
                        "details": skip_details,
                    })
                    continue
                ok_noisy, noisy_details = self._passes_noisy_entry_filter(symbol, analysis)
                if not ok_noisy:
                    # фиксируем причину в аудит
                    self._audit_event({
                        "event": "skip",
                        "symbol": symbol,
                        "skip_reason": "noisy_quality_filter",
                        "price": float(current_price),
                        "confidence": float(analysis.get("confidence", 0) or 0),
                        "buy_signals": analysis.get("buy_signals"),
                        "sell_signals": analysis.get("sell_signals"),
                        "rsi": analysis.get("rsi"),
                        "trend": analysis.get("trend"),
                        "atr": analysis.get("atr"),
                        "macd_hist": analysis.get("macd_hist"),
                        "equity": float(account_info.get("equity", 0) or 0),
                        "cash": float(account_info.get("cash", 0) or 0),
                        "open_positions": int(open_positions_count),
                        "trades_today_buy": int(self.trades_today),
                        "details": {"fails": noisy_details},
                    })
                    continue

                # Глобальные фильтры качества BUY (включаются через .env)
                try:
                    trend = str(analysis.get("trend") or "").strip().lower()
                except Exception:
                    trend = ""
                if REQUIRE_TREND_UP_BUY and trend and trend != "up":
                    self._audit_event({
                        "event": "skip",
                        "symbol": symbol,
                        "skip_reason": "quality_filter",
                        "price": float(current_price),
                        "confidence": float(analysis.get("confidence", 0) or 0),
                        "details": {"rule": "require_trend_up_buy", "trend": trend},
                    })
                    continue

                try:
                    vr = float(analysis.get("volume_ratio", 1.0) or 1.0)
                except Exception:
                    vr = 1.0
                if float(MIN_VOLUME_RATIO_BUY or 0.0) > 0 and float(vr) < float(MIN_VOLUME_RATIO_BUY):
                    self._audit_event({
                        "event": "skip",
                        "symbol": symbol,
                        "skip_reason": "quality_filter",
                        "price": float(current_price),
                        "confidence": float(analysis.get("confidence", 0) or 0),
                        "details": {"rule": "min_volume_ratio_buy", "need_gte": float(MIN_VOLUME_RATIO_BUY), "got": float(vr)},
                    })
                    continue

                if REQUIRE_MACD_RISING_BUY:
                    try:
                        mh = float(analysis.get("macd_hist")) if analysis.get("macd_hist") is not None else None
                        mh_prev = float(analysis.get("macd_hist_prev")) if analysis.get("macd_hist_prev") is not None else None
                    except Exception:
                        mh = None
                        mh_prev = None
                    if mh is not None and mh_prev is not None and float(mh) < float(mh_prev):
                        self._audit_event({
                            "event": "skip",
                            "symbol": symbol,
                            "skip_reason": "quality_filter",
                            "price": float(current_price),
                            "confidence": float(analysis.get("confidence", 0) or 0),
                            "details": {"rule": "require_macd_rising_buy", "macd_hist": float(mh), "macd_hist_prev": float(mh_prev)},
                        })
                        continue

                score = self._buy_score(symbol, analysis)
                buy_candidates.append({
                    "symbol": symbol,
                    "score": float(score),
                    "analysis": analysis,
                })
            except Exception as e:
                logger.error(f"Ошибка обработки {symbol}: {e}", exc_info=True)

        # --- PASS 2: ранжирование и выбор топ-N ---
        if not buy_candidates:
            return

        remaining_trades = max(0, int(MAX_TRADES_PER_DAY) - int(self.trades_today))
        remaining_positions = 999999
        if int(MAX_OPEN_POSITIONS) > 0:
            remaining_positions = max(0, int(MAX_OPEN_POSITIONS) - int(open_positions_count))
        max_buys = max(0, int(MAX_BUYS_PER_CYCLE or 0))
        allowed = min(remaining_trades, remaining_positions, max_buys)

        buy_candidates.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)

        # Если места нет — логируем причину для диагностики.
        if allowed <= 0:
            for i, c in enumerate(buy_candidates[:10], start=1):
                self._audit_event({
                    "event": "skip",
                    "symbol": c.get("symbol"),
                    "skip_reason": "rank_not_selected",
                    "price": float(c.get("analysis", {}).get("price", 0) or 0),
                    "confidence": float(c.get("analysis", {}).get("confidence", 0) or 0),
                    "details": {
                        "rank": int(i),
                        "score": float(c.get("score", 0.0) or 0.0),
                        "reason": "no_slots",
                        "remaining_trades": int(remaining_trades),
                        "remaining_positions": int(remaining_positions),
                        "max_buys_per_cycle": int(max_buys),
                    },
                })
            return

        selected = buy_candidates[:allowed]
        rejected = buy_candidates[allowed:]

        # Логируем, что не выбрали из-за ранжирования (чтобы понимать “что пропустили”)
        cutoff = float(selected[-1]["score"]) if selected else 0.0
        for i, c in enumerate(rejected[:20], start=allowed + 1):
            self._audit_event({
                "event": "skip",
                "symbol": c.get("symbol"),
                "skip_reason": "rank_not_selected",
                "price": float(c.get("analysis", {}).get("price", 0) or 0),
                "confidence": float(c.get("analysis", {}).get("confidence", 0) or 0),
                "details": {
                    "rank": int(i),
                    "score": float(c.get("score", 0.0) or 0.0),
                    "cutoff": float(cutoff),
                    "selected": int(allowed),
                },
            })

        # Покупаем выбранные
        for i, c in enumerate(selected, start=1):
            try:
                await self._execute_buy(c["symbol"], account_info, open_symbols, c["analysis"], rank=i, score=float(c["score"]))
            except Exception as e:
                logger.error(f"Ошибка BUY {c.get('symbol')}: {e}", exc_info=True)
    
    async def process_symbol(self, symbol: str, account_info: Dict, open_positions: Dict):
        """Обработать один символ"""
        logger.info(f"Обработка {symbol}...")

        # open_positions здесь — multi-key index (symbol/ticker/figi/alias) → pos,
        # поэтому для лимитов считаем уникальные значения (реальные позиции).
        try:
            unique_open_positions_count = len({id(v) for v in (open_positions or {}).values()})
        except Exception:
            unique_open_positions_count = len(open_positions or {})
        
        # Получаем исторические данные (интервал/глубина настраиваются через .env)
        data = self.broker.get_historical_data(symbol, period=HISTORY_LOOKBACK, interval=BAR_INTERVAL)
        if data.empty:
            logger.warning(f"Нет данных для {symbol}")
            return

        # Sampling для расширенных decision/market логов (чтобы не раздувать файл при желании)
        sample_n = max(1, int(AUDIT_DECISION_EVERY_N or 1))
        sampled = (int(self.cycle_no) % sample_n) == 0
        
        # Анализируем данные
        analysis = self.strategy.analyze(data)
        current_price = analysis.get('price', 0)
        
        if current_price == 0:
            return

        # Срез входных данных (последняя свеча) — полезно для анализа качества сигналов
        if AUDIT_MARKET and sampled:
            try:
                last = data.iloc[-1]
                t = None
                try:
                    idx = data.index[-1]
                    t = idx.isoformat() if hasattr(idx, "isoformat") else str(idx)
                except Exception:
                    t = ""
                self._audit_event({
                    "event": "market",
                    "cycle_no": int(self.cycle_no),
                    "symbol": symbol,
                    "bar_interval": str(BAR_INTERVAL),
                    "history_lookback": str(HISTORY_LOOKBACK),
                    "bar_time": t,
                    "ohlcv": {
                        "open": float(last.get("Open", 0) or 0),
                        "high": float(last.get("High", 0) or 0),
                        "low": float(last.get("Low", 0) or 0),
                        "close": float(last.get("Close", 0) or 0),
                        "volume": float(last.get("Volume", 0) or 0),
                    },
                    "equity": float(account_info.get("equity", 0) or 0),
                    "cash": float(account_info.get("cash", 0) or 0),
                })
            except Exception:
                pass
        
        # Проверяем открытые позиции
        sym_key = _canon_symbol(symbol)
        has_position = sym_key in open_positions

        # Предварительная запись decision: что стратегия “видит” и какие гейты активны
        if AUDIT_DECISIONS and sampled:
            try:
                cd_until = self.cooldown_until.get(symbol)
                now = datetime.now()
                gates = {
                    "has_position": bool(has_position),
                    "allow_entries": bool(self.allow_entries),
                    "enable_trading": bool(ENABLE_TRADING),
                    "max_open_positions_ok": (not (MAX_OPEN_POSITIONS > 0 and int(unique_open_positions_count) >= int(MAX_OPEN_POSITIONS))),
                    "cooldown_ok": (not (cd_until and now < cd_until)),
                    "max_trades_ok": (int(self.trades_today) < int(MAX_TRADES_PER_DAY)),
                }
                # проверяем сигналы в “чистом виде” (без внешних гейтов)
                sig_buy = bool(self.strategy.should_buy(analysis, min_confidence=MIN_CONF_BUY))
                sig_sell = bool(self.strategy.should_sell(analysis, min_confidence=MIN_CONF_SELL))
                self._audit_event({
                    "event": "decision",
                    "cycle_no": int(self.cycle_no),
                    "symbol": symbol,
                    "price": float(current_price),
                    "signal": str(analysis.get("signal", "")),
                    "confidence": float(analysis.get("confidence", 0) or 0),
                    "buy_signals": analysis.get("buy_signals"),
                    "sell_signals": analysis.get("sell_signals"),
                    "rsi": analysis.get("rsi"),
                    "trend": analysis.get("trend"),
                    "atr": analysis.get("atr"),
                    "macd": analysis.get("macd"),
                    "macd_signal": analysis.get("macd_signal"),
                    "macd_hist": analysis.get("macd_hist"),
                    "details": {
                        "strategy_should_buy": sig_buy,
                        "strategy_should_sell": sig_sell,
                        "gates": gates,
                        "cooldown_until": cd_until.isoformat() if cd_until else "",
                        "live_position_sizing": str(LIVE_POSITION_SIZING),
                        "min_conf_buy": float(MIN_CONF_BUY),
                        "min_conf_sell": float(MIN_CONF_SELL),
                    },
                    "equity": float(account_info.get("equity", 0) or 0),
                    "cash": float(account_info.get("cash", 0) or 0),
                    "open_positions": int(unique_open_positions_count),
                    "trades_today_buy": int(self.trades_today),
                })
            except Exception:
                pass
        
        if has_position:
            # Обновляем "трейлинг-стоп" (только вверх) на основе ATR, если есть трекинг по символу.
            try:
                tracking = self.positions_tracking.get(symbol)
                if tracking and analysis.get("atr") is not None:
                    atr = float(analysis.get("atr") or 0.0)
                    if atr > 0:
                        cur_stop = float(tracking.get("stop_loss") or tracking.get("stop_loss_price") or 0.0)
                        entry = float(tracking.get("entry_price") or 0.0)
                        # не двигаем стоп ниже исходного, но можем подтянуть вверх
                        new_trail = float(current_price) - float(ATR_TRAIL_MULT) * atr

                        # Guard-rail: не делаем трейлинг “слишком плотным” (типичный источник churn на 15m),
                        # ограничиваем минимальную дистанцию от текущей цены.
                        try:
                            min_trail_pct = float(TRAIL_MIN_PCT) if float(TRAIL_MIN_PCT) > 0 else 0.0
                        except Exception:
                            min_trail_pct = 0.0
                        if min_trail_pct > 0:
                            min_allowed = float(current_price) * (1.0 - float(min_trail_pct))
                            # если ATR-расчёт дал стоп слишком близко (выше, чем min_allowed) — сдвигаем дальше
                            if float(new_trail) > float(min_allowed):
                                new_trail = float(min_allowed)
                        if cur_stop <= 0:
                            cur_stop = float(entry) * (1 - float(STOP_LOSS_PERCENT))
                        if new_trail > cur_stop:
                            tracking["stop_loss"] = float(new_trail)
                            self.positions_tracking[symbol] = tracking
                            self._audit_event({
                                "event": "risk_update",
                                "symbol": symbol,
                                "price": float(current_price),
                                "details": {
                                    "stop_loss_old": float(cur_stop),
                                    "stop_loss_new": float(new_trail),
                                    "atr": float(atr),
                                    "atr_trail_mult": float(ATR_TRAIL_MULT),
                                    "trail_min_pct": float(min_trail_pct) if min_trail_pct else 0.0,
                                },
                            })
            except Exception:
                pass

            # Если есть позиция, проверяем только на продажу
            if self.strategy.should_sell(analysis, min_confidence=MIN_CONF_SELL):
                # "Умный" выход по сигналу: чтобы не пилить позицию на шуме и не отдавать прибыль комиссиям.
                # Если сигнал слабый и позиция в минусе — ждём подтверждение N циклов.
                # ИСКЛЮЧЕНИЕ: если RSI > RSI_STRONG_OVERBOUGHT — продаём сразу (успешный паттерн из анализа).
                try:
                    conf = float(analysis.get("confidence", 0) or 0.0)
                except Exception:
                    conf = 0.0

                # Проверяем RSI для "форсированного" выхода при сильной перекупленности
                try:
                    rsi_val = float(analysis.get("rsi", 50) or 50)
                except Exception:
                    rsi_val = 50.0
                force_sell_rsi = (rsi_val > float(RSI_STRONG_OVERBOUGHT))

                entry_px = None
                try:
                    tr = self.positions_tracking.get(symbol) or {}
                    if tr.get("entry_price") is not None:
                        entry_px = float(tr.get("entry_price"))
                except Exception:
                    entry_px = None

                pnl_pct = None
                try:
                    if entry_px and float(entry_px) > 0:
                        pnl_pct = (float(current_price) - float(entry_px)) / float(entry_px)
                except Exception:
                    pnl_pct = None

                # Если RSI сильно overbought — продаём без ожидания подтверждений
                if not force_sell_rsi and conf < float(MIN_CONF_SELL_STRONG) and pnl_pct is not None and float(pnl_pct) < 0:
                    n = int(self._sell_confirm.get(symbol, 0) or 0) + 1
                    self._sell_confirm[symbol] = n
                    if n < int(SELL_CONFIRM_BARS):
                        self._audit_event({
                            "event": "skip",
                            "symbol": symbol,
                            "skip_reason": "sell_confirm_pending",
                            "price": float(current_price),
                            "confidence": float(conf),
                            "details": {
                                "need_bars": int(SELL_CONFIRM_BARS),
                                "got_bars": int(n),
                                "min_conf_sell_strong": float(MIN_CONF_SELL_STRONG),
                                "pnl_pct": float(pnl_pct),
                            },
                        })
                        return
                else:
                    # сбрасываем подтверждение, если условие не актуально
                    self._sell_confirm[symbol] = 0

                position = open_positions.get(sym_key) or open_positions.get(_canon_symbol(symbol)) or open_positions.get(str(symbol)) or open_positions.get(sym_key.lower())
                if not position:
                    return
                
                # Для T-Invest qty трактуем как ЛОТЫ - берем реальное количество из позиции
                try:
                    qty_lots = int(position.get('qty_lots', position.get('qty', 0)) or 0)
                    if qty_lots <= 0:
                        logger.debug(f"Позиция {symbol} не содержит лотов для продажи (qty_lots={qty_lots})")
                        return
                    logger.debug(f"Продажа по сигналу для {symbol}: {qty_lots} лотов")
                except Exception as e:
                    logger.error(f"Ошибка при определении количества лотов для {symbol}: {e}")
                    return
                
                if qty_lots > 0 and ENABLE_TRADING:
                    # Проверка торговой сессии перед размещением ордера
                    is_session_open, session_reason = _is_trading_session_open()
                    if not is_session_open:
                        logger.warning(f"⚠️ Пропуск размещения ордера на продажу {symbol}: {session_reason}")
                        return
                    
                    # Убеждаемся, что symbol является тикером, а не FIGI
                    symbol_for_api = _ensure_ticker_not_figi(symbol, self.broker)
                    instrument = self.broker.get_instrument_details(symbol_for_api)
                    # ВАЖНО: В sandbox флаги trading_status могут быть False даже когда торговля возможна (особенно в ночное время)
                    # Не блокируем продажи по этой проверке - полагаемся на реальную ошибку API (30079)
                    if instrument:
                        st = str(instrument.get("trading_status") or "").upper()
                        api_ok = instrument.get("api_trade_available_flag")
                        sell_ok = instrument.get("sell_available_flag")
                        # Только логируем, но не блокируем
                        if ("NOT_AVAILABLE" in st) or (api_ok is False) or (sell_ok is False):
                            logger.debug(f"Инструмент {symbol} (SELL) имеет флаги: trading_status={st}, api_ok={api_ok}, sell_ok={sell_ok} - продолжим попытку размещения ордера")
                    # Используем symbol_for_api для размещения ордера
                    order = self.broker.place_market_order(symbol_for_api, qty_lots, 'sell')
                    if not order:
                        # Получаем детальную информацию об ошибке
                        error_details = {}
                        if hasattr(self.broker, 'client') and hasattr(self.broker.client, '_last_order_error'):
                            error_details = self.broker.client._last_order_error.copy() if self.broker.client._last_order_error else {}
                        
                        # Формируем детальное сообщение об ошибке
                        error_reason = error_details.get('reason', 'unknown')
                        error_code = error_details.get('error_code', 'N/A')
                        error_description = error_details.get('description', 'place_market_order returned None')
                        
                        logger.error(f"❌ НЕ УДАЛОСЬ РАЗМЕСТИТЬ ЗАЯВКУ НА ПРОДАЖУ: {symbol} | "
                                    f"Причина: {error_reason} | Код ошибки: {error_code} | "
                                    f"Описание: {error_description} | "
                                    f"Параметры: qty_lots={qty_lots}, price={current_price:.2f}, lot={lot}, "
                                    f"figi={instrument.get('figi') if instrument else 'N/A'}, "
                                    f"instrument_ok={instrument is not None}")
                        
                        # Дополнительное логирование в зависимости от типа ошибки
                        if error_reason == 'instrument_not_available':
                            from datetime import datetime
                            current_time_msk = datetime.now().strftime('%H:%M:%S MSK')
                            logger.warning(f"   Время: {current_time_msk} | MOEX работает 10:00-18:45 MSK (основная сессия)")
                        elif error_reason == 'insufficient_balance':
                            logger.warning(f"   Баланс: cash={account_info.get('cash', 0):.2f}, equity={account_info.get('equity', 0):.2f}")
                            logger.warning(f"   Позиция: qty_lots={qty_lots}, lot={lot}, qty_shares={qty_lots * lot}")
                        
                        self._audit_event({
                            "event": "skip",
                            "symbol": symbol,
                            "skip_reason": "order_placement_failed",
                            "price": float(current_price),
                            "confidence": float(analysis.get("confidence", 0) or 0),
                            "equity": float(account_info.get("equity", 0) or 0),
                            "cash": float(account_info.get("cash", 0) or 0),
                            "open_positions": int(len({id(v) for v in (open_positions or {}).values()})) if open_positions is not None else 0,
                            "trades_today_buy": int(self.trades_today),
                            "details": {
                                "reason": error_reason,
                                "error_code": error_code,
                                "error_description": error_description,
                                "error_type": error_details.get('error_type', 'unknown'),
                                "qty_lots": int(qty_lots),
                                "lot": int(lot),
                                "instrument_ok": instrument is not None,
                                "figi": instrument.get("figi") if instrument else None,
                                **{k: v for k, v in error_details.items() if k not in ['reason', 'error_code', 'error_description', 'error_type']}
                            },
                        })
                        return
                    if order:
                        # Безопасное извлечение скалярного значения confidence
                        try:
                            if isinstance(analysis['confidence'], pd.Series):
                                conf_val = float(analysis['confidence'].iloc[0] if len(analysis['confidence']) > 0 else analysis['confidence'].values[0])
                            else:
                                conf_val = float(analysis['confidence'])
                        except (IndexError, AttributeError, ValueError, TypeError):
                            conf_val = float(analysis.get('confidence', 0) or 0)
                        reason = f"Сигнал продажи (уверенность: {conf_val*100:.1f}%)"
                        # Преобразуем FIGI в тикер для корректного отображения в Telegram
                        symbol_for_telegram = _ensure_ticker_not_figi(symbol, self.broker)
                        symbol_for_telegram = _canon_symbol(symbol_for_telegram)
                        
                        currency = (account_info.get("currency") or "RUB")
                        currency_symbol = {"RUB": "₽", "USD": "$", "EUR": "€"}.get(str(currency).upper(), str(currency).upper() + " ")
                        lot = int(position.get("lot", 1) or 1)
                        qty_shares = float(qty_lots) * float(lot)
                        message = self.telegram.format_trade_notification(
                            symbol_for_telegram, "SELL", qty_lots, current_price,
                            current_price * qty_lots * lot, reason,
                            currency=currency,
                            currency_symbol=currency_symbol,
                            lot=lot,
                            qty_shares=qty_shares,
                        )
                        await self.telegram.send_message(message, parse_mode='Markdown')
                        # SELL не считаем в лимит входов, но логируем
                        pnl = None
                        try:
                            if symbol in self.positions_tracking:
                                entry_px = float(self.positions_tracking[symbol].get("entry_price", current_price))
                                lot_sz = int(self.positions_tracking[symbol].get("lot", lot) or lot or 1)
                                pnl = (float(current_price) - entry_px) * float(qty_lots) * float(lot_sz)
                        except Exception:
                            pnl = None
                        self.trade_history.append({
                            "ts": datetime.now(),
                            "symbol": symbol,
                            "action": "SELL",
                            "qty_lots": qty_lots,
                            "price": current_price,
                            "reason": "signal",
                            **({"pnl": pnl} if pnl is not None else {}),
                        })
                        self.trade_history = self.trade_history[-50:]
                        self.cooldown_until[symbol] = datetime.now() + timedelta(minutes=SYMBOL_COOLDOWN_MIN)
                        # Обновляем локальное состояние, чтобы лимит позиций работал в текущем цикле
                        # удаляем по тикеру и по figi (если есть)
                        try:
                            if sym_key in open_positions:
                                del open_positions[sym_key]
                            figi_k = str(position.get("figi") or "").strip().upper()
                            if figi_k and figi_k in open_positions:
                                del open_positions[figi_k]
                        except Exception:
                            pass

                        # Аудит-лог (SELL по сигналу)
                        self._audit_event({
                            "event": "trade",
                            "symbol": symbol,
                            "action": "SELL",
                            "qty_lots": int(qty_lots),
                            "lot": int(lot),
                            "price": float(current_price),
                            "reason": "signal",
                            "confidence": float(analysis.get("confidence", 0) or 0),
                            "buy_signals": analysis.get("buy_signals"),
                            "sell_signals": analysis.get("sell_signals"),
                            "rsi": analysis.get("rsi"),
                            "trend": analysis.get("trend"),
                            "atr": analysis.get("atr"),
                            "macd": analysis.get("macd"),
                            "macd_signal": analysis.get("macd_signal"),
                            "macd_hist": analysis.get("macd_hist"),
                            "order": order,
                            "equity": float(account_info.get("equity", 0) or 0),
                            "cash": float(account_info.get("cash", 0) or 0),
                            "open_positions": int(unique_open_positions_count),
                            "trades_today_buy": int(self.trades_today),
                            "details": {
                                "qty_shares": float(qty_shares),
                                **({"pnl": float(pnl)} if pnl is not None else {}),
                            },
                        })
                        # Symbol Tracker: записываем результат сделки
                        if self.symbol_tracker is not None and pnl is not None:
                            try:
                                self.symbol_tracker.record_trade(
                                    symbol, float(pnl), "signal", float(analysis.get("confidence", 0) or 0)
                                )
                            except Exception:
                                pass
                        
                        # Удаляем из отслеживания
                        if symbol in self.positions_tracking:
                            del self.positions_tracking[symbol]
                        # сбрасываем подтверждение sell-сигнала
                        self._sell_confirm[symbol] = 0
        else:
            # Если нет позиции, проверяем на покупку
            if not self.allow_entries:
                self._audit_event({
                    "event": "skip",
                    "symbol": symbol,
                    "skip_reason": "entries_disabled",
                    "price": float(current_price),
                    "confidence": float(analysis.get("confidence", 0) or 0),
                    "buy_signals": analysis.get("buy_signals"),
                    "sell_signals": analysis.get("sell_signals"),
                    "rsi": analysis.get("rsi"),
                    "trend": analysis.get("trend"),
                    "atr": analysis.get("atr"),
                    "macd_hist": analysis.get("macd_hist"),
                    "equity": float(account_info.get("equity", 0) or 0),
                    "cash": float(account_info.get("cash", 0) or 0),
                    "open_positions": int(unique_open_positions_count),
                    "trades_today_buy": int(self.trades_today),
                })
                return

            # лимит по количеству открытых позиций
            if MAX_OPEN_POSITIONS > 0 and int(unique_open_positions_count) >= int(MAX_OPEN_POSITIONS):
                self._audit_event({
                    "event": "skip",
                    "symbol": symbol,
                    "skip_reason": "max_open_positions",
                    "open_positions": int(unique_open_positions_count),
                    "price": float(current_price),
                    "confidence": float(analysis.get("confidence", 0) or 0),
                    "equity": float(account_info.get("equity", 0) or 0),
                    "cash": float(account_info.get("cash", 0) or 0),
                })
                return

            # кулдаун на повторный вход после продажи
            cd_until = self.cooldown_until.get(symbol)
            if cd_until and datetime.now() < cd_until:
                self._audit_event({
                    "event": "skip",
                    "symbol": symbol,
                    "skip_reason": "cooldown",
                    "price": float(current_price),
                    "confidence": float(analysis.get("confidence", 0) or 0),
                    "details": {"cooldown_until": cd_until.isoformat()},
                })
                return

            # лимит сделок (учитываем только входы)
            if self.trades_today >= MAX_TRADES_PER_DAY:
                logger.info(f"Лимит сделок на сегодня достигнут: {self.trades_today}/{MAX_TRADES_PER_DAY}")
                self._audit_event({
                    "event": "skip",
                    "symbol": symbol,
                    "skip_reason": "max_trades_per_day",
                    "price": float(current_price),
                    "trades_today_buy": int(self.trades_today),
                    "details": {"max_trades_per_day": int(MAX_TRADES_PER_DAY)},
                })
                return

            # Recommendation D: для шумных/дешёвых бумаг требуем "подтверждение" входа
            ok_noisy, noisy_details = self._passes_noisy_entry_filter(symbol, analysis)
            if not ok_noisy:
                self._audit_event({
                    "event": "skip",
                    "symbol": symbol,
                    "skip_reason": "noisy_quality_filter",
                    "price": float(current_price),
                    "confidence": float(analysis.get("confidence", 0) or 0),
                    "buy_signals": analysis.get("buy_signals"),
                    "sell_signals": analysis.get("sell_signals"),
                    "rsi": analysis.get("rsi"),
                    "trend": analysis.get("trend"),
                    "atr": analysis.get("atr"),
                    "macd_hist": analysis.get("macd_hist"),
                    "equity": float(account_info.get("equity", 0) or 0),
                    "cash": float(account_info.get("cash", 0) or 0),
                    "open_positions": int(unique_open_positions_count),
                    "trades_today_buy": int(self.trades_today),
                    "details": {
                        "noisy_symbols": ",".join(NOISY_SYMBOLS or []),
                        "volume_ratio": analysis.get("volume_ratio"),
                        "macd_hist_prev": analysis.get("macd_hist_prev"),
                        "rules": {
                            "require_trend_up": bool(NOISY_REQUIRE_TREND_UP),
                            "volume_ratio_min": float(NOISY_VOLUME_RATIO_MIN),
                            "macd_hist_min": float(NOISY_MACD_HIST_MIN),
                            "require_macd_rising": bool(NOISY_REQUIRE_MACD_RISING),
                        },
                        "fails": noisy_details,
                    },
                })
                return

            # Глобальные фильтры качества BUY (включаются через .env)
            try:
                trend = str(analysis.get("trend") or "").strip().lower()
            except Exception:
                trend = ""
            if REQUIRE_TREND_UP_BUY and trend and trend != "up":
                self._audit_event({
                    "event": "skip",
                    "symbol": symbol,
                    "skip_reason": "quality_filter",
                    "price": float(current_price),
                    "confidence": float(analysis.get("confidence", 0) or 0),
                    "details": {"rule": "require_trend_up_buy", "trend": trend},
                })
                return
            try:
                vr = float(analysis.get("volume_ratio", 1.0) or 1.0)
            except Exception:
                vr = 1.0
            if float(MIN_VOLUME_RATIO_BUY or 0.0) > 0 and float(vr) < float(MIN_VOLUME_RATIO_BUY):
                self._audit_event({
                    "event": "skip",
                    "symbol": symbol,
                    "skip_reason": "quality_filter",
                    "price": float(current_price),
                    "confidence": float(analysis.get("confidence", 0) or 0),
                    "details": {"rule": "min_volume_ratio_buy", "need_gte": float(MIN_VOLUME_RATIO_BUY), "got": float(vr)},
                })
                return
            if REQUIRE_MACD_RISING_BUY:
                try:
                    mh = float(analysis.get("macd_hist")) if analysis.get("macd_hist") is not None else None
                    mh_prev = float(analysis.get("macd_hist_prev")) if analysis.get("macd_hist_prev") is not None else None
                except Exception:
                    mh = None
                    mh_prev = None
                if mh is not None and mh_prev is not None and float(mh) < float(mh_prev):
                    self._audit_event({
                        "event": "skip",
                        "symbol": symbol,
                        "skip_reason": "quality_filter",
                        "price": float(current_price),
                        "confidence": float(analysis.get("confidence", 0) or 0),
                        "details": {"rule": "require_macd_rising_buy", "macd_hist": float(mh), "macd_hist_prev": float(mh_prev)},
                    })
                    return

            if self.strategy.should_buy(analysis, min_confidence=MIN_CONF_BUY):
                # Для T-Invest торгуем лотами, поэтому получаем lot
                # Убеждаемся, что symbol является тикером, а не FIGI
                symbol_for_api = _ensure_ticker_not_figi(symbol, self.broker)
                instrument = self.broker.get_instrument_details(symbol_for_api)
                # ВАЖНО: В sandbox флаги trading_status могут быть False даже когда торговля возможна (особенно в ночное время)
                # Не блокируем покупки по этой проверке - полагаемся на реальную ошибку API (30079)
                if instrument:
                    st = str(instrument.get("trading_status") or "").upper()
                    api_ok = instrument.get("api_trade_available_flag")
                    buy_ok = instrument.get("buy_available_flag")
                    # Только логируем, но не блокируем
                    if ("NOT_AVAILABLE" in st) or (api_ok is False) or (buy_ok is False):
                        logger.debug(f"Инструмент {symbol} имеет флаги: trading_status={st}, api_ok={api_ok}, buy_ok={buy_ok} - продолжим попытку размещения ордера")
                lot = int(instrument.get("lot", 1)) if instrument else 1
                lot = max(1, lot)

                # Рассчитываем stop/take (ATR если доступен, иначе проценты) и размер позиции
                atr = analysis.get("atr")
                stop_price = None
                take_price = None
                try:
                    if atr is not None:
                        stop_price = float(current_price) - float(ATR_STOP_MULT) * float(atr)
                        take_price = float(current_price) + float(ATR_TAKE_MULT) * float(atr)
                except Exception:
                    stop_price = None
                    take_price = None
                if stop_price is None:
                    stop_price = self.risk_manager.calculate_stop_loss(float(current_price))
                if take_price is None:
                    take_price = self.risk_manager.calculate_take_profit(float(current_price))

                # Guard-rails: ATR на 5m может быть слишком мал → стоп будет слишком близко и выбьет шумом.
                # Делаем стоп не уже, чем процентный STOP_LOSS_PERCENT, а тейк не дальше, чем TAKE_PROFIT_PERCENT.
                try:
                    pct_stop = float(current_price) * (1 - float(STOP_LOSS_PERCENT))
                    stop_price = min(float(stop_price), float(pct_stop))
                except Exception:
                    pass
                try:
                    pct_take = float(current_price) * (1 + float(TAKE_PROFIT_PERCENT))
                    take_price = min(float(take_price), float(pct_take))
                except Exception:
                    pass
                try:
                    pct_take_min = float(current_price) * (1 + float(TAKE_MIN_PCT))
                    take_price = max(float(take_price), float(pct_take_min))
                except Exception:
                    pass

                if str(LIVE_POSITION_SIZING).lower() == "risk":
                    qty_shares = self.risk_manager.calculate_position_size_by_risk(
                        float(account_info.get("equity", 10000) or 10000),
                        float(current_price),
                        float(stop_price),
                        confidence=float(analysis.get("confidence", 1.0) or 1.0),
                    )
                else:
                    qty_shares = self.risk_manager.calculate_position_size(
                        float(account_info.get("equity", 10000) or 10000),
                        float(current_price),
                        float(analysis.get("confidence", 1.0) or 1.0),
                    )
                qty_lots = max(1, int(qty_shares // lot))
                
                # Валидируем сделку
                validation = self.risk_manager.validate_trade(
                    account_info.get('equity', 10000),
                    current_price,
                    qty_lots * lot
                )
                
                if not validation.get('valid', False):
                    self._audit_event({
                        "event": "skip",
                        "symbol": symbol,
                        "skip_reason": "validation_failed",
                        "price": float(current_price),
                        "qty_lots": int(qty_lots),
                        "lot": int(lot),
                        "confidence": float(analysis.get("confidence", 0) or 0),
                        "equity": float(account_info.get("equity", 0) or 0),
                        "cash": float(account_info.get("cash", 0) or 0),
                        "details": {"validation": validation},
                    })
                    return

                if validation['valid'] and ENABLE_TRADING:
                    order = self.broker.place_market_order(symbol, qty_lots, 'buy')
                    if order:
                        # Безопасное извлечение скалярного значения confidence
                        try:
                            if isinstance(analysis['confidence'], pd.Series):
                                conf_val = float(analysis['confidence'].iloc[0] if len(analysis['confidence']) > 0 else analysis['confidence'].values[0])
                            else:
                                conf_val = float(analysis['confidence'])
                        except (IndexError, AttributeError, ValueError, TypeError):
                            conf_val = float(analysis.get('confidence', 0) or 0)
                        reason = f"Сигнал покупки (уверенность: {conf_val*100:.1f}%)"
                        # Преобразуем FIGI в тикер для корректного отображения в Telegram
                        symbol_for_telegram = _ensure_ticker_not_figi(symbol, self.broker)
                        symbol_for_telegram = _canon_symbol(symbol_for_telegram)
                        
                        currency = (instrument.get("currency") if instrument else None) or (account_info.get("currency") or "RUB")
                        currency_symbol = {"RUB": "₽", "USD": "$", "EUR": "€"}.get(str(currency).upper(), str(currency).upper() + " ")
                        qty_shares_total = float(qty_lots) * float(lot)
                        message = self.telegram.format_trade_notification(
                            symbol_for_telegram, "BUY", qty_lots, current_price,
                            current_price * qty_lots * lot, reason,
                            currency=currency,
                            currency_symbol=currency_symbol,
                            lot=lot,
                            qty_shares=qty_shares_total,
                        )
                        await self.telegram.send_message(message, parse_mode='Markdown')
                        self.trades_today += 1
                        self.trade_history.append({
                            "ts": datetime.now(),
                            "symbol": symbol,
                            "action": "BUY",
                            "qty_lots": qty_lots,
                            "price": current_price,
                            "reason": reason,
                        })
                        self.trade_history = self.trade_history[-50:]
                        # Обновляем локальное состояние, чтобы лимит позиций работал в текущем цикле
                        open_positions[sym_key] = {"symbol": symbol, "qty_lots": qty_lots, "qty": qty_lots}

                        # Аудит-лог (BUY по сигналу)
                        self._audit_event({
                            "event": "trade",
                            "symbol": symbol,
                            "action": "BUY",
                            "qty_lots": int(qty_lots),
                            "lot": int(lot),
                            "price": float(current_price),
                            "reason": "signal",
                            "confidence": float(analysis.get("confidence", 0) or 0),
                            "buy_signals": analysis.get("buy_signals"),
                            "sell_signals": analysis.get("sell_signals"),
                            "rsi": analysis.get("rsi"),
                            "trend": analysis.get("trend"),
                            "atr": analysis.get("atr"),
                            "macd": analysis.get("macd"),
                            "macd_signal": analysis.get("macd_signal"),
                            "macd_hist": analysis.get("macd_hist"),
                            "order": order,
                            "equity": float(account_info.get("equity", 0) or 0),
                            "cash": float(account_info.get("cash", 0) or 0),
                            "open_positions": int(unique_open_positions_count),
                            "trades_today_buy": int(self.trades_today),
                            "details": {
                                "qty_shares": float(qty_shares_total),
                                "stop_price": float(stop_price),
                                "take_price": float(take_price),
                                "position_sizing": str(LIVE_POSITION_SIZING),
                                "atr_stop_mult": float(ATR_STOP_MULT),
                                "atr_take_mult": float(ATR_TAKE_MULT),
                            },
                        })

                        # Добавляем в отслеживание для стоп-лоссов и тейк-профитов
                        self.positions_tracking[symbol] = {
                            'entry_price': current_price,
                            'entry_ts_utc': datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                            'qty_lots': qty_lots,
                            'lot': lot,
                            'stop_loss': float(stop_price),
                            'take_profit': float(take_price),
                        }
                elif validation['valid'] and not ENABLE_TRADING:
                    self._audit_event({
                        "event": "skip",
                        "symbol": symbol,
                        "skip_reason": "enable_trading_false",
                        "price": float(current_price),
                        "qty_lots": int(qty_lots),
                        "lot": int(lot),
                        "confidence": float(analysis.get("confidence", 0) or 0),
                        "details": {"note": "Сигнал BUY был, но ENABLE_TRADING=false"},
                    })
    
    async def check_positions(self):
        """Проверить открытые позиции на стоп-лоссы и тейк-профиты"""
        positions = self.broker.get_positions() or []

        # Для восстановления entry_price/трекинга после рестартов
        cost_map = {}
        if RESTORE_TRACKING_FROM_AUDIT:
            try:
                cost_map = compute_avg_cost_from_audit(AUDIT_LOG_PATH) or {}
            except Exception:
                cost_map = {}
        
        for position in positions:
            # Всегда работаем в терминах тикера (не FIGI), чтобы совпадать с strategy/analyze и orders.
            # Позиция должна содержать 'symbol' с тикером (из get_positions)
            symbol_raw = position.get('symbol') or position.get('ticker') or ""
            symbol = _canon_symbol(symbol_raw)
            
            # Дополнительное логирование для диагностики валютных пар
            if symbol_raw != symbol:
                logger.debug(f"Нормализация символа: {symbol_raw} -> {symbol}")
            
            # Если symbol является FIGI (начинается с BBG), пытаемся найти тикер
            if symbol and symbol.startswith("BBG") and len(symbol) > 10:
                # Это похоже на FIGI, пытаемся найти тикер через API
                try:
                    figi = symbol
                    # Сначала пробуем взять тикер из самой позиции (если он там есть)
                    pos_ticker = position.get('ticker')
                    if pos_ticker and not str(pos_ticker).startswith("BBG"):
                        symbol = _canon_symbol(pos_ticker)
                        logger.debug(f"Использован тикер {symbol} из позиции для FIGI {figi}")
                    else:
                        # Пробуем найти тикер через get_instrument_by_figi
                        instrument = self.broker.get_instrument_by_figi(figi) if hasattr(self.broker, 'get_instrument_by_figi') else None
                        if instrument and instrument.get('ticker'):
                            symbol = _canon_symbol(instrument.get('ticker'))
                            logger.info(f"Найден тикер {symbol} для FIGI {figi} через API")
                        else:
                            # Если не нашли тикер, пропускаем эту позицию (не можем обработать)
                            logger.warning(f"Не удалось найти тикер для FIGI {figi}, пропускаем позицию")
                            continue
                except Exception as e:
                    logger.warning(f"Ошибка при поиске тикера для FIGI {symbol}: {e}")
                    continue
            
            if not symbol:
                continue
            current_price = position.get('current_price', 0)
            try:
                current_price = float(current_price or 0)
            except Exception:
                current_price = 0.0
            if current_price <= 0:
                continue

            # Если трекинга нет (например, после рестарта) — восстановим.
            if symbol not in self.positions_tracking and RESTORE_TRACKING_FROM_AUDIT:
                try:
                    qty_lots = int(position.get("qty_lots", position.get("qty", 0)) or 0)
                except Exception:
                    qty_lots = 0
                if qty_lots <= 0:
                    continue
                try:
                    lot = int(position.get("lot", 1) or 1)
                except Exception:
                    lot = 1
                lot = max(1, lot)

                entry = None
                try:
                    if position.get("avg_entry_price") is not None:
                        entry = float(position.get("avg_entry_price"))
                except Exception:
                    entry = None
                if entry is None:
                    try:
                        cm = cost_map.get(symbol) or {}
                        if cm.get("avg_price") is not None:
                            entry = float(cm.get("avg_price"))
                    except Exception:
                        entry = None
                if entry is None:
                    entry = float(current_price)

                stop = float(entry) * (1.0 - float(STOP_LOSS_PERCENT))
                take = float(entry) * (1.0 + max(float(TAKE_PROFIT_PERCENT), float(TAKE_MIN_PCT)))
                self.positions_tracking[symbol] = {
                    "entry_price": float(entry),
                    "qty_lots": int(qty_lots),
                    "lot": int(lot),
                    "stop_loss": float(stop),
                    "take_profit": float(take),
                    "entry_ts_utc": "",
                    "restored_from": "audit_or_position",
                }
            
            if symbol in self.positions_tracking:
                tracking = self.positions_tracking[symbol]
                entry_price = tracking['entry_price']
                
                # ВАЖНО: Используем реальное количество лотов из позиции, а не из tracking
                # Позиция может быть частично продана или изменена
                try:
                    pos_qty_lots = int(position.get("qty_lots", position.get("qty", 0)) or 0)
                    tracking_qty_lots = int(tracking.get('qty_lots', tracking.get('qty', 0)) or 0)
                    # Используем минимум из двух, чтобы не продать больше, чем есть
                    qty_lots = min(pos_qty_lots, tracking_qty_lots) if pos_qty_lots > 0 else tracking_qty_lots
                    if pos_qty_lots != tracking_qty_lots:
                        logger.warning(f"Расхождение количества лотов для {symbol}: позиция={pos_qty_lots}, tracking={tracking_qty_lots}, используем {qty_lots}")
                except Exception as e:
                    logger.error(f"Ошибка при определении количества лотов для {symbol}: {e}")
                    qty_lots = int(tracking.get('qty_lots', tracking.get('qty', 0)) or 0)
                
                if qty_lots <= 0:
                    logger.warning(f"Пропускаем позицию {symbol}: количество лотов = {qty_lots}")
                    continue
                
                lot = int(tracking.get("lot", 1) or 1)
                qty_shares = float(qty_lots) * float(lot)

                # Перевод стопа в безубыток (опционально)
                try:
                    be_trig = float(BREAKEVEN_TRIGGER_PCT or 0.0)
                    be_lock = float(BREAKEVEN_LOCK_PCT or 0.0)
                except Exception:
                    be_trig = 0.0
                    be_lock = 0.0
                if be_trig > 0 and be_lock >= 0 and float(entry_price) > 0:
                    try:
                        pnl_pct = (float(current_price) - float(entry_price)) / float(entry_price)
                    except Exception:
                        pnl_pct = 0.0
                    if pnl_pct >= float(be_trig):
                        desired = float(entry_price) * (1.0 + float(be_lock))
                        try:
                            # не ставим стоп слишком близко к текущей цене
                            min_trail_pct = float(TRAIL_MIN_PCT) if float(TRAIL_MIN_PCT) > 0 else 0.0
                        except Exception:
                            min_trail_pct = 0.0
                        if min_trail_pct > 0:
                            desired = min(float(desired), float(current_price) * (1.0 - float(min_trail_pct)))
                        try:
                            cur_sl = float(tracking.get("stop_loss") or 0.0)
                        except Exception:
                            cur_sl = 0.0
                        if desired > cur_sl:
                            tracking["stop_loss"] = float(desired)
                            self.positions_tracking[symbol] = tracking
                            self._audit_event({
                                "event": "risk_update",
                                "symbol": symbol,
                                "price": float(current_price),
                                "details": {"rule": "breakeven", "stop_loss_old": float(cur_sl), "stop_loss_new": float(desired), "be_trigger_pct": float(be_trig), "be_lock_pct": float(be_lock)},
                            })

                # Используем сохранённые уровни стопа/тейка (они могут быть ATR-основанными)
                stop_level = float(tracking.get("stop_loss") or self.risk_manager.calculate_stop_loss(float(entry_price)))
                take_level = float(tracking.get("take_profit") or self.risk_manager.calculate_take_profit(float(entry_price)))
                
                # Логирование для диагностики стоп-лоссов (особенно важно для валютных пар)
                try:
                    pnl_pct = ((float(current_price) - float(entry_price)) / float(entry_price) * 100.0) if float(entry_price) > 0 else 0.0
                    stop_distance_pct = ((float(current_price) - float(stop_level)) / float(entry_price) * 100.0) if float(entry_price) > 0 else 0.0
                    logger.info(f"Проверка стоп-лосса для {symbol}: цена={current_price:.2f}, вход={entry_price:.2f}, стоп={stop_level:.2f}, P/L={pnl_pct:.2f}%, до_стопа={stop_distance_pct:.2f}%")
                except Exception:
                    pass
                
                # Проверка стоп-лосса
                if float(current_price) <= float(stop_level):
                    logger.info(f"Стоп-лосс сработал для {symbol} (цена: {current_price:.2f}, стоп: {stop_level:.2f}, лотов: {qty_lots})")
                    if ENABLE_TRADING:
                        # Финальная проверка: убеждаемся, что количество лотов не превышает доступное
                        try:
                            pos_qty_lots = int(position.get("qty_lots", position.get("qty", 0)) or 0)
                            if pos_qty_lots > 0:
                                qty_lots = min(qty_lots, pos_qty_lots)
                                logger.info(f"Финальная проверка для {symbol}: позиция={pos_qty_lots} лотов, продаем {qty_lots} лотов")
                            else:
                                logger.warning(f"Позиция {symbol} не содержит лотов (pos_qty_lots={pos_qty_lots})")
                        except Exception as e:
                            logger.error(f"Ошибка при проверке количества лотов для {symbol}: {e}")
                        
                        if qty_lots <= 0:
                            logger.warning(f"Невозможно продать {symbol}: количество лотов = {qty_lots}")
                            continue
                        
                        # Финальная проверка: запрашиваем актуальные позиции перед продажей
                        try:
                            current_positions = self.broker.get_positions() or []
                            current_pos = None
                            # get_positions() возвращает список, а не словарь
                            for pos_val in current_positions:
                                if not isinstance(pos_val, dict):
                                    continue
                                pos_sym = _canon_symbol(pos_val.get('symbol') or pos_val.get('ticker') or '')
                                # Проверяем совпадение по символу (учитываем возможные варианты написания)
                                symbol_canon = _canon_symbol(symbol)
                                pos_ticker_canon = _canon_symbol(position.get('ticker') or '')
                                if pos_sym == symbol_canon or pos_sym == pos_ticker_canon:
                                    current_pos = pos_val
                                    break
                            
                            if current_pos:
                                actual_qty = int(current_pos.get('qty_lots', current_pos.get('qty', 0)) or 0)
                                if actual_qty < qty_lots:
                                    logger.warning(f"Актуальное количество лотов для {symbol} меньше ожидаемого: {actual_qty} < {qty_lots}, используем {actual_qty}")
                                    qty_lots = actual_qty
                                elif actual_qty > 0:
                                    logger.info(f"Подтверждено количество лотов для {symbol}: {actual_qty} лотов (продаем {qty_lots})")
                            else:
                                logger.warning(f"Позиция {symbol} не найдена в актуальных позициях, возможно уже закрыта")
                                if qty_lots > 0:
                                    logger.info(f"Попытка продажи {qty_lots} лотов {symbol} несмотря на отсутствие в актуальных позициях")
                        except Exception as e:
                            logger.warning(f"Не удалось проверить актуальные позиции перед продажей {symbol}: {e}", exc_info=True)
                        
                        if qty_lots <= 0:
                            logger.warning(f"Пропускаем продажу {symbol}: количество лотов = {qty_lots}")
                            continue
                        
                        # Если symbol является FIGI, пытаемся найти тикер для размещения ордера
                        order_symbol = symbol
                        if symbol.startswith("BBG") and len(symbol) > 10:
                            # Это FIGI, пытаемся найти тикер
                            try:
                                pos_ticker = position.get('ticker') or position.get('symbol')
                                if pos_ticker and not pos_ticker.startswith("BBG"):
                                    order_symbol = _canon_symbol(pos_ticker)
                                else:
                                    # Пробуем найти через API
                                    instrument = self.broker.get_instrument_by_figi(symbol) if hasattr(self.broker, 'get_instrument_by_figi') else None
                                    if instrument and instrument.get('ticker'):
                                        order_symbol = _canon_symbol(instrument.get('ticker'))
                            except Exception:
                                pass
                        
                        logger.info(f"Размещение ордера на продажу (стоп-лосс): {order_symbol}, {qty_lots} лотов")
                        order = self.broker.place_market_order(order_symbol, qty_lots, 'sell')
                        if not order:
                            # Получаем детальную информацию об ошибке
                            error_details = {}
                            if hasattr(self.broker, 'client') and hasattr(self.broker.client, '_last_order_error'):
                                error_details = self.broker.client._last_order_error.copy() if self.broker.client._last_order_error else {}
                            
                            error_reason = error_details.get('reason', 'unknown')
                            error_code = error_details.get('error_code', 'N/A')
                            error_description = error_details.get('description', 'place_market_order returned None')
                            
                            logger.error(f"❌ НЕ УДАЛОСЬ РАЗМЕСТИТЬ СТОП-ЛОСС: {symbol} | "
                                        f"Причина: {error_reason} | Код ошибки: {error_code} | "
                                        f"Описание: {error_description} | "
                                        f"Параметры: qty_lots={qty_lots}, price={current_price:.2f}, entry={entry_price:.2f}, stop={stop_level:.2f}")
                            
                            if error_reason == 'instrument_not_available':
                                from datetime import datetime
                                current_time_msk = datetime.now().strftime('%H:%M:%S MSK')
                                logger.warning(f"   Время: {current_time_msk} | MOEX работает 10:00-18:45 MSK (основная сессия)")
                            elif error_reason == 'insufficient_balance':
                                logger.warning(f"   Позиция: qty_lots={qty_lots}, lot={lot}, qty_shares={qty_shares}")
                            
                            continue
                        if order:
                            # Преобразуем FIGI в тикер для корректного отображения в Telegram
                            symbol_for_telegram = _ensure_ticker_not_figi(symbol, self.broker)
                            symbol_for_telegram = _canon_symbol(symbol_for_telegram)
                            
                            loss = (float(current_price) - float(entry_price)) * float(qty_shares)
                            ai = self.broker.get_account_info()
                            currency = (ai.get("currency") or "RUB")
                            currency_symbol = {"RUB": "₽", "USD": "$", "EUR": "€"}.get(str(currency).upper(), str(currency).upper() + " ")
                            message = f"🛑 *Стоп-лосс сработал*\n\n"
                            message += f"Символ: {symbol_for_telegram}\n"
                            message += f"Вход: {currency_symbol}{entry_price:.2f} {currency}\n"
                            message += f"Выход: {currency_symbol}{current_price:.2f} {currency}\n"
                            message += f"Убыток: {currency_symbol}{loss:.2f} {currency}"
                            await self.telegram.send_message(message, parse_mode='Markdown')
                            del self.positions_tracking[symbol]
                            self.trade_history.append({
                                "ts": datetime.now(),
                                "symbol": symbol,
                                "action": "SELL",
                                "qty_lots": qty_lots,
                                "price": current_price,
                                "reason": "stop_loss",
                                "pnl": loss,
                            })
                            self.trade_history = self.trade_history[-50:]
                            self.cooldown_until[symbol] = datetime.now() + timedelta(minutes=SYMBOL_COOLDOWN_MIN)
                            try:
                                self._audit_event({
                                    "event": "trade",
                                    "symbol": symbol,
                                    "action": "SELL",
                                    "qty_lots": int(qty_lots),
                                    "lot": int(lot),
                                    "price": float(current_price),
                                    "reason": "stop_loss",
                                    "details": {
                                        "pnl": float(loss),
                                        "entry_price": float(entry_price),
                                        "qty_shares": float(qty_shares),
                                        "stop_level": float(stop_level),
                                    },
                                    "order": order,
                                })
                            except Exception:
                                pass
                            # Symbol Tracker: записываем stop_loss как убыток
                            if self.symbol_tracker is not None:
                                try:
                                    self.symbol_tracker.record_trade(symbol, float(loss), "stop_loss", 0.0)
                                except Exception:
                                    pass
                    continue
                
                # Проверка тейк-профита
                if float(current_price) >= float(take_level):
                    logger.info(f"Тейк-профит сработал для {symbol} (цена: {current_price:.2f}, тейк: {take_level:.2f}, лотов: {qty_lots})")
                    if ENABLE_TRADING:
                        # Финальная проверка: убеждаемся, что количество лотов не превышает доступное
                        try:
                            pos_qty_lots = int(position.get("qty_lots", position.get("qty", 0)) or 0)
                            if pos_qty_lots > 0:
                                qty_lots = min(qty_lots, pos_qty_lots)
                                logger.info(f"Финальная проверка для {symbol}: позиция={pos_qty_lots} лотов, продаем {qty_lots} лотов")
                            else:
                                logger.warning(f"Позиция {symbol} не содержит лотов (pos_qty_lots={pos_qty_lots})")
                        except Exception as e:
                            logger.error(f"Ошибка при проверке количества лотов для {symbol}: {e}")
                        
                        if qty_lots <= 0:
                            logger.warning(f"Невозможно продать {symbol}: количество лотов = {qty_lots}")
                            continue
                        
                        # Финальная проверка: запрашиваем актуальные позиции перед продажей
                        try:
                            current_positions = self.broker.get_positions() or []
                            current_pos = None
                            # get_positions() возвращает список, а не словарь
                            for pos_val in current_positions:
                                if not isinstance(pos_val, dict):
                                    continue
                                pos_sym = _canon_symbol(pos_val.get('symbol') or pos_val.get('ticker') or '')
                                # Проверяем совпадение по символу (учитываем возможные варианты написания)
                                symbol_canon = _canon_symbol(symbol)
                                pos_ticker_canon = _canon_symbol(position.get('ticker') or '')
                                if pos_sym == symbol_canon or pos_sym == pos_ticker_canon:
                                    current_pos = pos_val
                                    break
                            
                            if current_pos:
                                actual_qty = int(current_pos.get('qty_lots', current_pos.get('qty', 0)) or 0)
                                if actual_qty < qty_lots:
                                    logger.warning(f"Актуальное количество лотов для {symbol} меньше ожидаемого: {actual_qty} < {qty_lots}, используем {actual_qty}")
                                    qty_lots = actual_qty
                                elif actual_qty > 0:
                                    logger.info(f"Подтверждено количество лотов для {symbol}: {actual_qty} лотов (продаем {qty_lots})")
                            else:
                                logger.warning(f"Позиция {symbol} не найдена в актуальных позициях, возможно уже закрыта")
                                if qty_lots > 0:
                                    logger.info(f"Попытка продажи {qty_lots} лотов {symbol} несмотря на отсутствие в актуальных позициях")
                        except Exception as e:
                            logger.warning(f"Не удалось проверить актуальные позиции перед продажей {symbol}: {e}", exc_info=True)
                        
                        if qty_lots <= 0:
                            logger.warning(f"Пропускаем продажу {symbol}: количество лотов = {qty_lots}")
                            continue
                        
                        # Если symbol является FIGI, пытаемся найти тикер для размещения ордера
                        order_symbol = symbol
                        if symbol.startswith("BBG") and len(symbol) > 10:
                            # Это FIGI, пытаемся найти тикер
                            try:
                                pos_ticker = position.get('ticker') or position.get('symbol')
                                if pos_ticker and not pos_ticker.startswith("BBG"):
                                    order_symbol = _canon_symbol(pos_ticker)
                                else:
                                    # Пробуем найти через API
                                    instrument = self.broker.get_instrument_by_figi(symbol) if hasattr(self.broker, 'get_instrument_by_figi') else None
                                    if instrument and instrument.get('ticker'):
                                        order_symbol = _canon_symbol(instrument.get('ticker'))
                            except Exception:
                                pass
                        
                        logger.info(f"Размещение ордера на продажу (тейк-профит): {order_symbol}, {qty_lots} лотов")
                        order = self.broker.place_market_order(order_symbol, qty_lots, 'sell')
                        if not order:
                            # Получаем детальную информацию об ошибке
                            error_details = {}
                            if hasattr(self.broker, 'client') and hasattr(self.broker.client, '_last_order_error'):
                                error_details = self.broker.client._last_order_error.copy() if self.broker.client._last_order_error else {}
                            
                            error_reason = error_details.get('reason', 'unknown')
                            error_code = error_details.get('error_code', 'N/A')
                            error_description = error_details.get('description', 'place_market_order returned None')
                            
                            logger.error(f"❌ НЕ УДАЛОСЬ РАЗМЕСТИТЬ ТЕЙК-ПРОФИТ: {symbol} | "
                                        f"Причина: {error_reason} | Код ошибки: {error_code} | "
                                        f"Описание: {error_description} | "
                                        f"Параметры: qty_lots={qty_lots}, price={current_price:.2f}, entry={entry_price:.2f}, take={take_level:.2f}")
                            
                            if error_reason == 'instrument_not_available':
                                from datetime import datetime
                                current_time_msk = datetime.now().strftime('%H:%M:%S MSK')
                                logger.warning(f"   Время: {current_time_msk} | MOEX работает 10:00-18:45 MSK (основная сессия)")
                            elif error_reason == 'insufficient_balance':
                                logger.warning(f"   Позиция: qty_lots={qty_lots}, lot={lot}, qty_shares={qty_shares}")
                            
                            continue
                        if order:
                            # Преобразуем FIGI в тикер для корректного отображения в Telegram
                            symbol_for_telegram = _ensure_ticker_not_figi(symbol, self.broker)
                            symbol_for_telegram = _canon_symbol(symbol_for_telegram)
                            
                            profit = (float(current_price) - float(entry_price)) * float(qty_shares)
                            ai = self.broker.get_account_info()
                            currency = (ai.get("currency") or "RUB")
                            currency_symbol = {"RUB": "₽", "USD": "$", "EUR": "€"}.get(str(currency).upper(), str(currency).upper() + " ")
                            message = f"🎯 *Тейк-профит сработал*\n\n"
                            message += f"Символ: {symbol_for_telegram}\n"
                            message += f"Вход: {currency_symbol}{entry_price:.2f} {currency}\n"
                            message += f"Выход: {currency_symbol}{current_price:.2f} {currency}\n"
                            message += f"Прибыль: {currency_symbol}{profit:.2f} {currency}"
                            await self.telegram.send_message(message, parse_mode='Markdown')
                            del self.positions_tracking[symbol]
                            self.trade_history.append({
                                "ts": datetime.now(),
                                "symbol": symbol,
                                "action": "SELL",
                                "qty_lots": qty_lots,
                                "price": current_price,
                                "reason": "take_profit",
                                "pnl": profit,
                            })
                            self.trade_history = self.trade_history[-50:]
                            self.cooldown_until[symbol] = datetime.now() + timedelta(minutes=SYMBOL_COOLDOWN_MIN)
                            try:
                                self._audit_event({
                                    "event": "trade",
                                    "symbol": symbol,
                                    "action": "SELL",
                                    "qty_lots": int(qty_lots),
                                    "lot": int(lot),
                                    "price": float(current_price),
                                    "reason": "take_profit",
                                    "details": {
                                        "pnl": float(profit),
                                        "entry_price": float(entry_price),
                                        "qty_shares": float(qty_shares),
                                        "take_level": float(take_level),
                                    },
                                    "order": order,
                                })
                            except Exception:
                                pass
                            # Symbol Tracker: записываем take_profit как прибыль
                            if self.symbol_tracker is not None:
                                try:
                                    self.symbol_tracker.record_trade(symbol, float(profit), "take_profit", 0.0)
                                except Exception:
                                    pass
    
    async def stop(self):
        """Остановить бота"""
        self.running = False
        logger.info("Торговый бот остановлен")
        await self.telegram.send_message("🛑 *Торговый бот остановлен*")
        if self.telegram_control:
            try:
                await self.telegram_control.stop()
            except Exception:
                pass


async def main():
    """Главная функция"""
    bot = TradingBot()
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Остановка бота...")
        await bot.stop()
    except asyncio.CancelledError:
        logger.info("Остановка бота (CancelledError)...")
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
