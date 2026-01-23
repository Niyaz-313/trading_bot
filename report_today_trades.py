#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Отчет по всем операциям за сегодня (по МСК)
Показывает покупки, продажи, прибыли/убытки и баланс кошелька
"""

import json
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import List, Dict, Optional
from collections import defaultdict

# Пути к файлам
AUDIT_LOG_PATH = "audit_logs/trades_audit.jsonl"
MSK_TZ = ZoneInfo("Europe/Moscow")


def parse_timestamp(ts_str: str) -> datetime:
    """Парсит timestamp из audit-лога в datetime"""
    try:
        # Формат: "2026-01-23T09:17:25.963334+00:00" или "2026-01-23T09:17:25.963334Z"
        if ts_str.endswith('Z'):
            dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        else:
            dt = datetime.fromisoformat(ts_str)
        # Конвертируем в MSK
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(MSK_TZ)
    except Exception as e:
        print(f"Ошибка парсинга времени {ts_str}: {e}")
        return datetime.now(MSK_TZ)


def is_today_msk(dt: datetime) -> bool:
    """Проверяет, что дата относится к сегодня (по МСК)"""
    today_msk = datetime.now(MSK_TZ).date()
    return dt.date() == today_msk


def calculate_trade_amount(qty_lots: int, lot: int, price: float) -> float:
    """Вычисляет сумму сделки"""
    return float(qty_lots) * float(lot) * float(price)


def load_trades_today() -> List[Dict]:
    """Загружает все сделки за сегодня из audit-лога"""
    if not os.path.exists(AUDIT_LOG_PATH):
        print(f"ОШИБКА: Файл {AUDIT_LOG_PATH} не найден")
        return []
    
    trades = []
    today_start = datetime.now(MSK_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = datetime.now(MSK_TZ).replace(hour=23, minute=59, second=59, microsecond=999999)
    
    try:
        with open(AUDIT_LOG_PATH, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    event = json.loads(line)
                    if event.get("event") != "trade":
                        continue
                    
                    ts_utc = event.get("ts_utc", "")
                    if not ts_utc:
                        continue
                    
                    dt_msk = parse_timestamp(ts_utc)
                    
                    # Проверяем, что это сегодня
                    if not is_today_msk(dt_msk):
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
                    
                    trade_amount = calculate_trade_amount(qty_lots, lot, price)
                    
                    trades.append({
                        "timestamp": dt_msk,
                        "symbol": symbol,
                        "action": action,
                        "qty_lots": qty_lots,
                        "lot": lot,
                        "qty_shares": qty_lots * lot,
                        "price": price,
                        "trade_amount": trade_amount,
                        "equity": equity,
                        "cash": cash,
                        "reason": event.get("reason", ""),
                        "order_id": event.get("order", {}).get("order_id", "") if isinstance(event.get("order"), dict) else "",
                    })
                except json.JSONDecodeError as e:
                    print(f"Ошибка парсинга JSON в строке {line_num}: {e}")
                    continue
                except Exception as e:
                    print(f"Ошибка обработки строки {line_num}: {e}")
                    continue
    
    except Exception as e:
        print(f"ОШИБКА при чтении файла: {e}")
        return []
    
    # Сортируем по времени
    trades.sort(key=lambda x: x["timestamp"])
    return trades


def calculate_pnl(trades: List[Dict]) -> Dict[str, Dict]:
    """Вычисляет прибыль/убыток для каждой позиции"""
    positions = defaultdict(list)  # symbol -> список операций
    
    for trade in trades:
        symbol = trade["symbol"]
        positions[symbol].append(trade)
    
    pnl_data = {}
    
    for symbol, symbol_trades in positions.items():
        buy_trades = [t for t in symbol_trades if t["action"] == "BUY"]
        sell_trades = [t for t in symbol_trades if t["action"] == "SELL"]
        
        # Вычисляем среднюю цену покупки и продажи
        total_buy_amount = sum(t["trade_amount"] for t in buy_trades)
        total_buy_shares = sum(t["qty_shares"] for t in buy_trades)
        avg_buy_price = total_buy_amount / total_buy_shares if total_buy_shares > 0 else 0
        
        total_sell_amount = sum(t["trade_amount"] for t in sell_trades)
        total_sell_shares = sum(t["qty_shares"] for t in sell_trades)
        avg_sell_price = total_sell_amount / total_sell_shares if total_sell_shares > 0 else 0
        
        # Прибыль/убыток
        if total_sell_shares > 0 and total_buy_shares > 0:
            pnl = total_sell_amount - (avg_buy_price * total_sell_shares)
            pnl_percent = (pnl / (avg_buy_price * total_sell_shares) * 100) if avg_buy_price > 0 else 0
        else:
            pnl = 0
            pnl_percent = 0
        
        pnl_data[symbol] = {
            "buy_count": len(buy_trades),
            "sell_count": len(sell_trades),
            "total_buy_amount": total_buy_amount,
            "total_sell_amount": total_sell_amount,
            "total_buy_shares": total_buy_shares,
            "total_sell_shares": total_sell_shares,
            "avg_buy_price": avg_buy_price,
            "avg_sell_price": avg_sell_price,
            "pnl": pnl,
            "pnl_percent": pnl_percent,
        }
    
    return pnl_data


def format_report(trades: List[Dict], pnl_data: Dict[str, Dict]) -> str:
    """Форматирует отчет"""
    if not trades:
        return "За сегодня сделок не было."
    
    today_str = datetime.now(MSK_TZ).strftime("%Y-%m-%d")
    report = []
    report.append("=" * 80)
    report.append(f"ОТЧЕТ ПО ОПЕРАЦИЯМ ЗА {today_str} (МСК)")
    report.append("=" * 80)
    report.append("")
    
    # Общая статистика
    buy_trades = [t for t in trades if t["action"] == "BUY"]
    sell_trades = [t for t in trades if t["action"] == "SELL"]
    
    total_buy_amount = sum(t["trade_amount"] for t in buy_trades)
    total_sell_amount = sum(t["trade_amount"] for t in sell_trades)
    total_pnl = sum(pnl_data[s]["pnl"] for s in pnl_data.keys())
    
    report.append("ОБЩАЯ СТАТИСТИКА:")
    report.append(f"  Покупок: {len(buy_trades)}")
    report.append(f"  Продаж: {len(sell_trades)}")
    report.append(f"  Всего операций: {len(trades)}")
    report.append(f"  Сумма покупок: {total_buy_amount:,.2f} RUB")
    report.append(f"  Сумма продаж: {total_sell_amount:,.2f} RUB")
    report.append(f"  Общая прибыль/убыток: {total_pnl:,.2f} RUB ({total_pnl/total_buy_amount*100:.2f}%)" if total_buy_amount > 0 else f"  Общая прибыль/убыток: {total_pnl:,.2f} RUB")
    report.append("")
    
    # Детали по операциям
    report.append("ДЕТАЛИ ПО ОПЕРАЦИЯМ:")
    report.append("-" * 80)
    report.append(f"{'Время (МСК)':<20} {'Операция':<8} {'Символ':<15} {'Кол-во':<10} {'Цена':<12} {'Сумма':<15} {'Баланс':<15}")
    report.append("-" * 80)
    
    for trade in trades:
        time_str = trade["timestamp"].strftime("%H:%M:%S")
        action_str = "🟢 ПОКУПКА" if trade["action"] == "BUY" else "🔴 ПРОДАЖА"
        symbol = trade["symbol"]
        qty_str = f"{trade['qty_shares']} шт"
        price_str = f"{trade['price']:,.2f}"
        amount_str = f"{trade['trade_amount']:,.2f} RUB"
        equity_str = f"{trade['equity']:,.2f} RUB"
        
        report.append(f"{time_str:<20} {action_str:<8} {symbol:<15} {qty_str:<10} {price_str:<12} {amount_str:<15} {equity_str:<15}")
    
    report.append("-" * 80)
    report.append("")
    
    # Прибыль/убыток по символам
    if pnl_data:
        report.append("ПРИБЫЛЬ/УБЫТОК ПО СИМВОЛАМ:")
        report.append("-" * 80)
        report.append(f"{'Символ':<15} {'Покупок':<10} {'Продаж':<10} {'Покупка':<15} {'Продажа':<15} {'P/L':<15} {'P/L %':<10}")
        report.append("-" * 80)
        
        for symbol in sorted(pnl_data.keys()):
            data = pnl_data[symbol]
            pnl_str = f"{data['pnl']:,.2f} RUB"
            pnl_percent_str = f"{data['pnl_percent']:.2f}%"
            
            if data['pnl'] >= 0:
                pnl_str = f"✅ {pnl_str}"
            else:
                pnl_str = f"❌ {pnl_str}"
            
            report.append(
                f"{symbol:<15} "
                f"{data['buy_count']:<10} "
                f"{data['sell_count']:<10} "
                f"{data['total_buy_amount']:>14,.2f} "
                f"{data['total_sell_amount']:>14,.2f} "
                f"{pnl_str:<15} "
                f"{pnl_percent_str:<10}"
            )
        
        report.append("-" * 80)
        report.append("")
    
    # Баланс на момент последней операции
    if trades:
        last_trade = trades[-1]
        report.append("БАЛАНС НА МОМЕНТ ПОСЛЕДНЕЙ ОПЕРАЦИИ:")
        report.append(f"  Капитал (equity): {last_trade['equity']:,.2f} RUB")
        report.append(f"  Наличные (cash): {last_trade['cash']:,.2f} RUB")
        report.append("")
    
    report.append("=" * 80)
    
    return "\n".join(report)


def main():
    """Главная функция"""
    print("Загрузка сделок за сегодня...")
    trades = load_trades_today()
    
    if not trades:
        print("За сегодня сделок не найдено.")
        return
    
    print(f"Найдено сделок: {len(trades)}")
    print("Вычисление прибыли/убытка...")
    
    pnl_data = calculate_pnl(trades)
    
    print("Формирование отчета...")
    report = format_report(trades, pnl_data)
    
    print("\n" + report)
    
    # Сохраняем в файл
    today_str = datetime.now(MSK_TZ).strftime("%Y-%m-%d")
    output_file = f"reports/report_today_{today_str}.txt"
    os.makedirs("reports", exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\nОтчет сохранен в: {output_file}")


if __name__ == "__main__":
    main()

