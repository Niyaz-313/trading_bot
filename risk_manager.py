"""
Модуль управления рисками
Оптимизирован для снижения убытков и увеличения прибыли
"""
import logging
from typing import Dict
from config import (
    MAX_POSITION_SIZE, STOP_LOSS_PERCENT, TAKE_PROFIT_PERCENT,
    INITIAL_CAPITAL, RISK_PER_TRADE
)

logger = logging.getLogger(__name__)


class RiskManager:
    """Класс для управления рисками"""
    
    def __init__(self):
        """Инициализация менеджера рисков"""
        self.max_position_size = MAX_POSITION_SIZE
        self.stop_loss_percent = STOP_LOSS_PERCENT
        self.take_profit_percent = TAKE_PROFIT_PERCENT
        self.initial_capital = INITIAL_CAPITAL
        self.risk_per_trade = RISK_PER_TRADE
    
    def calculate_position_size(self, account_equity: float, price: float, confidence: float = 1.0) -> int:
        """
        Рассчитать размер позиции
        
        Args:
            account_equity: Текущий капитал на счете
            price: Цена акции
            confidence: Уверенность в сигнале (0.0 - 1.0)
        
        Returns:
            Количество акций для покупки
        """
        # Учитываем уверенность в сигнале
        adjusted_size = self.max_position_size * confidence
        # Ограничиваем максимальный размер позиции
        max_investment = account_equity * min(adjusted_size, self.max_position_size)
        qty = int(max_investment / price)
        return max(1, qty)  # Минимум 1 акция

    def calculate_position_size_by_risk(
        self,
        account_equity: float,
        price: float,
        stop_price: float,
        confidence: float = 1.0,
        risk_per_trade: float | None = None,
    ) -> int:
        """
        Рассчитать размер позиции по риску (budget / stop_distance), с ограничением max_position_size.

        Это полезно для волатильных бумаг: если стоп далеко, qty будет меньше, и серия стопов
        не "съест" портфель.
        """
        rp = self.risk_per_trade if risk_per_trade is None else float(risk_per_trade)
        rp = max(0.0, rp)

        try:
            stop_distance = abs(float(price) - float(stop_price))
        except Exception:
            stop_distance = 0.0

        # fallback: если стоп невалиден — используем старый метод
        if stop_distance <= 0:
            return self.calculate_position_size(account_equity, price, confidence=confidence)

        # риск-бюджет с учетом уверенности
        risk_budget = float(account_equity) * float(rp) * max(0.0, min(float(confidence), 1.0))
        qty_by_risk = int(risk_budget / stop_distance) if risk_budget > 0 else 0

        # ограничение по максимальной доле капитала
        max_investment = float(account_equity) * float(self.max_position_size)
        qty_cap = int(max_investment / float(price)) if float(price) > 0 else 0

        qty = min(qty_by_risk, qty_cap) if qty_cap > 0 else qty_by_risk
        return max(0, qty)
    
    def calculate_stop_loss(self, entry_price: float) -> float:
        """Рассчитать цену стоп-лосса"""
        return entry_price * (1 - self.stop_loss_percent)
    
    def calculate_take_profit(self, entry_price: float) -> float:
        """Рассчитать цену тейк-профита"""
        return entry_price * (1 + self.take_profit_percent)
    
    def check_stop_loss(self, entry_price: float, current_price: float) -> bool:
        """Проверить, сработал ли стоп-лосс"""
        stop_loss_price = self.calculate_stop_loss(entry_price)
        return current_price <= stop_loss_price
    
    def check_take_profit(self, entry_price: float, current_price: float) -> bool:
        """Проверить, сработал ли тейк-профит"""
        take_profit_price = self.calculate_take_profit(entry_price)
        return current_price >= take_profit_price
    
    def validate_trade(self, account_equity: float, price: float, qty: int) -> Dict:
        """
        Валидировать сделку
        
        Returns:
            Словарь с результатом валидации
        """
        trade_value = price * qty
        max_allowed = account_equity * self.max_position_size
        
        if trade_value > max_allowed:
            return {
                'valid': False,
                'reason': f'Размер позиции превышает максимум: {trade_value:.2f} > {max_allowed:.2f}'
            }
        
        if qty < 1:
            return {
                'valid': False,
                'reason': 'Количество акций должно быть не менее 1'
            }
        
        return {
            'valid': True,
            'trade_value': trade_value,
            'max_allowed': max_allowed
        }
    
    def calculate_risk_reward_ratio(self, entry_price: float) -> float:
        """Рассчитать соотношение риск/прибыль"""
        stop_loss = self.calculate_stop_loss(entry_price)
        take_profit = self.calculate_take_profit(entry_price)
        risk = entry_price - stop_loss
        reward = take_profit - entry_price
        return reward / risk if risk > 0 else 0.0
