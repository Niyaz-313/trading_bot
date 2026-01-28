"""
Набор стратегий и фабрика выбора стратегии.

Стратегии возвращают единый формат анализа:
{
  'signal': 'buy'|'sell'|'hold',
  'confidence': float (0..1),
  'buy_signals': int,
  'sell_signals': int,
  'trend': 'up'|'down'|'sideways',
  'atr': float|None,
  'rsi': float|None,
  'ma_short': float|None,
  'ma_long': float|None,
  'macd': float|None,
  'macd_signal': float|None,
  'macd_hist': float|None,
}
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd

from trading_strategy import TradingStrategy


@dataclass
class StrategyResult:
    signal: str
    confidence: float
    buy_signals: int = 0
    sell_signals: int = 0
    trend: str | None = None
    atr: float | None = None
    rsi: float | None = None
    ma_short: float | None = None
    ma_long: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_hist: float | None = None

    def to_dict(self) -> Dict:
        return {
            "signal": self.signal,
            "confidence": float(self.confidence),
            "buy_signals": int(self.buy_signals),
            "sell_signals": int(self.sell_signals),
            "trend": self.trend,
            "atr": self.atr,
            "rsi": self.rsi,
            "ma_short": self.ma_short,
            "ma_long": self.ma_long,
            "macd": self.macd,
            "macd_signal": self.macd_signal,
            "macd_hist": self.macd_hist,
        }


class BaseStrategy:
    name = "base"

    def analyze(self, data: pd.DataFrame) -> Dict:
        raise NotImplementedError

    def should_buy(self, analysis: Dict, min_confidence: float = 0.55) -> bool:
        # Общие "фильтры безопасности" (чтобы не покупать на вершине/в падающем ножe)
        rsi = analysis.get("rsi")
        trend = analysis.get("trend")
        macd_hist = analysis.get("macd_hist")
        macd_hist_prev = analysis.get("macd_hist_prev")

        # Не покупаем на перекупленности (в GAZP это давало стопы)
        if rsi is not None:
            try:
                if float(rsi) > 68:
                    return False
            except Exception:
                pass

        # Не покупаем против падающего тренда
        if trend == "down":
            return False

        # В боковике не покупаем при отрицательном импульсе
        if trend == "sideways" and macd_hist is not None:
            try:
                if float(macd_hist) < 0:
                    # Разрешаем mean-reversion вход в боковике только на перепроданности.
                    # Иначе bot часто "пилится" на шуме.
                    if rsi is None or float(rsi) > 35:
                        return False

                    # Доп. защита от "падающего ножа": если импульс ухудшается — не покупаем.
                    if macd_hist_prev is not None and float(macd_hist) < float(macd_hist_prev):
                        return False
            except Exception:
                pass

        return analysis.get("signal") == "buy" and float(analysis.get("confidence", 0.0) or 0.0) >= float(min_confidence)

    def should_sell(self, analysis: Dict, min_confidence: float = 0.5) -> bool:
        return analysis.get("signal") == "sell" and analysis.get("confidence", 0.0) >= min_confidence


class HybridStrategy(BaseStrategy):
    """
    Текущая "гибридная" стратегия из `trading_strategy.py`
    (RSI+MA+MACD+BB+Volume + фильтры).
    """

    name = "hybrid"

    def __init__(self):
        self._impl = TradingStrategy()

    def analyze(self, data: pd.DataFrame) -> Dict:
        return self._impl.analyze(data)

    def should_buy(self, analysis: Dict, min_confidence: float = 0.55) -> bool:
        return self._impl.should_buy(analysis, min_confidence=min_confidence)

    def should_sell(self, analysis: Dict, min_confidence: float = 0.5) -> bool:
        return self._impl.should_sell(analysis, min_confidence=min_confidence)


class TrendFollowingStrategy(BaseStrategy):
    """
    Упрощённая трендовая стратегия: торгует только по направлению тренда.
    Цель: меньше "ловить ножи" (особенно VTBR/GAZP).
    """

    name = "trend"

    def __init__(self):
        self._ta = TradingStrategy()

    def analyze(self, data: pd.DataFrame) -> Dict:
        base = self._ta.analyze(data)
        # Если base - не словарь, преобразуем его
        if not isinstance(base, dict):
            if hasattr(base, 'to_dict'):
                base = base.to_dict()
            elif hasattr(base, '__dict__'):
                base = dict(base.__dict__)
            else:
                base = dict(base) if hasattr(base, 'get') else {}
        
        # Получаем signal безопасно (может быть Series или другой тип)
        base_signal = base.get("signal")
        if isinstance(base_signal, pd.Series):
            base_signal = str(base_signal.iloc[-1]) if len(base_signal) > 0 else "hold"
        elif hasattr(base_signal, '__iter__') and not isinstance(base_signal, str):
            # Если это итерируемый объект, но не строка
            try:
                base_signal = str(list(base_signal)[-1]) if len(list(base_signal)) > 0 else "hold"
            except:
                base_signal = "hold"
        elif base_signal is None:
            base_signal = "hold"
        else:
            base_signal = str(base_signal)
        
        # Если данных мало — возвращаем base
        if base.get("confidence", 0.0) == 0.0 and base_signal == "hold":
            return base

        trend = base.get("trend")
        macd_hist = base.get("macd_hist")
        rsi = base.get("rsi")

        buy = 0
        sell = 0
        conf = 0.0

        # Покупка: только в up-тренде и с положительным импульсом
        if trend == "up" and (macd_hist is None or macd_hist >= 0):
            # не покупаем на перекупленности
            if rsi is not None:
                try:
                    if float(rsi) > 68:
                        base["signal"] = "hold"
                        base["confidence"] = 0.0
                        return base
                except Exception:
                    pass
            buy = 1
            conf = 0.6
            # усиливаем, если совпадает с гибридным buy
            if base_signal == "buy":
                buy += 1
                conf = max(conf, base.get("confidence", 0.0))

        # Продажа: при down/ослаблении импульса
        if trend == "down" or (macd_hist is not None and macd_hist < 0 and trend != "up"):
            sell = 1
            conf = max(conf, 0.55)
            if base_signal == "sell":
                sell += 1
                conf = max(conf, base.get("confidence", 0.0))

        if buy > sell and conf >= 0.55:
            return StrategyResult(
                signal="buy",
                confidence=conf,
                buy_signals=buy,
                sell_signals=sell,
                trend=trend,
                atr=base.get("atr"),
                rsi=base.get("rsi"),
                ma_short=base.get("ma_short"),
                ma_long=base.get("ma_long"),
                macd=base.get("macd"),
                macd_signal=base.get("macd_signal"),
                macd_hist=macd_hist,
            ).to_dict()
        if sell > buy and conf >= 0.5:
            return StrategyResult(
                signal="sell",
                confidence=conf,
                buy_signals=buy,
                sell_signals=sell,
                trend=trend,
                atr=base.get("atr"),
                rsi=base.get("rsi"),
                ma_short=base.get("ma_short"),
                ma_long=base.get("ma_long"),
                macd=base.get("macd"),
                macd_signal=base.get("macd_signal"),
                macd_hist=macd_hist,
            ).to_dict()

        # Если стратегия не уверена — hold
        base["signal"] = "hold"
        base["confidence"] = 0.0
        return base


class MeanReversionStrategy(BaseStrategy):
    """
    Контртренд/mean-reversion: покупает сильную перепроданность,
    но только при признаках стабилизации (чтобы не ловить нож).
    """

    name = "mean"

    def __init__(self):
        self._ta = TradingStrategy()

    def analyze(self, data: pd.DataFrame) -> Dict:
        if data.empty or len(data) < 50:
            return {"signal": "hold", "confidence": 0.0}

        # Используем базовые индикаторы из TradingStrategy
        base = self._ta.analyze(data)
        # Если base - не словарь, преобразуем его
        if not isinstance(base, dict):
            base = dict(base) if hasattr(base, 'get') else {}
        
        rsi = base.get("rsi")
        macd_hist = base.get("macd_hist")
        trend = base.get("trend")

        # Требуем "перепроданность" и НЕ сильный отрицательный импульс (чтобы не ловить нож)
        buy = 0
        sell = 0
        conf = 0.0

        if rsi is not None and rsi <= 30:
            buy += 1
            conf = 0.55
            # если импульс уже перестал быть отрицательным (или почти не отрицательный) — усиливаем
            if macd_hist is None or macd_hist >= -0.05:
                buy += 1
                conf = 0.65

        # Выход по перекупленности / ухудшению импульса
        if rsi is not None and rsi >= 68:
            sell += 1
            conf = max(conf, 0.55)
        if macd_hist is not None and macd_hist < 0 and trend != "up":
            sell += 1
            conf = max(conf, 0.6)

        if buy > sell and conf >= 0.55:
            return StrategyResult(
                signal="buy",
                confidence=conf,
                buy_signals=buy,
                sell_signals=sell,
                trend=trend,
                atr=base.get("atr"),
                rsi=rsi,
                ma_short=base.get("ma_short"),
                ma_long=base.get("ma_long"),
                macd=base.get("macd"),
                macd_signal=base.get("macd_signal"),
                macd_hist=macd_hist,
            ).to_dict()
        if sell > buy and conf >= 0.5:
            return StrategyResult(
                signal="sell",
                confidence=conf,
                buy_signals=buy,
                sell_signals=sell,
                trend=trend,
                atr=base.get("atr"),
                rsi=rsi,
                ma_short=base.get("ma_short"),
                ma_long=base.get("ma_long"),
                macd=base.get("macd"),
                macd_signal=base.get("macd_signal"),
                macd_hist=macd_hist,
            ).to_dict()

        base["signal"] = "hold"
        base["confidence"] = 0.0
        return base


class EnsembleStrategy(BaseStrategy):
    """
    Ансамбль: запускает несколько стратегий и принимает решение по голосованию.

    Логика:
    - если >=2 голосов за buy → buy
    - если >=2 голосов за sell → sell
    - если 1 голос, но confidence >= 0.70 → разрешаем (чтобы сделки не пропали)
    - иначе hold
    """

    name = "ensemble"

    def __init__(self, strategies: List[BaseStrategy] | None = None):
        self.strategies = strategies or [HybridStrategy(), TrendFollowingStrategy(), MeanReversionStrategy()]

    def analyze(self, data: pd.DataFrame) -> Dict:
        # Собираем анализы по именам стратегий
        by_name: Dict[str, Dict] = {}
        best_conf = 0.0
        for s in self.strategies:
            a = s.analyze(data)
            by_name[getattr(s, "name", s.__class__.__name__).lower()] = a
            best_conf = max(best_conf, float(a.get("confidence", 0.0) or 0.0))

        # Базовый анализ берём из hybrid (самый "богатый" по полям)
        hybrid = by_name.get("hybrid") or next(iter(by_name.values()), {"signal": "hold", "confidence": 0.0})
        trend = by_name.get("trend", {"signal": "hold", "confidence": 0.0})
        mean = by_name.get("mean", {"signal": "hold", "confidence": 0.0})

        # Безопасное получение signal (может быть Series)
        def safe_get_signal(d: Dict) -> str:
            if not isinstance(d, dict):
                if hasattr(d, 'to_dict'):
                    d = d.to_dict()
                elif hasattr(d, '__dict__'):
                    d = dict(d.__dict__)
                else:
                    return "hold"
            sig = d.get("signal")
            if isinstance(sig, pd.Series):
                sig = str(sig.iloc[-1]) if len(sig) > 0 else "hold"
            elif hasattr(sig, '__iter__') and not isinstance(sig, str):
                try:
                    sig = str(list(sig)[-1]) if len(list(sig)) > 0 else "hold"
                except:
                    sig = "hold"
            elif sig is None:
                sig = "hold"
            else:
                sig = str(sig)
            return sig
        
        hybrid_signal = safe_get_signal(hybrid)
        trend_signal = safe_get_signal(trend)
        mean_signal = safe_get_signal(mean)

        # Считаем голоса (для информации/логов)
        sigs = [hybrid_signal, trend_signal, mean_signal]
        buy_votes = sum(1 for s in sigs if s == "buy")
        sell_votes = sum(1 for s in sigs if s == "sell")

        # "Veto-only ансамбль":
        # - берем сигнал ТОЛЬКО от hybrid
        # - trend/mean могут только запретить BUY, если они считают, что это SELL/опасно
        # Это устраняет ситуацию, когда ансамбль ухудшает результат относительно hybrid.
        base = dict(hybrid)
        base["subsignals"] = {"hybrid": hybrid_signal, "trend": trend_signal, "mean": mean_signal}
        base["buy_signals"] = buy_votes
        base["sell_signals"] = sell_votes
        
        if hybrid_signal == "buy":
            if trend_signal == "sell" or mean_signal == "sell":
                base["signal"] = "hold"
                base["confidence"] = 0.0
                return base
            base["signal"] = "buy"
            base["confidence"] = float(hybrid.get("confidence", 0.0) or 0.0)
            return base

        if hybrid_signal == "sell":
            base["signal"] = "sell"
            base["confidence"] = float(hybrid.get("confidence", 0.0) or 0.0)
            return base

        base["signal"] = "hold"
        base["confidence"] = 0.0
        return base

    # ВАЖНО: для ансамбля используем общие фильтры безопасности из BaseStrategy,
    # иначе ансамбль будет покупать то, что hybrid отфильтровал (например RSI>68).
    # BaseStrategy.should_buy уже содержит эти фильтры, поэтому ничего не переопределяем.


def get_strategy(mode: str) -> BaseStrategy:
    m = (mode or "hybrid").strip().lower()
    if m in ("hybrid", "default"):
        return HybridStrategy()
    if m in ("trend", "trend_follow", "trendfollowing"):
        return TrendFollowingStrategy()
    if m in ("mean", "mean_reversion", "reversion"):
        return MeanReversionStrategy()
    if m in ("ensemble", "meta", "vote"):
        return EnsembleStrategy()
    raise ValueError(f"Unknown strategy mode: {mode}")


