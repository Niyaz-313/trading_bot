"""
Скрипт для проверки подключений и настроек бота
"""
import asyncio
import logging
from broker_api import BrokerAPI
from telegram_bot import TelegramBot
from config import SYMBOLS, BROKER

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_connections():
    """Проверить все подключения"""
    print("=" * 50)
    print("Проверка подключений торгового бота")
    print("=" * 50)
    
    # Проверка брокерского API
    print("\n1. Проверка брокерского API...")
    from config import TINVEST_SANDBOX
    paper_trading = TINVEST_SANDBOX if BROKER == 'tinvest' else True
    broker = BrokerAPI(paper_trading=paper_trading)
    account_info = broker.get_account_info()
    if account_info:
        print(f"✓ Подключение к брокеру успешно ({BROKER})")
        print(f"  Капитал: ${account_info.get('equity', 0):.2f}")
        print(f"  Наличные: ${account_info.get('cash', 0):.2f}")
    else:
        print("⚠ Брокерский API не настроен (режим симуляции)")
    
    # Проверка получения данных
    print("\n2. Проверка получения данных по акциям...")
    for symbol in SYMBOLS[:3]:
        try:
            price = broker.get_current_price(symbol)
            if price > 0:
                print(f"✓ {symbol}: ${price:.2f}")
            else:
                print(f"✗ {symbol}: Не удалось получить цену")
        except Exception as e:
            print(f"✗ {symbol}: Ошибка - {e}")
    
    # Проверка Telegram
    print("\n3. Проверка Telegram бота...")
    telegram = TelegramBot()
    if telegram.bot:
        test_message = "🧪 Тестовое сообщение от торгового бота"
        success = await telegram.send_message(test_message)
        if success:
            print("✓ Telegram бот работает корректно")
        else:
            print("✗ Не удалось отправить сообщение в Telegram")
    else:
        print("⚠ Telegram бот не настроен (проверьте TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID)")
    
    print("\n" + "=" * 50)
    print("Проверка завершена")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(test_connections())







