#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для принудительной покупки по одному лоту всех акций из списка SYMBOLS
Используется для проверки работоспособности бота и тестирования подключения к API
"""

import logging
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Fallback для старых версий Python
    from datetime import timezone as tz
    ZoneInfo = None

from broker_api import BrokerAPI
from config import TINVEST_SANDBOX, BROKER, SYMBOLS

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def _canon_symbol(sym: str) -> str:
    """Канонизация символа (как в main.py)"""
    s = str(sym or "").strip().upper()
    if not s:
        return s
    try:
        # Дополнительная нормализация для валютных пар
        currency_map = {
            "PLTRUBTOM": "PLTRUB_TOM",
            "PLDRUBTOM": "PLDRUB_TOM",
            "CNYRUBTOM": "CNYRUB_TOM",
            "GLDRUBTOM": "GLDRUB_TOM",
            "SLVRUBTOM": "SLVRUB_TOM",
        }
        if s in currency_map:
            return currency_map[s]
        return s
    except Exception:
        return s

def force_buy_all_symbols():
    """
    Принудительно купить по одному лоту всех акций из списка SYMBOLS
    
    Returns:
        bool: True если все доступные инструменты куплены, False если были критичные ошибки
    """
    now_utc = datetime.now(timezone.utc)
    try:
        if ZoneInfo:
            now_moscow = now_utc.astimezone(ZoneInfo("Europe/Moscow"))
        else:
            now_moscow = now_utc
    except Exception:
        now_moscow = now_utc
    
    logger.info("=" * 80)
    logger.info("СКРИПТ ПРИНУДИТЕЛЬНОЙ ПОКУПКИ ВСЕХ СИМВОЛОВ")
    logger.info("=" * 80)
    logger.info(f"Брокер: {BROKER}")
    logger.info(f"Sandbox: {TINVEST_SANDBOX}")
    logger.info(f"Текущее время UTC: {now_utc.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Текущее время МСК: {now_moscow.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Символов для покупки: {len(SYMBOLS)}")
    logger.info(f"Список символов: {', '.join(SYMBOLS[:10])}{'...' if len(SYMBOLS) > 10 else ''}")
    logger.info("")
    logger.info("⚠ ВНИМАНИЕ: Ошибка 30079 'Instrument is not available for trading' может возникать")
    logger.info("   если торговая сессия закрыта (вне торговых часов).")
    logger.info("   Это нормально и не является критичной ошибкой - такие инструменты будут пропущены.")
    logger.info("")
    
    # Инициализация брокера
    logger.info("Инициализация брокера...")
    try:
        broker = BrokerAPI(paper_trading=TINVEST_SANDBOX)
        
        if not broker.client:
            logger.error("❌ Не удалось инициализировать клиент брокера")
            return False
        
        logger.info("✓ Брокер инициализирован успешно")
        
        # Проверка подключения - получаем информацию о счете
        logger.info("Проверка подключения к API...")
        account_info = broker.get_account_info()
        if not account_info:
            logger.error("❌ Не удалось получить информацию о счете")
            return False
        
        equity = float(account_info.get("equity", 0) or 0)
        cash = float(account_info.get("cash", 0) or 0)
        currency = account_info.get("currency", "RUB")
        
        logger.info(f"✓ Подключение успешно")
        logger.info(f"  Equity: {equity:.2f} {currency}")
        logger.info(f"  Cash: {cash:.2f} {currency}")
        logger.info("")
        
        # Получаем текущие позиции
        logger.info("Получение текущих позиций...")
        positions = broker.get_positions() or []
        logger.info(f"Найдено открытых позиций: {len(positions)}")
        
        # Создаем словарь существующих позиций для проверки
        existing_positions = {}
        for pos in positions:
            pos_symbol = pos.get('symbol') or pos.get('ticker') or ''
            pos_figi = pos.get('figi', '')
            pos_symbol_canon = _canon_symbol(pos_symbol)
            if pos_symbol_canon:
                existing_positions[pos_symbol_canon] = pos
            if pos_figi:
                existing_positions[pos_figi] = pos
        
        logger.info("")
        
        # Покупка по одному лоту каждого символа
        logger.info("=" * 80)
        logger.info("НАЧИНАЕМ ПРИНУДИТЕЛЬНУЮ ПОКУПКУ")
        logger.info("=" * 80)
        logger.info("")
        
        success_count = 0
        skipped_existing_count = 0
        skipped_unavailable_count = 0
        error_count = 0
        
        for symbol in SYMBOLS:
            symbol_canon = _canon_symbol(symbol)
            
            logger.info(f"Обработка символа: {symbol} ({symbol_canon})")
            
            # Проверяем, есть ли уже позиция
            if symbol_canon in existing_positions or symbol in existing_positions:
                logger.info(f"  ⏭ Пропуск: позиция уже существует")
                skipped_existing_count += 1
                continue
            
            # Получаем информацию об инструменте
            try:
                instrument = broker.get_instrument_details(symbol_canon)
                if not instrument:
                    logger.warning(f"  ⚠ Инструмент {symbol_canon} не найден, пробуем оригинальный символ {symbol}")
                    instrument = broker.get_instrument_details(symbol)
                
                if not instrument:
                    logger.warning(f"  ⚠ Инструмент {symbol} не найден - пропускаем")
                    skipped_unavailable_count += 1
                    continue
                
                lot = int(instrument.get("lot", 1) or 1)
                trading_status = instrument.get("trading_status", "")
                api_trade_available = instrument.get("api_trade_available_flag", False)
                buy_available = instrument.get("buy_available_flag", False)
                
                logger.info(f"  Лот: {lot}")
                logger.info(f"  Статус торговли: {trading_status}")
                logger.info(f"  API торговля доступна: {api_trade_available}")
                logger.info(f"  Покупка доступна: {buy_available}")
                
                # ВАЖНО: В sandbox флаги trading_status могут быть False даже когда торговля возможна (особенно в ночное время)
                # Не блокируем покупки по этой проверке - полагаемся на реальную ошибку API (30079)
                # Логируем информацию для диагностики, но продолжаем попытку размещения ордера
                status_str = str(trading_status).upper()
                is_not_available_by_flags = (
                    (trading_status and "NOT_AVAILABLE" in status_str) or
                    (trading_status and str(trading_status) == "0") or
                    not api_trade_available or
                    not buy_available
                )
                
                if is_not_available_by_flags:
                    logger.info(f"  ℹ Инструмент имеет флаги (статус: {trading_status}, api: {api_trade_available}, buy: {buy_available}) - продолжим попытку размещения ордера")
                
                # Покупаем 1 лот
                logger.info(f"  📈 Размещение ордера: BUY 1 лот {symbol_canon}...")
                
                try:
                    order_result = broker.place_market_order(symbol_canon, 1, 'buy')
                    
                    if order_result:
                        order_id = order_result.get('order_id', 'N/A')
                        status = order_result.get('status', 'unknown')
                        logger.info(f"  ✓ Ордер размещен успешно!")
                        logger.info(f"    Order ID: {order_id}")
                        logger.info(f"    Status: {status}")
                        success_count += 1
                    else:
                        # Проверяем, была ли это ошибка "инструмент недоступен" (30079)
                        # Такие ошибки уже логируются как WARNING в tinvest_api.py
                        logger.warning(f"  ⚠ Ордер не размещен - инструмент может быть недоступен для торговли")
                        skipped_unavailable_count += 1
                        
                except Exception as e:
                    error_msg = str(e).lower()
                    # Проверяем код ошибки 30079 - это не критичная ошибка
                    if '30079' in error_msg or 'instrument is not available' in error_msg:
                        logger.warning(f"  ⚠ Инструмент недоступен для торговли (ошибка 30079) - пропускаем")
                        skipped_unavailable_count += 1
                    else:
                        logger.error(f"  ❌ Ошибка при размещении ордера: {e}", exc_info=True)
                        error_count += 1
            
            except Exception as e:
                logger.error(f"  ❌ Ошибка при обработке символа {symbol}: {e}", exc_info=True)
                error_count += 1
            
            logger.info("")
        
        # Итоговая статистика
        logger.info("=" * 80)
        logger.info("РЕЗУЛЬТАТЫ ПРИНУДИТЕЛЬНОЙ ПОКУПКИ:")
        logger.info(f"  Всего символов: {len(SYMBOLS)}")
        logger.info(f"  ✓ Успешно куплено: {success_count}")
        logger.info(f"  ⏭ Пропущено (уже есть позиция): {skipped_existing_count}")
        logger.info(f"  ⚠ Пропущено (недоступен для торговли): {skipped_unavailable_count}")
        logger.info(f"  ❌ Ошибок (критичные): {error_count}")
        logger.info("")
        if skipped_unavailable_count > 0:
            logger.info("ℹ  ПРИМЕЧАНИЕ: Инструменты, недоступные для торговли (включая ошибку 30079),")
            logger.info("   обычно недоступны из-за закрытой торговой сессии или ограничений sandbox.")
            logger.info("   Это нормально и не является ошибкой - попробуйте запустить в торговые часы.")
        logger.info("=" * 80)
        
        # Считаем успешным, если нет критичных ошибок (ошибки 30079 не критичные)
        return error_count == 0
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    logger.info("")
    logger.info("=" * 80)
    logger.info("ПРОВЕРКА РАБОТОСПОСОБНОСТИ БОТА И ПРИНУДИТЕЛЬНАЯ ПОКУПКА")
    logger.info("=" * 80)
    logger.info("")
    
    # Подтверждение
    response = input("Вы уверены, что хотите купить по 1 лоту всех символов из SYMBOLS? (yes/no): ")
    if response.lower() not in ['yes', 'y', 'да', 'д']:
        logger.info("Операция отменена пользователем")
        sys.exit(0)
    
    logger.info("")
    success = force_buy_all_symbols()
    
    if success:
        logger.info("")
        logger.info("✓ Операция завершена успешно (все доступные инструменты обработаны)")
        sys.exit(0)
    else:
        logger.error("")
        logger.error("✗ Операция завершена с ошибками")
        sys.exit(1)

"""
Скрипт для принудительной покупки по одному лоту всех акций из списка SYMBOLS
Используется для проверки работоспособности бота и тестирования подключения к API
"""

import logging
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Fallback для старых версий Python
    from datetime import timezone as tz
    ZoneInfo = None

from broker_api import BrokerAPI
from config import TINVEST_SANDBOX, BROKER, SYMBOLS

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def _canon_symbol(sym: str) -> str:
    """Канонизация символа (как в main.py)"""
    s = str(sym or "").strip().upper()
    if not s:
        return s
    try:
        # Дополнительная нормализация для валютных пар
        currency_map = {
            "PLTRUBTOM": "PLTRUB_TOM",
            "PLDRUBTOM": "PLDRUB_TOM",
            "CNYRUBTOM": "CNYRUB_TOM",
            "GLDRUBTOM": "GLDRUB_TOM",
            "SLVRUBTOM": "SLVRUB_TOM",
        }
        if s in currency_map:
            return currency_map[s]
        return s
    except Exception:
        return s

def force_buy_all_symbols():
    """
    Принудительно купить по одному лоту всех акций из списка SYMBOLS
    
    Returns:
        bool: True если все доступные инструменты куплены, False если были критичные ошибки
    """
    now_utc = datetime.now(timezone.utc)
    try:
        if ZoneInfo:
            now_moscow = now_utc.astimezone(ZoneInfo("Europe/Moscow"))
        else:
            now_moscow = now_utc
    except Exception:
        now_moscow = now_utc
    
    logger.info("=" * 80)
    logger.info("СКРИПТ ПРИНУДИТЕЛЬНОЙ ПОКУПКИ ВСЕХ СИМВОЛОВ")
    logger.info("=" * 80)
    logger.info(f"Брокер: {BROKER}")
    logger.info(f"Sandbox: {TINVEST_SANDBOX}")
    logger.info(f"Текущее время UTC: {now_utc.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Текущее время МСК: {now_moscow.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Символов для покупки: {len(SYMBOLS)}")
    logger.info(f"Список символов: {', '.join(SYMBOLS[:10])}{'...' if len(SYMBOLS) > 10 else ''}")
    logger.info("")
    logger.info("⚠ ВНИМАНИЕ: Ошибка 30079 'Instrument is not available for trading' может возникать")
    logger.info("   если торговая сессия закрыта (вне торговых часов).")
    logger.info("   Это нормально и не является критичной ошибкой - такие инструменты будут пропущены.")
    logger.info("")
    
    # Инициализация брокера
    logger.info("Инициализация брокера...")
    try:
        broker = BrokerAPI(paper_trading=TINVEST_SANDBOX)
        
        if not broker.client:
            logger.error("❌ Не удалось инициализировать клиент брокера")
            return False
        
        logger.info("✓ Брокер инициализирован успешно")
        
        # Проверка подключения - получаем информацию о счете
        logger.info("Проверка подключения к API...")
        account_info = broker.get_account_info()
        if not account_info:
            logger.error("❌ Не удалось получить информацию о счете")
            return False
        
        equity = float(account_info.get("equity", 0) or 0)
        cash = float(account_info.get("cash", 0) or 0)
        currency = account_info.get("currency", "RUB")
        
        logger.info(f"✓ Подключение успешно")
        logger.info(f"  Equity: {equity:.2f} {currency}")
        logger.info(f"  Cash: {cash:.2f} {currency}")
        logger.info("")
        
        # Получаем текущие позиции
        logger.info("Получение текущих позиций...")
        positions = broker.get_positions() or []
        logger.info(f"Найдено открытых позиций: {len(positions)}")
        
        # Создаем словарь существующих позиций для проверки
        existing_positions = {}
        for pos in positions:
            pos_symbol = pos.get('symbol') or pos.get('ticker') or ''
            pos_figi = pos.get('figi', '')
            pos_symbol_canon = _canon_symbol(pos_symbol)
            if pos_symbol_canon:
                existing_positions[pos_symbol_canon] = pos
            if pos_figi:
                existing_positions[pos_figi] = pos
        
        logger.info("")
        
        # Покупка по одному лоту каждого символа
        logger.info("=" * 80)
        logger.info("НАЧИНАЕМ ПРИНУДИТЕЛЬНУЮ ПОКУПКУ")
        logger.info("=" * 80)
        logger.info("")
        
        success_count = 0
        skipped_existing_count = 0
        skipped_unavailable_count = 0
        error_count = 0
        
        for symbol in SYMBOLS:
            symbol_canon = _canon_symbol(symbol)
            
            logger.info(f"Обработка символа: {symbol} ({symbol_canon})")
            
            # Проверяем, есть ли уже позиция
            if symbol_canon in existing_positions or symbol in existing_positions:
                logger.info(f"  ⏭ Пропуск: позиция уже существует")
                skipped_existing_count += 1
                continue
            
            # Получаем информацию об инструменте
            try:
                instrument = broker.get_instrument_details(symbol_canon)
                if not instrument:
                    logger.warning(f"  ⚠ Инструмент {symbol_canon} не найден, пробуем оригинальный символ {symbol}")
                    instrument = broker.get_instrument_details(symbol)
                
                if not instrument:
                    logger.warning(f"  ⚠ Инструмент {symbol} не найден - пропускаем")
                    skipped_unavailable_count += 1
                    continue
                
                lot = int(instrument.get("lot", 1) or 1)
                trading_status = instrument.get("trading_status", "")
                api_trade_available = instrument.get("api_trade_available_flag", False)
                buy_available = instrument.get("buy_available_flag", False)
                
                logger.info(f"  Лот: {lot}")
                logger.info(f"  Статус торговли: {trading_status}")
                logger.info(f"  API торговля доступна: {api_trade_available}")
                logger.info(f"  Покупка доступна: {buy_available}")
                
                # ВАЖНО: В sandbox флаги trading_status могут быть False даже когда торговля возможна (особенно в ночное время)
                # Не блокируем покупки по этой проверке - полагаемся на реальную ошибку API (30079)
                # Логируем информацию для диагностики, но продолжаем попытку размещения ордера
                status_str = str(trading_status).upper()
                is_not_available_by_flags = (
                    (trading_status and "NOT_AVAILABLE" in status_str) or
                    (trading_status and str(trading_status) == "0") or
                    not api_trade_available or
                    not buy_available
                )
                
                if is_not_available_by_flags:
                    logger.info(f"  ℹ Инструмент имеет флаги (статус: {trading_status}, api: {api_trade_available}, buy: {buy_available}) - продолжим попытку размещения ордера")
                
                # Покупаем 1 лот
                logger.info(f"  📈 Размещение ордера: BUY 1 лот {symbol_canon}...")
                
                try:
                    order_result = broker.place_market_order(symbol_canon, 1, 'buy')
                    
                    if order_result:
                        order_id = order_result.get('order_id', 'N/A')
                        status = order_result.get('status', 'unknown')
                        logger.info(f"  ✓ Ордер размещен успешно!")
                        logger.info(f"    Order ID: {order_id}")
                        logger.info(f"    Status: {status}")
                        success_count += 1
                    else:
                        # Проверяем, была ли это ошибка "инструмент недоступен" (30079)
                        # Такие ошибки уже логируются как WARNING в tinvest_api.py
                        logger.warning(f"  ⚠ Ордер не размещен - инструмент может быть недоступен для торговли")
                        skipped_unavailable_count += 1
                        
                except Exception as e:
                    error_msg = str(e).lower()
                    # Проверяем код ошибки 30079 - это не критичная ошибка
                    if '30079' in error_msg or 'instrument is not available' in error_msg:
                        logger.warning(f"  ⚠ Инструмент недоступен для торговли (ошибка 30079) - пропускаем")
                        skipped_unavailable_count += 1
                    else:
                        logger.error(f"  ❌ Ошибка при размещении ордера: {e}", exc_info=True)
                        error_count += 1
            
            except Exception as e:
                logger.error(f"  ❌ Ошибка при обработке символа {symbol}: {e}", exc_info=True)
                error_count += 1
            
            logger.info("")
        
        # Итоговая статистика
        logger.info("=" * 80)
        logger.info("РЕЗУЛЬТАТЫ ПРИНУДИТЕЛЬНОЙ ПОКУПКИ:")
        logger.info(f"  Всего символов: {len(SYMBOLS)}")
        logger.info(f"  ✓ Успешно куплено: {success_count}")
        logger.info(f"  ⏭ Пропущено (уже есть позиция): {skipped_existing_count}")
        logger.info(f"  ⚠ Пропущено (недоступен для торговли): {skipped_unavailable_count}")
        logger.info(f"  ❌ Ошибок (критичные): {error_count}")
        logger.info("")
        if skipped_unavailable_count > 0:
            logger.info("ℹ  ПРИМЕЧАНИЕ: Инструменты, недоступные для торговли (включая ошибку 30079),")
            logger.info("   обычно недоступны из-за закрытой торговой сессии или ограничений sandbox.")
            logger.info("   Это нормально и не является ошибкой - попробуйте запустить в торговые часы.")
        logger.info("=" * 80)
        
        # Считаем успешным, если нет критичных ошибок (ошибки 30079 не критичные)
        return error_count == 0
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    logger.info("")
    logger.info("=" * 80)
    logger.info("ПРОВЕРКА РАБОТОСПОСОБНОСТИ БОТА И ПРИНУДИТЕЛЬНАЯ ПОКУПКА")
    logger.info("=" * 80)
    logger.info("")
    
    # Подтверждение
    response = input("Вы уверены, что хотите купить по 1 лоту всех символов из SYMBOLS? (yes/no): ")
    if response.lower() not in ['yes', 'y', 'да', 'д']:
        logger.info("Операция отменена пользователем")
        sys.exit(0)
    
    logger.info("")
    success = force_buy_all_symbols()
    
    if success:
        logger.info("")
        logger.info("✓ Операция завершена успешно (все доступные инструменты обработаны)")
        sys.exit(0)
    else:
        logger.error("")
        logger.error("✗ Операция завершена с ошибками")
        sys.exit(1)

"""
Скрипт для принудительной покупки по одному лоту всех акций из списка SYMBOLS
Используется для проверки работоспособности бота и тестирования подключения к API
"""

import logging
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Fallback для старых версий Python
    from datetime import timezone as tz
    ZoneInfo = None

from broker_api import BrokerAPI
from config import TINVEST_SANDBOX, BROKER, SYMBOLS

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def _canon_symbol(sym: str) -> str:
    """Канонизация символа (как в main.py)"""
    s = str(sym or "").strip().upper()
    if not s:
        return s
    try:
        # Дополнительная нормализация для валютных пар
        currency_map = {
            "PLTRUBTOM": "PLTRUB_TOM",
            "PLDRUBTOM": "PLDRUB_TOM",
            "CNYRUBTOM": "CNYRUB_TOM",
            "GLDRUBTOM": "GLDRUB_TOM",
            "SLVRUBTOM": "SLVRUB_TOM",
        }
        if s in currency_map:
            return currency_map[s]
        return s
    except Exception:
        return s

def force_buy_all_symbols():
    """
    Принудительно купить по одному лоту всех акций из списка SYMBOLS
    
    Returns:
        bool: True если все доступные инструменты куплены, False если были критичные ошибки
    """
    now_utc = datetime.now(timezone.utc)
    try:
        if ZoneInfo:
            now_moscow = now_utc.astimezone(ZoneInfo("Europe/Moscow"))
        else:
            now_moscow = now_utc
    except Exception:
        now_moscow = now_utc
    
    logger.info("=" * 80)
    logger.info("СКРИПТ ПРИНУДИТЕЛЬНОЙ ПОКУПКИ ВСЕХ СИМВОЛОВ")
    logger.info("=" * 80)
    logger.info(f"Брокер: {BROKER}")
    logger.info(f"Sandbox: {TINVEST_SANDBOX}")
    logger.info(f"Текущее время UTC: {now_utc.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Текущее время МСК: {now_moscow.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Символов для покупки: {len(SYMBOLS)}")
    logger.info(f"Список символов: {', '.join(SYMBOLS[:10])}{'...' if len(SYMBOLS) > 10 else ''}")
    logger.info("")
    logger.info("⚠ ВНИМАНИЕ: Ошибка 30079 'Instrument is not available for trading' может возникать")
    logger.info("   если торговая сессия закрыта (вне торговых часов).")
    logger.info("   Это нормально и не является критичной ошибкой - такие инструменты будут пропущены.")
    logger.info("")
    
    # Инициализация брокера
    logger.info("Инициализация брокера...")
    try:
        broker = BrokerAPI(paper_trading=TINVEST_SANDBOX)
        
        if not broker.client:
            logger.error("❌ Не удалось инициализировать клиент брокера")
            return False
        
        logger.info("✓ Брокер инициализирован успешно")
        
        # Проверка подключения - получаем информацию о счете
        logger.info("Проверка подключения к API...")
        account_info = broker.get_account_info()
        if not account_info:
            logger.error("❌ Не удалось получить информацию о счете")
            return False
        
        equity = float(account_info.get("equity", 0) or 0)
        cash = float(account_info.get("cash", 0) or 0)
        currency = account_info.get("currency", "RUB")
        
        logger.info(f"✓ Подключение успешно")
        logger.info(f"  Equity: {equity:.2f} {currency}")
        logger.info(f"  Cash: {cash:.2f} {currency}")
        logger.info("")
        
        # Получаем текущие позиции
        logger.info("Получение текущих позиций...")
        positions = broker.get_positions() or []
        logger.info(f"Найдено открытых позиций: {len(positions)}")
        
        # Создаем словарь существующих позиций для проверки
        existing_positions = {}
        for pos in positions:
            pos_symbol = pos.get('symbol') or pos.get('ticker') or ''
            pos_figi = pos.get('figi', '')
            pos_symbol_canon = _canon_symbol(pos_symbol)
            if pos_symbol_canon:
                existing_positions[pos_symbol_canon] = pos
            if pos_figi:
                existing_positions[pos_figi] = pos
        
        logger.info("")
        
        # Покупка по одному лоту каждого символа
        logger.info("=" * 80)
        logger.info("НАЧИНАЕМ ПРИНУДИТЕЛЬНУЮ ПОКУПКУ")
        logger.info("=" * 80)
        logger.info("")
        
        success_count = 0
        skipped_existing_count = 0
        skipped_unavailable_count = 0
        error_count = 0
        
        for symbol in SYMBOLS:
            symbol_canon = _canon_symbol(symbol)
            
            logger.info(f"Обработка символа: {symbol} ({symbol_canon})")
            
            # Проверяем, есть ли уже позиция
            if symbol_canon in existing_positions or symbol in existing_positions:
                logger.info(f"  ⏭ Пропуск: позиция уже существует")
                skipped_existing_count += 1
                continue
            
            # Получаем информацию об инструменте
            try:
                instrument = broker.get_instrument_details(symbol_canon)
                if not instrument:
                    logger.warning(f"  ⚠ Инструмент {symbol_canon} не найден, пробуем оригинальный символ {symbol}")
                    instrument = broker.get_instrument_details(symbol)
                
                if not instrument:
                    logger.warning(f"  ⚠ Инструмент {symbol} не найден - пропускаем")
                    skipped_unavailable_count += 1
                    continue
                
                lot = int(instrument.get("lot", 1) or 1)
                trading_status = instrument.get("trading_status", "")
                api_trade_available = instrument.get("api_trade_available_flag", False)
                buy_available = instrument.get("buy_available_flag", False)
                
                logger.info(f"  Лот: {lot}")
                logger.info(f"  Статус торговли: {trading_status}")
                logger.info(f"  API торговля доступна: {api_trade_available}")
                logger.info(f"  Покупка доступна: {buy_available}")
                
                # ВАЖНО: В sandbox флаги trading_status могут быть False даже когда торговля возможна (особенно в ночное время)
                # Не блокируем покупки по этой проверке - полагаемся на реальную ошибку API (30079)
                # Логируем информацию для диагностики, но продолжаем попытку размещения ордера
                status_str = str(trading_status).upper()
                is_not_available_by_flags = (
                    (trading_status and "NOT_AVAILABLE" in status_str) or
                    (trading_status and str(trading_status) == "0") or
                    not api_trade_available or
                    not buy_available
                )
                
                if is_not_available_by_flags:
                    logger.info(f"  ℹ Инструмент имеет флаги (статус: {trading_status}, api: {api_trade_available}, buy: {buy_available}) - продолжим попытку размещения ордера")
                
                # Покупаем 1 лот
                logger.info(f"  📈 Размещение ордера: BUY 1 лот {symbol_canon}...")
                
                try:
                    order_result = broker.place_market_order(symbol_canon, 1, 'buy')
                    
                    if order_result:
                        order_id = order_result.get('order_id', 'N/A')
                        status = order_result.get('status', 'unknown')
                        logger.info(f"  ✓ Ордер размещен успешно!")
                        logger.info(f"    Order ID: {order_id}")
                        logger.info(f"    Status: {status}")
                        success_count += 1
                    else:
                        # Проверяем, была ли это ошибка "инструмент недоступен" (30079)
                        # Такие ошибки уже логируются как WARNING в tinvest_api.py
                        logger.warning(f"  ⚠ Ордер не размещен - инструмент может быть недоступен для торговли")
                        skipped_unavailable_count += 1
                        
                except Exception as e:
                    error_msg = str(e).lower()
                    # Проверяем код ошибки 30079 - это не критичная ошибка
                    if '30079' in error_msg or 'instrument is not available' in error_msg:
                        logger.warning(f"  ⚠ Инструмент недоступен для торговли (ошибка 30079) - пропускаем")
                        skipped_unavailable_count += 1
                    else:
                        logger.error(f"  ❌ Ошибка при размещении ордера: {e}", exc_info=True)
                        error_count += 1
            
            except Exception as e:
                logger.error(f"  ❌ Ошибка при обработке символа {symbol}: {e}", exc_info=True)
                error_count += 1
            
            logger.info("")
        
        # Итоговая статистика
        logger.info("=" * 80)
        logger.info("РЕЗУЛЬТАТЫ ПРИНУДИТЕЛЬНОЙ ПОКУПКИ:")
        logger.info(f"  Всего символов: {len(SYMBOLS)}")
        logger.info(f"  ✓ Успешно куплено: {success_count}")
        logger.info(f"  ⏭ Пропущено (уже есть позиция): {skipped_existing_count}")
        logger.info(f"  ⚠ Пропущено (недоступен для торговли): {skipped_unavailable_count}")
        logger.info(f"  ❌ Ошибок (критичные): {error_count}")
        logger.info("")
        if skipped_unavailable_count > 0:
            logger.info("ℹ  ПРИМЕЧАНИЕ: Инструменты, недоступные для торговли (включая ошибку 30079),")
            logger.info("   обычно недоступны из-за закрытой торговой сессии или ограничений sandbox.")
            logger.info("   Это нормально и не является ошибкой - попробуйте запустить в торговые часы.")
        logger.info("=" * 80)
        
        # Считаем успешным, если нет критичных ошибок (ошибки 30079 не критичные)
        return error_count == 0
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    logger.info("")
    logger.info("=" * 80)
    logger.info("ПРОВЕРКА РАБОТОСПОСОБНОСТИ БОТА И ПРИНУДИТЕЛЬНАЯ ПОКУПКА")
    logger.info("=" * 80)
    logger.info("")
    
    # Подтверждение
    response = input("Вы уверены, что хотите купить по 1 лоту всех символов из SYMBOLS? (yes/no): ")
    if response.lower() not in ['yes', 'y', 'да', 'д']:
        logger.info("Операция отменена пользователем")
        sys.exit(0)
    
    logger.info("")
    success = force_buy_all_symbols()
    
    if success:
        logger.info("")
        logger.info("✓ Операция завершена успешно (все доступные инструменты обработаны)")
        sys.exit(0)
    else:
        logger.error("")
        logger.error("✗ Операция завершена с ошибками")
        sys.exit(1)
