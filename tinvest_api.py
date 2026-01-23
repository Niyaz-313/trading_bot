"""
Модуль для работы с T-Invest API (Т-Инвестиции)
Поддерживает песочницу и продакшн
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
import pandas as pd
import os

# Пробуем импортировать официальный SDK
try:
    from tinkoff.invest import Client, RequestError
    from tinkoff.invest.schemas import (
        OrderDirection,
        OrderType,
        Quotation,
        MoneyValue,
    )
    TINVEST_AVAILABLE = True
    TINVEST_SDK_TYPE = 'official'
except ImportError:
    # Пробуем альтернативный пакет tinkoff_invest
    try:
        import importlib

        _ti = importlib.import_module("tinkoff_invest")
        SandboxSession = getattr(_ti, "SandboxSession")
        ProductionSession = getattr(_ti, "ProductionSession")
        TINVEST_AVAILABLE = True
        TINVEST_SDK_TYPE = 'alternative'
    except ImportError:
        TINVEST_AVAILABLE = False
        TINVEST_SDK_TYPE = None
        logging.warning("T-Invest API SDK не установлен. Установите: pip install tinkoff-invest")

from config import TINVEST_TOKEN, TINVEST_SANDBOX, TINVEST_ACCOUNT_ID, TINVEST_GRPC_TARGET

logger = logging.getLogger(__name__)


class TInvestAPI:
    """Класс для работы с T-Invest API"""

    # Алиасы тикеров (часто меняются после корпоративных событий/переименований)
    # Пример: после реорганизации Яндекса тикер может отличаться в списке инструментов.
    TICKER_ALIASES = {
        "YNDX": "YDEX",  # запасной вариант
    }
    # Маппинг для валютных пар: в позициях может быть без подчеркивания, в SYMBOLS - с подчеркиванием
    CURRENCY_TICKER_MAP = {
        "PLTRUBTOM": "PLTRUB_TOM",
        "PLDRUBTOM": "PLDRUB_TOM",
        "CNYRUBTOM": "CNYRUB_TOM",
        "GLDRUBTOM": "GLDRUB_TOM",
        "SLVRUBTOM": "SLVRUB_TOM",
        "USD000UTSTOM": "USD000UTSTOM",  # без изменений
    }
    # Канонизация тикеров для единообразия в логах/портфеле (обратная карта алиасов)
    CANONICAL_TICKERS = {v: k for k, v in TICKER_ALIASES.items()}
    # Добавляем валютные пары в канонизацию
    for k, v in CURRENCY_TICKER_MAP.items():
        CANONICAL_TICKERS[k] = v
        CANONICAL_TICKERS[v] = v  # Обратная карта

    # ExecutionReportStatus enum mapping (protobuf int -> label)
    # В документации перечислены статусы: FILL/REJECTED/CANCELLED/NEW/PARTIALLYFILL
    # https://developer.tbank.ru/invest/api/sandbox-service-get-sandbox-orders
    EXEC_STATUS_MAP = {
        0: "UNSPECIFIED",
        1: "FILL",
        2: "REJECTED",
        3: "CANCELLED",
        4: "NEW",
        5: "PARTIALLYFILL",
    }
    
    def __init__(self, sandbox: bool = True):
        """
        Инициализация T-Invest API
        
        Args:
            sandbox: Использовать песочницу (True) или продакшн (False)
        """
        self.sandbox = sandbox
        self.token = TINVEST_TOKEN
        self.account_id = TINVEST_ACCOUNT_ID
        # ВАЖНО: `tinkoff.invest.Client` закрывает gRPC-канал после `with Client(...) as client:`.
        # Если хранить один Client и многократно использовать `with self.client as client:`,
        # на втором вызове получим: "Cannot invoke RPC on closed channel!".
        # Поэтому для official SDK мы создаём новый Client на каждый запрос.
        self.client = None  # None = не настроено; True = official SDK готов (см. ниже); session = alternative SDK
        self._target = None
        self._did_sandbox_pay_in = False
        
        # Проверяем наличие SDK
        if not TINVEST_AVAILABLE:
            logger.warning("T-Invest API SDK не установлен. Установите: pip install tinkoff-invest")
            self.client = None
            return
        
        # Проверяем наличие токена
        token_str = str(self.token).strip() if self.token else ''
        if not self.token or not token_str:
            logger.warning("T-Invest API токен не настроен. Установите TINVEST_TOKEN в .env файле")
            self.client = None
            return
        
        # Проверяем, что токен не примерный
        token_lower = token_str.lower()
        if 'your_token' in token_lower or 'example' in token_lower or 'your_tinvest' in token_lower:
            logger.warning("T-Invest API токен содержит примерное значение. Установите реальный токен в .env")
            self.client = None
            return
        
        # Инициализируем клиент в зависимости от типа SDK
        try:
            if TINVEST_SDK_TYPE == 'official':
                # Официальный SDK использует параметр 'target' для выбора окружения
                if sandbox:
                    # allow explicit override (useful when DNS/hosts change)
                    if TINVEST_GRPC_TARGET:
                        self._target = TINVEST_GRPC_TARGET
                    else:
                        try:
                            from tinkoff.invest.constants import INVEST_GRPC_API_SANDBOX
                            self._target = INVEST_GRPC_API_SANDBOX
                        except ImportError:
                            # актуальный домен T‑Bank (см. docs url_difference)
                            self._target = 'sandbox-invest-public-api.tbank.ru:443'
                else:
                    self._target = None

                # маркер "настроено" (сам Client создаём лениво на каждый вызов)
                self.client = True
                logger.info(f"✓ Подключение к T-Invest API установлено (sandbox={sandbox}, SDK: official)")

                # Для песочницы обеспечиваем наличие account_id (создаем sandbox-account при необходимости)
                try:
                    self._ensure_account_id()
                except Exception as e:
                    logger.warning(f"Не удалось инициализировать account_id: {e}")
            elif TINVEST_SDK_TYPE == 'alternative':
                if sandbox:
                    self.client = SandboxSession(token=self.token)
                else:
                    self.client = ProductionSession(token=self.token)
                logger.info(f"✓ Подключение к T-Invest API установлено (sandbox={sandbox}, SDK: alternative)")
            else:
                logger.error("Неизвестный тип SDK")
                self.client = None
        except Exception as e:
            logger.error(f"Ошибка подключения к T-Invest API: {e}", exc_info=True)
            self.client = None

    def _create_official_client(self) -> Optional["Client"]:
        """Создать новый Client для official SDK."""
        if not self.client or TINVEST_SDK_TYPE != "official":
            return None
        if self._target:
            return Client(token=self.token, target=self._target)
        return Client(token=self.token)

    @staticmethod
    def _call_first(obj, method_names: list[str]):
        """Вернуть первый существующий метод из списка имен."""
        for name in method_names:
            if hasattr(obj, name):
                return getattr(obj, name)
        return None

    def _get_accounts(self, client):
        """Получить список аккаунтов (sandbox-aware)."""
        if self.sandbox:
            sb = getattr(client, "sandbox", None)
            if sb is not None:
                fn = self._call_first(sb, ["get_sandbox_accounts", "get_accounts", "sandbox_get_accounts"])
                if fn:
                    return fn()
        # fallback
        return client.users.get_accounts()

    def _get_portfolio(self, client, account_id: str):
        """Получить портфель (sandbox-aware)."""
        if self.sandbox:
            sb = getattr(client, "sandbox", None)
            if sb is not None:
                fn = self._call_first(sb, ["get_sandbox_portfolio", "get_portfolio", "sandbox_get_portfolio"])
                if fn:
                    return fn(account_id=account_id)
        return client.operations.get_portfolio(account_id=account_id)

    def _get_positions_resp(self, client, account_id: str):
        """Получить позиции (sandbox-aware)."""
        if self.sandbox:
            sb = getattr(client, "sandbox", None)
            if sb is not None:
                fn = self._call_first(sb, ["get_sandbox_positions", "get_positions", "sandbox_get_positions"])
                if fn:
                    return fn(account_id=account_id)
        return client.operations.get_positions(account_id=account_id)

    def _get_orders_resp(self, client, account_id: str):
        """Получить активные заявки (sandbox-aware)."""
        if self.sandbox:
            sb = getattr(client, "sandbox", None)
            if sb is not None:
                fn = self._call_first(sb, ["get_sandbox_orders", "get_orders", "sandbox_get_orders"])
                if fn:
                    return fn(account_id=account_id)
        return client.orders.get_orders(account_id=account_id)

    def _get_order_state_resp(self, client, account_id: str, order_id: str):
        """Получить статус заявки (sandbox-aware)."""
        if self.sandbox:
            sb = getattr(client, "sandbox", None)
            if sb is not None:
                fn = self._call_first(sb, ["get_sandbox_order_state", "get_order_state", "sandbox_get_order_state"])
                if fn:
                    return fn(account_id=account_id, order_id=order_id)
        # production
        return client.orders.get_order_state(account_id=account_id, order_id=order_id)

    def _get_operations_resp(self, client, account_id: str, from_dt: datetime, to_dt: datetime):
        """Получить операции (sandbox-aware)."""
        if self.sandbox:
            sb = getattr(client, "sandbox", None)
            if sb is not None:
                fn = self._call_first(sb, ["get_sandbox_operations", "get_operations", "sandbox_get_operations"])
                if fn:
                    # В SDK параметры могут называться from_/to или from/to.
                    try:
                        return fn(account_id=account_id, from_=from_dt, to=to_dt)
                    except TypeError:
                        return fn(account_id=account_id, from_dt=from_dt, to_dt=to_dt)
        # production
        return client.operations.get_operations(account_id=account_id, from_=from_dt, to=to_dt)

    def _sandbox_pay_in(self, client, account_id: str, amount_mv: MoneyValue):
        """Пополнить песочницу (sandbox-aware)."""
        sb = getattr(client, "sandbox", None)
        if sb is None:
            raise AttributeError("sandbox service is not available")

        # По документации метод называется SandboxPayIn (в SDK обычно sandbox_pay_in)
        # https://developer.tbank.ru/invest/api/sandbox-service-sandbox-pay-in
        fn = self._call_first(sb, ["sandbox_pay_in", "pay_in", "pay_in_sandbox"])
        if not fn:
            raise AttributeError("'SandboxService' has no sandbox_pay_in/pay_in/pay_in_sandbox")
        return fn(account_id=account_id, amount=amount_mv)

    def _post_order(self, client, account_id: str, figi: str, qty: int, direction, order_type, price: Optional[Quotation] = None):
        """Выставить заявку (sandbox-aware)."""
        if self.sandbox:
            sb = getattr(client, "sandbox", None)
            if sb is not None:
                fn = self._call_first(sb, ["post_sandbox_order", "post_order", "sandbox_post_order"])
                if fn:
                    # ВАЖНО: Для sandbox API параметр должен называться "quantity" и быть целым числом (количество лотов)
                    # Убеждаемся, что qty - это целое число >= 1
                    qty_int = int(qty) if qty > 0 else 1
                    qty_int = max(1, qty_int)
                    
                    kwargs = dict(
                        figi=str(figi).strip(),
                        quantity=qty_int,
                        direction=direction,
                        account_id=str(account_id).strip(),
                        order_type=order_type,
                    )
                    if price is not None:
                        kwargs["price"] = price
                    
                    # Детальное логирование параметров для диагностики
                    logger.debug(f"PostSandboxOrder параметры: figi={kwargs['figi']}, quantity={kwargs['quantity']}, direction={direction}, account_id={kwargs['account_id']}, order_type={order_type}")
                    
                    try:
                        return fn(**kwargs)
                    except Exception as e:
                        # Дополнительное логирование при ошибке
                        logger.error(f"Ошибка при вызове PostSandboxOrder: figi={kwargs['figi']}, quantity={kwargs['quantity']}, direction={direction}, account_id={kwargs['account_id']}, error={e}")
                        raise
        # production
        kwargs = dict(
            figi=figi,
            quantity=qty,
            direction=direction,
            account_id=account_id,
            order_type=order_type,
        )
        if price is not None:
            kwargs["price"] = price
        return client.orders.post_order(**kwargs)

    def _cancel_order(self, client, account_id: str, order_id: str):
        """Отменить заявку (sandbox-aware)."""
        if self.sandbox:
            sb = getattr(client, "sandbox", None)
            if sb is not None:
                fn = self._call_first(sb, ["cancel_sandbox_order", "cancel_order", "sandbox_cancel_order"])
                if fn:
                    return fn(account_id=account_id, order_id=order_id)
        return client.orders.cancel_order(account_id=account_id, order_id=order_id)

    def _ensure_account_id(self) -> Optional[str]:
        """
        Убедиться, что account_id существует.

        В sandbox аккаунт может отсутствовать — тогда создаём через sandbox.open_sandbox_account().
        """
        if not self.client or TINVEST_SDK_TYPE != "official":
            return self.account_id or None

        if self.account_id:
            return self.account_id

        temp = self._create_official_client()
        if temp is None:
            return None

        with temp as client:
            accounts_response = self._get_accounts(client)
            accounts = getattr(accounts_response, "accounts", None) or []
            if accounts:
                # Если аккаунтов несколько, выбираем "самый активный" по размеру портфеля.
                # Иначе можем смотреть пустой account_id, пока активный счет другой.
                if len(accounts) == 1:
                    self.account_id = accounts[0].id
                    # ВАЖНО: не пополняем существующий аккаунт автоматически (это искажает статистику).
                    return self.account_id

                best_id = None
                best_value = -1.0
                debug = []
                for acc in accounts:
                    acc_id = getattr(acc, "id", None)
                    if not acc_id:
                        continue
                    try:
                        pf = self._get_portfolio(client, account_id=acc_id)
                        val = self._money_value_to_float(getattr(pf, "total_amount_portfolio", None))
                    except Exception:
                        val = 0.0
                    debug.append((acc_id, val))
                    if val > best_value:
                        best_value = val
                        best_id = acc_id

                if debug:
                    try:
                        logger.info(
                            "Sandbox accounts (auto-pick by portfolio_value): "
                            + ", ".join([f"{aid}:{v:.2f}" for aid, v in debug])
                        )
                    except Exception:
                        pass

                self.account_id = best_id or accounts[0].id
                # ВАЖНО: не пополняем существующий аккаунт автоматически (это искажает статистику).
                return self.account_id

            if not self.sandbox:
                return None

            # sandbox: создаём аккаунт
            opened = client.sandbox.open_sandbox_account()
            new_id = getattr(opened, "account_id", None) or getattr(opened, "accountId", None)
            if new_id:
                self.account_id = new_id

            # Разрешаем пополнение ТОЛЬКО для только что созданного аккаунта (если пользователь включил SANDBOX_PAY_IN_RUB).
            self._maybe_sandbox_pay_in(client)

            return self.account_id or None

    def _maybe_sandbox_pay_in(self, client):
        """
        Автопополнение песочницы, если задан SANDBOX_PAY_IN_RUB (делаем один раз за процесс).

        Примечание: вызывается только при создании НОВОГО sandbox-аккаунта,
        чтобы не “подливать” деньги на существующий счёт при каждом запуске и не искажать статистику.
        """
        if not self.sandbox or self._did_sandbox_pay_in:
            return
        pay_in = os.getenv("SANDBOX_PAY_IN_RUB", "").strip()
        if not pay_in or not self.account_id:
            return

        try:
            desired = float(pay_in)
        except Exception:
            return

        if desired <= 0:
            return

        # Пополняем только если cash почти 0 (на новом счёте обычно так и есть)
        try:
            portfolio = self._get_portfolio(client, account_id=self.account_id)
            cash = self._money_value_to_float(getattr(portfolio, "total_amount_currencies", None))
        except Exception:
            cash = 0.0

        if cash >= desired * 0.5:
            self._did_sandbox_pay_in = True
            return

        mv = MoneyValue(currency="rub", units=int(desired), nano=int((desired - int(desired)) * 1e9))
        self._sandbox_pay_in(client, account_id=self.account_id, amount_mv=mv)
        self._did_sandbox_pay_in = True
        logger.info(f"✓ Sandbox пополнен: +{desired:.2f} RUB")
    
    def _quotation_to_float(self, quotation) -> float:
        """Преобразовать Quotation в float"""
        if not TINVEST_AVAILABLE:
            return 0.0
        if hasattr(quotation, 'units') and hasattr(quotation, 'nano'):
            return float(quotation.units) + float(quotation.nano) / 1e9
        return 0.0

    @staticmethod
    def _to_float_any(x) -> float:
        """
        Безопасное преобразование разных типов "количества" в float.

        В разных ответах SDK количество может быть:
        - Quotation (units/nano)
        - int/float
        - str
        """
        if x is None:
            return 0.0
        if hasattr(x, "units") and hasattr(x, "nano"):
            try:
                return float(x.units) + float(x.nano) / 1e9
            except Exception:
                return 0.0
        if isinstance(x, (int, float)):
            try:
                return float(x)
            except Exception:
                return 0.0
        try:
            return float(str(x))
        except Exception:
            return 0.0
    
    def _money_value_to_float(self, money: MoneyValue) -> float:
        """Преобразовать MoneyValue в float"""
        if hasattr(money, 'units') and hasattr(money, 'nano'):
            return float(money.units) + float(money.nano) / 1e9
        return 0.0
    
    def get_account_info(self) -> Dict:
        """Получить информацию о счете"""
        if not self.client:
            return {'equity': 10000, 'cash': 10000, 'buying_power': 10000, 'portfolio_value': 10000}
        
        try:
            if TINVEST_SDK_TYPE != "official":
                return {'equity': 10000, 'cash': 10000, 'buying_power': 10000, 'portfolio_value': 10000}

            account_id = self._ensure_account_id()
            if not account_id:
                logger.warning("Счет не найден")
                return {'equity': 10000, 'cash': 10000, 'buying_power': 10000, 'portfolio_value': 10000}

            with self._create_official_client() as client:
                # ВАЖНО: здесь больше не делаем автопополнение, чтобы не искажать статистику при каждом запуске.
                portfolio = self._get_portfolio(client, account_id=account_id)
                
                total_amount = self._money_value_to_float(portfolio.total_amount_portfolio)
                total_amount_currencies = self._money_value_to_float(portfolio.total_amount_currencies)
                total_amount_bonds = self._money_value_to_float(portfolio.total_amount_bonds)
                total_amount_shares = self._money_value_to_float(portfolio.total_amount_shares)
                
                return {
                    'equity': total_amount,
                    'cash': total_amount_currencies,
                    'buying_power': total_amount_currencies,
                    'portfolio_value': total_amount,
                    'bonds': total_amount_bonds,
                    'shares': total_amount_shares,
                    'account_id': account_id,
                    'currency': 'RUB'
                }
        except Exception as e:
            logger.error(f"Ошибка получения информации о счете: {e}", exc_info=True)
            return {'equity': 10000, 'cash': 10000, 'buying_power': 10000, 'portfolio_value': 10000}
    
    def get_positions(self) -> List[Dict]:
        """Получить список открытых позиций"""
        if not self.client:
            return []

        try:
            if TINVEST_SDK_TYPE != "official":
                return []

            account_id = self._ensure_account_id()
            if not account_id:
                return []

            with self._create_official_client() as client:
                # Быстрый маппинг figi -> ticker/lot через списки всех типов инструментов
                figi_to_meta = {}
                try:
                    # 1) Акции
                    shares_response = client.instruments.shares()
                    for sh in getattr(shares_response, "instruments", []) or []:
                        figi_to_meta[str(sh.figi)] = {"ticker": str(sh.ticker), "lot": int(getattr(sh, "lot", 1) or 1)}
                except Exception:
                    pass
                
                try:
                    # 2) ETF (включая валютные и металлы)
                    etfs_response = client.instruments.etfs()
                    for etf in getattr(etfs_response, "instruments", []) or []:
                        figi = str(etf.figi)
                        if figi not in figi_to_meta:  # Не перезаписываем, если уже есть в акциях
                            figi_to_meta[figi] = {"ticker": str(etf.ticker), "lot": int(getattr(etf, "lot", 1) or 1)}
                except Exception:
                    pass
                
                try:
                    # 3) Валюты
                    currencies_response = client.instruments.currencies()
                    for curr in getattr(currencies_response, "instruments", []) or []:
                        figi = str(curr.figi)
                        if figi not in figi_to_meta:  # Не перезаписываем, если уже есть
                            figi_to_meta[figi] = {"ticker": str(curr.ticker), "lot": int(getattr(curr, "lot", 1) or 1)}
                except Exception:
                    pass
                
                try:
                    # 4) Облигации
                    bonds_response = client.instruments.bonds()
                    for bond in getattr(bonds_response, "instruments", []) or []:
                        figi = str(bond.figi)
                        if figi not in figi_to_meta:  # Не перезаписываем, если уже есть
                            figi_to_meta[figi] = {"ticker": str(bond.ticker), "lot": int(getattr(bond, "lot", 1) or 1)}
                except Exception:
                    pass

                # Портфель (нужен для средней цены входа и иногда для текущей цены/кол-ва)
                pf = None
                pf_map: dict[str, dict] = {}
                try:
                    pf = self._get_portfolio(client, account_id=account_id)
                    for pp in list(getattr(pf, "positions", None) or []):
                        figi = getattr(pp, "figi", None)
                        if not figi:
                            continue
                        avg_mv = getattr(pp, "average_position_price", None)
                        if avg_mv is None:
                            avg_mv = getattr(pp, "average_position_price_fifo", None)
                        avg_entry = self._money_value_to_float(avg_mv) if avg_mv is not None else 0.0

                        cp_mv = getattr(pp, "current_price", None)
                        cp = self._money_value_to_float(cp_mv) if cp_mv is not None else 0.0

                        ql = getattr(pp, "quantity_lots", None)
                        qty_lots = int(self._to_float_any(ql)) if ql is not None else 0

                        q = getattr(pp, "quantity", None)
                        qty_shares = float(self._to_float_any(q)) if q is not None else 0.0

                        pf_map[str(figi)] = {
                            "avg_entry_price": float(avg_entry),
                            "current_price": float(cp),
                            "qty_lots": int(qty_lots),
                            "qty_shares": float(qty_shares),
                        }
                except Exception:
                    pf = None
                    pf_map = {}

                # Получаем позиции
                positions_response = self._get_positions_resp(client, account_id=account_id)

                result: list[Dict] = []
                securities = list(getattr(positions_response, "securities", None) or [])

                # Fallback: иногда в песочнице бумаги видны в portfolio, но не в positions
                if not securities:
                    try:
                        portfolio = self._get_portfolio(client, account_id=account_id)
                        securities = list(getattr(portfolio, "positions", None) or [])
                    except Exception:
                        securities = []

                for position in securities:
                    figi = getattr(position, "figi", None)
                    if not figi:
                        continue

                    meta = figi_to_meta.get(str(figi), {})
                    ticker = meta.get("ticker") or None
                    lot_from_meta = meta.get("lot")
                    
                    # Если тикер не найден в meta, пытаемся найти его через API (используем текущий client)
                    if not ticker:
                        try:
                            # Пробуем найти в валютах (часто для валютных инструментов)
                            try:
                                resp = client.instruments.currencies()
                                for it in getattr(resp, "instruments", []) or []:
                                    if str(getattr(it, "figi", "")).strip().upper() == str(figi).strip().upper():
                                        ticker = str(getattr(it, "ticker", "")).strip().upper()
                                        if not lot_from_meta:
                                            lot_from_meta = int(getattr(it, "lot", 1) or 1)
                                        break
                            except Exception:
                                pass
                            
                            # Пробуем найти в ETF
                            if not ticker:
                                try:
                                    resp = client.instruments.etfs()
                                    for it in getattr(resp, "instruments", []) or []:
                                        if str(getattr(it, "figi", "")).strip().upper() == str(figi).strip().upper():
                                            ticker = str(getattr(it, "ticker", "")).strip().upper()
                                            if not lot_from_meta:
                                                lot_from_meta = int(getattr(it, "lot", 1) or 1)
                                            break
                                except Exception:
                                    pass
                            
                            # Пробуем найти в акциях
                            if not ticker:
                                try:
                                    resp = client.instruments.shares()
                                    for it in getattr(resp, "instruments", []) or []:
                                        if str(getattr(it, "figi", "")).strip().upper() == str(figi).strip().upper():
                                            ticker = str(getattr(it, "ticker", "")).strip().upper()
                                            if not lot_from_meta:
                                                lot_from_meta = int(getattr(it, "lot", 1) or 1)
                                            break
                                except Exception:
                                    pass
                            
                            # Пробуем найти в облигациях
                            if not ticker:
                                try:
                                    resp = client.instruments.bonds()
                                    for it in getattr(resp, "instruments", []) or []:
                                        if str(getattr(it, "figi", "")).strip().upper() == str(figi).strip().upper():
                                            ticker = str(getattr(it, "ticker", "")).strip().upper()
                                            if not lot_from_meta:
                                                lot_from_meta = int(getattr(it, "lot", 1) or 1)
                                            break
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    
                    # Если тикер всё ещё не найден, используем FIGI как fallback
                    if not ticker:
                        ticker = str(figi)
                    
                    # канонизируем тикер (например, YDEX -> YNDX), чтобы совпадал с SYMBOLS и логами
                    try:
                        ticker = self.CANONICAL_TICKERS.get(str(ticker), str(ticker))
                    except Exception:
                        ticker = str(ticker)
                    
                    # Получаем lot из meta или из найденного инструмента
                    lot = int(lot_from_meta or 1)
                    lot = max(1, lot)

                    # --- Количество ---
                    # В GetSandboxPortfolio (portfolio.positions) обычно:
                    # - quantity_lots: int
                    # - quantity: Quotation (акции/штуки)
                    # В GetSandboxPositions (operations.get_positions.securities) обычно:
                    # - balance: Quotation (акции/штуки)
                    qty_lots = None
                    qty_shares = None

                    if hasattr(position, "quantity_lots"):
                        ql = getattr(position, "quantity_lots", None)
                        ql_f = self._to_float_any(ql)
                        if ql_f > 0:
                            qty_lots = int(ql_f)

                    if qty_lots is None and hasattr(position, "balance"):
                        bal = getattr(position, "balance", None)
                        bal_f = self._to_float_any(bal)
                        if bal_f > 0:
                            qty_shares = float(bal_f)
                            qty_lots = int(qty_shares // lot)

                    if qty_shares is None and hasattr(position, "quantity"):
                        q = getattr(position, "quantity", None)
                        q_f = self._to_float_any(q)
                        if q_f > 0:
                            qty_shares = float(q_f)
                            if qty_lots is None:
                                qty_lots = int(qty_shares // lot)

                    if qty_lots is None or qty_lots <= 0:
                        continue
                    if qty_shares is None:
                        qty_shares = float(qty_lots) * float(lot)

                    # Получаем текущую цену
                    current_price = 0.0
                    try:
                        # если в portfolio есть текущая цена — используем её
                        cp_mv = getattr(position, "current_price", None)
                        if cp_mv is not None:
                            current_price = self._money_value_to_float(cp_mv)
                        else:
                            last_prices_response = client.market_data.get_last_prices(figi=[figi])
                            if last_prices_response.last_prices:
                                current_price = self._quotation_to_float(last_prices_response.last_prices[0].price)
                    except Exception:
                        current_price = 0.0

                    # Средняя цена входа (покупная) из portfolio, если доступна
                    avg_entry_price = 0.0
                    pf_meta = pf_map.get(str(figi), {})
                    if pf_meta:
                        avg_entry_price = float(pf_meta.get("avg_entry_price", 0.0) or 0.0)
                        # если current_price не удалось получить — попробуем взять из portfolio
                        if not current_price:
                            current_price = float(pf_meta.get("current_price", 0.0) or 0.0)

                    result.append({
                        'figi': figi,
                        'symbol': ticker,
                        'qty': qty_lots,  # lots
                        'qty_lots': qty_lots,
                        'qty_shares': qty_shares,
                        'lot': lot,
                        'avg_entry_price': avg_entry_price,
                        'current_price': current_price,
                        'market_value': current_price * qty_shares,
                        'unrealized_pl': 0.0,
                        'unrealized_plpc': 0.0
                    })

                # Диагностика: если общая стоимость акций > 0, но позиций не нашли — значит парсинг не попал в нужные поля.
                try:
                    if pf is None:
                        pf = self._get_portfolio(client, account_id=account_id)
                    shares_total = self._money_value_to_float(getattr(pf, "total_amount_shares", None))
                    pf_positions_count = len(list(getattr(pf, "positions", None) or []))
                except Exception:
                    shares_total = 0.0
                    pf_positions_count = 0

                logger.info(
                    f"Позиции: найдено {len(result)} (account_id={account_id}, sandbox={self.sandbox}); "
                    f"portfolio_shares_total={shares_total:.2f}, portfolio_positions={pf_positions_count}"
                )
                return result
        except Exception as e:
            logger.error(f"Ошибка получения позиций: {e}", exc_info=True)
            return []

    def get_open_orders(self) -> List[Dict]:
        """Получить список активных заявок (для отображения в Telegram)."""
        if not self.client or TINVEST_SDK_TYPE != "official":
            return []

    def get_order_state(self, order_id: str) -> Optional[Dict]:
        """Получить статус конкретной заявки по order_id (полезно, когда orders пуст, но деньги уже изменились)."""
        if not self.client or TINVEST_SDK_TYPE != "official":
            return None
        if not order_id:
            return None

        try:
            account_id = self._ensure_account_id()
            if not account_id:
                return None
            with self._create_official_client() as client:
                st = self._get_order_state_resp(client, account_id=account_id, order_id=order_id)
                status_raw = getattr(st, "execution_report_status", None) or getattr(st, "status", None)
                # status может быть int (enum) или объект enum/строка
                status_code = None
                status_name = ""
                try:
                    status_code = int(status_raw)
                    status_name = self.EXEC_STATUS_MAP.get(status_code, str(status_code))
                except Exception:
                    status_name = str(status_raw) if status_raw is not None else ""
                lots_req = getattr(st, "lots_requested", None)
                if lots_req is None:
                    lots_req = getattr(st, "quantity", None)
                try:
                    qty_lots = int(lots_req) if lots_req is not None else 0
                except Exception:
                    qty_lots = 0
                price_q = getattr(st, "price", None)
                price = self._quotation_to_float(price_q) if price_q is not None else 0.0
                return {
                    "order_id": order_id,
                    "status": status_name,
                    "status_code": status_code,
                    "qty_lots": qty_lots,
                    "price": float(price),
                    "figi": getattr(st, "figi", None) or "",
                    "account_id": account_id,
                }
        except Exception as e:
            logger.error(f"Ошибка получения статуса заявки {order_id}: {e}", exc_info=True)
            return None

    def get_recent_operations(self, limit: int = 10, days: int = 7) -> List[Dict]:
        """Последние операции по счету (sandbox-aware)."""
        if not self.client or TINVEST_SDK_TYPE != "official":
            return []

        try:
            account_id = self._ensure_account_id()
            if not account_id:
                return []
            to_dt = datetime.now(timezone.utc)
            from_dt = to_dt - timedelta(days=int(days))
            with self._create_official_client() as client:
                # figi -> ticker/lot (для читабельности)
                figi_to_meta = {}
                try:
                    shares_response = client.instruments.shares()
                    for sh in getattr(shares_response, "instruments", []) or []:
                        figi_to_meta[str(sh.figi)] = {"ticker": str(sh.ticker), "lot": int(getattr(sh, "lot", 1) or 1)}
                except Exception:
                    figi_to_meta = {}

                resp = self._get_operations_resp(client, account_id=account_id, from_dt=from_dt, to_dt=to_dt)
                ops = list(getattr(resp, "operations", None) or [])
                out: list[Dict] = []
                for op in ops[: max(200, limit * 10)]:
                    dt = getattr(op, "date", None)
                    figi = str(getattr(op, "figi", None) or "")
                    meta = figi_to_meta.get(figi, {})
                    ticker = meta.get("ticker") or ""
                    lot = int(meta.get("lot") or 1)

                    payment = getattr(op, "payment", None)
                    pay = float(self._money_value_to_float(payment)) if payment is not None else 0.0
                    cur = (getattr(payment, "currency", None) if payment is not None else None) or "rub"

                    qty = getattr(op, "quantity", None)
                    if qty is None:
                        qty = getattr(op, "quantity_rest", None)
                    try:
                        qty = int(qty) if qty is not None else None
                    except Exception:
                        qty = None

                    price_q = getattr(op, "price", None)
                    price = self._quotation_to_float(price_q) if price_q is not None else None

                    out.append({
                        "date": dt.isoformat() if hasattr(dt, "isoformat") else str(dt),
                        "type": str(getattr(op, "type", None) or ""),
                        "state": str(getattr(op, "state", None) or ""),
                        "figi": figi,
                        "ticker": ticker,
                        "lot": lot,
                        "quantity": qty,
                        "price": float(price) if price is not None else None,
                        "payment": pay,
                        "currency": str(cur).upper(),
                        "operation_id": str(getattr(op, "id", None) or ""),
                    })
                    if len(out) >= limit:
                        break

                return out
        except Exception as e:
            logger.error(f"Ошибка получения операций: {e}", exc_info=True)
            return []

        try:
            account_id = self._ensure_account_id()
            if not account_id:
                return []

            with self._create_official_client() as client:
                # figi -> ticker/lot
                figi_to_meta = {}
                try:
                    shares_response = client.instruments.shares()
                    for sh in getattr(shares_response, "instruments", []) or []:
                        figi_to_meta[str(sh.figi)] = {"ticker": str(sh.ticker), "lot": int(getattr(sh, "lot", 1) or 1)}
                except Exception:
                    figi_to_meta = {}

                resp = self._get_orders_resp(client, account_id=account_id)
                orders = list(getattr(resp, "orders", None) or [])

                out: list[Dict] = []
                for o in orders:
                    figi = getattr(o, "figi", None)
                    if not figi:
                        continue
                    meta = figi_to_meta.get(str(figi), {})
                    ticker = meta.get("ticker") or str(figi)
                    lot = int(meta.get("lot") or 1)

                    lots_req = getattr(o, "lots_requested", None)
                    if lots_req is None:
                        lots_req = getattr(o, "quantity", None)
                    try:
                        qty_lots = int(lots_req) if lots_req is not None else 0
                    except Exception:
                        qty_lots = 0

                    direction = getattr(o, "direction", None)
                    order_type = getattr(o, "order_type", None) or getattr(o, "type", None)
                    status = getattr(o, "execution_report_status", None) or getattr(o, "status", None)
                    price_q = getattr(o, "price", None)
                    price = self._quotation_to_float(price_q) if price_q is not None else 0.0

                    out.append({
                        "order_id": getattr(o, "order_id", None) or getattr(o, "id", None) or "",
                        "figi": figi,
                        "symbol": ticker,
                        "qty_lots": qty_lots,
                        "lot": lot,
                        "side": str(direction) if direction is not None else "",
                        "order_type": str(order_type) if order_type is not None else "",
                        "status": str(status) if status is not None else "",
                        "price": float(price),
                    })

                logger.info(f"Активные заявки: найдено {len(out)} (account_id={account_id}, sandbox={self.sandbox})")
                return out
        except Exception as e:
            logger.error(f"Ошибка получения активных заявок: {e}", exc_info=True)
            return []
    
    def get_instrument_by_figi(self, figi: str) -> Optional[Dict]:
        """Получить информацию об инструменте по FIGI"""
        if not self.client:
            return None
        
        try:
            if TINVEST_SDK_TYPE != "official":
                return None
            figi_u = str(figi).strip().upper()
            if not figi_u:
                return None

            def _pack(obj, instrument_type: str) -> Dict:
                trading_status = getattr(obj, "trading_status", None)
                api_trade_available = getattr(obj, "api_trade_available_flag", None)
                buy_available = getattr(obj, "buy_available_flag", None)
                sell_available = getattr(obj, "sell_available_flag", None)
                lot = getattr(obj, "lot", 1)
                try:
                    lot_i = int(lot) if lot is not None else 1
                except Exception:
                    lot_i = 1
                lot_i = max(1, lot_i)
                return {
                    "figi": getattr(obj, "figi", "") or "",
                    "ticker": getattr(obj, "ticker", "") or "",
                    "name": getattr(obj, "name", "") or "",
                    "lot": lot_i,
                    "currency": getattr(obj, "currency", "") or "",
                    "instrument_type": str(instrument_type),
                    "trading_status": str(trading_status) if trading_status is not None else "",
                    "api_trade_available_flag": bool(api_trade_available) if api_trade_available is not None else None,
                    "buy_available_flag": bool(buy_available) if buy_available is not None else None,
                    "sell_available_flag": bool(sell_available) if sell_available is not None else None,
                }

            found: Optional[Dict] = None
            with self._create_official_client() as client:
                # 1) Валюты (часто для валютных инструментов)
                try:
                    resp = client.instruments.currencies()
                    for it in getattr(resp, "instruments", []) or []:
                        if str(getattr(it, "figi", "")).strip().upper() == figi_u:
                            found = _pack(it, "currency")
                            break
                except Exception:
                    found = None

                # 2) ETF
                if found is None:
                    try:
                        resp = client.instruments.etfs()
                        for it in getattr(resp, "instruments", []) or []:
                            if str(getattr(it, "figi", "")).strip().upper() == figi_u:
                                found = _pack(it, "etf")
                                break
                    except Exception:
                        found = None

                # 3) Акции
                if found is None:
                    try:
                        resp = client.instruments.shares()
                        for it in getattr(resp, "instruments", []) or []:
                            if str(getattr(it, "figi", "")).strip().upper() == figi_u:
                                found = _pack(it, "share")
                                break
                    except Exception:
                        found = None

                # 4) Облигации
                if found is None:
                    try:
                        resp = client.instruments.bonds()
                        for it in getattr(resp, "instruments", []) or []:
                            if str(getattr(it, "figi", "")).strip().upper() == figi_u:
                                found = _pack(it, "bond")
                                break
                    except Exception:
                        found = None

            return found
        except Exception as e:
            logger.error(f"Ошибка получения инструмента по FIGI {figi}: {e}")
            return None

    def get_instrument_details(self, symbol: str) -> Optional[Dict]:
        """
        Получить информацию об инструменте по тикеру или FIGI.
        Алиас для get_instrument_by_ticker для совместимости с broker_api.
        """
        return self.get_instrument_by_ticker(symbol)
    
    def get_instrument_by_ticker(self, ticker: str) -> Optional[Dict]:
        """Получить информацию об инструменте по тикеру"""
        if not self.client:
            return None
        
        try:
            if TINVEST_SDK_TYPE != "official":
                return None
            ticker_u = str(ticker).strip().upper()
            if not ticker_u:
                return None
            
            # Если это FIGI (начинается с BBG и длинный), используем get_instrument_by_figi
            if ticker_u.startswith("BBG") and len(ticker_u) > 10:
                return self.get_instrument_by_figi(ticker_u)

            # Локальный кэш (внутри процесса), чтобы не дёргать instruments.*() на каждый тикер в каждом цикле.
            cache = getattr(self, "_ticker_cache", None)
            if cache is None:
                cache = {}
                setattr(self, "_ticker_cache", cache)
            if ticker_u in cache:
                return cache.get(ticker_u)

            ticker_variants = [ticker_u]
            alias = self.TICKER_ALIASES.get(ticker_u)
            if alias and alias not in ticker_variants:
                ticker_variants.append(str(alias).strip().upper())

            def _pack(obj, instrument_type: str) -> Dict:
                trading_status = getattr(obj, "trading_status", None)
                api_trade_available = getattr(obj, "api_trade_available_flag", None)
                buy_available = getattr(obj, "buy_available_flag", None)
                sell_available = getattr(obj, "sell_available_flag", None)
                lot = getattr(obj, "lot", 1)
                try:
                    lot_i = int(lot) if lot is not None else 1
                except Exception:
                    lot_i = 1
                lot_i = max(1, lot_i)
                return {
                    "figi": getattr(obj, "figi", "") or "",
                    "ticker": getattr(obj, "ticker", "") or "",
                    "name": getattr(obj, "name", "") or "",
                    "lot": lot_i,
                    "currency": getattr(obj, "currency", "") or "",
                    "instrument_type": str(instrument_type),
                    "trading_status": str(trading_status) if trading_status is not None else "",
                    "api_trade_available_flag": bool(api_trade_available) if api_trade_available is not None else None,
                    "buy_available_flag": bool(buy_available) if buy_available is not None else None,
                    "sell_available_flag": bool(sell_available) if sell_available is not None else None,
                }

            found: Optional[Dict] = None
            with self._create_official_client() as client:
                # 1) Акции
                try:
                    resp = client.instruments.shares()
                    for it in getattr(resp, "instruments", []) or []:
                        if str(getattr(it, "ticker", "")).strip().upper() in ticker_variants:
                            found = _pack(it, "share")
                            break
                except Exception:
                    found = None

                # 2) ETF (в т.ч. “валютные” и “золото”)
                if found is None:
                    try:
                        resp = client.instruments.etfs()
                        for it in getattr(resp, "instruments", []) or []:
                            if str(getattr(it, "ticker", "")).strip().upper() in ticker_variants:
                                found = _pack(it, "etf")
                                break
                    except Exception:
                        found = None

                # 3) Валюты (MOEX currency)
                if found is None:
                    try:
                        resp = client.instruments.currencies()
                        for it in getattr(resp, "instruments", []) or []:
                            if str(getattr(it, "ticker", "")).strip().upper() in ticker_variants:
                                found = _pack(it, "currency")
                                break
                    except Exception:
                        found = None

                # 4) Облигации (на всякий случай — иногда пользователи добавляют их в SYMBOLS)
                if found is None:
                    try:
                        resp = client.instruments.bonds()
                        for it in getattr(resp, "instruments", []) or []:
                            if str(getattr(it, "ticker", "")).strip().upper() in ticker_variants:
                                found = _pack(it, "bond")
                                break
                    except Exception:
                        found = None

            cache[ticker_u] = found
            return found
        except Exception as e:
            logger.error(f"Ошибка поиска инструмента {ticker}: {e}", exc_info=True)
            return None
    
    def get_current_price_by_figi(self, figi: str) -> float:
        """Получить текущую цену по FIGI"""
        if not self.client:
            return 0.0
        
        try:
            if TINVEST_SDK_TYPE != "official":
                return 0.0
            with self._create_official_client() as client:
                last_prices_response = client.market_data.get_last_prices(figi=[figi])
                
                if last_prices_response.last_prices:
                    return self._quotation_to_float(last_prices_response.last_prices[0].price)
                
                return 0.0
        except Exception as e:
            logger.error(f"Ошибка получения цены для {figi}: {e}", exc_info=True)
            return 0.0
    
    def get_current_price(self, symbol: str) -> float:
        """Получить текущую цену акции по тикеру или FIGI"""
        # Поддерживаем как тикер, так и FIGI
        symbol_u = str(symbol).strip().upper()
        if symbol_u.startswith("BBG") and len(symbol_u) > 10:
            # Это FIGI, используем напрямую
            return self.get_current_price_by_figi(symbol_u)
        else:
            # Это тикер, используем get_instrument_by_ticker
            instrument = self.get_instrument_by_ticker(symbol_u)
            if instrument:
                return self.get_current_price_by_figi(instrument['figi'])
        return 0.0
    
    def get_historical_data(self, symbol: str, period: str = '1d', interval: str = '5m') -> pd.DataFrame:
        """Получить исторические данные по акции через T-Invest API"""
        if not self.client:
            logger.warning(f"T-Invest API клиент не инициализирован для {symbol}")
            return pd.DataFrame()
        
        try:
            from datetime import datetime, timedelta

            # --- КЭШ ИСТОРИЧЕСКИХ ДАННЫХ ---
            cache_dir = os.getenv("DATA_CACHE_DIR", "data_cache").strip() or "data_cache"
            cache_refresh = os.getenv("CACHE_REFRESH", "false").lower().strip() == "true"
            cache_subdir = "tinvest_sandbox" if self.sandbox else "tinvest_prod"
            cache_path = os.path.join(cache_dir, cache_subdir, f"candles_{symbol.upper()}_{interval}.csv")

            def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
                if df is None or df.empty:
                    return pd.DataFrame()
                # приводим индекс к datetime без tz
                if not isinstance(df.index, pd.DatetimeIndex):
                    df.index = pd.to_datetime(df.index, errors="coerce")
                if isinstance(df.index, pd.DatetimeIndex) and df.index.tz is not None:
                    df.index = df.index.tz_convert("UTC").tz_localize(None)
                df = df[~df.index.isna()]
                df.sort_index(inplace=True)
                df = df[~df.index.duplicated(keep="first")]
                return df
            
            # Преобразуем period в даты
            now = datetime.now()
            p = str(period or "").strip().lower()

            def _parse_relative(p: str) -> Optional[timedelta]:
                # поддержка форматов: 10d, 48h, 2w, 6mo, 1y
                try:
                    if not p:
                        return None
                    if p.endswith("d") and p[:-1].isdigit():
                        return timedelta(days=int(p[:-1]))
                    if p.endswith("h") and p[:-1].isdigit():
                        return timedelta(hours=int(p[:-1]))
                    if p.endswith("w") and p[:-1].isdigit():
                        return timedelta(days=int(p[:-1]) * 7)
                    # mo / y оставляем как раньше отдельными ветками (там удобнее)
                    return None
                except Exception:
                    return None

            if p == '2024':
                # Для 2024 года
                from_date = datetime(2024, 1, 1)
                to_date = datetime(2024, 12, 31, 23, 59, 59)
                if to_date > now:
                    to_date = now
            elif p == '1y':
                # За последний год от текущей даты
                from_date = now - timedelta(days=365)
                to_date = now
            elif p == '2y':
                # За последние 2 года
                from_date = now - timedelta(days=730)
                to_date = now
            elif p == '3y':
                # За последние 3 года
                from_date = now - timedelta(days=1095)
                to_date = now
            elif p in ('all', 'max'):
                # Максимум доступной истории (чем раньше тем лучше; если данных нет - API вернет пусто)
                from_date = datetime(2018, 1, 1)
                to_date = now
            elif p == '6mo':
                from_date = now - timedelta(days=180)
                to_date = now
            elif p == '3mo':
                from_date = now - timedelta(days=90)
                to_date = now
            elif p == '1mo':
                from_date = now - timedelta(days=30)
                to_date = now
            elif p == '5d':
                from_date = now - timedelta(days=5)
                to_date = now
            else:
                rel = _parse_relative(p)
                if rel is not None:
                    from_date = now - rel
                    to_date = now
                else:
                    # fallback: ранее использовался 2024-01-01, но для live это приводит к огромным запросам.
                    # Берём безопасный дефолт: 30 дней.
                    from_date = now - timedelta(days=30)
                    to_date = now

            # Попытка чтения из кэша (если покрывает нужный период)
            cached_df = pd.DataFrame()
            if (not cache_refresh) and os.path.exists(cache_path):
                try:
                    cached_df = pd.read_csv(cache_path)
                    if "Time" in cached_df.columns:
                        cached_df["Time"] = pd.to_datetime(cached_df["Time"], errors="coerce")
                        cached_df.set_index("Time", inplace=True)
                    cached_df = _normalize_df(cached_df)
                    if not cached_df.empty:
                        # Безопасное преобразование: если это уже datetime, не вызываем to_pydatetime()
                        min_idx = cached_df.index.min()
                        max_idx = cached_df.index.max()
                        try:
                            cached_from = min_idx.to_pydatetime() if hasattr(min_idx, 'to_pydatetime') else min_idx
                            cached_to = max_idx.to_pydatetime() if hasattr(max_idx, 'to_pydatetime') else max_idx
                        except (AttributeError, TypeError):
                            # Если уже datetime или ошибка - используем как есть
                            cached_from = min_idx if isinstance(min_idx, datetime) else min_idx
                            cached_to = max_idx if isinstance(max_idx, datetime) else max_idx
                        if cached_from <= from_date and cached_to >= to_date:
                            logger.info(f"✓ Данные для {symbol} загружены из кэша: {cache_path}")
                            return cached_df.loc[(cached_df.index >= from_date) & (cached_df.index <= to_date)]
                except Exception as e:
                    logger.warning(f"Не удалось прочитать кэш {cache_path}: {e}")
                    cached_df = pd.DataFrame()
            
            # Преобразуем interval в CandleInterval
            if TINVEST_SDK_TYPE == 'official':
                try:
                    from tinkoff.invest.schemas import CandleInterval as CI
                except ImportError:
                    try:
                        from tinkoff.invest.constants import CandleInterval as CI
                    except ImportError:
                        from tinkoff.invest import CandleInterval as CI
                
                interval_map = {
                    '1m': CI.CANDLE_INTERVAL_1_MIN,
                    '5m': CI.CANDLE_INTERVAL_5_MIN,
                    '15m': CI.CANDLE_INTERVAL_15_MIN,
                    '1h': CI.CANDLE_INTERVAL_HOUR,
                    '1d': CI.CANDLE_INTERVAL_DAY,
                }
                candle_interval = interval_map.get(interval, CI.CANDLE_INTERVAL_DAY)
            else:
                # Для альтернативного SDK используем строковые значения
                interval_map = {
                    '1m': 1,
                    '5m': 5,
                    '15m': 15,
                    '1h': 60,
                    '1d': 24,
                }
                candle_interval = interval_map.get(interval, 24)
            
            # Для дневных свечей максимальный период - 1 год, поэтому разбиваем на части если нужно
            all_candles = []
            current_from = from_date
            
            # Работаем с клиентом в зависимости от типа SDK
            if TINVEST_SDK_TYPE == 'official':
                # Лимит окна запроса зависит от интервала свечей.
                # Ошибка 30014 = "The maximum request period for the given candle interval has been exceeded"
                interval_norm = str(interval or "").strip().lower()
                if interval_norm == "1d":
                    max_days_per_request = 365
                elif interval_norm == "1h":
                    max_days_per_request = 30
                elif interval_norm in ("15m", "5m", "1m"):
                    max_days_per_request = 7
                else:
                    max_days_per_request = 7
                
                # Создаем новый клиент для этого запроса, чтобы избежать проблем с закрытым каналом
                # ВАЖНО: получаем instrument внутри того же контекста, чтобы канал не закрывался
                try:
                    # Создаем новый client через фабрику (учитывает TINVEST_GRPC_TARGET)
                    with self._create_official_client() as client:
                        # Получаем инструмент внутри того же контекста
                        instrument = None
                        try:
                            symbol_u = str(symbol).upper()
                            
                            # Если это FIGI (начинается с BBG и длинный), ищем по FIGI
                            if symbol_u.startswith("BBG") and len(symbol_u) > 10:
                                # Поиск по FIGI
                                def _pick_by_figi(resp):
                                    for it in getattr(resp, "instruments", []) or []:
                                        if str(getattr(it, "figi", "")).upper() == symbol_u:
                                            return it
                                    return None
                                
                                picked = None
                                # 1) currencies (часто для валютных инструментов)
                                try:
                                    picked = _pick_by_figi(client.instruments.currencies())
                                except Exception:
                                    picked = None
                                # 2) etfs
                                if picked is None:
                                    try:
                                        picked = _pick_by_figi(client.instruments.etfs())
                                    except Exception:
                                        picked = None
                                # 3) shares
                                if picked is None:
                                    try:
                                        picked = _pick_by_figi(client.instruments.shares())
                                    except Exception:
                                        picked = None
                                # 4) bonds
                                if picked is None:
                                    try:
                                        picked = _pick_by_figi(client.instruments.bonds())
                                    except Exception:
                                        picked = None
                            else:
                                # Поиск по тикеру (как раньше)
                                symbol_variants = [symbol_u]
                                alias = self.TICKER_ALIASES.get(symbol_u)
                                if alias and alias not in symbol_variants:
                                    symbol_variants.append(alias)

                                def _pick_by_ticker(resp):
                                    for it in getattr(resp, "instruments", []) or []:
                                        if str(getattr(it, "ticker", "")).upper() in symbol_variants:
                                            return it
                                    return None

                                picked = None
                                # 1) shares
                                try:
                                    picked = _pick_by_ticker(client.instruments.shares())
                                except Exception:
                                    picked = None
                                # 2) etfs
                                if picked is None:
                                    try:
                                        picked = _pick_by_ticker(client.instruments.etfs())
                                    except Exception:
                                        picked = None
                                # 3) currencies
                                if picked is None:
                                    try:
                                        picked = _pick_by_ticker(client.instruments.currencies())
                                    except Exception:
                                        picked = None
                                # 4) bonds
                                if picked is None:
                                    try:
                                        picked = _pick_by_ticker(client.instruments.bonds())
                                    except Exception:
                                        picked = None

                            if picked is not None:
                                instrument = {
                                    "figi": getattr(picked, "figi", None),
                                    "ticker": getattr(picked, "ticker", None),
                                    "name": getattr(picked, "name", None),
                                    "lot": getattr(picked, "lot", None) or 1,
                                    "currency": getattr(picked, "currency", None),
                                }
                        except Exception as e:
                            logger.error(f"Ошибка поиска инструмента {symbol}: {e}", exc_info=True)
                        
                        if not instrument:
                            logger.warning(f"Инструмент {symbol} не найден")
                            return pd.DataFrame()

                        # Если есть кэш, и он частично покрывает диапазон — догружаем только недостающее.
                        # ВАЖНО: для intraday (m/h) не пытаемся “докачивать древнюю историю”, нам важен текущий lookback.
                        interval_norm = str(interval or "").strip().lower()
                        if not cache_refresh and not cached_df.empty:
                            # Безопасное преобразование: если это уже datetime, не вызываем to_pydatetime()
                            min_idx = cached_df.index.min()
                            max_idx = cached_df.index.max()
                            try:
                                cached_from = min_idx.to_pydatetime() if hasattr(min_idx, 'to_pydatetime') else min_idx
                                cached_to = max_idx.to_pydatetime() if hasattr(max_idx, 'to_pydatetime') else max_idx
                            except (AttributeError, TypeError):
                                cached_from = min_idx if isinstance(min_idx, datetime) else min_idx
                                cached_to = max_idx if isinstance(max_idx, datetime) else max_idx
                            # догружаем только то, чего нет
                            if cached_from <= from_date:
                                # снизу покрыто
                                current_from = max(current_from, cached_to + timedelta(seconds=1))
                            else:
                                if interval_norm == "1d":
                                    # для дневок можно докачивать “старый” диапазон (актуально для backtest/all)
                                    current_from = from_date
                                    to_date_old = min(to_date, cached_from - timedelta(seconds=1))
                                    if current_from < to_date_old:
                                        tmp_from = current_from
                                        while tmp_from < to_date_old:
                                            tmp_to = min(tmp_from + timedelta(days=max_days_per_request), to_date_old)
                                            try:
                                                logger.info(f"Запрос (догрузка) {symbol} {tmp_from.date()} - {tmp_to.date()}")
                                                candles_response = client.market_data.get_candles(
                                                    figi=instrument['figi'],
                                                    from_=tmp_from,
                                                    to=tmp_to,
                                                    interval=candle_interval
                                                )
                                                if candles_response.candles:
                                                    all_candles.extend(candles_response.candles)
                                            except Exception as e:
                                                logger.error(f"Ошибка догрузки {symbol}: {e}", exc_info=True)
                                            tmp_from = tmp_to + timedelta(seconds=1)
                                    current_from = max(cached_to + timedelta(seconds=1), from_date)
                                else:
                                    # intraday: не докачиваем “древнюю” часть, работаем только в рамках lookback
                                    current_from = from_date
                        
                        while current_from < to_date:
                            current_to = min(current_from + timedelta(days=max_days_per_request), to_date)
                            
                            try:
                                logger.info(f"Запрос данных для {symbol} с {current_from.date()} по {current_to.date()}")
                                
                                # Получаем свечи (SDK автоматически преобразует datetime)
                                candles_response = client.market_data.get_candles(
                                    figi=instrument['figi'],
                                    from_=current_from,
                                    to=current_to,
                                    interval=candle_interval
                                )
                                
                                if candles_response.candles:
                                    all_candles.extend(candles_response.candles)
                                    logger.info(f"✓ Получено {len(candles_response.candles)} свечей для {symbol}")
                                else:
                                    logger.warning(f"Нет данных для {symbol} за период {current_from.date()} - {current_to.date()}")
                                
                            except Exception as e:
                                logger.error(f"Ошибка при получении данных с {current_from.date()} по {current_to.date()}: {e}", exc_info=True)
                                # Не прерываем цикл, продолжаем с следующим периодом
                            
                            # Переходим к следующему периоду
                            current_from = current_to + timedelta(seconds=1)
                            
                except Exception as e:
                    logger.error(f"Ошибка при работе с клиентом T-Invest: {e}", exc_info=True)
            else:
                # Альтернативный SDK - используем другой API
                logger.warning(f"Альтернативный SDK не поддерживает получение исторических данных через этот метод")
                logger.warning(f"Используйте официальный SDK или другой способ получения данных")
                return pd.DataFrame()
            
            # ВАЖНО: если новых свечей не пришло (например, праздничные дни),
            # но кэш есть — возвращаем кэш, а не пустоту.
            if not all_candles:
                if (not cache_refresh) and (cached_df is not None) and (not cached_df.empty):
                    try:
                        # Безопасное преобразование
                        max_idx = cached_df.index.max()
                        try:
                            cached_to = max_idx.to_pydatetime() if hasattr(max_idx, 'to_pydatetime') else max_idx
                        except (AttributeError, TypeError):
                            cached_to = max_idx if isinstance(max_idx, datetime) else max_idx
                        effective_to = min(to_date, cached_to)
                        logger.info(f"✓ Новых свечей для {symbol} нет; используем кэш: {cache_path}")
                        return cached_df.loc[(cached_df.index >= from_date) & (cached_df.index <= effective_to)]
                    except Exception:
                        return cached_df

                logger.warning(f"Нет исторических данных для {symbol} за период {from_date.date()} - {to_date.date()}")
                return pd.DataFrame()
            
            # Преобразуем в DataFrame
            data = []
            for candle in all_candles:
                # Преобразуем время свечи в datetime
                if hasattr(candle.time, 'ToDatetime'):
                    candle_time = candle.time.ToDatetime()
                elif hasattr(candle.time, 'seconds'):
                    candle_time = datetime.fromtimestamp(candle.time.seconds + getattr(candle.time, 'nanos', 0) / 1e9)
                elif isinstance(candle.time, datetime):
                    candle_time = candle.time
                else:
                    # Пробуем преобразовать из timestamp
                    try:
                        candle_time = datetime.fromtimestamp(candle.time)
                    except:
                        candle_time = datetime.now()
                
                data.append({
                    'Open': self._quotation_to_float(candle.open),
                    'High': self._quotation_to_float(candle.high),
                    'Low': self._quotation_to_float(candle.low),
                    'Close': self._quotation_to_float(candle.close),
                    'Volume': candle.volume,
                    'Time': candle_time
                })
            
            df = pd.DataFrame(data)
            if df.empty:
                return pd.DataFrame()
            
            df.set_index('Time', inplace=True)
            df.sort_index(inplace=True)
            
            # Удаляем дубликаты (на случай перекрытий)
            df = df[~df.index.duplicated(keep='first')]

            # Сохраняем/обновляем кэш: объединяем с тем, что уже было
            try:
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                df_norm = _normalize_df(df)
                if not cache_refresh and not cached_df.empty:
                    merged = pd.concat([cached_df, df_norm], axis=0)
                    merged = _normalize_df(merged)
                else:
                    merged = df_norm
                # сохраняем с колонкой Time для удобства чтения
                out = merged.copy()
                out.reset_index(inplace=True)
                out.rename(columns={"index": "Time"}, inplace=True)
                if "Time" not in out.columns:
                    out.rename(columns={out.columns[0]: "Time"}, inplace=True)
                out.to_csv(cache_path, index=False, encoding="utf-8-sig")
                logger.info(f"✓ Кэш обновлён: {cache_path} ({len(merged)} строк)")
            except Exception as e:
                logger.warning(f"Не удалось сохранить кэш {cache_path}: {e}")
            
            # Возвращаем объединённые данные (кэш + новые свечи), чтобы не терять историю
            if not cache_refresh and not cached_df.empty:
                merged = pd.concat([cached_df, df], axis=0)
                merged = _normalize_df(merged)
            else:
                merged = _normalize_df(df)

            logger.info(f"✓ Получены исторические данные для {symbol}: {len(merged)} свечей за период {merged.index.min().date()} - {merged.index.max().date()}")
            # Безопасное преобразование индекса в datetime
            if not merged.empty:
                max_idx = merged.index.max()
                try:
                    max_dt = max_idx.to_pydatetime() if hasattr(max_idx, 'to_pydatetime') else max_idx
                except (AttributeError, TypeError):
                    max_dt = max_idx if isinstance(max_idx, datetime) else max_idx
                effective_to = min(to_date, max_dt)
            else:
                effective_to = to_date
            return merged.loc[(merged.index >= from_date) & (merged.index <= effective_to)]
                
        except Exception as e:
            logger.error(f"Ошибка получения исторических данных через T-Invest API для {symbol}: {e}", exc_info=True)
            return pd.DataFrame()
    
    def place_market_order(self, symbol: str, qty: int, side: str) -> Optional[Dict]:
        """Разместить рыночный ордер"""
        if not self.client:
            logger.info(f"СИМУЛЯЦИЯ: {side.upper()} {qty} {symbol}")
            return {'symbol': symbol, 'qty': qty, 'side': side, 'status': 'filled', 'simulated': True}
        
        try:
            if TINVEST_SDK_TYPE != "official":
                logger.error("Размещение ордеров поддерживается только в official SDK")
                return None

            # Поддерживаем как тикер, так и FIGI
            instrument = None
            symbol_u = str(symbol).strip().upper()
            if symbol_u.startswith("BBG") and len(symbol_u) > 10:
                # Это FIGI, используем get_instrument_by_figi
                instrument = self.get_instrument_by_figi(symbol_u)
            else:
                # Это тикер, используем get_instrument_by_ticker (который теперь тоже поддерживает FIGI)
                instrument = self.get_instrument_by_ticker(symbol_u)
            
            if not instrument:
                logger.error(f"Инструмент {symbol} не найден")
                return None
            
            figi = instrument.get('figi', '')
            if not figi:
                logger.error(f"FIGI для инструмента {symbol} не найден")
                return None
            
            # Проверка лота: убеждаемся, что qty кратно лоту
            # ВАЖНО: qty уже должно быть в лотах, а не в штуках
            lot = int(instrument.get("lot", 1) or 1)
            if lot <= 0:
                lot = 1
            
            # Проверяем кратность только если qty не кратно lot
            # Но не блокируем, если qty >= lot - возможно, это правильное значение
            if qty > 0 and lot > 1 and qty % lot != 0:
                # Корректируем только если qty меньше lot или не кратно ему
                corrected_qty = ((qty // lot) + 1) * lot if qty > 0 else lot
                logger.info(f"Количество {qty} не кратно лоту {lot} для {symbol}. Корректируем до {corrected_qty}")
                qty = corrected_qty
            elif qty <= 0:
                # Если qty <= 0, устанавливаем минимум в 1 лот
                logger.warning(f"Некорректное количество {qty} для {symbol}. Устанавливаем минимум 1 лот")
                qty = max(1, lot)
            
            # Получаем account_id
            account_id = self._ensure_account_id()
            if not account_id:
                logger.error("Счет не найден")
                return None
            
            # Проверка торгового статуса через GetTradingStatus (информационная, не блокирующая)
            # ВАЖНО: Не блокируем покупки по этой проверке, так как в sandbox могут быть особенности
            # Полагаемся на реальную ошибку API (30079), а не на предварительную проверку
            try:
                with self._create_official_client() as client:
                    try:
                        status_resp = client.market_data.get_trading_status(figi=figi)
                        if hasattr(status_resp, 'trading_status'):
                            status_value = status_resp.trading_status
                            if hasattr(status_value, 'value'):
                                status_int = int(status_value.value) if status_value.value is not None else 0
                            elif isinstance(status_value, int):
                                status_int = status_value
                            else:
                                status_int = 0
                            
                            # Логируем статус для диагностики, но не блокируем
                            if status_int == 2:
                                logger.debug(f"Торговый статус для {symbol}: {status_int} (NOT_AVAILABLE) - продолжим попытку размещения ордера")
                            elif status_int == 0:
                                logger.debug(f"Торговый статус для {symbol}: {status_int} (UNSPECIFIED) - продолжим попытку размещения ордера")
                            elif status_int == 1:
                                logger.debug(f"Торговый статус для {symbol}: {status_int} (NORMAL_TRADING)")
                    except Exception as status_e:
                        # Если GetTradingStatus недоступен - это нормально, продолжаем
                        logger.debug(f"Не удалось проверить торговый статус для {symbol}: {status_e}")
            except Exception:
                pass
            
            # Детальное логирование перед размещением ордера
            logger.debug(f"Размещение ордера: symbol={symbol}, figi={figi}, qty={qty}, side={side}, account_id={account_id}, lot={lot}")
            
            with self._create_official_client() as client:
                order = self._post_order(
                    client,
                    account_id=account_id,
                    figi=figi,
                    qty=qty,
                    direction=OrderDirection.ORDER_DIRECTION_BUY if side == 'buy' else OrderDirection.ORDER_DIRECTION_SELL,
                    order_type=OrderType.ORDER_TYPE_MARKET,
                    price=None,
                )
                
                logger.info(f"Ордер размещен: {side.upper()} {qty} {symbol} (order_id: {order.order_id})")
                return {
                    'order_id': order.order_id,
                    'symbol': symbol,
                    'qty': qty,
                    'side': side,
                    'status': 'new',
                    'figi': instrument['figi'],
                    'account_id': account_id,
                }
        except RequestError as e:
            error_msg = str(e)
            error_code = None
            error_details = {}
            
            # Пытаемся извлечь код ошибки из метаданных
            if hasattr(e, 'metadata'):
                if hasattr(e.metadata, 'message'):
                    error_msg = e.metadata.message
                # Извлекаем код ошибки из строки ошибки или metadata
                error_code_str = str(e)
                if '30034' in error_code_str:
                    error_code = '30034'
                elif '30079' in error_code_str:
                    error_code = '30079'
                elif hasattr(e.metadata, 'tracking_id'):
                    error_code = str(e.metadata.tracking_id)
            
            # Собираем детальную информацию об ошибке
            error_details = {
                'error_type': 'RequestError',
                'error_code': error_code,
                'error_message': error_msg,
                'symbol': symbol,
                'figi': figi if 'figi' in locals() else None,
                'qty': qty,
                'side': side,
                'lot': lot if 'lot' in locals() else None,
                'account_id': account_id if 'account_id' in locals() else None,
            }
            
            # Обработка специфичных ошибок с детальным логированием
            if '30034' in error_msg or '30034' in str(e) or 'Not enough balance' in error_msg or error_code == '30034':
                error_details['reason'] = 'insufficient_balance'
                error_details['description'] = 'Недостаточно баланса для размещения ордера'
                logger.error(f"❌ ОШИБКА РАЗМЕЩЕНИЯ ОРДЕРА {side.upper()}: {symbol} | "
                           f"Код: 30034 | Причина: Недостаточно баланса | "
                           f"Параметры: qty={qty} лотов, lot={lot if 'lot' in locals() else 'N/A'}, "
                           f"figi={figi if 'figi' in locals() else 'N/A'}, account_id={account_id if 'account_id' in locals() else 'N/A'}")
                logger.warning(f"   Проверьте: 1) количество лотов в позиции, 2) баланс счета, 3) что позиция не была частично продана")
                if side.lower() == 'sell':
                    logger.warning(f"   Рекомендуется проверить актуальное количество лотов в позиции {symbol} через get_positions()")
            elif '30079' in error_msg or '30079' in str(e) or error_code == '30079' or 'Instrument is not available for trading' in error_msg:
                error_details['reason'] = 'instrument_not_available'
                error_details['description'] = 'Инструмент недоступен для торговли'
                from datetime import datetime
                current_time_msk = datetime.now().strftime('%H:%M:%S MSK')
                logger.error(f"❌ ОШИБКА РАЗМЕЩЕНИЯ ОРДЕРА {side.upper()}: {symbol} | "
                           f"Код: 30079 | Причина: Инструмент недоступен для торговли | "
                           f"Время: {current_time_msk} | "
                           f"Параметры: qty={qty} лотов, lot={lot if 'lot' in locals() else 'N/A'}, "
                           f"figi={figi if 'figi' in locals() else 'N/A'}")
                logger.warning(f"   Возможные причины: торговая сессия закрыта (MOEX работает 10:00-18:45 MSK), "
                             f"инструмент приостановлен, или недоступен в sandbox")
            else:
                error_details['reason'] = 'unknown_request_error'
                error_details['description'] = f'Неизвестная ошибка RequestError: {error_msg}'
                logger.error(f"❌ ОШИБКА РАЗМЕЩЕНИЯ ОРДЕРА {side.upper()}: {symbol} | "
                           f"Тип: RequestError | Сообщение: {error_msg} | "
                           f"Параметры: qty={qty} лотов, lot={lot if 'lot' in locals() else 'N/A'}, "
                           f"figi={figi if 'figi' in locals() else 'N/A'}, account_id={account_id if 'account_id' in locals() else 'N/A'}", 
                           exc_info=True)
            
            # Сохраняем детали ошибки в атрибуте для доступа извне
            if not hasattr(self, '_last_order_error'):
                self._last_order_error = {}
            self._last_order_error = error_details
            
            return None
        except Exception as e:
            error_msg = str(e)
            error_type = type(e).__name__
            error_details = {
                'error_type': error_type,
                'error_message': error_msg,
                'symbol': symbol,
                'figi': figi if 'figi' in locals() else None,
                'qty': qty,
                'side': side,
                'lot': lot if 'lot' in locals() else None,
                'account_id': account_id if 'account_id' in locals() else None,
            }
            
            if '30034' in error_msg or 'Not enough balance' in error_msg:
                error_details['reason'] = 'insufficient_balance'
                error_details['description'] = 'Недостаточно баланса для размещения ордера'
                logger.error(f"❌ ОШИБКА РАЗМЕЩЕНИЯ ОРДЕРА {side.upper()}: {symbol} | "
                           f"Тип: {error_type} | Причина: Недостаточно баланса | "
                           f"Параметры: qty={qty} лотов, lot={lot if 'lot' in locals() else 'N/A'}, "
                           f"figi={figi if 'figi' in locals() else 'N/A'}")
                logger.warning(f"   Проверьте: 1) количество лотов в позиции, 2) баланс счета, 3) что позиция не была частично продана")
                if side.lower() == 'sell':
                    logger.warning(f"   Рекомендуется проверить актуальное количество лотов в позиции {symbol} через get_positions()")
            elif '30079' in error_msg or 'Instrument is not available for trading' in error_msg:
                error_details['reason'] = 'instrument_not_available'
                error_details['description'] = 'Инструмент недоступен для торговли'
                from datetime import datetime
                current_time_msk = datetime.now().strftime('%H:%M:%S MSK')
                logger.error(f"❌ ОШИБКА РАЗМЕЩЕНИЯ ОРДЕРА {side.upper()}: {symbol} | "
                           f"Тип: {error_type} | Код: 30079 | Причина: Инструмент недоступен для торговли | "
                           f"Время: {current_time_msk} | "
                           f"Параметры: qty={qty} лотов, lot={lot if 'lot' in locals() else 'N/A'}, "
                           f"figi={figi if 'figi' in locals() else 'N/A'}")
                logger.warning(f"   Возможные причины: торговая сессия закрыта (MOEX работает 10:00-18:45 MSK), "
                             f"инструмент приостановлен, или недоступен в sandbox")
            else:
                error_details['reason'] = 'unknown_error'
                error_details['description'] = f'Неожиданная ошибка: {error_msg}'
                logger.error(f"❌ ОШИБКА РАЗМЕЩЕНИЯ ОРДЕРА {side.upper()}: {symbol} | "
                           f"Тип: {error_type} | Сообщение: {error_msg} | "
                           f"Параметры: qty={qty} лотов, lot={lot if 'lot' in locals() else 'N/A'}, "
                           f"figi={figi if 'figi' in locals() else 'N/A'}, account_id={account_id if 'account_id' in locals() else 'N/A'}", 
                           exc_info=True)
            
            # Сохраняем детали ошибки в атрибуте для доступа извне
            if not hasattr(self, '_last_order_error'):
                self._last_order_error = {}
            self._last_order_error = error_details
            
            return None
    
    def place_limit_order(self, symbol: str, qty: int, side: str, limit_price: float) -> Optional[Dict]:
        """Разместить лимитный ордер"""
        if not self.client:
            logger.info(f"СИМУЛЯЦИЯ: {side.upper()} {qty} {symbol} @ {limit_price}")
            return {'symbol': symbol, 'qty': qty, 'side': side, 'limit_price': limit_price, 'status': 'pending', 'simulated': True}
        
        try:
            if TINVEST_SDK_TYPE != "official":
                logger.error("Размещение ордеров поддерживается только в official SDK")
                return None

            # Поддерживаем как тикер, так и FIGI
            instrument = None
            symbol_u = str(symbol).strip().upper()
            if symbol_u.startswith("BBG") and len(symbol_u) > 10:
                # Это FIGI, используем get_instrument_by_figi
                instrument = self.get_instrument_by_figi(symbol_u)
            else:
                # Это тикер, используем get_instrument_by_ticker (который теперь тоже поддерживает FIGI)
                instrument = self.get_instrument_by_ticker(symbol_u)
            
            if not instrument:
                logger.error(f"Инструмент {symbol} не найден")
                return None
            
            # Получаем account_id
            account_id = self._ensure_account_id()
            if not account_id:
                logger.error("Счет не найден")
                return None
            
            with self._create_official_client() as client:
                # Преобразуем цену в Quotation
                price_units = int(limit_price)
                price_nano = int((limit_price - price_units) * 1e9)
                price = Quotation(units=price_units, nano=price_nano)
                
                order = self._post_order(
                    client,
                    account_id=account_id,
                    figi=instrument['figi'],
                    qty=qty,
                    direction=OrderDirection.ORDER_DIRECTION_BUY if side == 'buy' else OrderDirection.ORDER_DIRECTION_SELL,
                    order_type=OrderType.ORDER_TYPE_LIMIT,
                    price=price,
                )
                
                logger.info(f"Лимитный ордер размещен: {side.upper()} {qty} {symbol} @ {limit_price} (order_id: {order.order_id})")
                return {
                    'order_id': order.order_id,
                    'symbol': symbol,
                    'qty': qty,
                    'side': side,
                    'status': 'new',
                    'limit_price': limit_price,
                    'figi': instrument['figi']
                }
        except RequestError as e:
            logger.error(f"Ошибка размещения лимитного ордера для {symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при размещении лимитного ордера для {symbol}: {e}", exc_info=True)
            return None
    
    def cancel_order(self, order_id: str, account_id: str = None) -> bool:
        """Отменить ордер"""
        if not self.client:
            return True
        
        try:
            if TINVEST_SDK_TYPE != "official":
                return False

            if not account_id:
                account_id = self._ensure_account_id()
                if not account_id:
                    return False

            with self._create_official_client() as client:
                self._cancel_order(client, account_id=account_id, order_id=order_id)
                logger.info(f"Ордер {order_id} отменен")
                return True
        except Exception as e:
            logger.error(f"Ошибка отмены ордера {order_id}: {e}", exc_info=True)
            return False
