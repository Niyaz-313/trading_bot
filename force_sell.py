"""
Скрипт для принудительной продажи позиций PLDRUBTOM и PLTRUBTOM
"""
import logging
import sys
from broker_api import BrokerAPI
from config import TINVEST_SANDBOX, BROKER

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

def force_sell_symbols(symbols_to_sell: list):
    """
    Принудительно продать все позиции для указанных символов
    
    Args:
        symbols_to_sell: Список символов для продажи (например, ['PLDRUBTOM', 'PLTRUBTOM'])
    """
    logger.info(f"Инициализация брокера (sandbox={TINVEST_SANDBOX}, broker={BROKER})...")
    
    try:
        broker = BrokerAPI(paper_trading=TINVEST_SANDBOX)
        
        if not broker.client:
            logger.error("Не удалось инициализировать клиент брокера")
            return False
        
        logger.info("Получение позиций...")
        positions = broker.get_positions()
        
        if not positions:
            logger.info("Нет открытых позиций")
            return True
        
        logger.info(f"Найдено позиций: {len(positions)}")
        
        # Канонизируем символы для поиска
        symbols_to_sell_canon = [_canon_symbol(s) for s in symbols_to_sell]
        logger.info(f"Ищем позиции для символов: {symbols_to_sell} (канонизированные: {symbols_to_sell_canon})")
        
        found_positions = []
        for pos in positions:
            pos_symbol = pos.get('symbol') or pos.get('ticker') or ''
            pos_figi = pos.get('figi', '')
            pos_symbol_canon = _canon_symbol(pos_symbol)
            
            # Проверяем, совпадает ли позиция с одним из искомых символов
            # Проверяем как оригинальный символ, так и канонизированный
            # Также проверяем варианты с подчеркиванием и без
            matches = False
            for target_symbol in symbols_to_sell:
                target_canon = _canon_symbol(target_symbol)
                # Проверяем различные варианты написания
                if (pos_symbol_canon == target_canon or 
                    pos_symbol == target_symbol or
                    pos_symbol_canon == target_symbol or
                    pos_symbol == target_canon):
                    matches = True
                    break
            
            if matches:
                qty_lots = int(pos.get('qty_lots', pos.get('qty', 0)) or 0)
                if qty_lots > 0:
                    # Получаем дополнительную информацию о позиции
                    lot = int(pos.get('lot', 1) or 1)
                    qty_shares = float(pos.get('qty_shares', 0) or 0)
                    
                    found_positions.append({
                        'symbol': pos_symbol,
                        'symbol_canon': pos_symbol_canon,
                        'qty_lots': qty_lots,
                        'qty_shares': qty_shares,
                        'lot': lot,
                        'figi': pos_figi,
                        'current_price': pos.get('current_price', 0.0),
                        'avg_entry_price': pos.get('avg_entry_price', 0.0),
                        'position': pos
                    })
                    logger.info(f"Найдена позиция: {pos_symbol} ({pos_symbol_canon}) [FIGI: {pos_figi}] - {qty_lots} лотов (lot={lot}, qty_shares={qty_shares})")
        
        if not found_positions:
            logger.info(f"Позиции для символов {symbols_to_sell} не найдены")
            return True
        
        # Продаем все найденные позиции
        logger.info(f"\n{'='*60}")
        logger.info(f"НАЧИНАЕМ ПРИНУДИТЕЛЬНУЮ ПРОДАЖУ {len(found_positions)} ПОЗИЦИЙ")
        logger.info(f"{'='*60}\n")
        
        success_count = 0
        error_count = 0
        
        for pos_info in found_positions:
            symbol = pos_info['symbol']
            symbol_canon = pos_info['symbol_canon']
            qty_lots = pos_info['qty_lots']
            qty_shares = pos_info.get('qty_shares', 0)
            lot = pos_info.get('lot', 1)
            figi = pos_info['figi']
            current_price = pos_info['current_price']
            avg_entry_price = pos_info['avg_entry_price']
            
            logger.info(f"\nПозиция: {symbol} ({symbol_canon})")
            logger.info(f"  Лотов: {qty_lots}")
            logger.info(f"  Лот (lot): {lot}")
            logger.info(f"  Количество в штуках (qty_shares): {qty_shares}")
            logger.info(f"  FIGI: {figi}")
            logger.info(f"  Текущая цена: {current_price:.4f}")
            logger.info(f"  Средняя цена входа: {avg_entry_price:.4f}")
            
            # Проверка: для валютных пар lot обычно = 1, и qty_lots должно совпадать с qty_shares
            if lot == 1 and qty_shares > 0:
                calculated_lots = int(qty_shares / lot)
                if calculated_lots != qty_lots:
                    logger.warning(f"  ⚠ Несоответствие: qty_shares/lot={calculated_lots}, но qty_lots={qty_lots}")
                    # Используем расчетное значение, если оно отличается
                    if calculated_lots > 0:
                        logger.info(f"  Используем расчетное количество лотов: {calculated_lots}")
                        qty_lots = calculated_lots
            
            if qty_lots <= 0:
                logger.warning(f"  Пропуск: количество лотов = {qty_lots}")
                continue
            
            # ФИНАЛЬНАЯ ПРОВЕРКА: запрашиваем актуальные позиции перед продажей
            # Это важно, так как количество лотов может измениться или быть неточным
            try:
                logger.info(f"  Проверка актуального количества лотов...")
                current_positions = broker.get_positions() or []
                current_pos = None
                
                for pos_val in current_positions:
                    if not isinstance(pos_val, dict):
                        continue
                    pos_sym = _canon_symbol(pos_val.get('symbol') or pos_val.get('ticker') or '')
                    pos_figi_val = pos_val.get('figi', '')
                    
                    # Проверяем совпадение по символу или FIGI
                    if (pos_sym == symbol_canon or 
                        pos_sym == symbol or
                        (figi and pos_figi_val == figi)):
                        current_pos = pos_val
                        break
                
                if current_pos:
                    actual_qty = int(current_pos.get('qty_lots', current_pos.get('qty', 0)) or 0)
                    if actual_qty < qty_lots:
                        logger.warning(f"  Актуальное количество лотов меньше ожидаемого: {actual_qty} < {qty_lots}, используем {actual_qty}")
                        qty_lots = actual_qty
                    elif actual_qty > 0:
                        logger.info(f"  Подтверждено количество лотов: {actual_qty} лотов (продаем {qty_lots})")
                    else:
                        logger.warning(f"  Позиция не содержит лотов (actual_qty={actual_qty})")
                else:
                    logger.warning(f"  Позиция не найдена в актуальных позициях, возможно уже закрыта")
                    if qty_lots > 0:
                        logger.info(f"  Попытка продажи {qty_lots} лотов несмотря на отсутствие в актуальных позициях")
            except Exception as e:
                logger.warning(f"  Не удалось проверить актуальные позиции: {e}", exc_info=True)
            
            if qty_lots <= 0:
                logger.warning(f"  Пропуск: количество лотов = {qty_lots}")
                continue
            
            # Используем канонизированный символ для продажи
            # Если это FIGI (начинается с BBG), используем его напрямую
            order_symbol = symbol_canon if symbol_canon else symbol
            if figi and figi.startswith("BBG") and len(figi) > 10:
                # Если тикер не найден или это FIGI, пробуем использовать FIGI
                # Но сначала пробуем тикер
                try_order_symbols = [order_symbol]
                if order_symbol != figi:
                    try_order_symbols.append(figi)
            else:
                try_order_symbols = [order_symbol]
            
            order_placed = False
            last_error = None
            
            # Пробуем продать разными способами
            # 1. Сначала пробуем полную продажу
            # 2. Если не получается, пробуем продать по частям (по 1 лоту)
            # 3. Если и это не работает, пробуем продать половину
            sell_attempts = [
                ("полная продажа", qty_lots),
                ("продажа по частям (по 1 лоту)", 1),
                ("продажа половины", max(1, qty_lots // 2)),
            ]
            
            for attempt_name, attempt_qty in sell_attempts:
                if attempt_qty <= 0:
                    continue
                
                if attempt_name != "полная продажа" and order_placed:
                    # Если уже продали что-то, пробуем продать оставшееся
                    # Но сначала проверим актуальное количество
                    try:
                        current_positions = broker.get_positions() or []
                        for pos_val in current_positions:
                            if not isinstance(pos_val, dict):
                                continue
                            pos_sym = _canon_symbol(pos_val.get('symbol') or pos_val.get('ticker') or '')
                            pos_figi_val = pos_val.get('figi', '')
                            if (pos_sym == symbol_canon or pos_sym == symbol or (figi and pos_figi_val == figi)):
                                remaining_qty = int(pos_val.get('qty_lots', pos_val.get('qty', 0)) or 0)
                                if remaining_qty <= 0:
                                    logger.info(f"  Позиция полностью продана")
                                    break
                                attempt_qty = min(attempt_qty, remaining_qty)
                                logger.info(f"  Осталось {remaining_qty} лотов, пробуем продать {attempt_qty}")
                    except Exception:
                        pass
                
                for try_symbol in try_order_symbols:
                    logger.info(f"  Попытка {attempt_name}: SELL {attempt_qty} лотов {try_symbol}...")
                    
                    try:
                        order_result = broker.place_market_order(try_symbol, attempt_qty, 'sell')
                        
                        if order_result:
                            order_id = order_result.get('order_id', 'N/A')
                            status = order_result.get('status', 'unknown')
                            logger.info(f"  ✓ Ордер размещен успешно! ({attempt_name})")
                            logger.info(f"    Order ID: {order_id}")
                            logger.info(f"    Status: {status}")
                            order_placed = True
                            
                            # Если продали не всё, продолжаем попытки
                            if attempt_qty < qty_lots:
                                logger.info(f"  Продано {attempt_qty} из {qty_lots} лотов, продолжаем...")
                                # Обновляем qty_lots для следующих попыток
                                qty_lots = qty_lots - attempt_qty
                                break
                            else:
                                success_count += 1
                                break
                        else:
                            last_error = "Результат: None"
                            
                    except Exception as e:
                        last_error = str(e)
                        error_msg = str(e).lower()
                        # Если ошибка "недостаточно баланса", пробуем другой способ
                        if "30034" in error_msg or "not enough" in error_msg or "недостаточно" in error_msg:
                            logger.warning(f"  Ошибка баланса при {attempt_name} с {try_symbol}, пробуем другой способ...")
                            continue
                        else:
                            logger.warning(f"  Попытка {attempt_name} с {try_symbol} не удалась: {e}")
                            continue
                    
                    if order_placed and attempt_qty >= qty_lots:
                        break
                
                if order_placed and attempt_qty >= qty_lots:
                    break
            
            if not order_placed:
                logger.error(f"  ✗ Не удалось разместить ордер после всех попыток. Последняя ошибка: {last_error}")
                error_count += 1
            elif order_placed and qty_lots > 0:
                # Если продали частично, но не всё
                logger.warning(f"  ⚠ Продано частично, осталось {qty_lots} лотов")
                error_count += 1
        
        logger.info(f"\n{'='*60}")
        logger.info(f"РЕЗУЛЬТАТЫ ПРОДАЖИ:")
        logger.info(f"  Успешно: {success_count}")
        logger.info(f"  Ошибок: {error_count}")
        logger.info(f"{'='*60}\n")
        
        return error_count == 0
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    # Символы для принудительной продажи
    symbols_to_sell = ['PLDRUBTOM', 'PLTRUBTOM']
    
    logger.info("="*60)
    logger.info("СКРИПТ ПРИНУДИТЕЛЬНОЙ ПРОДАЖИ ПОЗИЦИЙ")
    logger.info("="*60)
    logger.info(f"Символы для продажи: {symbols_to_sell}")
    logger.info("")
    
    # Подтверждение
    response = input("Вы уверены, что хотите продать все позиции для этих символов? (yes/no): ")
    if response.lower() not in ['yes', 'y', 'да', 'д']:
        logger.info("Операция отменена пользователем")
        sys.exit(0)
    
    success = force_sell_symbols(symbols_to_sell)
    
    if success:
        logger.info("✓ Операция завершена успешно")
        sys.exit(0)
    else:
        logger.error("✗ Операция завершена с ошибками")
        sys.exit(1)


"""
import logging
import sys
from broker_api import BrokerAPI
from config import TINVEST_SANDBOX, BROKER

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

def force_sell_symbols(symbols_to_sell: list):
    """
    Принудительно продать все позиции для указанных символов
    
    Args:
        symbols_to_sell: Список символов для продажи (например, ['PLDRUBTOM', 'PLTRUBTOM'])
    """
    logger.info(f"Инициализация брокера (sandbox={TINVEST_SANDBOX}, broker={BROKER})...")
    
    try:
        broker = BrokerAPI(paper_trading=TINVEST_SANDBOX)
        
        if not broker.client:
            logger.error("Не удалось инициализировать клиент брокера")
            return False
        
        logger.info("Получение позиций...")
        positions = broker.get_positions()
        
        if not positions:
            logger.info("Нет открытых позиций")
            return True
        
        logger.info(f"Найдено позиций: {len(positions)}")
        
        # Канонизируем символы для поиска
        symbols_to_sell_canon = [_canon_symbol(s) for s in symbols_to_sell]
        logger.info(f"Ищем позиции для символов: {symbols_to_sell} (канонизированные: {symbols_to_sell_canon})")
        
        found_positions = []
        for pos in positions:
            pos_symbol = pos.get('symbol') or pos.get('ticker') or ''
            pos_figi = pos.get('figi', '')
            pos_symbol_canon = _canon_symbol(pos_symbol)
            
            # Проверяем, совпадает ли позиция с одним из искомых символов
            # Проверяем как оригинальный символ, так и канонизированный
            # Также проверяем варианты с подчеркиванием и без
            matches = False
            for target_symbol in symbols_to_sell:
                target_canon = _canon_symbol(target_symbol)
                # Проверяем различные варианты написания
                if (pos_symbol_canon == target_canon or 
                    pos_symbol == target_symbol or
                    pos_symbol_canon == target_symbol or
                    pos_symbol == target_canon):
                    matches = True
                    break
            
            if matches:
                qty_lots = int(pos.get('qty_lots', pos.get('qty', 0)) or 0)
                if qty_lots > 0:
                    # Получаем дополнительную информацию о позиции
                    lot = int(pos.get('lot', 1) or 1)
                    qty_shares = float(pos.get('qty_shares', 0) or 0)
                    
                    found_positions.append({
                        'symbol': pos_symbol,
                        'symbol_canon': pos_symbol_canon,
                        'qty_lots': qty_lots,
                        'qty_shares': qty_shares,
                        'lot': lot,
                        'figi': pos_figi,
                        'current_price': pos.get('current_price', 0.0),
                        'avg_entry_price': pos.get('avg_entry_price', 0.0),
                        'position': pos
                    })
                    logger.info(f"Найдена позиция: {pos_symbol} ({pos_symbol_canon}) [FIGI: {pos_figi}] - {qty_lots} лотов (lot={lot}, qty_shares={qty_shares})")
        
        if not found_positions:
            logger.info(f"Позиции для символов {symbols_to_sell} не найдены")
            return True
        
        # Продаем все найденные позиции
        logger.info(f"\n{'='*60}")
        logger.info(f"НАЧИНАЕМ ПРИНУДИТЕЛЬНУЮ ПРОДАЖУ {len(found_positions)} ПОЗИЦИЙ")
        logger.info(f"{'='*60}\n")
        
        success_count = 0
        error_count = 0
        
        for pos_info in found_positions:
            symbol = pos_info['symbol']
            symbol_canon = pos_info['symbol_canon']
            qty_lots = pos_info['qty_lots']
            qty_shares = pos_info.get('qty_shares', 0)
            lot = pos_info.get('lot', 1)
            figi = pos_info['figi']
            current_price = pos_info['current_price']
            avg_entry_price = pos_info['avg_entry_price']
            
            logger.info(f"\nПозиция: {symbol} ({symbol_canon})")
            logger.info(f"  Лотов: {qty_lots}")
            logger.info(f"  Лот (lot): {lot}")
            logger.info(f"  Количество в штуках (qty_shares): {qty_shares}")
            logger.info(f"  FIGI: {figi}")
            logger.info(f"  Текущая цена: {current_price:.4f}")
            logger.info(f"  Средняя цена входа: {avg_entry_price:.4f}")
            
            # Проверка: для валютных пар lot обычно = 1, и qty_lots должно совпадать с qty_shares
            if lot == 1 and qty_shares > 0:
                calculated_lots = int(qty_shares / lot)
                if calculated_lots != qty_lots:
                    logger.warning(f"  ⚠ Несоответствие: qty_shares/lot={calculated_lots}, но qty_lots={qty_lots}")
                    # Используем расчетное значение, если оно отличается
                    if calculated_lots > 0:
                        logger.info(f"  Используем расчетное количество лотов: {calculated_lots}")
                        qty_lots = calculated_lots
            
            if qty_lots <= 0:
                logger.warning(f"  Пропуск: количество лотов = {qty_lots}")
                continue
            
            # ФИНАЛЬНАЯ ПРОВЕРКА: запрашиваем актуальные позиции перед продажей
            # Это важно, так как количество лотов может измениться или быть неточным
            try:
                logger.info(f"  Проверка актуального количества лотов...")
                current_positions = broker.get_positions() or []
                current_pos = None
                
                for pos_val in current_positions:
                    if not isinstance(pos_val, dict):
                        continue
                    pos_sym = _canon_symbol(pos_val.get('symbol') or pos_val.get('ticker') or '')
                    pos_figi_val = pos_val.get('figi', '')
                    
                    # Проверяем совпадение по символу или FIGI
                    if (pos_sym == symbol_canon or 
                        pos_sym == symbol or
                        (figi and pos_figi_val == figi)):
                        current_pos = pos_val
                        break
                
                if current_pos:
                    actual_qty = int(current_pos.get('qty_lots', current_pos.get('qty', 0)) or 0)
                    if actual_qty < qty_lots:
                        logger.warning(f"  Актуальное количество лотов меньше ожидаемого: {actual_qty} < {qty_lots}, используем {actual_qty}")
                        qty_lots = actual_qty
                    elif actual_qty > 0:
                        logger.info(f"  Подтверждено количество лотов: {actual_qty} лотов (продаем {qty_lots})")
                    else:
                        logger.warning(f"  Позиция не содержит лотов (actual_qty={actual_qty})")
                else:
                    logger.warning(f"  Позиция не найдена в актуальных позициях, возможно уже закрыта")
                    if qty_lots > 0:
                        logger.info(f"  Попытка продажи {qty_lots} лотов несмотря на отсутствие в актуальных позициях")
            except Exception as e:
                logger.warning(f"  Не удалось проверить актуальные позиции: {e}", exc_info=True)
            
            if qty_lots <= 0:
                logger.warning(f"  Пропуск: количество лотов = {qty_lots}")
                continue
            
            # Используем канонизированный символ для продажи
            # Если это FIGI (начинается с BBG), используем его напрямую
            order_symbol = symbol_canon if symbol_canon else symbol
            if figi and figi.startswith("BBG") and len(figi) > 10:
                # Если тикер не найден или это FIGI, пробуем использовать FIGI
                # Но сначала пробуем тикер
                try_order_symbols = [order_symbol]
                if order_symbol != figi:
                    try_order_symbols.append(figi)
            else:
                try_order_symbols = [order_symbol]
            
            order_placed = False
            last_error = None
            
            # Пробуем продать разными способами
            # 1. Сначала пробуем полную продажу
            # 2. Если не получается, пробуем продать по частям (по 1 лоту)
            # 3. Если и это не работает, пробуем продать половину
            sell_attempts = [
                ("полная продажа", qty_lots),
                ("продажа по частям (по 1 лоту)", 1),
                ("продажа половины", max(1, qty_lots // 2)),
            ]
            
            for attempt_name, attempt_qty in sell_attempts:
                if attempt_qty <= 0:
                    continue
                
                if attempt_name != "полная продажа" and order_placed:
                    # Если уже продали что-то, пробуем продать оставшееся
                    # Но сначала проверим актуальное количество
                    try:
                        current_positions = broker.get_positions() or []
                        for pos_val in current_positions:
                            if not isinstance(pos_val, dict):
                                continue
                            pos_sym = _canon_symbol(pos_val.get('symbol') or pos_val.get('ticker') or '')
                            pos_figi_val = pos_val.get('figi', '')
                            if (pos_sym == symbol_canon or pos_sym == symbol or (figi and pos_figi_val == figi)):
                                remaining_qty = int(pos_val.get('qty_lots', pos_val.get('qty', 0)) or 0)
                                if remaining_qty <= 0:
                                    logger.info(f"  Позиция полностью продана")
                                    break
                                attempt_qty = min(attempt_qty, remaining_qty)
                                logger.info(f"  Осталось {remaining_qty} лотов, пробуем продать {attempt_qty}")
                    except Exception:
                        pass
                
                for try_symbol in try_order_symbols:
                    logger.info(f"  Попытка {attempt_name}: SELL {attempt_qty} лотов {try_symbol}...")
                    
                    try:
                        order_result = broker.place_market_order(try_symbol, attempt_qty, 'sell')
                        
                        if order_result:
                            order_id = order_result.get('order_id', 'N/A')
                            status = order_result.get('status', 'unknown')
                            logger.info(f"  ✓ Ордер размещен успешно! ({attempt_name})")
                            logger.info(f"    Order ID: {order_id}")
                            logger.info(f"    Status: {status}")
                            order_placed = True
                            
                            # Если продали не всё, продолжаем попытки
                            if attempt_qty < qty_lots:
                                logger.info(f"  Продано {attempt_qty} из {qty_lots} лотов, продолжаем...")
                                # Обновляем qty_lots для следующих попыток
                                qty_lots = qty_lots - attempt_qty
                                break
                            else:
                                success_count += 1
                                break
                        else:
                            last_error = "Результат: None"
                            
                    except Exception as e:
                        last_error = str(e)
                        error_msg = str(e).lower()
                        # Если ошибка "недостаточно баланса", пробуем другой способ
                        if "30034" in error_msg or "not enough" in error_msg or "недостаточно" in error_msg:
                            logger.warning(f"  Ошибка баланса при {attempt_name} с {try_symbol}, пробуем другой способ...")
                            continue
                        else:
                            logger.warning(f"  Попытка {attempt_name} с {try_symbol} не удалась: {e}")
                            continue
                    
                    if order_placed and attempt_qty >= qty_lots:
                        break
                
                if order_placed and attempt_qty >= qty_lots:
                    break
            
            if not order_placed:
                logger.error(f"  ✗ Не удалось разместить ордер после всех попыток. Последняя ошибка: {last_error}")
                error_count += 1
            elif order_placed and qty_lots > 0:
                # Если продали частично, но не всё
                logger.warning(f"  ⚠ Продано частично, осталось {qty_lots} лотов")
                error_count += 1
        
        logger.info(f"\n{'='*60}")
        logger.info(f"РЕЗУЛЬТАТЫ ПРОДАЖИ:")
        logger.info(f"  Успешно: {success_count}")
        logger.info(f"  Ошибок: {error_count}")
        logger.info(f"{'='*60}\n")
        
        return error_count == 0
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    # Символы для принудительной продажи
    symbols_to_sell = ['PLDRUBTOM', 'PLTRUBTOM']
    
    logger.info("="*60)
    logger.info("СКРИПТ ПРИНУДИТЕЛЬНОЙ ПРОДАЖИ ПОЗИЦИЙ")
    logger.info("="*60)
    logger.info(f"Символы для продажи: {symbols_to_sell}")
    logger.info("")
    
    # Подтверждение
    response = input("Вы уверены, что хотите продать все позиции для этих символов? (yes/no): ")
    if response.lower() not in ['yes', 'y', 'да', 'д']:
        logger.info("Операция отменена пользователем")
        sys.exit(0)
    
    success = force_sell_symbols(symbols_to_sell)
    
    if success:
        logger.info("✓ Операция завершена успешно")
        sys.exit(0)
    else:
        logger.error("✗ Операция завершена с ошибками")
        sys.exit(1)


"""
import logging
import sys
from broker_api import BrokerAPI
from config import TINVEST_SANDBOX, BROKER

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

def force_sell_symbols(symbols_to_sell: list):
    """
    Принудительно продать все позиции для указанных символов
    
    Args:
        symbols_to_sell: Список символов для продажи (например, ['PLDRUBTOM', 'PLTRUBTOM'])
    """
    logger.info(f"Инициализация брокера (sandbox={TINVEST_SANDBOX}, broker={BROKER})...")
    
    try:
        broker = BrokerAPI(paper_trading=TINVEST_SANDBOX)
        
        if not broker.client:
            logger.error("Не удалось инициализировать клиент брокера")
            return False
        
        logger.info("Получение позиций...")
        positions = broker.get_positions()
        
        if not positions:
            logger.info("Нет открытых позиций")
            return True
        
        logger.info(f"Найдено позиций: {len(positions)}")
        
        # Канонизируем символы для поиска
        symbols_to_sell_canon = [_canon_symbol(s) for s in symbols_to_sell]
        logger.info(f"Ищем позиции для символов: {symbols_to_sell} (канонизированные: {symbols_to_sell_canon})")
        
        found_positions = []
        for pos in positions:
            pos_symbol = pos.get('symbol') or pos.get('ticker') or ''
            pos_figi = pos.get('figi', '')
            pos_symbol_canon = _canon_symbol(pos_symbol)
            
            # Проверяем, совпадает ли позиция с одним из искомых символов
            # Проверяем как оригинальный символ, так и канонизированный
            # Также проверяем варианты с подчеркиванием и без
            matches = False
            for target_symbol in symbols_to_sell:
                target_canon = _canon_symbol(target_symbol)
                # Проверяем различные варианты написания
                if (pos_symbol_canon == target_canon or 
                    pos_symbol == target_symbol or
                    pos_symbol_canon == target_symbol or
                    pos_symbol == target_canon):
                    matches = True
                    break
            
            if matches:
                qty_lots = int(pos.get('qty_lots', pos.get('qty', 0)) or 0)
                if qty_lots > 0:
                    # Получаем дополнительную информацию о позиции
                    lot = int(pos.get('lot', 1) or 1)
                    qty_shares = float(pos.get('qty_shares', 0) or 0)
                    
                    found_positions.append({
                        'symbol': pos_symbol,
                        'symbol_canon': pos_symbol_canon,
                        'qty_lots': qty_lots,
                        'qty_shares': qty_shares,
                        'lot': lot,
                        'figi': pos_figi,
                        'current_price': pos.get('current_price', 0.0),
                        'avg_entry_price': pos.get('avg_entry_price', 0.0),
                        'position': pos
                    })
                    logger.info(f"Найдена позиция: {pos_symbol} ({pos_symbol_canon}) [FIGI: {pos_figi}] - {qty_lots} лотов (lot={lot}, qty_shares={qty_shares})")
        
        if not found_positions:
            logger.info(f"Позиции для символов {symbols_to_sell} не найдены")
            return True
        
        # Продаем все найденные позиции
        logger.info(f"\n{'='*60}")
        logger.info(f"НАЧИНАЕМ ПРИНУДИТЕЛЬНУЮ ПРОДАЖУ {len(found_positions)} ПОЗИЦИЙ")
        logger.info(f"{'='*60}\n")
        
        success_count = 0
        error_count = 0
        
        for pos_info in found_positions:
            symbol = pos_info['symbol']
            symbol_canon = pos_info['symbol_canon']
            qty_lots = pos_info['qty_lots']
            qty_shares = pos_info.get('qty_shares', 0)
            lot = pos_info.get('lot', 1)
            figi = pos_info['figi']
            current_price = pos_info['current_price']
            avg_entry_price = pos_info['avg_entry_price']
            
            logger.info(f"\nПозиция: {symbol} ({symbol_canon})")
            logger.info(f"  Лотов: {qty_lots}")
            logger.info(f"  Лот (lot): {lot}")
            logger.info(f"  Количество в штуках (qty_shares): {qty_shares}")
            logger.info(f"  FIGI: {figi}")
            logger.info(f"  Текущая цена: {current_price:.4f}")
            logger.info(f"  Средняя цена входа: {avg_entry_price:.4f}")
            
            # Проверка: для валютных пар lot обычно = 1, и qty_lots должно совпадать с qty_shares
            if lot == 1 and qty_shares > 0:
                calculated_lots = int(qty_shares / lot)
                if calculated_lots != qty_lots:
                    logger.warning(f"  ⚠ Несоответствие: qty_shares/lot={calculated_lots}, но qty_lots={qty_lots}")
                    # Используем расчетное значение, если оно отличается
                    if calculated_lots > 0:
                        logger.info(f"  Используем расчетное количество лотов: {calculated_lots}")
                        qty_lots = calculated_lots
            
            if qty_lots <= 0:
                logger.warning(f"  Пропуск: количество лотов = {qty_lots}")
                continue
            
            # ФИНАЛЬНАЯ ПРОВЕРКА: запрашиваем актуальные позиции перед продажей
            # Это важно, так как количество лотов может измениться или быть неточным
            try:
                logger.info(f"  Проверка актуального количества лотов...")
                current_positions = broker.get_positions() or []
                current_pos = None
                
                for pos_val in current_positions:
                    if not isinstance(pos_val, dict):
                        continue
                    pos_sym = _canon_symbol(pos_val.get('symbol') or pos_val.get('ticker') or '')
                    pos_figi_val = pos_val.get('figi', '')
                    
                    # Проверяем совпадение по символу или FIGI
                    if (pos_sym == symbol_canon or 
                        pos_sym == symbol or
                        (figi and pos_figi_val == figi)):
                        current_pos = pos_val
                        break
                
                if current_pos:
                    actual_qty = int(current_pos.get('qty_lots', current_pos.get('qty', 0)) or 0)
                    if actual_qty < qty_lots:
                        logger.warning(f"  Актуальное количество лотов меньше ожидаемого: {actual_qty} < {qty_lots}, используем {actual_qty}")
                        qty_lots = actual_qty
                    elif actual_qty > 0:
                        logger.info(f"  Подтверждено количество лотов: {actual_qty} лотов (продаем {qty_lots})")
                    else:
                        logger.warning(f"  Позиция не содержит лотов (actual_qty={actual_qty})")
                else:
                    logger.warning(f"  Позиция не найдена в актуальных позициях, возможно уже закрыта")
                    if qty_lots > 0:
                        logger.info(f"  Попытка продажи {qty_lots} лотов несмотря на отсутствие в актуальных позициях")
            except Exception as e:
                logger.warning(f"  Не удалось проверить актуальные позиции: {e}", exc_info=True)
            
            if qty_lots <= 0:
                logger.warning(f"  Пропуск: количество лотов = {qty_lots}")
                continue
            
            # Используем канонизированный символ для продажи
            # Если это FIGI (начинается с BBG), используем его напрямую
            order_symbol = symbol_canon if symbol_canon else symbol
            if figi and figi.startswith("BBG") and len(figi) > 10:
                # Если тикер не найден или это FIGI, пробуем использовать FIGI
                # Но сначала пробуем тикер
                try_order_symbols = [order_symbol]
                if order_symbol != figi:
                    try_order_symbols.append(figi)
            else:
                try_order_symbols = [order_symbol]
            
            order_placed = False
            last_error = None
            
            # Пробуем продать разными способами
            # 1. Сначала пробуем полную продажу
            # 2. Если не получается, пробуем продать по частям (по 1 лоту)
            # 3. Если и это не работает, пробуем продать половину
            sell_attempts = [
                ("полная продажа", qty_lots),
                ("продажа по частям (по 1 лоту)", 1),
                ("продажа половины", max(1, qty_lots // 2)),
            ]
            
            for attempt_name, attempt_qty in sell_attempts:
                if attempt_qty <= 0:
                    continue
                
                if attempt_name != "полная продажа" and order_placed:
                    # Если уже продали что-то, пробуем продать оставшееся
                    # Но сначала проверим актуальное количество
                    try:
                        current_positions = broker.get_positions() or []
                        for pos_val in current_positions:
                            if not isinstance(pos_val, dict):
                                continue
                            pos_sym = _canon_symbol(pos_val.get('symbol') or pos_val.get('ticker') or '')
                            pos_figi_val = pos_val.get('figi', '')
                            if (pos_sym == symbol_canon or pos_sym == symbol or (figi and pos_figi_val == figi)):
                                remaining_qty = int(pos_val.get('qty_lots', pos_val.get('qty', 0)) or 0)
                                if remaining_qty <= 0:
                                    logger.info(f"  Позиция полностью продана")
                                    break
                                attempt_qty = min(attempt_qty, remaining_qty)
                                logger.info(f"  Осталось {remaining_qty} лотов, пробуем продать {attempt_qty}")
                    except Exception:
                        pass
                
                for try_symbol in try_order_symbols:
                    logger.info(f"  Попытка {attempt_name}: SELL {attempt_qty} лотов {try_symbol}...")
                    
                    try:
                        order_result = broker.place_market_order(try_symbol, attempt_qty, 'sell')
                        
                        if order_result:
                            order_id = order_result.get('order_id', 'N/A')
                            status = order_result.get('status', 'unknown')
                            logger.info(f"  ✓ Ордер размещен успешно! ({attempt_name})")
                            logger.info(f"    Order ID: {order_id}")
                            logger.info(f"    Status: {status}")
                            order_placed = True
                            
                            # Если продали не всё, продолжаем попытки
                            if attempt_qty < qty_lots:
                                logger.info(f"  Продано {attempt_qty} из {qty_lots} лотов, продолжаем...")
                                # Обновляем qty_lots для следующих попыток
                                qty_lots = qty_lots - attempt_qty
                                break
                            else:
                                success_count += 1
                                break
                        else:
                            last_error = "Результат: None"
                            
                    except Exception as e:
                        last_error = str(e)
                        error_msg = str(e).lower()
                        # Если ошибка "недостаточно баланса", пробуем другой способ
                        if "30034" in error_msg or "not enough" in error_msg or "недостаточно" in error_msg:
                            logger.warning(f"  Ошибка баланса при {attempt_name} с {try_symbol}, пробуем другой способ...")
                            continue
                        else:
                            logger.warning(f"  Попытка {attempt_name} с {try_symbol} не удалась: {e}")
                            continue
                    
                    if order_placed and attempt_qty >= qty_lots:
                        break
                
                if order_placed and attempt_qty >= qty_lots:
                    break
            
            if not order_placed:
                logger.error(f"  ✗ Не удалось разместить ордер после всех попыток. Последняя ошибка: {last_error}")
                error_count += 1
            elif order_placed and qty_lots > 0:
                # Если продали частично, но не всё
                logger.warning(f"  ⚠ Продано частично, осталось {qty_lots} лотов")
                error_count += 1
        
        logger.info(f"\n{'='*60}")
        logger.info(f"РЕЗУЛЬТАТЫ ПРОДАЖИ:")
        logger.info(f"  Успешно: {success_count}")
        logger.info(f"  Ошибок: {error_count}")
        logger.info(f"{'='*60}\n")
        
        return error_count == 0
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    # Символы для принудительной продажи
    symbols_to_sell = ['PLDRUBTOM', 'PLTRUBTOM']
    
    logger.info("="*60)
    logger.info("СКРИПТ ПРИНУДИТЕЛЬНОЙ ПРОДАЖИ ПОЗИЦИЙ")
    logger.info("="*60)
    logger.info(f"Символы для продажи: {symbols_to_sell}")
    logger.info("")
    
    # Подтверждение
    response = input("Вы уверены, что хотите продать все позиции для этих символов? (yes/no): ")
    if response.lower() not in ['yes', 'y', 'да', 'д']:
        logger.info("Операция отменена пользователем")
        sys.exit(0)
    
    success = force_sell_symbols(symbols_to_sell)
    
    if success:
        logger.info("✓ Операция завершена успешно")
        sys.exit(0)
    else:
        logger.error("✗ Операция завершена с ошибками")
        sys.exit(1)

