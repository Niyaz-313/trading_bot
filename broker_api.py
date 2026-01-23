"""
Модуль для работы с брокерским API
Поддерживает T-Invest API (Т-Инвестиции).

Примечание: поддержка Alpaca удалена из базовой сборки (бот ориентирован на рынок РФ).
"""
import logging
from typing import Dict, List, Optional
import pandas as pd

# Импорт T-Invest API
try:
    from tinvest_api import TInvestAPI
    TINVEST_AVAILABLE = True
except ImportError:
    TINVEST_AVAILABLE = False
    logging.warning("T-Invest API модуль не найден.")

ALPACA_AVAILABLE = False  # оставлено для совместимости, Alpaca не используется

from config import (
    BROKER, TINVEST_TOKEN, TINVEST_SANDBOX, TINVEST_ACCOUNT_ID,
    ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL  # опционально/не используется
)

logger = logging.getLogger(__name__)


class BrokerAPI:
    """Универсальный класс для работы с брокерским API"""
    
    def __init__(self, paper_trading: bool = True):
        """Инициализация брокерского API"""
        self.paper_trading = paper_trading
        self.client = None
        self.broker_type = BROKER
        
        # Инициализация T-Invest API
        if self.broker_type == 'tinvest' and TINVEST_AVAILABLE:
            if TINVEST_TOKEN:
                try:
                    self.client = TInvestAPI(sandbox=TINVEST_SANDBOX)
                    logger.info(f"Подключение к T-Invest API установлено (sandbox={TINVEST_SANDBOX})")
                except Exception as e:
                    logger.error(f"Ошибка подключения к T-Invest API: {e}")
                    self.client = None
            else:
                logger.warning("T-Invest токен не указан. Используется режим симуляции.")
        elif self.broker_type != 'tinvest':
            logger.warning(f"BROKER={self.broker_type} не поддерживается. Используется режим симуляции.")
        
        if not self.client:
            logger.warning("Используется режим симуляции (без реальных сделок)")
    
    def get_account_info(self) -> Dict:
        """Получить информацию о счете"""
        if self.client:
            try:
                if isinstance(self.client, TInvestAPI):
                    return self.client.get_account_info()
            except Exception as e:
                logger.error(f"Ошибка получения информации о счете: {e}")
                return {}
        return {'equity': 10000, 'cash': 10000, 'buying_power': 10000, 'portfolio_value': 10000}
    
    def get_positions(self) -> List[Dict]:
        """Получить список открытых позиций"""
        if self.client:
            try:
                if isinstance(self.client, TInvestAPI):
                    res = self.client.get_positions()
                    return res if isinstance(res, list) else []
            except Exception as e:
                logger.error(f"Ошибка получения позиций: {e}")
                return []
        return []

    def get_open_orders(self) -> List[Dict]:
        """Получить активные заявки (если брокер поддерживает)."""
        if self.client and isinstance(self.client, TInvestAPI):
            try:
                return self.client.get_open_orders()
            except Exception as e:
                logger.error(f"Ошибка получения активных заявок: {e}")
                return []
        return []

    def get_recent_operations(self, limit: int = 10, days: int = 7) -> List[Dict]:
        """Получить последние операции по счету (если брокер поддерживает)."""
        if self.client and isinstance(self.client, TInvestAPI):
            try:
                return self.client.get_recent_operations(limit=limit, days=days)
            except Exception as e:
                logger.error(f"Ошибка получения операций: {e}")
                return []
        return []

    def get_order_state(self, order_id: str) -> Optional[Dict]:
        """Получить статус заявки по order_id (если брокер поддерживает)."""
        if self.client and isinstance(self.client, TInvestAPI):
            try:
                return self.client.get_order_state(order_id)
            except Exception as e:
                logger.error(f"Ошибка получения статуса заявки {order_id}: {e}")
                return None
        return None

    def get_instrument_details(self, symbol: str) -> Optional[Dict]:
        """Получить детали инструмента (lot/figi). Нужно для корректной торговли лотами в T-Invest."""
        if self.client and isinstance(self.client, TInvestAPI):
            try:
                # get_instrument_details теперь поддерживает и тикер, и FIGI
                return self.client.get_instrument_details(symbol)
            except Exception as e:
                logger.error(f"Ошибка получения деталей инструмента {symbol}: {e}")
                return None
        return None
    
    def get_instrument_by_figi(self, figi: str) -> Optional[Dict]:
        """Получить детали инструмента по FIGI"""
        if self.client and isinstance(self.client, TInvestAPI):
            try:
                return self.client.get_instrument_by_figi(figi)
            except Exception as e:
                logger.error(f"Ошибка получения инструмента по FIGI {figi}: {e}")
                return None
        return None
    
    def get_historical_data(self, symbol: str, period: str = '5d', interval: str = '5m') -> pd.DataFrame:
        """Получить исторические данные по акции"""
        if self.client and isinstance(self.client, TInvestAPI):
            return self.client.get_historical_data(symbol, period, interval)

        logger.error(f"Исторические данные для {symbol} доступны только через T-Invest (BROKER=tinvest).")
        return pd.DataFrame()
    
    def get_current_price(self, symbol: str) -> float:
        """Получить текущую цену акции"""
        if self.client:
            try:
                if isinstance(self.client, TInvestAPI):
                    return self.client.get_current_price(symbol)
            except Exception as e:
                logger.error(f"Ошибка получения цены через API для {symbol}: {e}")

        logger.error(f"Цена для {symbol} доступна только через T-Invest (BROKER=tinvest).")
        return 0.0
    
    def place_market_order(self, symbol: str, qty: int, side: str) -> Optional[Dict]:
        """Разместить рыночный ордер"""
        if not self.client:
            logger.info(f"СИМУЛЯЦИЯ: {side.upper()} {qty} {symbol}")
            return {'symbol': symbol, 'qty': qty, 'side': side, 'status': 'filled', 'simulated': True}
        
        try:
            if isinstance(self.client, TInvestAPI):
                result = self.client.place_market_order(symbol, qty, side)
                # Если ордер не размещён, получаем детали ошибки из клиента
                if result is None and hasattr(self.client, '_last_order_error'):
                    error_details = self.client._last_order_error
                    logger.debug(f"Детали ошибки размещения ордера для {symbol}: {error_details}")
                return result
        except Exception as e:
            logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА при размещении ордера для {symbol}: {e}", exc_info=True)
            return None
    
    def place_limit_order(self, symbol: str, qty: int, side: str, limit_price: float) -> Optional[Dict]:
        """Разместить лимитный ордер"""
        if not self.client:
            logger.info(f"СИМУЛЯЦИЯ: {side.upper()} {qty} {symbol} @ {limit_price}")
            return {'symbol': symbol, 'qty': qty, 'side': side, 'limit_price': limit_price, 'status': 'pending', 'simulated': True}
        
        try:
            if isinstance(self.client, TInvestAPI):
                return self.client.place_limit_order(symbol, qty, side, limit_price)
        except Exception as e:
            logger.error(f"Ошибка размещения лимитного ордера для {symbol}: {e}")
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """Отменить ордер"""
        if not self.client:
            return True
        
        try:
            if isinstance(self.client, TInvestAPI):
                return self.client.cancel_order(order_id)
        except Exception as e:
            logger.error(f"Ошибка отмены ордера {order_id}: {e}")
            return False
