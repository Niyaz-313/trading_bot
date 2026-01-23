#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Построить отчет за сегодня на основе локальных файлов"""

import json
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

MSK_TZ = ZoneInfo("Europe/Moscow")
AUDIT_LOG = "audit_logs/trades_audit.jsonl"

def main():
    today_msk = datetime.now(MSK_TZ).date()
    print(f"Поиск сделок за {today_msk} (МСК)...")
    
    trades = []
    
    if not os.path.exists(AUDIT_LOG):
        print(f"Файл {AUDIT_LOG} не найден!")
        return
    
    with open(AUDIT_LOG, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                if event.get("event") != "trade":
                    continue
                
                ts_str = event.get("ts_utc", "")
                if not ts_str:
                    continue
                
                # Парсим время
                if ts_str.endswith('Z'):
                    dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                else:
                    dt = datetime.fromisoformat(ts_str)
                
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                
                dt_msk = dt.astimezone(MSK_TZ)
                
                if dt_msk.date() != today_msk:
                    continue
                
                action = event.get("action", "").upper()
                if action not in ["BUY", "SELL"]:
                    continue
                
                symbol = event.get("symbol", "")
                qty_lots = int(event.get("qty_lots", 0) or 0)
                lot = int(event.get("lot", 1) or 1)
                price = float(event.get("price", 0) or 0)
                equity = float(event.get("equity", 0) or 0)
                cash = float(event.get("cash", 0) or 0)
                
                trade_amount = qty_lots * lot * price
                
                trades.append({
                    "time": dt_msk.strftime("%H:%M:%S"),
                    "datetime": dt_msk,
                    "symbol": symbol,
                    "action": action,
                    "qty_lots": qty_lots,
                    "lot": lot,
                    "qty_shares": qty_lots * lot,
                    "price": price,
                    "amount": trade_amount,
                    "equity": equity,
                    "cash": cash,
                })
            except Exception as e:
                continue
    
    if not trades:
        print(f"\n⚠️ Сделок за {today_msk} не найдено в локальных файлах.")
        print("\nВозможные причины:")
        print("1. Локальные файлы не синхронизированы с сервером")
        print("2. Бот не совершал сделок сегодня")
        print("\nДля получения актуальных данных:")
        print("  git pull origin main")
        return
    
    trades.sort(key=lambda x: x["datetime"])
    
    # Формируем отчет
    report = []
    report.append("=" * 100)
    report.append(f"ОТЧЕТ ПО ОПЕРАЦИЯМ ЗА {today_msk} (МСК)")
    report.append("=" * 100)
    report.append("")
    
    # Статистика
    buy_trades = [t for t in trades if t["action"] == "BUY"]
    sell_trades = [t for t in trades if t["action"] == "SELL"]
    total_buy = sum(t["amount"] for t in buy_trades)
    total_sell = sum(t["amount"] for t in sell_trades)
    
    report.append("ОБЩАЯ СТАТИСТИКА:")
    report.append(f"  Покупок: {len(buy_trades)}")
    report.append(f"  Продаж: {len(sell_trades)}")
    report.append(f"  Всего операций: {len(trades)}")
    report.append(f"  Сумма покупок: {total_buy:,.2f} RUB")
    report.append(f"  Сумма продаж: {total_sell:,.2f} RUB")
    report.append("")
    
    # Детали операций
    report.append("ДЕТАЛИ ПО ОПЕРАЦИЯМ:")
    report.append("-" * 100)
    report.append(f"{'Время (МСК)':<12} {'Операция':<12} {'Символ':<20} {'Кол-во':<10} {'Цена':<12} {'Сумма':<15} {'Баланс':<15}")
    report.append("-" * 100)
    
    for t in trades:
        action_str = "🟢 ПОКУПКА" if t["action"] == "BUY" else "🔴 ПРОДАЖА"
        report.append(
            f"{t['time']:<12} "
            f"{action_str:<12} "
            f"{t['symbol']:<20} "
            f"{t['qty_shares']:<10} шт "
            f"{t['price']:>11,.2f} "
            f"{t['amount']:>14,.2f} RUB "
            f"{t['equity']:>14,.2f} RUB"
        )
    
    report.append("-" * 100)
    
    # P/L по символам
    symbols = {}
    for t in trades:
        sym = t["symbol"]
        if sym not in symbols:
            symbols[sym] = {"buy": [], "sell": []}
        symbols[sym][t["action"].lower()].append(t)
    
    if symbols:
        report.append("")
        report.append("ПРИБЫЛЬ/УБЫТОК ПО СИМВОЛАМ:")
        report.append("-" * 100)
        report.append(f"{'Символ':<20} {'Покупок':<10} {'Продаж':<10} {'Покупка':<15} {'Продажа':<15} {'P/L':<15} {'P/L %':<10}")
        report.append("-" * 100)
        
        for sym in sorted(symbols.keys()):
            s = symbols[sym]
            buy_total = sum(t["amount"] for t in s["buy"])
            sell_total = sum(t["amount"] for t in s["sell"])
            buy_shares = sum(t["qty_shares"] for t in s["buy"])
            sell_shares = sum(t["qty_shares"] for t in s["sell"])
            
            if buy_shares > 0 and sell_shares > 0:
                avg_buy = buy_total / buy_shares
                pnl = sell_total - (avg_buy * sell_shares)
                pnl_pct = (pnl / (avg_buy * sell_shares) * 100) if avg_buy > 0 else 0
            else:
                pnl = 0
                pnl_pct = 0
            
            pnl_str = f"{pnl:,.2f} RUB"
            if pnl >= 0:
                pnl_str = f"✅ {pnl_str}"
            else:
                pnl_str = f"❌ {pnl_str}"
            
            report.append(
                f"{sym:<20} "
                f"{len(s['buy']):<10} "
                f"{len(s['sell']):<10} "
                f"{buy_total:>14,.2f} "
                f"{sell_total:>14,.2f} "
                f"{pnl_str:<15} "
                f"{pnl_pct:>9.2f}%"
            )
        
        report.append("-" * 100)
    
    # Последний баланс
    if trades:
        last = trades[-1]
        report.append("")
        report.append("БАЛАНС НА МОМЕНТ ПОСЛЕДНЕЙ ОПЕРАЦИИ:")
        report.append(f"  Капитал (equity): {last['equity']:,.2f} RUB")
        report.append(f"  Наличные (cash): {last['cash']:,.2f} RUB")
    
    report.append("")
    report.append("=" * 100)
    
    # Выводим отчет
    report_text = "\n".join(report)
    print("\n" + report_text)
    
    # Сохраняем
    os.makedirs("reports", exist_ok=True)
    output_file = f"reports/report_today_{today_msk}.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report_text)
    print(f"\nОтчет сохранен в: {output_file}")

if __name__ == "__main__":
    main()

