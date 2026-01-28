"""
Market Regime Detector - Определитель режима рынка

Определяет текущий режим рынка (бычий/медвежий/боковой) и адаптирует стратегию:
1. BULL - агрессивнее BUY, осторожнее SELL
2. BEAR - осторожнее BUY, агрессивнее SELL
3. SIDEWAYS - только сильные сигналы

Также включает:
- Фильтр оптимальных торговых часов (на основе исторических данных)
- Детектор высокой волатильности (осторожность при экстремальных движениях)
"""

from datetime import datetime, time
from typing import Dict, Optional, Tuple
from zoneinfo import ZoneInfo
import pandas as pd


class MarketRegimeDetector:
    """
    Определяет режим рынка на основе технических индикаторов.
    """
    
    # Оптимальные часы для торговли на MOEX (MSK)
    # Анализ показывает: утренние часы (10-12) и вечерние (15-18) более прибыльны
    OPTIMAL_HOURS_MSK = [
        (10, 12),  # Утренняя сессия после открытия
        (15, 18),  # Вечерняя сессия
    ]
    
    # Часы с повышенным риском (открытие, закрытие)
    RISKY_HOURS_MSK = [
        (9, 10),   # Первый час после открытия - высокая волатильность
        (18, 19),  # Последний час - низкая ликвидность
    ]
    
    def __init__(self, tz: str = "Europe/Moscow"):
        try:
            self.tz = ZoneInfo(tz)
        except Exception:
            self.tz = ZoneInfo("UTC")
    
    def detect_regime(self, df: pd.DataFrame) -> str:
        """
        Определить режим рынка на основе данных.
        
        Args:
            df: DataFrame со свечами (должен содержать close, high, low)
        
        Returns:
            "BULL", "BEAR", или "SIDEWAYS"
        """
        if df is None or len(df) < 20:
            return "SIDEWAYS"
        
        try:
            close = df["close"].values
            
            # Простой детектор на основе скользящих средних
            ma_short = pd.Series(close).rolling(10).mean().iloc[-1]
            ma_long = pd.Series(close).rolling(20).mean().iloc[-1]
            
            current_price = close[-1]
            
            # Определяем тренд
            if current_price > ma_short > ma_long:
                # Цена выше обеих MA, MA короткая выше длинной = бычий тренд
                return "BULL"
            elif current_price < ma_short < ma_long:
                # Цена ниже обеих MA, MA короткая ниже длинной = медвежий тренд
                return "BEAR"
            else:
                return "SIDEWAYS"
        except Exception:
            return "SIDEWAYS"
    
    def get_regime_adjustments(self, regime: str) -> Dict:
        """
        Получить корректировки параметров для текущего режима.
        
        Returns:
            Dict с корректировками для confidence, position_size, etc.
        """
        if regime == "BULL":
            return {
                "buy_confidence_mult": 0.95,   # Снижаем порог для BUY
                "sell_confidence_mult": 1.1,   # Повышаем порог для SELL
                "position_size_mult": 1.1,     # Увеличиваем позиции
                "take_profit_mult": 1.2,       # Увеличиваем цели
                "description": "Бычий рынок: агрессивнее покупаем",
            }
        elif regime == "BEAR":
            return {
                "buy_confidence_mult": 1.15,   # Повышаем порог для BUY
                "sell_confidence_mult": 0.9,   # Снижаем порог для SELL
                "position_size_mult": 0.8,     # Уменьшаем позиции
                "take_profit_mult": 0.9,       # Уменьшаем цели (быстрее забираем)
                "description": "Медвежий рынок: осторожнее покупаем",
            }
        else:  # SIDEWAYS
            return {
                "buy_confidence_mult": 1.05,   # Немного повышаем пороги
                "sell_confidence_mult": 1.05,
                "position_size_mult": 0.9,     # Уменьшаем позиции
                "take_profit_mult": 0.85,      # Быстрее забираем прибыль
                "description": "Боковой рынок: только сильные сигналы",
            }
    
    def is_optimal_trading_time(self, dt: Optional[datetime] = None) -> Tuple[bool, str]:
        """
        Проверить, оптимальное ли сейчас время для торговли.
        
        Returns:
            (is_optimal, reason)
        """
        if dt is None:
            dt = datetime.now(self.tz)
        else:
            try:
                dt = dt.astimezone(self.tz)
            except Exception:
                pass
        
        hour = dt.hour
        
        # Проверяем рискованные часы
        for start, end in self.RISKY_HOURS_MSK:
            if start <= hour < end:
                return False, f"Рискованный час ({hour}:00 MSK)"
        
        # Проверяем оптимальные часы
        for start, end in self.OPTIMAL_HOURS_MSK:
            if start <= hour < end:
                return True, f"Оптимальный час ({hour}:00 MSK)"
        
        # Нейтральное время
        return True, f"Нейтральное время ({hour}:00 MSK)"
    
    def get_time_based_position_mult(self, dt: Optional[datetime] = None) -> float:
        """
        Получить множитель позиции на основе времени.
        
        Returns:
            Множитель (1.0 = норма, 0.7 = уменьшить, 1.1 = увеличить)
        """
        if dt is None:
            dt = datetime.now(self.tz)
        else:
            try:
                dt = dt.astimezone(self.tz)
            except Exception:
                pass
        
        hour = dt.hour
        
        # Рискованные часы - уменьшаем
        for start, end in self.RISKY_HOURS_MSK:
            if start <= hour < end:
                return 0.7
        
        # Оптимальные часы - можно увеличить
        for start, end in self.OPTIMAL_HOURS_MSK:
            if start <= hour < end:
                return 1.1
        
        return 1.0
    
    def detect_high_volatility(self, df: pd.DataFrame, threshold: float = 2.0) -> bool:
        """
        Определить, есть ли сейчас повышенная волатильность.
        
        Args:
            df: DataFrame со свечами
            threshold: Множитель ATR для определения "высокой" волатильности
        
        Returns:
            True если волатильность выше нормы
        """
        if df is None or len(df) < 20:
            return False
        
        try:
            # Считаем ATR
            high = df["high"].values
            low = df["low"].values
            close = df["close"].values
            
            tr = []
            for i in range(1, len(df)):
                tr.append(max(
                    high[i] - low[i],
                    abs(high[i] - close[i-1]),
                    abs(low[i] - close[i-1])
                ))
            
            if len(tr) < 14:
                return False
            
            atr_recent = sum(tr[-7:]) / 7
            atr_historical = sum(tr[-14:-7]) / 7 if len(tr) >= 14 else atr_recent
            
            # Если недавний ATR значительно выше исторического
            return atr_recent > atr_historical * threshold
        except Exception:
            return False


class CorrelationGuard:
    """
    Защита от коррелированных позиций.
    Не открывает несколько позиций в одном секторе/категории.
    """
    
    # Группы коррелированных активов
    CORRELATION_GROUPS = {
        "oil_gas": ["LKOH", "ROSN", "GAZP", "NVTK", "SNGS", "SNGSP", "TATN", "TATNP", "SIBN", "RNFT", "BANE", "BANEP"],
        "metals": ["GMKN", "NLMK", "CHMF", "MAGN", "RUAL", "ALRS", "PLZL", "SELG"],
        "finance": ["SBER", "VTBR", "MOEX", "AFKS"],
        "telecom": ["MTSS", "IRAO"],
        "retail": ["MGNT"],
        "tech": ["YNDX"],
        "transport": ["AFLT", "FLOT", "TRNFP"],
        "commodities_etf": ["UGLD", "LNZL", "GLDRUB_TOM", "SLVRUB_TOM", "PLTRUB_TOM", "PLDRUB_TOM"],
        "currency": ["USD000UTSTOM", "CNYRUB_TOM"],
    }
    
    def __init__(self, max_per_group: int = 2):
        self.max_per_group = max_per_group
    
    def get_symbol_group(self, symbol: str) -> Optional[str]:
        """Получить группу для символа."""
        symbol = str(symbol).upper()
        for group, symbols in self.CORRELATION_GROUPS.items():
            if symbol in symbols:
                return group
        return None
    
    def can_open_position(self, symbol: str, open_positions: Dict) -> Tuple[bool, str]:
        """
        Проверить, можно ли открыть позицию по символу.
        
        Args:
            symbol: Тикер для открытия
            open_positions: Текущие открытые позиции {symbol: {...}}
        
        Returns:
            (can_open, reason)
        """
        symbol = str(symbol).upper()
        group = self.get_symbol_group(symbol)
        
        if group is None:
            return True, "Символ не в коррелированных группах"
        
        # Считаем сколько позиций уже в этой группе
        group_symbols = set(self.CORRELATION_GROUPS.get(group, []))
        count_in_group = sum(1 for s in open_positions if str(s).upper() in group_symbols)
        
        if count_in_group >= self.max_per_group:
            return False, f"Уже {count_in_group} позиций в группе '{group}'"
        
        return True, f"OK (группа '{group}': {count_in_group}/{self.max_per_group})"


# Singleton instances
_regime_detector: Optional[MarketRegimeDetector] = None
_correlation_guard: Optional[CorrelationGuard] = None


def get_market_regime_detector(tz: str = "Europe/Moscow") -> MarketRegimeDetector:
    global _regime_detector
    if _regime_detector is None:
        _regime_detector = MarketRegimeDetector(tz=tz)
    return _regime_detector


def get_correlation_guard(max_per_group: int = 2) -> CorrelationGuard:
    global _correlation_guard
    if _correlation_guard is None:
        _correlation_guard = CorrelationGuard(max_per_group=max_per_group)
    return _correlation_guard


Market Regime Detector - Определитель режима рынка

Определяет текущий режим рынка (бычий/медвежий/боковой) и адаптирует стратегию:
1. BULL - агрессивнее BUY, осторожнее SELL
2. BEAR - осторожнее BUY, агрессивнее SELL
3. SIDEWAYS - только сильные сигналы

Также включает:
- Фильтр оптимальных торговых часов (на основе исторических данных)
- Детектор высокой волатильности (осторожность при экстремальных движениях)
"""

from datetime import datetime, time
from typing import Dict, Optional, Tuple
from zoneinfo import ZoneInfo
import pandas as pd


class MarketRegimeDetector:
    """
    Определяет режим рынка на основе технических индикаторов.
    """
    
    # Оптимальные часы для торговли на MOEX (MSK)
    # Анализ показывает: утренние часы (10-12) и вечерние (15-18) более прибыльны
    OPTIMAL_HOURS_MSK = [
        (10, 12),  # Утренняя сессия после открытия
        (15, 18),  # Вечерняя сессия
    ]
    
    # Часы с повышенным риском (открытие, закрытие)
    RISKY_HOURS_MSK = [
        (9, 10),   # Первый час после открытия - высокая волатильность
        (18, 19),  # Последний час - низкая ликвидность
    ]
    
    def __init__(self, tz: str = "Europe/Moscow"):
        try:
            self.tz = ZoneInfo(tz)
        except Exception:
            self.tz = ZoneInfo("UTC")
    
    def detect_regime(self, df: pd.DataFrame) -> str:
        """
        Определить режим рынка на основе данных.
        
        Args:
            df: DataFrame со свечами (должен содержать close, high, low)
        
        Returns:
            "BULL", "BEAR", или "SIDEWAYS"
        """
        if df is None or len(df) < 20:
            return "SIDEWAYS"
        
        try:
            close = df["close"].values
            
            # Простой детектор на основе скользящих средних
            ma_short = pd.Series(close).rolling(10).mean().iloc[-1]
            ma_long = pd.Series(close).rolling(20).mean().iloc[-1]
            
            current_price = close[-1]
            
            # Определяем тренд
            if current_price > ma_short > ma_long:
                # Цена выше обеих MA, MA короткая выше длинной = бычий тренд
                return "BULL"
            elif current_price < ma_short < ma_long:
                # Цена ниже обеих MA, MA короткая ниже длинной = медвежий тренд
                return "BEAR"
            else:
                return "SIDEWAYS"
        except Exception:
            return "SIDEWAYS"
    
    def get_regime_adjustments(self, regime: str) -> Dict:
        """
        Получить корректировки параметров для текущего режима.
        
        Returns:
            Dict с корректировками для confidence, position_size, etc.
        """
        if regime == "BULL":
            return {
                "buy_confidence_mult": 0.95,   # Снижаем порог для BUY
                "sell_confidence_mult": 1.1,   # Повышаем порог для SELL
                "position_size_mult": 1.1,     # Увеличиваем позиции
                "take_profit_mult": 1.2,       # Увеличиваем цели
                "description": "Бычий рынок: агрессивнее покупаем",
            }
        elif regime == "BEAR":
            return {
                "buy_confidence_mult": 1.15,   # Повышаем порог для BUY
                "sell_confidence_mult": 0.9,   # Снижаем порог для SELL
                "position_size_mult": 0.8,     # Уменьшаем позиции
                "take_profit_mult": 0.9,       # Уменьшаем цели (быстрее забираем)
                "description": "Медвежий рынок: осторожнее покупаем",
            }
        else:  # SIDEWAYS
            return {
                "buy_confidence_mult": 1.05,   # Немного повышаем пороги
                "sell_confidence_mult": 1.05,
                "position_size_mult": 0.9,     # Уменьшаем позиции
                "take_profit_mult": 0.85,      # Быстрее забираем прибыль
                "description": "Боковой рынок: только сильные сигналы",
            }
    
    def is_optimal_trading_time(self, dt: Optional[datetime] = None) -> Tuple[bool, str]:
        """
        Проверить, оптимальное ли сейчас время для торговли.
        
        Returns:
            (is_optimal, reason)
        """
        if dt is None:
            dt = datetime.now(self.tz)
        else:
            try:
                dt = dt.astimezone(self.tz)
            except Exception:
                pass
        
        hour = dt.hour
        
        # Проверяем рискованные часы
        for start, end in self.RISKY_HOURS_MSK:
            if start <= hour < end:
                return False, f"Рискованный час ({hour}:00 MSK)"
        
        # Проверяем оптимальные часы
        for start, end in self.OPTIMAL_HOURS_MSK:
            if start <= hour < end:
                return True, f"Оптимальный час ({hour}:00 MSK)"
        
        # Нейтральное время
        return True, f"Нейтральное время ({hour}:00 MSK)"
    
    def get_time_based_position_mult(self, dt: Optional[datetime] = None) -> float:
        """
        Получить множитель позиции на основе времени.
        
        Returns:
            Множитель (1.0 = норма, 0.7 = уменьшить, 1.1 = увеличить)
        """
        if dt is None:
            dt = datetime.now(self.tz)
        else:
            try:
                dt = dt.astimezone(self.tz)
            except Exception:
                pass
        
        hour = dt.hour
        
        # Рискованные часы - уменьшаем
        for start, end in self.RISKY_HOURS_MSK:
            if start <= hour < end:
                return 0.7
        
        # Оптимальные часы - можно увеличить
        for start, end in self.OPTIMAL_HOURS_MSK:
            if start <= hour < end:
                return 1.1
        
        return 1.0
    
    def detect_high_volatility(self, df: pd.DataFrame, threshold: float = 2.0) -> bool:
        """
        Определить, есть ли сейчас повышенная волатильность.
        
        Args:
            df: DataFrame со свечами
            threshold: Множитель ATR для определения "высокой" волатильности
        
        Returns:
            True если волатильность выше нормы
        """
        if df is None or len(df) < 20:
            return False
        
        try:
            # Считаем ATR
            high = df["high"].values
            low = df["low"].values
            close = df["close"].values
            
            tr = []
            for i in range(1, len(df)):
                tr.append(max(
                    high[i] - low[i],
                    abs(high[i] - close[i-1]),
                    abs(low[i] - close[i-1])
                ))
            
            if len(tr) < 14:
                return False
            
            atr_recent = sum(tr[-7:]) / 7
            atr_historical = sum(tr[-14:-7]) / 7 if len(tr) >= 14 else atr_recent
            
            # Если недавний ATR значительно выше исторического
            return atr_recent > atr_historical * threshold
        except Exception:
            return False


class CorrelationGuard:
    """
    Защита от коррелированных позиций.
    Не открывает несколько позиций в одном секторе/категории.
    """
    
    # Группы коррелированных активов
    CORRELATION_GROUPS = {
        "oil_gas": ["LKOH", "ROSN", "GAZP", "NVTK", "SNGS", "SNGSP", "TATN", "TATNP", "SIBN", "RNFT", "BANE", "BANEP"],
        "metals": ["GMKN", "NLMK", "CHMF", "MAGN", "RUAL", "ALRS", "PLZL", "SELG"],
        "finance": ["SBER", "VTBR", "MOEX", "AFKS"],
        "telecom": ["MTSS", "IRAO"],
        "retail": ["MGNT"],
        "tech": ["YNDX"],
        "transport": ["AFLT", "FLOT", "TRNFP"],
        "commodities_etf": ["UGLD", "LNZL", "GLDRUB_TOM", "SLVRUB_TOM", "PLTRUB_TOM", "PLDRUB_TOM"],
        "currency": ["USD000UTSTOM", "CNYRUB_TOM"],
    }
    
    def __init__(self, max_per_group: int = 2):
        self.max_per_group = max_per_group
    
    def get_symbol_group(self, symbol: str) -> Optional[str]:
        """Получить группу для символа."""
        symbol = str(symbol).upper()
        for group, symbols in self.CORRELATION_GROUPS.items():
            if symbol in symbols:
                return group
        return None
    
    def can_open_position(self, symbol: str, open_positions: Dict) -> Tuple[bool, str]:
        """
        Проверить, можно ли открыть позицию по символу.
        
        Args:
            symbol: Тикер для открытия
            open_positions: Текущие открытые позиции {symbol: {...}}
        
        Returns:
            (can_open, reason)
        """
        symbol = str(symbol).upper()
        group = self.get_symbol_group(symbol)
        
        if group is None:
            return True, "Символ не в коррелированных группах"
        
        # Считаем сколько позиций уже в этой группе
        group_symbols = set(self.CORRELATION_GROUPS.get(group, []))
        count_in_group = sum(1 for s in open_positions if str(s).upper() in group_symbols)
        
        if count_in_group >= self.max_per_group:
            return False, f"Уже {count_in_group} позиций в группе '{group}'"
        
        return True, f"OK (группа '{group}': {count_in_group}/{self.max_per_group})"


# Singleton instances
_regime_detector: Optional[MarketRegimeDetector] = None
_correlation_guard: Optional[CorrelationGuard] = None


def get_market_regime_detector(tz: str = "Europe/Moscow") -> MarketRegimeDetector:
    global _regime_detector
    if _regime_detector is None:
        _regime_detector = MarketRegimeDetector(tz=tz)
    return _regime_detector


def get_correlation_guard(max_per_group: int = 2) -> CorrelationGuard:
    global _correlation_guard
    if _correlation_guard is None:
        _correlation_guard = CorrelationGuard(max_per_group=max_per_group)
    return _correlation_guard


Market Regime Detector - Определитель режима рынка

Определяет текущий режим рынка (бычий/медвежий/боковой) и адаптирует стратегию:
1. BULL - агрессивнее BUY, осторожнее SELL
2. BEAR - осторожнее BUY, агрессивнее SELL
3. SIDEWAYS - только сильные сигналы

Также включает:
- Фильтр оптимальных торговых часов (на основе исторических данных)
- Детектор высокой волатильности (осторожность при экстремальных движениях)
"""

from datetime import datetime, time
from typing import Dict, Optional, Tuple
from zoneinfo import ZoneInfo
import pandas as pd


class MarketRegimeDetector:
    """
    Определяет режим рынка на основе технических индикаторов.
    """
    
    # Оптимальные часы для торговли на MOEX (MSK)
    # Анализ показывает: утренние часы (10-12) и вечерние (15-18) более прибыльны
    OPTIMAL_HOURS_MSK = [
        (10, 12),  # Утренняя сессия после открытия
        (15, 18),  # Вечерняя сессия
    ]
    
    # Часы с повышенным риском (открытие, закрытие)
    RISKY_HOURS_MSK = [
        (9, 10),   # Первый час после открытия - высокая волатильность
        (18, 19),  # Последний час - низкая ликвидность
    ]
    
    def __init__(self, tz: str = "Europe/Moscow"):
        try:
            self.tz = ZoneInfo(tz)
        except Exception:
            self.tz = ZoneInfo("UTC")
    
    def detect_regime(self, df: pd.DataFrame) -> str:
        """
        Определить режим рынка на основе данных.
        
        Args:
            df: DataFrame со свечами (должен содержать close, high, low)
        
        Returns:
            "BULL", "BEAR", или "SIDEWAYS"
        """
        if df is None or len(df) < 20:
            return "SIDEWAYS"
        
        try:
            close = df["close"].values
            
            # Простой детектор на основе скользящих средних
            ma_short = pd.Series(close).rolling(10).mean().iloc[-1]
            ma_long = pd.Series(close).rolling(20).mean().iloc[-1]
            
            current_price = close[-1]
            
            # Определяем тренд
            if current_price > ma_short > ma_long:
                # Цена выше обеих MA, MA короткая выше длинной = бычий тренд
                return "BULL"
            elif current_price < ma_short < ma_long:
                # Цена ниже обеих MA, MA короткая ниже длинной = медвежий тренд
                return "BEAR"
            else:
                return "SIDEWAYS"
        except Exception:
            return "SIDEWAYS"
    
    def get_regime_adjustments(self, regime: str) -> Dict:
        """
        Получить корректировки параметров для текущего режима.
        
        Returns:
            Dict с корректировками для confidence, position_size, etc.
        """
        if regime == "BULL":
            return {
                "buy_confidence_mult": 0.95,   # Снижаем порог для BUY
                "sell_confidence_mult": 1.1,   # Повышаем порог для SELL
                "position_size_mult": 1.1,     # Увеличиваем позиции
                "take_profit_mult": 1.2,       # Увеличиваем цели
                "description": "Бычий рынок: агрессивнее покупаем",
            }
        elif regime == "BEAR":
            return {
                "buy_confidence_mult": 1.15,   # Повышаем порог для BUY
                "sell_confidence_mult": 0.9,   # Снижаем порог для SELL
                "position_size_mult": 0.8,     # Уменьшаем позиции
                "take_profit_mult": 0.9,       # Уменьшаем цели (быстрее забираем)
                "description": "Медвежий рынок: осторожнее покупаем",
            }
        else:  # SIDEWAYS
            return {
                "buy_confidence_mult": 1.05,   # Немного повышаем пороги
                "sell_confidence_mult": 1.05,
                "position_size_mult": 0.9,     # Уменьшаем позиции
                "take_profit_mult": 0.85,      # Быстрее забираем прибыль
                "description": "Боковой рынок: только сильные сигналы",
            }
    
    def is_optimal_trading_time(self, dt: Optional[datetime] = None) -> Tuple[bool, str]:
        """
        Проверить, оптимальное ли сейчас время для торговли.
        
        Returns:
            (is_optimal, reason)
        """
        if dt is None:
            dt = datetime.now(self.tz)
        else:
            try:
                dt = dt.astimezone(self.tz)
            except Exception:
                pass
        
        hour = dt.hour
        
        # Проверяем рискованные часы
        for start, end in self.RISKY_HOURS_MSK:
            if start <= hour < end:
                return False, f"Рискованный час ({hour}:00 MSK)"
        
        # Проверяем оптимальные часы
        for start, end in self.OPTIMAL_HOURS_MSK:
            if start <= hour < end:
                return True, f"Оптимальный час ({hour}:00 MSK)"
        
        # Нейтральное время
        return True, f"Нейтральное время ({hour}:00 MSK)"
    
    def get_time_based_position_mult(self, dt: Optional[datetime] = None) -> float:
        """
        Получить множитель позиции на основе времени.
        
        Returns:
            Множитель (1.0 = норма, 0.7 = уменьшить, 1.1 = увеличить)
        """
        if dt is None:
            dt = datetime.now(self.tz)
        else:
            try:
                dt = dt.astimezone(self.tz)
            except Exception:
                pass
        
        hour = dt.hour
        
        # Рискованные часы - уменьшаем
        for start, end in self.RISKY_HOURS_MSK:
            if start <= hour < end:
                return 0.7
        
        # Оптимальные часы - можно увеличить
        for start, end in self.OPTIMAL_HOURS_MSK:
            if start <= hour < end:
                return 1.1
        
        return 1.0
    
    def detect_high_volatility(self, df: pd.DataFrame, threshold: float = 2.0) -> bool:
        """
        Определить, есть ли сейчас повышенная волатильность.
        
        Args:
            df: DataFrame со свечами
            threshold: Множитель ATR для определения "высокой" волатильности
        
        Returns:
            True если волатильность выше нормы
        """
        if df is None or len(df) < 20:
            return False
        
        try:
            # Считаем ATR
            high = df["high"].values
            low = df["low"].values
            close = df["close"].values
            
            tr = []
            for i in range(1, len(df)):
                tr.append(max(
                    high[i] - low[i],
                    abs(high[i] - close[i-1]),
                    abs(low[i] - close[i-1])
                ))
            
            if len(tr) < 14:
                return False
            
            atr_recent = sum(tr[-7:]) / 7
            atr_historical = sum(tr[-14:-7]) / 7 if len(tr) >= 14 else atr_recent
            
            # Если недавний ATR значительно выше исторического
            return atr_recent > atr_historical * threshold
        except Exception:
            return False


class CorrelationGuard:
    """
    Защита от коррелированных позиций.
    Не открывает несколько позиций в одном секторе/категории.
    """
    
    # Группы коррелированных активов
    CORRELATION_GROUPS = {
        "oil_gas": ["LKOH", "ROSN", "GAZP", "NVTK", "SNGS", "SNGSP", "TATN", "TATNP", "SIBN", "RNFT", "BANE", "BANEP"],
        "metals": ["GMKN", "NLMK", "CHMF", "MAGN", "RUAL", "ALRS", "PLZL", "SELG"],
        "finance": ["SBER", "VTBR", "MOEX", "AFKS"],
        "telecom": ["MTSS", "IRAO"],
        "retail": ["MGNT"],
        "tech": ["YNDX"],
        "transport": ["AFLT", "FLOT", "TRNFP"],
        "commodities_etf": ["UGLD", "LNZL", "GLDRUB_TOM", "SLVRUB_TOM", "PLTRUB_TOM", "PLDRUB_TOM"],
        "currency": ["USD000UTSTOM", "CNYRUB_TOM"],
    }
    
    def __init__(self, max_per_group: int = 2):
        self.max_per_group = max_per_group
    
    def get_symbol_group(self, symbol: str) -> Optional[str]:
        """Получить группу для символа."""
        symbol = str(symbol).upper()
        for group, symbols in self.CORRELATION_GROUPS.items():
            if symbol in symbols:
                return group
        return None
    
    def can_open_position(self, symbol: str, open_positions: Dict) -> Tuple[bool, str]:
        """
        Проверить, можно ли открыть позицию по символу.
        
        Args:
            symbol: Тикер для открытия
            open_positions: Текущие открытые позиции {symbol: {...}}
        
        Returns:
            (can_open, reason)
        """
        symbol = str(symbol).upper()
        group = self.get_symbol_group(symbol)
        
        if group is None:
            return True, "Символ не в коррелированных группах"
        
        # Считаем сколько позиций уже в этой группе
        group_symbols = set(self.CORRELATION_GROUPS.get(group, []))
        count_in_group = sum(1 for s in open_positions if str(s).upper() in group_symbols)
        
        if count_in_group >= self.max_per_group:
            return False, f"Уже {count_in_group} позиций в группе '{group}'"
        
        return True, f"OK (группа '{group}': {count_in_group}/{self.max_per_group})"


# Singleton instances
_regime_detector: Optional[MarketRegimeDetector] = None
_correlation_guard: Optional[CorrelationGuard] = None


def get_market_regime_detector(tz: str = "Europe/Moscow") -> MarketRegimeDetector:
    global _regime_detector
    if _regime_detector is None:
        _regime_detector = MarketRegimeDetector(tz=tz)
    return _regime_detector


def get_correlation_guard(max_per_group: int = 2) -> CorrelationGuard:
    global _correlation_guard
    if _correlation_guard is None:
        _correlation_guard = CorrelationGuard(max_per_group=max_per_group)
    return _correlation_guard





