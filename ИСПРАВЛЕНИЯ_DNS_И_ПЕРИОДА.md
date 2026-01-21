# ✅ Исправления DNS и ограничений по периоду

## ❌ Проблема 1: DNS resolution failed for sandbox

**Ошибка:** `DNS resolution failed for sandbox: UNAVAILABLE: getaddrinfo: WSA Error (No such host is known.`

**Причина:** SDK пытался подключиться к хосту "sandbox" вместо правильного адреса `sandbox-invest-public-api.tinkoff.ru`

**Решение:** Используем константу `INVEST_GRPC_API_SANDBOX` из SDK для правильного адреса

```python
from tinkoff.invest.constants import INVEST_GRPC_API_SANDBOX
self.client = Client(token=self.token, target=INVEST_GRPC_API_SANDBOX)
```

## ❌ Проблема 2: Ограничения по периоду

**Причина:** Было ограничение на 365 дней для дневных свечей

**Решение:** 
- Увеличено до 730 дней (2 года) для дневных свечей
- Добавлена поддержка периодов: '1y', '2y', '3y', 'all'
- Период по умолчанию изменен с '2024' на '1y'

## ✅ Что изменено

1. **tinvest_api.py:**
   - Исправлена инициализация Client с правильным адресом песочницы
   - Увеличен max_days_per_request до 730 дней
   - Добавлена поддержка периодов: '1y', '2y', '3y', 'all'

2. **backtest.py:**
   - Период по умолчанию изменен с '2024' на '1y'
   - Улучшен вывод информации о периоде

## ✅ Проверка

Запустите: `python backtest.py`

Теперь должно работать подключение к песочнице и получение данных без ограничений!



