#!/usr/bin/env python3
"""
Скрипт для продажи всех позиций в портфеле
"""
import sys
import logging
from datetime import datetime
from broker_api import BrokerAPI
from config import TINVEST_SANDBOX, BROKER, ENABLE_TRADING

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def _canon_symbol(sym: str) -> str:
    """Канонизация символа"""
    s = str(sym or "").strip().upper()
    if not s:
        return s
    try:
        from tinvest_api import TICKER_CANONICAL_MAP
        result = str(TICKER_CANONICAL_MAP.get(s, s)).strip().upper()
        return result
    except Exception:
        return s

def _ensure_ticker_not_figi(symbol: str, broker_api) -> str:
    """Убедиться, что symbol является тикером, а не FIGI"""
    symbol_u = str(symbol or "").strip().upper()
    if not symbol_u:
        return symbol_u
    
    if not symbol_u.startswith("BBG") or len(symbol_u) <= 10:
        return symbol_u
    
    # Это похоже на FIGI, пытаемся найти тикер
    try:
        instrument = broker_api.get_instrument_by_figi(symbol_u) if hasattr(broker_api, 'get_instrument_by_figi') else None
        if instrument and instrument.get('ticker'):
            ticker = str(instrument.get('ticker')).strip().upper()
            logger.info(f"Преобразовано FIGI {symbol_u} -> тикер {ticker}")
            return _canon_symbol(ticker)
    except Exception as e:
        logger.debug(f"Не удалось найти тикер для FIGI {symbol_u}: {e}")
    
    return symbol_u

def sell_all_positions():
    """Продать все позиции в портфеле"""
    
    if not ENABLE_TRADING:
        logger.error("❌ ТОРГОВЛЯ ОТКЛЮЧЕНА (ENABLE_TRADING=False)")
        logger.error("Для продажи позиций включите торговлю в .env файле")
        return False
    
    # Инициализация брокера
    paper_trading = TINVEST_SANDBOX if BROKER == 'tinvest' else True
    broker = BrokerAPI(paper_trading=paper_trading)
    
    if not broker.client:
        logger.error("❌ Не удалось подключиться к брокеру")
        return False
    
    logger.info("=" * 60)
    logger.info("ПРОДАЖА ВСЕХ ПОЗИЦИЙ")
    logger.info("=" * 60)
    
    # Получаем информацию о счете
    account_info = broker.get_account_info()
    if account_info:
        logger.info(f"Счет: equity={account_info.get('equity', 0):.2f}, cash={account_info.get('cash', 0):.2f}")
    
    # Получаем все позиции
    positions = broker.get_positions() or []
    
    if not positions:
        logger.info("✅ Нет открытых позиций для продажи")
        return True
    
    logger.info(f"📊 Найдено позиций: {len(positions)}")
    logger.info("")
    
    # Подтверждение
    print("\n" + "=" * 60)
    print("⚠️  ВНИМАНИЕ: Вы собираетесь продать ВСЕ позиции!")
    print("=" * 60)
    print(f"Количество позиций: {len(positions)}")
    print("\nСписок позиций для продажи:")
    for i, pos in enumerate(positions, 1):
        symbol = pos.get('symbol', '?')
        qty_lots = pos.get('qty_lots', pos.get('qty', 0)) or 0
        lot = pos.get('lot', 1) or 1
        current_price = pos.get('current_price', 0) or 0
        qty_shares = float(qty_lots) * float(lot)
        total_value = float(current_price) * float(qty_shares) if current_price > 0 else 0
        print(f"  {i}. {symbol}: {qty_lots} лот(ов) (лот={lot}) = {qty_shares:.0f} акций @ {current_price:.2f} = {total_value:.2f} RUB")
    
    print("\n" + "=" * 60)
    response = input("Продолжить продажу всех позиций? (yes/no): ").strip().lower()
    
    if response not in ['yes', 'y', 'да', 'д']:
        logger.info("❌ Продажа отменена пользователем")
        return False
    
    logger.info("")
    logger.info("🚀 Начинаем продажу...")
    logger.info("")
    
    # Продаем каждую позицию
    success_count = 0
    error_count = 0
    total_value = 0.0
    
    for i, pos in enumerate(positions, 1):
        try:
            symbol = pos.get('symbol', '?')
            qty_lots = int(pos.get('qty_lots', pos.get('qty', 0)) or 0)
            lot = int(pos.get('lot', 1) or 1)
            current_price = float(pos.get('current_price', 0) or 0)
            qty_shares = float(qty_lots) * float(lot)
            position_value = float(current_price) * float(qty_shares) if current_price > 0 else 0
            
            if qty_lots <= 0:
                logger.warning(f"⚠️  {i}. {symbol}: пропущено (qty_lots={qty_lots})")
                continue
            
            logger.info(f"📤 {i}. Продажа {symbol}: {qty_lots} лот(ов) (лот={lot}) = {qty_shares:.0f} акций @ {current_price:.2f} RUB")
            
            # Убеждаемся, что symbol является тикером, а не FIGI
            symbol_for_api = _ensure_ticker_not_figi(symbol, broker)
            
            # Получаем детали инструмента (для проверки)
            instrument = broker.get_instrument_details(symbol_for_api)
            if instrument:
                ticker = instrument.get('ticker', symbol_for_api)
                logger.info(f"   Инструмент: {ticker} (FIGI: {instrument.get('figi', 'N/A')})")
            
            # Размещаем заявку на продажу
            order = broker.place_market_order(symbol_for_api, qty_lots, 'sell')
            
            if order:
                order_id = order.get('order_id', 'N/A')
                order_status = order.get('status', 'unknown')
                logger.info(f"   ✅ Заявка размещена: order_id={order_id}, status={order_status}")
                success_count += 1
                total_value += position_value
            else:
                logger.error(f"   ❌ Не удалось разместить заявку на продажу")
                error_count += 1
            
            logger.info("")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при продаже {pos.get('symbol', '?')}: {e}", exc_info=True)
            error_count += 1
            logger.info("")
    
    # Итоги
    logger.info("=" * 60)
    logger.info("ИТОГИ ПРОДАЖИ")
    logger.info("=" * 60)
    logger.info(f"✅ Успешно размещено заявок: {success_count}")
    logger.info(f"❌ Ошибок: {error_count}")
    logger.info(f"💰 Примерная стоимость проданных позиций: {total_value:.2f} RUB")
    logger.info("")
    
    if success_count > 0:
        logger.info("✅ Заявки на продажу размещены успешно!")
        logger.info("   Проверьте статус заявок в портфеле или через брокера")
    
    return success_count > 0

if __name__ == "__main__":
    try:
        success = sell_all_positions()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n❌ Прервано пользователем")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)





