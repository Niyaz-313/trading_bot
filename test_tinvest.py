"""
Скрипт для проверки подключения к T-Invest API
"""
import logging
from tinvest_api import TInvestAPI
from config import TINVEST_TOKEN, TINVEST_SANDBOX, SYMBOLS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_tinvest():
    """Проверить подключение к T-Invest API"""
    print("=" * 60)
    print("Проверка подключения к T-Invest API")
    print("=" * 60)
    print()
    
    # Проверка токена
    print("1. Проверка токена...")
    if not TINVEST_TOKEN:
        print("   ✗ TINVEST_TOKEN не найден в .env файле")
        print("   → Получите токен в настройках Т-Инвестиций")
        print("   → Добавьте в .env: TINVEST_TOKEN=ваш_токен")
        return
    elif 'your_tinvest_token' in TINVEST_TOKEN.lower() or 'your_token' in TINVEST_TOKEN.lower():
        print(f"   ✗ Токен не заменен на реальный!")
        print(f"   Текущее значение: {TINVEST_TOKEN[:30]}...")
        print("   → Получите реальный токен: Т-Инвестиции → Настройки → Токены T-Bank Invest API")
        print("   → Замените в .env: TINVEST_TOKEN=ваш_реальный_токен")
        return
    else:
        print(f"   ✓ Токен найден: {TINVEST_TOKEN[:10]}...{TINVEST_TOKEN[-5:]}")
    
    # Проверка режима
    print(f"\n2. Режим работы: {'Песочница' if TINVEST_SANDBOX else 'Продакшн'}")
    
    # Проверка установки SDK
    print("\n3. Проверка T-Invest SDK...")
    try:
        import tinkoff.invest
        print("   ✓ T-Invest SDK установлен")
    except ImportError:
        print("   ✗ T-Invest SDK не установлен!")
        print("   → Установите: pip install tinkoff-invest")
        return
    
    # Инициализация API
    print("\n4. Подключение к T-Invest API...")
    try:
        api = TInvestAPI(sandbox=TINVEST_SANDBOX)
        if not api.client:
            print("   ✗ Не удалось подключиться к T-Invest API")
            print("   → Проверьте правильность токена в .env")
            return
        print("   ✓ Подключение установлено")
    except Exception as e:
        print(f"   ✗ Ошибка подключения: {e}")
        return
    
    # Проверка информации о счете
    print("\n5. Проверка информации о счете...")
    try:
        account_info = api.get_account_info()
        if account_info:
            print(f"   ✓ Капитал: {account_info.get('equity', 0):.2f} {account_info.get('currency', 'RUB')}")
            print(f"   ✓ Наличные: {account_info.get('cash', 0):.2f} {account_info.get('currency', 'RUB')}")
            if 'account_id' in account_info:
                print(f"   ✓ Account ID: {account_info['account_id']}")
        else:
            print("   ⚠ Не удалось получить информацию о счете")
    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
    
    # Проверка получения данных по акциям
    print("\n6. Проверка получения данных по акциям...")
    for symbol in SYMBOLS[:3]:
        try:
            instrument = api.get_instrument_by_ticker(symbol)
            if instrument:
                print(f"   ✓ {symbol}: найден (FIGI: {instrument['figi']})")
                price = api.get_current_price(symbol)
                if price > 0:
                    print(f"      Цена: {price:.2f}")
                else:
                    print(f"      ⚠ Цена не получена")
            else:
                print(f"   ✗ {symbol}: инструмент не найден")
        except Exception as e:
            print(f"   ✗ {symbol}: ошибка - {e}")
    
    # Проверка позиций
    print("\n7. Проверка открытых позиций...")
    try:
        positions = api.get_positions()
        if positions:
            print(f"   ✓ Найдено позиций: {len(positions)}")
            for pos in positions[:3]:
                print(f"      {pos.get('symbol', 'N/A')}: {pos.get('qty', 0)} шт.")
        else:
            print("   ✓ Нет открытых позиций")
    except Exception as e:
        print(f"   ✗ Ошибка получения позиций: {e}")
    
    print("\n" + "=" * 60)
    print("Проверка завершена")
    print("=" * 60)
    print("\n💡 Следующие шаги:")
    print("   1. Убедитесь, что токен правильный")
    print("   2. Проверьте, что используете правильные тикеры (российские для T-Invest)")
    print("   3. Запустите бота: python main.py")


if __name__ == "__main__":
    test_tinvest()



