"""
Pre-flight проверка перед запуском main.py (песочница/продакшн).

Цель: быстро убедиться, что:
- .env загружен и ключевые параметры заданы
- SDK tinkoff.invest импортируется
- доступ к T-Invest API есть (аккаунт/портфель/котировки/история)
- Telegram настроен (опционально)

Скрипт НЕ размещает заявок.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone

from config import (
    BROKER,
    TINVEST_TOKEN,
    TINVEST_SANDBOX,
    TINVEST_GRPC_TARGET,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    SYMBOLS,
    BAR_INTERVAL,
    HISTORY_LOOKBACK,
    ENABLE_TRADING,
    AUTO_START,
)


def _ok(msg: str) -> None:
    print(f"✓ {msg}")


def _warn(msg: str) -> None:
    print(f"⚠ {msg}")


def _fail(msg: str) -> None:
    print(f"✗ {msg}")


async def _main_async(args: argparse.Namespace) -> int:
    print("=" * 70)
    print("PREFLIGHT: проверка перед запуском торгового бота")
    print("=" * 70)
    print(f"Время (UTC): {datetime.now(timezone.utc).isoformat().replace('+00:00','Z')}")
    print("")

    # 1) Базовые настройки
    if BROKER != "tinvest":
        _fail(f"BROKER={BROKER}. Для песочницы должен быть BROKER=tinvest")
        return 2
    _ok(f"BROKER={BROKER}")

    if not TINVEST_TOKEN or "your_" in str(TINVEST_TOKEN).lower() or "example" in str(TINVEST_TOKEN).lower():
        _fail("TINVEST_TOKEN не задан или содержит примерное значение")
        return 2
    _ok("TINVEST_TOKEN задан")

    _ok(f"TINVEST_SANDBOX={TINVEST_SANDBOX}")
    if TINVEST_SANDBOX:
        if TINVEST_GRPC_TARGET:
            _ok(f"TINVEST_GRPC_TARGET={TINVEST_GRPC_TARGET}")
        else:
            _warn("TINVEST_GRPC_TARGET не задан (это ок, SDK возьмёт дефолт для песочницы)")

    _ok(f"ENABLE_TRADING={ENABLE_TRADING} (это флаг реальных ордеров в main.py)")
    _ok(f"AUTO_START={AUTO_START} (входы BUY после старта)")

    if not SYMBOLS:
        _fail("SYMBOLS пустой")
        return 2
    _ok(f"SYMBOLS={', '.join(SYMBOLS)}")
    _ok(f"BAR_INTERVAL={BAR_INTERVAL}, HISTORY_LOOKBACK={HISTORY_LOOKBACK}")

    # 2) Проверка SDK и T-Invest API
    try:
        from tinvest_api import TInvestAPI  # noqa
    except Exception as e:
        _fail(f"Не удалось импортировать tinvest_api/TInvestAPI: {e}")
        return 2

    api = None
    try:
        api = TInvestAPI(sandbox=bool(TINVEST_SANDBOX))
    except Exception as e:
        _fail(f"Не удалось инициализировать TInvestAPI: {e}")
        return 2

    if not getattr(api, "client", None):
        _fail("TInvestAPI не настроен (client=None). Проверьте SDK/токен.")
        return 2
    _ok("TInvestAPI инициализирован")

    # account/portfolio/positions
    try:
        info = api.get_account_info()
        if not info:
            _warn("get_account_info вернул пусто")
        else:
            _ok(f"account_info: equity={info.get('equity')} cash={info.get('cash')} currency={info.get('currency','RUB')}")
    except Exception as e:
        _fail(f"get_account_info ошибка: {e}")
        return 2

    try:
        pos = api.get_positions() or []
        _ok(f"positions: найдено {len(pos)}")
    except Exception as e:
        _fail(f"get_positions ошибка: {e}")
        return 2

    # quotes + small history for the first symbol
    sym0 = SYMBOLS[0]
    try:
        px = api.get_current_price(sym0)
        _ok(f"price({sym0})={px}")
    except Exception as e:
        _warn(f"get_current_price({sym0}) ошибка: {e}")

    try:
        df = api.get_historical_data(sym0, period=str(args.history_period), interval="1d")
        if df is None or df.empty:
            _warn(f"historical({sym0}) пусто для period={args.history_period}")
        else:
            _ok(f"historical({sym0}) свечей={len(df)} диапазон={df.index.min().date()}..{df.index.max().date()}")
    except Exception as e:
        _fail(f"get_historical_data({sym0}) ошибка: {e}")
        return 2

    # 3) Telegram (опционально)
    if args.telegram:
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            _warn("Telegram не настроен: нет TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID")
        else:
            try:
                from telegram_bot import TelegramBot

                tg = TelegramBot()
                if not tg.bot:
                    _warn("TelegramBot не инициализировался (tg.bot=None)")
                else:
                    await tg.send_message("✅ Preflight OK. Бот готов к запуску в песочнице.", parse_mode=None)
                    _ok("Telegram: тестовое сообщение отправлено")
            except Exception as e:
                _warn(f"Telegram: ошибка отправки: {e}")

    print("")
    print("=" * 70)
    print("PREFLIGHT: готово")
    print("=" * 70)
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--telegram", action="store_true", help="Отправить тестовое сообщение в Telegram")
    p.add_argument("--history-period", default="1y", help="Период для теста истории (например 5d/1mo/1y)")
    args = p.parse_args()
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())








