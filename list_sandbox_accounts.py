"""
Диагностика sandbox-аккаунтов T-Invest.

Показывает все аккаунты, и по каждому:
- portfolio_value / cash (по GetSandboxPortfolio)
- количество позиций (GetSandboxPositions / fallback)
- количество активных заявок (GetSandboxOrders)

Это нужно, когда денег на одном account_id стало меньше, а бот смотрит другой account_id.
"""

from __future__ import annotations

from tinvest_api import TInvestAPI


def main():
    api = TInvestAPI(sandbox=True)
    if not api.client:
        print("T-Invest не инициализирован (проверьте токен/SDK).")
        return

    # Получаем список аккаунтов через внутренний helper
    temp = api._create_official_client()
    if temp is None:
        print("Не удалось создать client.")
        return

    with temp as client:
        resp = api._get_accounts(client)
        accounts = getattr(resp, "accounts", None) or []
        if not accounts:
            print("Sandbox accounts: 0")
            return

        print(f"Sandbox accounts: {len(accounts)}")
        for acc in accounts:
            acc_id = getattr(acc, "id", None)
            if not acc_id:
                continue
            try:
                pf = api._get_portfolio(client, account_id=acc_id)
                pv = api._money_value_to_float(getattr(pf, "total_amount_portfolio", None))
                cash = api._money_value_to_float(getattr(pf, "total_amount_currencies", None))
            except Exception:
                pv = 0.0
                cash = 0.0

            # positions / orders (через публичные методы, чтобы применились все fallback)
            api.account_id = acc_id
            positions = api.get_positions() or []
            orders = api.get_open_orders() or []

            print("-" * 60)
            print(f"account_id: {acc_id}")
            print(f"portfolio_value: {pv:.2f} RUB")
            print(f"cash (portfolio currencies): {cash:.2f} RUB")
            print(f"positions: {len(positions)}")
            if positions:
                for p in positions[:5]:
                    print(f"  - {p.get('symbol')} lots={p.get('qty_lots')} shares={p.get('qty_shares')} lot={p.get('lot')}")
            print(f"open_orders: {len(orders)}")
            if orders:
                for o in orders[:5]:
                    print(f"  - {o.get('symbol')} {o.get('side')} lots={o.get('qty_lots')} status={o.get('status')} id={o.get('order_id')}")

        print("-" * 60)
        print("Подсказка: установите нужный счет в .env -> TINVEST_ACCOUNT_ID=...")


if __name__ == "__main__":
    main()





