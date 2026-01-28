"""Тест импорта T-Invest SDK"""
print("Проверка импорта T-Invest SDK...")

try:
    from tinkoff.invest import Client
    print("✓ T-Invest SDK успешно импортирован")
except ImportError as e:
    print(f"✗ Ошибка импорта T-Invest SDK: {e}")
    print("Установите: pip install tinkoff-invest")
except Exception as e:
    print(f"✗ Неожиданная ошибка: {e}")

# Проверяем импорт из config
try:
    from config import TINVEST_TOKEN
    if TINVEST_TOKEN:
        token_preview = TINVEST_TOKEN[:10] + '...' if len(TINVEST_TOKEN) > 10 else TINVEST_TOKEN
        print(f"✓ TINVEST_TOKEN найден: {token_preview}")
        if 'your_token' in str(TINVEST_TOKEN).lower():
            print("⚠ Токен содержит примерное значение!")
    else:
        print("✗ TINVEST_TOKEN не найден в .env")
except Exception as e:
    print(f"✗ Ошибка загрузки конфига: {e}")






