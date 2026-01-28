#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для проверки работоспособности бота
Проверяет подключение к API, доступность инструментов и состояние счета
"""

import logging
import sys
from datetime import datetime, timezone

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

def check_bot_health():
    """
    Проверка работоспособности бота
    
    Returns:
        bool: True если все проверки пройдены, False если есть проблемы
    """
    logger.info("=" * 80)
    logger.info("ПРОВЕРКА РАБОТОСПОСОБНОСТИ БОТА")
    logger.info("=" * 80)
    logger.info("")
    
    all_checks_passed = True
    
    # 1. Проверка конфигурации
    logger.info("1. Проверка конфигурации...")
    logger.info(f"   Брокер: {BROKER}")
    logger.info(f"   Sandbox: {TINVEST_SANDBOX}")
    logger.info(f"   Символов в списке: {len(SYMBOLS)}")
    if len(SYMBOLS) > 0:
        logger.info(f"   Первые 5 символов: {', '.join(SYMBOLS[:5])}")
    logger.info("   ✓ Конфигурация загружена")
    logger.info("")
    
    # 2. Инициализация брокера
    logger.info("2. Инициализация брокера...")
    try:
        broker = BrokerAPI(paper_trading=TINVEST_SANDBOX)
        
        if not broker.client:
            logger.error("   ❌ Не удалось инициализировать клиент брокера")
            return False
        
        logger.info("   ✓ Брокер инициализирован успешно")
        logger.info("")
    except Exception as e:
        logger.error(f"   ❌ Ошибка инициализации брокера: {e}", exc_info=True)
        return False
    
    # 3. Проверка подключения к API
    logger.info("3. Проверка подключения к API...")
    try:
        account_info = broker.get_account_info()
        if not account_info:
            logger.error("   ❌ Не удалось получить информацию о счете")
            all_checks_passed = False
        else:
            equity = float(account_info.get("equity", 0) or 0)
            cash = float(account_info.get("cash", 0) or 0)
            currency = account_info.get("currency", "RUB")
            
            logger.info(f"   ✓ Подключение успешно")
            logger.info(f"   Equity: {equity:.2f} {currency}")
            logger.info(f"   Cash: {cash:.2f} {currency}")
            
            if equity <= 0:
                logger.warning("   ⚠ Equity равна нулю или отрицательна")
                all_checks_passed = False
            if cash <= 0:
                logger.warning("   ⚠ Cash равна нулю или отрицательна")
        logger.info("")
    except Exception as e:
        logger.error(f"   ❌ Ошибка при проверке подключения: {e}", exc_info=True)
        all_checks_passed = False
        logger.info("")
    
    # 4. Проверка получения позиций
    logger.info("4. Проверка получения позиций...")
    try:
        positions = broker.get_positions() or []
        logger.info(f"   ✓ Получено позиций: {len(positions)}")
        if len(positions) > 0:
            logger.info(f"   Примеры позиций:")
            for pos in positions[:3]:
                pos_symbol = pos.get('symbol') or pos.get('ticker') or 'N/A'
                pos_qty = pos.get('qty_lots', pos.get('qty', 0)) or 0
                logger.info(f"     - {pos_symbol}: {pos_qty} лотов")
        logger.info("")
    except Exception as e:
        logger.error(f"   ❌ Ошибка при получении позиций: {e}", exc_info=True)
        all_checks_passed = False
        logger.info("")
    
    # 5. Проверка доступности инструментов (первые 5 символов)
    logger.info("5. Проверка доступности инструментов (первые 5 символов)...")
    available_count = 0
    unavailable_count = 0
    
    for symbol in SYMBOLS[:5]:
        try:
            instrument = broker.get_instrument_details(symbol)
            if instrument:
                trading_status = instrument.get("trading_status", "")
                api_trade_available = instrument.get("api_trade_available_flag", False)
                buy_available = instrument.get("buy_available_flag", False)
                
                if api_trade_available and buy_available:
                    logger.info(f"   ✓ {symbol}: доступен для торговли")
                    available_count += 1
                else:
                    logger.warning(f"   ⚠ {symbol}: недоступен для торговли (status: {trading_status}, api: {api_trade_available}, buy: {buy_available})")
                    unavailable_count += 1
            else:
                logger.warning(f"   ⚠ {symbol}: инструмент не найден")
                unavailable_count += 1
        except Exception as e:
            logger.warning(f"   ⚠ {symbol}: ошибка при проверке - {e}")
            unavailable_count += 1
    
    logger.info(f"   Доступно: {available_count}, недоступно: {unavailable_count}")
    logger.info("")
    
    # Итоговый результат
    logger.info("=" * 80)
    if all_checks_passed and available_count > 0:
        logger.info("✓ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ - БОТ РАБОТОСПОСОБЕН")
    elif all_checks_passed:
        logger.warning("⚠ БОТ РАБОТОСПОСОБЕН, НО НЕКОТОРЫЕ ИНСТРУМЕНТЫ НЕДОСТУПНЫ")
    else:
        logger.error("❌ ОБНАРУЖЕНЫ ПРОБЛЕМЫ - ТРЕБУЕТСЯ ИСПРАВЛЕНИЕ")
    logger.info("=" * 80)
    
    return all_checks_passed and available_count > 0

if __name__ == "__main__":
    try:
        success = check_bot_health()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)

# -*- coding: utf-8 -*-
"""
Скрипт для проверки работоспособности бота
Проверяет подключение к API, доступность инструментов и состояние счета
"""

import logging
import sys
from datetime import datetime, timezone

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

def check_bot_health():
    """
    Проверка работоспособности бота
    
    Returns:
        bool: True если все проверки пройдены, False если есть проблемы
    """
    logger.info("=" * 80)
    logger.info("ПРОВЕРКА РАБОТОСПОСОБНОСТИ БОТА")
    logger.info("=" * 80)
    logger.info("")
    
    all_checks_passed = True
    
    # 1. Проверка конфигурации
    logger.info("1. Проверка конфигурации...")
    logger.info(f"   Брокер: {BROKER}")
    logger.info(f"   Sandbox: {TINVEST_SANDBOX}")
    logger.info(f"   Символов в списке: {len(SYMBOLS)}")
    if len(SYMBOLS) > 0:
        logger.info(f"   Первые 5 символов: {', '.join(SYMBOLS[:5])}")
    logger.info("   ✓ Конфигурация загружена")
    logger.info("")
    
    # 2. Инициализация брокера
    logger.info("2. Инициализация брокера...")
    try:
        broker = BrokerAPI(paper_trading=TINVEST_SANDBOX)
        
        if not broker.client:
            logger.error("   ❌ Не удалось инициализировать клиент брокера")
            return False
        
        logger.info("   ✓ Брокер инициализирован успешно")
        logger.info("")
    except Exception as e:
        logger.error(f"   ❌ Ошибка инициализации брокера: {e}", exc_info=True)
        return False
    
    # 3. Проверка подключения к API
    logger.info("3. Проверка подключения к API...")
    try:
        account_info = broker.get_account_info()
        if not account_info:
            logger.error("   ❌ Не удалось получить информацию о счете")
            all_checks_passed = False
        else:
            equity = float(account_info.get("equity", 0) or 0)
            cash = float(account_info.get("cash", 0) or 0)
            currency = account_info.get("currency", "RUB")
            
            logger.info(f"   ✓ Подключение успешно")
            logger.info(f"   Equity: {equity:.2f} {currency}")
            logger.info(f"   Cash: {cash:.2f} {currency}")
            
            if equity <= 0:
                logger.warning("   ⚠ Equity равна нулю или отрицательна")
                all_checks_passed = False
            if cash <= 0:
                logger.warning("   ⚠ Cash равна нулю или отрицательна")
        logger.info("")
    except Exception as e:
        logger.error(f"   ❌ Ошибка при проверке подключения: {e}", exc_info=True)
        all_checks_passed = False
        logger.info("")
    
    # 4. Проверка получения позиций
    logger.info("4. Проверка получения позиций...")
    try:
        positions = broker.get_positions() or []
        logger.info(f"   ✓ Получено позиций: {len(positions)}")
        if len(positions) > 0:
            logger.info(f"   Примеры позиций:")
            for pos in positions[:3]:
                pos_symbol = pos.get('symbol') or pos.get('ticker') or 'N/A'
                pos_qty = pos.get('qty_lots', pos.get('qty', 0)) or 0
                logger.info(f"     - {pos_symbol}: {pos_qty} лотов")
        logger.info("")
    except Exception as e:
        logger.error(f"   ❌ Ошибка при получении позиций: {e}", exc_info=True)
        all_checks_passed = False
        logger.info("")
    
    # 5. Проверка доступности инструментов (первые 5 символов)
    logger.info("5. Проверка доступности инструментов (первые 5 символов)...")
    available_count = 0
    unavailable_count = 0
    
    for symbol in SYMBOLS[:5]:
        try:
            instrument = broker.get_instrument_details(symbol)
            if instrument:
                trading_status = instrument.get("trading_status", "")
                api_trade_available = instrument.get("api_trade_available_flag", False)
                buy_available = instrument.get("buy_available_flag", False)
                
                if api_trade_available and buy_available:
                    logger.info(f"   ✓ {symbol}: доступен для торговли")
                    available_count += 1
                else:
                    logger.warning(f"   ⚠ {symbol}: недоступен для торговли (status: {trading_status}, api: {api_trade_available}, buy: {buy_available})")
                    unavailable_count += 1
            else:
                logger.warning(f"   ⚠ {symbol}: инструмент не найден")
                unavailable_count += 1
        except Exception as e:
            logger.warning(f"   ⚠ {symbol}: ошибка при проверке - {e}")
            unavailable_count += 1
    
    logger.info(f"   Доступно: {available_count}, недоступно: {unavailable_count}")
    logger.info("")
    
    # Итоговый результат
    logger.info("=" * 80)
    if all_checks_passed and available_count > 0:
        logger.info("✓ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ - БОТ РАБОТОСПОСОБЕН")
    elif all_checks_passed:
        logger.warning("⚠ БОТ РАБОТОСПОСОБЕН, НО НЕКОТОРЫЕ ИНСТРУМЕНТЫ НЕДОСТУПНЫ")
    else:
        logger.error("❌ ОБНАРУЖЕНЫ ПРОБЛЕМЫ - ТРЕБУЕТСЯ ИСПРАВЛЕНИЕ")
    logger.info("=" * 80)
    
    return all_checks_passed and available_count > 0

if __name__ == "__main__":
    try:
        success = check_bot_health()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)

# -*- coding: utf-8 -*-
"""
Скрипт для проверки работоспособности бота
Проверяет подключение к API, доступность инструментов и состояние счета
"""

import logging
import sys
from datetime import datetime, timezone

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

def check_bot_health():
    """
    Проверка работоспособности бота
    
    Returns:
        bool: True если все проверки пройдены, False если есть проблемы
    """
    logger.info("=" * 80)
    logger.info("ПРОВЕРКА РАБОТОСПОСОБНОСТИ БОТА")
    logger.info("=" * 80)
    logger.info("")
    
    all_checks_passed = True
    
    # 1. Проверка конфигурации
    logger.info("1. Проверка конфигурации...")
    logger.info(f"   Брокер: {BROKER}")
    logger.info(f"   Sandbox: {TINVEST_SANDBOX}")
    logger.info(f"   Символов в списке: {len(SYMBOLS)}")
    if len(SYMBOLS) > 0:
        logger.info(f"   Первые 5 символов: {', '.join(SYMBOLS[:5])}")
    logger.info("   ✓ Конфигурация загружена")
    logger.info("")
    
    # 2. Инициализация брокера
    logger.info("2. Инициализация брокера...")
    try:
        broker = BrokerAPI(paper_trading=TINVEST_SANDBOX)
        
        if not broker.client:
            logger.error("   ❌ Не удалось инициализировать клиент брокера")
            return False
        
        logger.info("   ✓ Брокер инициализирован успешно")
        logger.info("")
    except Exception as e:
        logger.error(f"   ❌ Ошибка инициализации брокера: {e}", exc_info=True)
        return False
    
    # 3. Проверка подключения к API
    logger.info("3. Проверка подключения к API...")
    try:
        account_info = broker.get_account_info()
        if not account_info:
            logger.error("   ❌ Не удалось получить информацию о счете")
            all_checks_passed = False
        else:
            equity = float(account_info.get("equity", 0) or 0)
            cash = float(account_info.get("cash", 0) or 0)
            currency = account_info.get("currency", "RUB")
            
            logger.info(f"   ✓ Подключение успешно")
            logger.info(f"   Equity: {equity:.2f} {currency}")
            logger.info(f"   Cash: {cash:.2f} {currency}")
            
            if equity <= 0:
                logger.warning("   ⚠ Equity равна нулю или отрицательна")
                all_checks_passed = False
            if cash <= 0:
                logger.warning("   ⚠ Cash равна нулю или отрицательна")
        logger.info("")
    except Exception as e:
        logger.error(f"   ❌ Ошибка при проверке подключения: {e}", exc_info=True)
        all_checks_passed = False
        logger.info("")
    
    # 4. Проверка получения позиций
    logger.info("4. Проверка получения позиций...")
    try:
        positions = broker.get_positions() or []
        logger.info(f"   ✓ Получено позиций: {len(positions)}")
        if len(positions) > 0:
            logger.info(f"   Примеры позиций:")
            for pos in positions[:3]:
                pos_symbol = pos.get('symbol') or pos.get('ticker') or 'N/A'
                pos_qty = pos.get('qty_lots', pos.get('qty', 0)) or 0
                logger.info(f"     - {pos_symbol}: {pos_qty} лотов")
        logger.info("")
    except Exception as e:
        logger.error(f"   ❌ Ошибка при получении позиций: {e}", exc_info=True)
        all_checks_passed = False
        logger.info("")
    
    # 5. Проверка доступности инструментов (первые 5 символов)
    logger.info("5. Проверка доступности инструментов (первые 5 символов)...")
    available_count = 0
    unavailable_count = 0
    
    for symbol in SYMBOLS[:5]:
        try:
            instrument = broker.get_instrument_details(symbol)
            if instrument:
                trading_status = instrument.get("trading_status", "")
                api_trade_available = instrument.get("api_trade_available_flag", False)
                buy_available = instrument.get("buy_available_flag", False)
                
                if api_trade_available and buy_available:
                    logger.info(f"   ✓ {symbol}: доступен для торговли")
                    available_count += 1
                else:
                    logger.warning(f"   ⚠ {symbol}: недоступен для торговли (status: {trading_status}, api: {api_trade_available}, buy: {buy_available})")
                    unavailable_count += 1
            else:
                logger.warning(f"   ⚠ {symbol}: инструмент не найден")
                unavailable_count += 1
        except Exception as e:
            logger.warning(f"   ⚠ {symbol}: ошибка при проверке - {e}")
            unavailable_count += 1
    
    logger.info(f"   Доступно: {available_count}, недоступно: {unavailable_count}")
    logger.info("")
    
    # Итоговый результат
    logger.info("=" * 80)
    if all_checks_passed and available_count > 0:
        logger.info("✓ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ - БОТ РАБОТОСПОСОБЕН")
    elif all_checks_passed:
        logger.warning("⚠ БОТ РАБОТОСПОСОБЕН, НО НЕКОТОРЫЕ ИНСТРУМЕНТЫ НЕДОСТУПНЫ")
    else:
        logger.error("❌ ОБНАРУЖЕНЫ ПРОБЛЕМЫ - ТРЕБУЕТСЯ ИСПРАВЛЕНИЕ")
    logger.info("=" * 80)
    
    return all_checks_passed and available_count > 0

if __name__ == "__main__":
    try:
        success = check_bot_health()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)





