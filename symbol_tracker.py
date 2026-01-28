"""
Symbol Performance Tracker - Адаптивный трекер производительности символов

Отслеживает историю успехов/неудач по каждому символу и адаптирует:
1. Размер позиции (уменьшаем для "холодных" символов)
2. Порог confidence (повышаем для проблемных символов)
3. Бонус за "горячую серию" (увеличиваем размер после побед)

Основано на анализе реальных данных:
- ROSN: 3 take_profit vs 1 stop = хороший символ
- MGNT: 0 take_profit vs 3 stop = плохой символ
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from collections import defaultdict


class SymbolTracker:
    """
    Трекер производительности символов.
    Сохраняет состояние между перезапусками.
    """
    
    def __init__(self, state_path: str = "state/symbol_performance.json", lookback_days: int = 14):
        self.state_path = state_path
        self.lookback_days = lookback_days
        self._ensure_dir()
        self.data = self._load()
    
    def _ensure_dir(self):
        dir_path = os.path.dirname(self.state_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
    
    def _load(self) -> Dict:
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"symbols": {}, "last_update": None}
    
    def _save(self):
        try:
            self.data["last_update"] = datetime.utcnow().isoformat()
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
    
    def record_trade(self, symbol: str, pnl: float, reason: str, confidence: float = 0.0):
        """
        Записывает результат сделки.
        
        Args:
            symbol: Тикер
            pnl: Прибыль/убыток в рублях
            reason: "take_profit", "stop_loss", "signal"
            confidence: Уверенность при входе (для анализа)
        """
        symbol = str(symbol).upper()
        if symbol not in self.data["symbols"]:
            self.data["symbols"][symbol] = {
                "trades": [],
                "total_pnl": 0.0,
                "wins": 0,
                "losses": 0,
                "streak": 0,  # положительный = серия побед, отрицательный = серия поражений
            }
        
        entry = {
            "ts": datetime.utcnow().isoformat(),
            "pnl": float(pnl),
            "reason": str(reason),
            "confidence": float(confidence),
        }
        
        sym_data = self.data["symbols"][symbol]
        sym_data["trades"].append(entry)
        sym_data["total_pnl"] += float(pnl)
        
        # Обновляем streak
        if pnl > 0:
            sym_data["wins"] += 1
            sym_data["streak"] = max(1, sym_data["streak"] + 1) if sym_data["streak"] >= 0 else 1
        else:
            sym_data["losses"] += 1
            sym_data["streak"] = min(-1, sym_data["streak"] - 1) if sym_data["streak"] <= 0 else -1
        
        # Храним только последние N дней
        cutoff = (datetime.utcnow() - timedelta(days=self.lookback_days)).isoformat()
        sym_data["trades"] = [t for t in sym_data["trades"] if t["ts"] >= cutoff]
        
        self._save()
    
    def get_symbol_stats(self, symbol: str) -> Dict:
        """
        Получить статистику по символу.
        
        Returns:
            Dict с полями: win_rate, avg_pnl, streak, recent_trades, risk_factor
        """
        symbol = str(symbol).upper()
        sym_data = self.data["symbols"].get(symbol, {})
        
        trades = sym_data.get("trades", [])
        wins = sym_data.get("wins", 0)
        losses = sym_data.get("losses", 0)
        total = wins + losses
        streak = sym_data.get("streak", 0)
        total_pnl = sym_data.get("total_pnl", 0.0)
        
        # Только недавние сделки (lookback период)
        cutoff = (datetime.utcnow() - timedelta(days=self.lookback_days)).isoformat()
        recent = [t for t in trades if t["ts"] >= cutoff]
        recent_wins = sum(1 for t in recent if t["pnl"] > 0)
        recent_losses = sum(1 for t in recent if t["pnl"] <= 0)
        recent_total = recent_wins + recent_losses
        
        win_rate = recent_wins / recent_total if recent_total > 0 else 0.5
        avg_pnl = sum(t["pnl"] for t in recent) / recent_total if recent_total > 0 else 0.0
        
        # Risk factor: 1.0 = нормальный, <1.0 = уменьшить размер, >1.0 = увеличить
        risk_factor = 1.0
        
        # Уменьшаем для символов с плохой статистикой
        if recent_total >= 3:
            if win_rate < 0.35:
                risk_factor *= 0.5  # Сильно уменьшаем
            elif win_rate < 0.45:
                risk_factor *= 0.75  # Немного уменьшаем
            elif win_rate > 0.60:
                risk_factor *= 1.2  # Немного увеличиваем
        
        # Корректируем по streak
        if streak >= 3:
            risk_factor *= 1.15  # Горячая серия
        elif streak <= -3:
            risk_factor *= 0.7  # Холодная серия
        
        return {
            "symbol": symbol,
            "win_rate": win_rate,
            "avg_pnl": avg_pnl,
            "streak": streak,
            "recent_trades": recent_total,
            "risk_factor": min(1.5, max(0.3, risk_factor)),  # Ограничиваем 0.3-1.5
            "total_pnl": total_pnl,
        }
    
    def get_confidence_adjustment(self, symbol: str) -> float:
        """
        Получить корректировку confidence для входа.
        Для проблемных символов повышаем требуемый confidence.
        
        Returns:
            Множитель (1.0 = норма, 1.1 = повысить порог на 10%)
        """
        stats = self.get_symbol_stats(symbol)
        
        if stats["recent_trades"] < 2:
            return 1.0
        
        # Для символов с win_rate < 40% требуем выше confidence
        if stats["win_rate"] < 0.40:
            return 1.15
        elif stats["win_rate"] < 0.50:
            return 1.05
        elif stats["win_rate"] > 0.65:
            return 0.95  # Для хороших символов можно чуть ниже
        
        return 1.0
    
    def get_position_size_multiplier(self, symbol: str) -> float:
        """
        Получить множитель размера позиции.
        
        Returns:
            Множитель (1.0 = норма, 0.5 = половина, 1.3 = на 30% больше)
        """
        stats = self.get_symbol_stats(symbol)
        return stats["risk_factor"]
    
    def is_symbol_blocked(self, symbol: str, min_trades: int = 5, max_loss_rate: float = 0.75) -> bool:
        """
        Проверить, заблокирован ли символ из-за плохой статистики.
        
        Args:
            min_trades: Минимум сделок для оценки
            max_loss_rate: Если loss_rate > этого, блокируем
        """
        stats = self.get_symbol_stats(symbol)
        
        if stats["recent_trades"] < min_trades:
            return False
        
        loss_rate = 1.0 - stats["win_rate"]
        return loss_rate > max_loss_rate
    
    def get_all_stats(self) -> List[Dict]:
        """Получить статистику по всем символам."""
        return [self.get_symbol_stats(sym) for sym in self.data["symbols"].keys()]
    
    def get_best_symbols(self, top_n: int = 10) -> List[str]:
        """Получить список лучших символов по win_rate."""
        all_stats = self.get_all_stats()
        # Фильтруем символы с достаточным количеством сделок
        valid = [s for s in all_stats if s["recent_trades"] >= 2]
        # Сортируем по win_rate и avg_pnl
        sorted_stats = sorted(valid, key=lambda x: (x["win_rate"], x["avg_pnl"]), reverse=True)
        return [s["symbol"] for s in sorted_stats[:top_n]]
    
    def get_worst_symbols(self, bottom_n: int = 5) -> List[str]:
        """Получить список худших символов."""
        all_stats = self.get_all_stats()
        valid = [s for s in all_stats if s["recent_trades"] >= 3]
        sorted_stats = sorted(valid, key=lambda x: (x["win_rate"], x["avg_pnl"]))
        return [s["symbol"] for s in sorted_stats[:bottom_n]]


# Singleton instance для использования в main.py
_tracker_instance: Optional[SymbolTracker] = None


def get_symbol_tracker(state_path: str = "state/symbol_performance.json") -> SymbolTracker:
    """Получить или создать глобальный трекер."""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = SymbolTracker(state_path=state_path)
    return _tracker_instance






