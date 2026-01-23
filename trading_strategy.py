"""
Торговая стратегия с использованием технических индикаторов
Оптимизирована для прибыльности
"""
import logging
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple

from config import (
    RSI_PERIOD, RSI_OVERSOLD, RSI_OVERBOUGHT,
    MA_SHORT_PERIOD, MA_LONG_PERIOD,
    MACD_FAST, MACD_SLOW, MACD_SIGNAL
)

logger = logging.getLogger(__name__)


class TradingStrategy:
    """Класс торговой стратегии - оптимизирован для прибыльности"""
    
    def __init__(self):
        """Инициализация стратегии"""
        self.rsi_period = RSI_PERIOD
        self.rsi_oversold = RSI_OVERSOLD
        self.rsi_overbought = RSI_OVERBOUGHT
        self.ma_short = MA_SHORT_PERIOD
        self.ma_long = MA_LONG_PERIOD
        self.macd_fast = MACD_FAST
        self.macd_slow = MACD_SLOW
        self.macd_signal = MACD_SIGNAL
    
    def calculate_rsi(self, data: pd.DataFrame, period: int = None) -> pd.Series:
        """Рассчитать RSI (Relative Strength Index)"""
        if period is None:
            period = self.rsi_period
        
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_moving_averages(self, data: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """Рассчитать скользящие средние"""
        ma_short = data['Close'].rolling(window=self.ma_short).mean()
        ma_long = data['Close'].rolling(window=self.ma_long).mean()
        return ma_short, ma_long
    
    def calculate_macd(self, data: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Рассчитать MACD"""
        ema_fast = data['Close'].ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = data['Close'].ewm(span=self.macd_slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.macd_signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    def calculate_bollinger_bands(self, data: pd.DataFrame, period: int = 20, std_dev: int = 2) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Рассчитать полосы Боллинджера"""
        sma = data['Close'].rolling(window=period).mean()
        std = data['Close'].rolling(window=period).std()
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        return upper_band, sma, lower_band
    
    def calculate_volume_indicator(self, data: pd.DataFrame) -> pd.Series:
        """Рассчитать индикатор объема (Volume Moving Average)"""
        if 'Volume' not in data.columns:
            return pd.Series(index=data.index, data=0.0)
        volume_ma = data['Volume'].rolling(window=20).mean()
        return volume_ma

    def calculate_atr(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Рассчитать ATR (Average True Range)"""
        if data.empty or not all(col in data.columns for col in ['High', 'Low', 'Close']):
            return pd.Series(index=data.index, data=np.nan)

        high = data['High']
        low = data['Low']
        close = data['Close']
        prev_close = close.shift(1)

        tr1 = (high - low).abs()
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = true_range.rolling(window=period).mean()
        return atr
    
    def analyze(self, data: pd.DataFrame) -> Dict:
        """
        Проанализировать данные и вернуть сигналы
        Оптимизировано для прибыльности
        """
        if data.empty or len(data) < self.ma_long:
            return {'signal': 'hold', 'confidence': 0.0}
        
        # Рассчитываем индикаторы
        rsi = self.calculate_rsi(data)
        ma_short, ma_long = self.calculate_moving_averages(data)
        macd, signal, histogram = self.calculate_macd(data)
        bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands(data)
        volume_ma = self.calculate_volume_indicator(data)
        atr = self.calculate_atr(data)
        
        # Получаем последние значения
        current_price = data['Close'].iloc[-1]
        current_rsi = rsi.iloc[-1]
        current_ma_short = ma_short.iloc[-1]
        current_ma_long = ma_long.iloc[-1]
        current_macd = macd.iloc[-1]
        current_signal = signal.iloc[-1]
        current_histogram = histogram.iloc[-1]
        prev_histogram = histogram.iloc[-2] if len(histogram) > 1 else current_histogram
        current_bb_upper = bb_upper.iloc[-1]
        current_bb_lower = bb_lower.iloc[-1]
        current_volume = data['Volume'].iloc[-1] if 'Volume' in data.columns else 0
        current_volume_ma = volume_ma.iloc[-1] if not volume_ma.empty else 0
        current_atr = atr.iloc[-1] if not atr.empty else np.nan

        # Тренд-фильтр (упрощённый, чтобы не "задушить" сделки)
        trend = 'sideways'
        if not pd.isna(current_ma_long) and not pd.isna(current_ma_short):
            if current_price > current_ma_long and current_ma_short > current_ma_long:
                trend = 'up'
            elif current_price < current_ma_long and current_ma_short < current_ma_long:
                trend = 'down'
        
        # Логика принятия решений (оптимизирована для прибыльности)
        buy_signals = 0
        sell_signals = 0
        confidence = 0.0
        
        # RSI сигналы (оптимизированы для прибыльности)
        if not pd.isna(current_rsi):
            if current_rsi < self.rsi_oversold:
                buy_signals += 2  # Усиленный сигнал покупки
                confidence += 0.35  # Увеличено с 0.3 для качества
            elif current_rsi < 35:  # Дополнительная зона покупки
                buy_signals += 1
                confidence += 0.18  # Увеличено с 0.15
            elif current_rsi < 40:  # Расширенная зона покупки (НОВОЕ)
                buy_signals += 1
                confidence += 0.12
            elif current_rsi > self.rsi_overbought:
                sell_signals += 2  # Усиленный сигнал продажи
                confidence += 0.35  # Увеличено с 0.3
            elif current_rsi > 65:  # Дополнительная зона продажи
                sell_signals += 1
                confidence += 0.18  # Увеличено с 0.15
        
        # Moving Average сигналы (золотой/смертельный крест)
        if not pd.isna(current_ma_short) and not pd.isna(current_ma_long):
            # Проверяем пересечение
            prev_ma_short = ma_short.iloc[-2] if len(ma_short) > 1 else current_ma_short
            prev_ma_long = ma_long.iloc[-2] if len(ma_long) > 1 else current_ma_long
            
            # Золотой крест (быстрая пересекает медленную снизу вверх)
            if prev_ma_short <= prev_ma_long and current_ma_short > current_ma_long:
                buy_signals += 2
                confidence += 0.35  # Увеличено с 0.3
            elif current_ma_short > current_ma_long:
                buy_signals += 1
                confidence += 0.22  # Увеличено с 0.2
            # Дополнительный сигнал: цена выше обеих MA (сильный тренд)
            elif current_price > current_ma_short and current_ma_short > current_ma_long:
                buy_signals += 1
                confidence += 0.15
            
            # Смертельный крест (быстрая пересекает медленную сверху вниз)
            if prev_ma_short >= prev_ma_long and current_ma_short < current_ma_long:
                sell_signals += 2
                confidence += 0.3
            elif current_ma_short < current_ma_long:
                sell_signals += 1
                confidence += 0.2
        
        # MACD сигналы
        if not pd.isna(current_macd) and not pd.isna(current_signal):
            prev_macd = macd.iloc[-2] if len(macd) > 1 else current_macd
            prev_signal = signal.iloc[-2] if len(signal) > 1 else current_signal
            
            # Пересечение MACD и сигнальной линии
            if prev_macd <= prev_signal and current_macd > current_signal and current_histogram > 0:
                buy_signals += 2
                confidence += 0.35  # Увеличено с 0.3
            elif current_macd > current_signal and current_histogram > 0:
                buy_signals += 1
                confidence += 0.22  # Увеличено с 0.2
            # Дополнительный сигнал: положительный MACD histogram (импульс)
            elif current_histogram > 0 and current_histogram > prev_histogram:
                buy_signals += 1
                confidence += 0.15
            
            if prev_macd >= prev_signal and current_macd < current_signal and current_histogram < 0:
                sell_signals += 2
                confidence += 0.3
            elif current_macd < current_signal and current_histogram < 0:
                sell_signals += 1
                confidence += 0.2
        
        # Bollinger Bands сигналы
        if not pd.isna(current_bb_lower) and not pd.isna(current_bb_upper):
            if current_price <= current_bb_lower:
                buy_signals += 1
                confidence += 0.2
            elif current_price >= current_bb_upper:
                sell_signals += 1
                confidence += 0.2
        
        # Объемные сигналы (подтверждение тренда)
        volume_ratio = 1.0
        if current_volume > 0 and current_volume_ma > 0:
            volume_ratio = current_volume / current_volume_ma
            if volume_ratio > 1.2:  # Высокий объем подтверждает сигнал
                if buy_signals > sell_signals:
                    confidence += 0.15  # Увеличено с 0.1 до 0.15
                    buy_signals += 1  # Высокий объем = дополнительный сигнал
                elif sell_signals > buy_signals:
                    confidence += 0.15
                    sell_signals += 1
            elif volume_ratio > 1.5:  # Очень высокий объем - сильное подтверждение
                if buy_signals > sell_signals:
                    confidence += 0.25
                    buy_signals += 1
                elif sell_signals > buy_signals:
                    confidence += 0.25
                    sell_signals += 1
        
        # ATR-based сигналы (волатильность и momentum)
        if not pd.isna(current_atr) and current_atr > 0 and current_price > 0:
            atr_pct = (current_atr / current_price) * 100
            # Нормальная волатильность (0.5% - 3%) - хорошие условия для торговли
            if 0.5 <= atr_pct <= 3.0:
                if buy_signals > sell_signals:
                    confidence += 0.1
                elif sell_signals > buy_signals:
                    confidence += 0.1
            
            # Momentum сигнал: цена движется быстрее ATR
            if len(data) >= 2:
                price_change = abs((current_price - data['Close'].iloc[-2]) / data['Close'].iloc[-2]) * 100
                if price_change > atr_pct * 1.5:  # Сильное движение
                    if current_price > data['Close'].iloc[-2] and buy_signals > sell_signals:
                        buy_signals += 1
                        confidence += 0.15
                    elif current_price < data['Close'].iloc[-2] and sell_signals > buy_signals:
                        sell_signals += 1
                        confidence += 0.15
        
        # Определяем финальный сигнал (оптимизировано для активности)
        # ОПТИМИЗИРОВАНО (2026-01-19): снижено требование с 2 до 1 сигнала для увеличения количества сделок
        # Для покупки: минимум 1 сигнал + уверенность >= 0.45 + не падающий тренд
        # При 1 сигнале требуем более высокий confidence (>= 0.55) для качества
        min_conf_for_1_signal = 0.55
        min_conf_for_2plus_signals = 0.45
        
        if buy_signals >= 1 and buy_signals > sell_signals and trend != 'down':
            required_conf = min_conf_for_1_signal if buy_signals == 1 else min_conf_for_2plus_signals
            if confidence >= required_conf:
                signal = 'buy'
                confidence = min(confidence, 1.0)
        # Для продажи: минимум 3 сигнала + уверенность >= 0.5
        elif sell_signals >= 3 and sell_signals > buy_signals and confidence >= 0.5:
            signal = 'sell'
            confidence = min(confidence, 1.0)
        else:
            signal = 'hold'
            # ВАЖНО: Сохраняем confidence даже для hold сигналов, чтобы видеть потенциал сигнала
            # Это помогает анализировать упущенные возможности и улучшать стратегию
            # Ограничиваем confidence для hold максимальным значением, но не сбрасываем в 0
            if confidence > 0:
                # Оставляем confidence как есть, но ограничиваем до 1.0
                confidence = min(confidence, 1.0)
            else:
                # Если confidence был 0 (нет сигналов), оставляем 0
                confidence = 0.0
        
        return {
            'signal': signal,
            'confidence': confidence,
            'rsi': current_rsi,
            'ma_short': current_ma_short,
            'ma_long': current_ma_long,
            'macd': current_macd,
            'macd_signal': current_signal,
            'macd_hist': current_histogram if not pd.isna(current_histogram) else None,
            'macd_hist_prev': prev_histogram if not pd.isna(prev_histogram) else None,
            'price': current_price,
            'bb_upper': current_bb_upper,
            'bb_lower': current_bb_lower,
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'volume_ratio': volume_ratio if current_volume > 0 and current_volume_ma > 0 else 1.0,
            'atr': float(current_atr) if not pd.isna(current_atr) else None,
            'trend': trend,
        }
    
    def should_buy(self, analysis: Dict, min_confidence: float = 0.55) -> bool:
        """Проверить, следует ли покупать"""
        rsi = analysis.get('rsi')
        macd_hist = analysis.get('macd_hist')
        macd_hist_prev = analysis.get('macd_hist_prev')
        trend = analysis.get('trend')

        # 1) Не покупаем на сильной перекупленности (в ваших сделках это давало стоп-лоссы)
        # ОПТИМИЗИРОВАНО (2026-01-17): увеличено до 75 для достижения 10+ сделок в день
        if rsi is not None and not pd.isna(rsi) and rsi > 75:
            return False

        # 2) В боковике BUY разрешаем только как mean-reversion вход на перепроданности.
        # Иначе (sideways + отрицательный импульс) слишком часто даёт "пилу"/стоп-лоссы.
        # Это ослабляет прежний фильтр: бот перестаёт "молчать" при сильной перепроданности,
        # но по-прежнему защищён от "падающего ножа" (см. пункт 3).
        if trend == 'sideways' and macd_hist is not None:
            try:
                if float(macd_hist) < 0:
                    # Разрешаем покупку в боковике при сильной перепроданности (RSI <= 30)
                    # или при очень высоком confidence (>0.8) - это важные сигналы
                    rsi_val = float(rsi) if rsi is not None and not pd.isna(rsi) else None
                    conf_val = float(analysis.get('confidence', 0) or 0)
                    
                    # ОПТИМИЗИРОВАНО (2026-01-16): расширена зона перепроданности с RSI <= 30 до RSI <= 35
                    # Если перепроданность (RSI <= 35) - разрешаем
                    if rsi_val is not None and rsi_val <= 35:
                        pass  # Продолжаем проверку, не блокируем
                    # Если очень высокий confidence (>0.8) - разрешаем
                    elif conf_val > 0.8:
                        pass  # Продолжаем проверку, не блокируем
                    # Иначе блокируем
                    else:
                        return False
            except Exception:
                pass

        # 3) Фильтр "падающий нож" даже в up-тренде:
        # если гистограмма MACD отрицательная И ухудшается (становится более отрицательной) — не покупаем
        try:
            if macd_hist is not None and macd_hist_prev is not None:
                if float(macd_hist) < 0 and float(macd_hist) < float(macd_hist_prev):
                    return False
        except Exception:
            pass

        # ОПТИМИЗИРОВАНО (2026-01-17): снижено требование buy_signals до 1 для достижения 10+ сделок в день
        # Безопасное извлечение скалярных значений из pandas Series
        try:
            if isinstance(analysis['signal'], pd.Series):
                signal_val = analysis['signal'].iloc[0] if len(analysis['signal']) > 0 else analysis['signal'].values[0] if len(analysis['signal'].values) > 0 else str(analysis['signal'].values[0])
            else:
                signal_val = analysis['signal']
        except (IndexError, AttributeError, ValueError):
            signal_val = str(analysis['signal']) if analysis['signal'] is not None else 'hold'
        
        try:
            if isinstance(analysis['confidence'], pd.Series):
                confidence_val = float(analysis['confidence'].iloc[0] if len(analysis['confidence']) > 0 else analysis['confidence'].values[0])
            else:
                confidence_val = float(analysis['confidence'])
        except (IndexError, AttributeError, ValueError, TypeError):
            confidence_val = float(analysis.get('confidence', 0) or 0)
        
        buy_signals_val = analysis.get('buy_signals', 0)
        try:
            if isinstance(buy_signals_val, pd.Series):
                buy_signals_val = int(buy_signals_val.iloc[0] if len(buy_signals_val) > 0 else buy_signals_val.values[0])
            else:
                buy_signals_val = int(buy_signals_val or 0)
        except (IndexError, AttributeError, ValueError, TypeError):
            buy_signals_val = 0
        
        return (signal_val == 'buy' and
                confidence_val >= min_confidence and
                buy_signals_val >= 1 and
                trend != 'down')
    
    def should_sell(self, analysis: Dict, min_confidence: float = 0.5) -> bool:
        """Проверить, следует ли продавать"""
        # Безопасное извлечение скалярных значений из pandas Series
        try:
            if isinstance(analysis['signal'], pd.Series):
                signal_val = analysis['signal'].iloc[0] if len(analysis['signal']) > 0 else analysis['signal'].values[0] if len(analysis['signal'].values) > 0 else str(analysis['signal'].values[0])
            else:
                signal_val = analysis['signal']
        except (IndexError, AttributeError, ValueError):
            signal_val = str(analysis['signal']) if analysis['signal'] is not None else 'hold'
        
        try:
            if isinstance(analysis['confidence'], pd.Series):
                confidence_val = float(analysis['confidence'].iloc[0] if len(analysis['confidence']) > 0 else analysis['confidence'].values[0])
            else:
                confidence_val = float(analysis['confidence'])
        except (IndexError, AttributeError, ValueError, TypeError):
            confidence_val = float(analysis.get('confidence', 0) or 0)
        
        return signal_val == 'sell' and confidence_val >= min_confidence
