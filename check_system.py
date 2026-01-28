"""
Полная проверка системы торгового бота
Проверяет все настройки, подключения и стратегию
"""
import asyncio
import logging
from config import *
from broker_api import BrokerAPI
from trading_strategy import TradingStrategy
from risk_manager import RiskManager
from telegram_bot import TelegramBot

logging.basicConfig(level=logging.WARNING)  # Уменьшаем логирование


async def check_system():
    """Полная проверка системы"""
    print("=" * 70)
    print("ПОЛНАЯ ПРОВЕРКА СИСТЕМЫ ТОРГОВОГО БОТА")
    print("=" * 70)
    print()
    
    errors = []
    warnings = []
    
    # 1. Проверка конфигурации
    print("1. ПРОВЕРКА КОНФИГУРАЦИИ")
    print("-" * 70)
    
    if not TINVEST_TOKEN or 'your_token' in str(TINVEST_TOKEN).lower():
        errors.append("TINVEST_TOKEN не настроен или содержит примерное значение")
        print("  ✗ TINVEST_TOKEN: не настроен")
    else:
        print(f"  ✓ TINVEST_TOKEN: настроен ({TINVEST_TOKEN[:10]}...)")
    
    if not TELEGRAM_BOT_TOKEN:
        warnings.append("TELEGRAM_BOT_TOKEN не настроен")
        print("  ⚠ TELEGRAM_BOT_TOKEN: не настроен")
    else:
        print(f"  ✓ TELEGRAM_BOT_TOKEN: настроен")
    
    if not TELEGRAM_CHAT_ID:
        warnings.append("TELEGRAM_CHAT_ID не настроен")
        print("  ⚠ TELEGRAM_CHAT_ID: не настроен")
    else:
        print(f"  ✓ TELEGRAM_CHAT_ID: настроен")
    
    print(f"  ✓ Брокер: {BROKER}")
    print(f"  ✓ Песочница: {TINVEST_SANDBOX}")
    print(f"  ✓ Символы: {', '.join(SYMBOLS)}")
    print(f"  ✓ Макс. размер позиции: {MAX_POSITION_SIZE*100:.0f}%")
    print(f"  ✓ Стоп-лосс: {STOP_LOSS_PERCENT*100:.0f}%")
    print(f"  ✓ Тейк-профит: {TAKE_PROFIT_PERCENT*100:.0f}%")
    print()
    
    # 2. Проверка подключений
    print("2. ПРОВЕРКА ПОДКЛЮЧЕНИЙ")
    print("-" * 70)
    
    # Брокер
    try:
        paper_trading = TINVEST_SANDBOX if BROKER == 'tinvest' else True
        broker = BrokerAPI(paper_trading=paper_trading)
        account_info = broker.get_account_info()
        if account_info and account_info.get('equity', 0) > 0:
            print(f"  ✓ Брокер API: подключен")
            print(f"    Капитал: {account_info.get('equity', 0):.2f}")
        else:
            warnings.append("Брокер API работает в режиме симуляции")
            print("  ⚠ Брокер API: режим симуляции")
    except Exception as e:
        errors.append(f"Ошибка подключения к брокеру: {e}")
        print(f"  ✗ Брокер API: ошибка - {e}")
    
    # Telegram
    try:
        telegram = TelegramBot()
        if telegram.bot:
            print("  ✓ Telegram: подключен")
        else:
            warnings.append("Telegram не настроен")
            print("  ⚠ Telegram: не настроен")
    except Exception as e:
        warnings.append(f"Ошибка Telegram: {e}")
        print(f"  ⚠ Telegram: ошибка - {e}")
    
    print()
    
    # 3. Проверка стратегии
    print("3. ПРОВЕРКА ТОРГОВОЙ СТРАТЕГИИ")
    print("-" * 70)
    
    strategy = TradingStrategy()
    print(f"  ✓ RSI период: {strategy.rsi_period}")
    print(f"  ✓ RSI перепроданность: {strategy.rsi_oversold}")
    print(f"  ✓ RSI перекупленность: {strategy.rsi_overbought}")
    print(f"  ✓ MA короткая: {strategy.ma_short}")
    print(f"  ✓ MA длинная: {strategy.ma_long}")
    print(f"  ✓ MACD: {strategy.macd_fast}/{strategy.macd_slow}/{strategy.macd_signal}")
    print()
    
    # 4. Проверка управления рисками
    print("4. ПРОВЕРКА УПРАВЛЕНИЯ РИСКАМИ")
    print("-" * 70)
    
    risk_manager = RiskManager()
    test_price = 100.0
    stop_loss = risk_manager.calculate_stop_loss(test_price)
    take_profit = risk_manager.calculate_take_profit(test_price)
    risk_reward = risk_manager.calculate_risk_reward_ratio(test_price)
    
    print(f"  ✓ Макс. размер позиции: {risk_manager.max_position_size*100:.0f}%")
    print(f"  ✓ Стоп-лосс: {stop_loss:.2f} ({STOP_LOSS_PERCENT*100:.0f}%)")
    print(f"  ✓ Тейк-профит: {take_profit:.2f} ({TAKE_PROFIT_PERCENT*100:.0f}%)")
    print(f"  ✓ Соотношение риск/прибыль: 1:{risk_reward:.2f}")
    
    if risk_reward >= 2.0:
        print("  ✓ Хорошее соотношение риск/прибыль")
    else:
        warnings.append("Соотношение риск/прибыль ниже рекомендуемого (минимум 1:2)")
        print("  ⚠ Соотношение риск/прибыль можно улучшить")
    
    print()
    
    # 5. Итоги
    print("=" * 70)
    print("ИТОГИ ПРОВЕРКИ")
    print("=" * 70)
    
    if errors:
        print(f"\n✗ КРИТИЧЕСКИЕ ОШИБКИ ({len(errors)}):")
        for error in errors:
            print(f"  - {error}")
    
    if warnings:
        print(f"\n⚠ ПРЕДУПРЕЖДЕНИЯ ({len(warnings)}):")
        for warning in warnings:
            print(f"  - {warning}")
    
    if not errors and not warnings:
        print("\n✓ Все проверки пройдены успешно!")
        print("  Система готова к работе.")
    elif not errors:
        print("\n⚠ Есть предупреждения, но система может работать.")
    else:
        print("\n✗ Обнаружены критические ошибки. Исправьте их перед запуском.")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(check_system())







