#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Отчет по операциям за сегодня на основе логов trading_bot.log
Используется, когда сделки были выполнены, но не записаны в audit-лог из-за ошибок
"""

import re
import os
from datetime import datetime
from zoneinfo import ZoneInfo

MSK_TZ = ZoneInfo("Europe/Moscow")
LOG_FILE = "logs/trading_bot.log"

def parse_trade_from_log(line: str) -> dict:
    """Парсит строку лога с информацией о размещении ордера"""
    # Формат: "2026-01-23 07:20:35,714 - tinvest_api - INFO - Ордер размещен: BUY 5 LNZL (order_id: ...)"
    match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*Ордер размещен: (BUY|SELL) (\d+) (\w+)', line)
    if not match:
        return None
    
    time_str, action, qty_str, symbol = match.groups()
    
    # Парсим время (логи в MSK)
    try:
        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(tzinfo=MSK_TZ)
    except:
        return None
    
    qty = int(qty_str)
    
    return {
        "datetime": dt,
        "time": dt.strftime("%H:%M:%S"),
        "action": action,
        "symbol": symbol,
        "qty_lots": qty,
        "qty_shares": qty,  # Предполагаем lot=1, если нет информации
    }

def get_account_info_from_logs(log_file: str, target_time: datetime) -> dict:
    """Получает информацию о балансе из логов около указанного времени"""
    equity = None
    cash = None
    
    # Ищем строки с equity/cash около времени сделки
    time_pattern = target_time.strftime("%Y-%m-%d %H:%M")
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                if time_pattern in line:
                    # Ищем equity в строке
                    equity_match = re.search(r'equity[=:]?\s*([\d.]+)', line, re.I)
                    if equity_match:
                        equity = float(equity_match.group(1))
                    
                    cash_match = re.search(r'cash[=:]?\s*([\d.]+)', line, re.I)
                    if cash_match:
                        cash = float(cash_match.group(1))
    except:
        pass
    
    return {"equity": equity or 0, "cash": cash or 0}

def main():
    today_msk = datetime.now(MSK_TZ).date()
    print(f"Поиск сделок за {today_msk} (МСК) в логах...")
    
    if not os.path.exists(LOG_FILE):
        print(f"Файл {LOG_FILE} не найден!")
        return
    
    trades = []
    
    # Читаем логи и ищем размещения ордеров
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if "Ордер размещен:" not in line:
                continue
            
            trade = parse_trade_from_log(line)
            if not trade:
                continue
            
            # Проверяем, что это сегодня
            if trade["datetime"].date() != today_msk:
                continue
            
            # Получаем информацию о балансе
            account_info = get_account_info_from_logs(LOG_FILE, trade["datetime"])
            trade["equity"] = account_info["equity"]
            trade["cash"] = account_info["cash"]
            
            # Пытаемся найти цену из следующих строк лога
            trade["price"] = 0  # Будет заполнено из других источников
            trade["amount"] = 0
            
            trades.append(trade)
    
    if not trades:
        print(f"\n⚠️ Сделок за {today_msk} не найдено в логах.")
        return
    
    # Сортируем по времени
    trades.sort(key=lambda x: x["datetime"])
    
    # Формируем отчет
    report = []
    report.append("=" * 100)
    report.append(f"ОТЧЕТ ПО ОПЕРАЦИЯМ ЗА {today_msk} (МСК)")
    report.append("(на основе логов trading_bot.log)")
    report.append("=" * 100)
    report.append("")
    report.append("⚠️ ВНИМАНИЕ: Данные из логов. Детальная информация (цены, суммы) может быть неполной.")
    report.append("")
    
    # Статистика
    buy_trades = [t for t in trades if t["action"] == "BUY"]
    sell_trades = [t for t in trades if t["action"] == "SELL"]
    
    report.append("ОБЩАЯ СТАТИСТИКА:")
    report.append(f"  Покупок: {len(buy_trades)}")
    report.append(f"  Продаж: {len(sell_trades)}")
    report.append(f"  Всего операций: {len(trades)}")
    report.append("")
    
    # Детали операций
    report.append("ДЕТАЛИ ПО ОПЕРАЦИЯМ:")
    report.append("-" * 100)
    report.append(f"{'Время (МСК)':<12} {'Операция':<12} {'Символ':<20} {'Кол-во (лоты)':<15} {'Баланс':<15}")
    report.append("-" * 100)
    
    for t in trades:
        action_str = "🟢 ПОКУПКА" if t["action"] == "BUY" else "🔴 ПРОДАЖА"
        equity_str = f"{t['equity']:,.2f} RUB" if t['equity'] > 0 else "N/A"
        
        report.append(
            f"{t['time']:<12} "
            f"{action_str:<12} "
            f"{t['symbol']:<20} "
            f"{t['qty_lots']:<15} "
            f"{equity_str:<15}"
        )
    
    report.append("-" * 100)
    report.append("")
    report.append("ПРИМЕЧАНИЕ:")
    report.append("  Для получения полной информации (цены, суммы, прибыль/убыток)")
    report.append("  необходимо исправить ошибку записи в audit-лог и перезапустить бота.")
    report.append("")
    report.append("=" * 100)
    
    # Выводим отчет
    report_text = "\n".join(report)
    print("\n" + report_text)
    
    # Сохраняем
    os.makedirs("reports", exist_ok=True)
    output_file = f"reports/report_today_from_logs_{today_msk}.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report_text)
    print(f"\nОтчет сохранен в: {output_file}")

if __name__ == "__main__":
    main()




