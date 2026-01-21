"""
Режим обучения на исторических данных (Backtesting)
Позволяет протестировать стратегию на исторических данных перед реальной торговлей
"""
import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List
import os
import sys

from strategies import get_strategy
from risk_manager import RiskManager
from config import TINVEST_TOKEN, TINVEST_SANDBOX, BROKER

# Импортируем фильтры качества BUY для консистентности с live-торговлей
try:
    from config import (
        BLOCK_SIDEWAYS_NEGATIVE_MACD, RSI_MAX_BUY, 
        MIN_MACD_HIST_ATR_RATIO_BUY, MACD_OVERRIDE_FOR_HIGH_RSI,
        REQUIRE_MACD_HIST_POSITIVE_BUY,
        NOISY_SYMBOLS, NOISY_REQUIRE_TREND_UP, NOISY_VOLUME_RATIO_MIN, 
        NOISY_MACD_HIST_MIN, NOISY_REQUIRE_MACD_RISING, NOISY_MIN_CONF_BUY
    )
except ImportError:
    BLOCK_SIDEWAYS_NEGATIVE_MACD = True
    RSI_MAX_BUY = 65
    MIN_MACD_HIST_ATR_RATIO_BUY = -0.1
    MACD_OVERRIDE_FOR_HIGH_RSI = 0.5
    REQUIRE_MACD_HIST_POSITIVE_BUY = False
    NOISY_SYMBOLS = []
    NOISY_REQUIRE_TREND_UP = True
    NOISY_VOLUME_RATIO_MIN = 1.2
    NOISY_MACD_HIST_MIN = 0.0
    NOISY_REQUIRE_MACD_RISING = True
    NOISY_MIN_CONF_BUY = 0.55

# Пробуем использовать T-Invest API для получения данных
try:
    from tinvest_api import TInvestAPI
    USE_TINVEST = True
except ImportError:
    USE_TINVEST = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Windows-консоли часто работают не в UTF-8 → из-за этого падают print() с символами вроде "ℹ/✅/📊".
# Принудительно выставляем UTF-8, если возможно.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


class Backtester:
    """Класс для тестирования стратегии на исторических данных"""
    
    def __init__(self, initial_capital: float = 10000, strategy_mode: str = "ensemble", cooldown_days: int = 10):
        """Инициализация бэктестера"""
        self.strategy_mode = (strategy_mode or "ensemble").strip().lower()
        self.strategy = get_strategy(self.strategy_mode)
        self.risk_manager = RiskManager()
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions = {}  # {symbol: {'qty': int, 'entry_price': float}}
        self.trades = []  # История сделок
        self.equity_history = []  # История капитала
        self.cooldown_days = int(cooldown_days)
        self.cooldown_until_idx = {}  # {symbol: idx_until}
        
    def get_historical_data(self, symbol: str, period: str = '1y') -> pd.DataFrame:
        """Получить исторические данные"""
        clean_symbol = symbol
        
        # Пробуем использовать T-Invest API (приоритет)
        if USE_TINVEST and TINVEST_TOKEN and BROKER == 'tinvest' and 'your_token' not in str(TINVEST_TOKEN).lower():
            try:
                logger.info(f"Попытка получения данных через T-Invest API для {clean_symbol}...")
                api = TInvestAPI(sandbox=TINVEST_SANDBOX)
                if api.client:
                    # Передаем период как есть, убираем ограничения
                    data = api.get_historical_data(clean_symbol, period=period, interval='1d')
                    if not data.empty and len(data) >= 50:
                        logger.info(f"✓ Получены данные через T-Invest API для {clean_symbol}: {len(data)} дней")
                        return data
                    else:
                        logger.warning(f"Недостаточно данных через T-Invest API: {len(data) if not data.empty else 0} дней")
                else:
                    logger.warning(f"T-Invest API клиент не инициализирован")
            except Exception as e:
                logger.warning(f"Не удалось получить данные через T-Invest API: {e}")
        
        # Для российских акций используется только T-Invest API
        logger.error(f"❌ Не удалось получить данные для {clean_symbol}")
        logger.error(f"Проверьте:")
        logger.error(f"1. TINVEST_TOKEN установлен в .env и является реальным токеном")
        logger.error(f"2. T-Invest SDK установлен: pip install tinkoff-invest")
        logger.error(f"3. Токен валиден и имеет доступ к песочнице/бирже")
        logger.error(f"4. Символ {clean_symbol} существует на бирже")
        
        return pd.DataFrame()
    
    def backtest_symbol(self, symbol: str, period: str = '1y') -> Dict:
        """Протестировать стратегию на одном символе"""
        logger.info(f"Тестирование {symbol} на исторических данных...")
        
        data = self.get_historical_data(symbol, period)
        if data.empty:
            return {'symbol': symbol, 'error': 'Нет данных'}
        
        # Сбрасываем состояние для нового символа
        self.capital = self.initial_capital
        self.positions = {}
        self.trades = []
        self.equity_history = [self.capital]
        self.cooldown_until_idx = {}
        
        # Проходим по историческим данным
        for i in range(50, len(data)):  # Начинаем с 50 для расчета индикаторов
            current_data = data.iloc[:i+1]
            current_price = data['Close'].iloc[i]
            current_open = data['Open'].iloc[i] if 'Open' in data.columns else current_price
            current_high = data['High'].iloc[i] if 'High' in data.columns else current_price
            current_low = data['Low'].iloc[i] if 'Low' in data.columns else current_price
            current_date = data.index[i]
            
            # Анализируем данные
            analysis = self.strategy.analyze(current_data)
            
            # Проверяем открытые позиции
            if symbol in self.positions:
                position = self.positions[symbol]
                entry_price = position['entry_price']
                qty = position['qty']
                entry_date = position.get('entry_date')
                stop_price = position.get('stop_price', self.risk_manager.calculate_stop_loss(entry_price))
                take_price = position.get('take_price', self.risk_manager.calculate_take_profit(entry_price))

                # Обновляем трейлинг-стоп (только вверх) на основе ATR, если доступен
                atr = analysis.get('atr')
                if atr is not None:
                    atr_trail_mult = float(os.getenv("ATR_TRAIL_MULT", "2.0"))
                    trailing_stop = current_price - atr_trail_mult * float(atr)
                    if trailing_stop > stop_price:
                        stop_price = trailing_stop
                        position['stop_price'] = stop_price
                
                # Проверка стоп-лосса
                # Исполнение стопа по внутридневному минимуму (консервативно) + учёт гэпа
                stop_hit = False
                stop_fill = None
                if current_open <= stop_price:
                    stop_hit = True
                    stop_fill = current_open
                elif current_low <= stop_price:
                    stop_hit = True
                    stop_fill = stop_price

                if stop_hit:
                    # Продаем по стоп-лоссу
                    revenue = stop_fill * qty
                    self.capital += revenue
                    loss = (stop_fill - entry_price) * qty
                    
                    self.trades.append({
                        'date': current_date,
                        'symbol': symbol,
                        'action': 'SELL',
                        'qty': qty,
                        'price': stop_fill,
                        'entry_price': entry_price,
                        'entry_date': entry_date,
                        'pnl': loss,
                        'reason': 'stop_loss',
                        'stop_price': stop_price,
                        'take_price': take_price,
                        'confidence': analysis.get('confidence', 0.0),
                        'buy_signals': analysis.get('buy_signals', 0),
                        'sell_signals': analysis.get('sell_signals', 0),
                        'rsi': analysis.get('rsi'),
                        'ma_short': analysis.get('ma_short'),
                        'ma_long': analysis.get('ma_long'),
                        'macd': analysis.get('macd'),
                        'macd_signal': analysis.get('macd_signal'),
                        'macd_hist': analysis.get('macd_hist'),
                        'macd_hist_prev': analysis.get('macd_hist_prev'),
                    })
                    
                    del self.positions[symbol]
                    # cooldown после стопа, чтобы не перезаходить сразу
                    self.cooldown_until_idx[symbol] = i + self.cooldown_days
                    continue
                
                # Проверка тейк-профита
                take_hit = False
                take_fill = None
                if current_open >= take_price:
                    take_hit = True
                    take_fill = current_open
                elif current_high >= take_price:
                    take_hit = True
                    take_fill = take_price

                if take_hit:
                    # Продаем по тейк-профиту
                    revenue = take_fill * qty
                    self.capital += revenue
                    profit = (take_fill - entry_price) * qty
                    
                    self.trades.append({
                        'date': current_date,
                        'symbol': symbol,
                        'action': 'SELL',
                        'qty': qty,
                        'price': take_fill,
                        'entry_price': entry_price,
                        'entry_date': entry_date,
                        'pnl': profit,
                        'reason': 'take_profit',
                        'stop_price': stop_price,
                        'take_price': take_price,
                        'confidence': analysis.get('confidence', 0.0),
                        'buy_signals': analysis.get('buy_signals', 0),
                        'sell_signals': analysis.get('sell_signals', 0),
                        'rsi': analysis.get('rsi'),
                        'ma_short': analysis.get('ma_short'),
                        'ma_long': analysis.get('ma_long'),
                        'macd': analysis.get('macd'),
                        'macd_signal': analysis.get('macd_signal'),
                        'macd_hist': analysis.get('macd_hist'),
                        'macd_hist_prev': analysis.get('macd_hist_prev'),
                    })
                    
                    del self.positions[symbol]
                    continue
                
                # Проверка сигнала продажи
                if self.strategy.should_sell(analysis, min_confidence=0.5):
                    revenue = current_price * qty
                    self.capital += revenue
                    pnl = (current_price - entry_price) * qty
                    
                    self.trades.append({
                        'date': current_date,
                        'symbol': symbol,
                        'action': 'SELL',
                        'qty': qty,
                        'price': current_price,
                        'entry_price': entry_price,
                        'entry_date': entry_date,
                        'pnl': pnl,
                        'reason': 'signal',
                        'stop_price': stop_price,
                        'take_price': take_price,
                        'confidence': analysis.get('confidence', 0.0),
                        'buy_signals': analysis.get('buy_signals', 0),
                        'sell_signals': analysis.get('sell_signals', 0),
                        'rsi': analysis.get('rsi'),
                        'ma_short': analysis.get('ma_short'),
                        'ma_long': analysis.get('ma_long'),
                        'macd': analysis.get('macd'),
                        'macd_signal': analysis.get('macd_signal'),
                        'macd_hist': analysis.get('macd_hist'),
                        'macd_hist_prev': analysis.get('macd_hist_prev'),
                    })
                    
                    del self.positions[symbol]
                    continue
            
            # Проверка сигнала покупки
            cd_until = self.cooldown_until_idx.get(symbol, -1)
            in_cooldown = i <= cd_until

            if symbol not in self.positions and (not in_cooldown) and self.strategy.should_buy(analysis, min_confidence=0.6):
                # ============================================
                # ФИЛЬТРЫ КАЧЕСТВА BUY (синхронизация с live)
                # ============================================
                trend = analysis.get("trend", "sideways")
                rsi_val = float(analysis.get("rsi", 50) or 50)
                macd_hist_val = float(analysis.get("macd_hist", 0) or 0)
                atr_val = float(analysis.get("atr", 1) or 1)
                macd_hist_atr_ratio = macd_hist_val / atr_val if atr_val > 0 else 0.0
                
                # Фильтр 1: sideways + отрицательный MACD = опасно
                if BLOCK_SIDEWAYS_NEGATIVE_MACD and trend == "sideways" and macd_hist_val < 0:
                    self.equity_history.append(self.capital + sum(
                        self.positions[s]['qty'] * current_price for s in self.positions
                    ) if self.positions else self.capital)
                    continue
                
                # Фильтр 2: требуем положительный MACD_hist
                if REQUIRE_MACD_HIST_POSITIVE_BUY and macd_hist_val < 0:
                    self.equity_history.append(self.capital + sum(
                        self.positions[s]['qty'] * current_price for s in self.positions
                    ) if self.positions else self.capital)
                    continue
                
                # Фильтр 3: минимальный MACD/ATR ratio
                if MIN_MACD_HIST_ATR_RATIO_BUY != 0 and macd_hist_atr_ratio < MIN_MACD_HIST_ATR_RATIO_BUY:
                    self.equity_history.append(self.capital + sum(
                        self.positions[s]['qty'] * current_price for s in self.positions
                    ) if self.positions else self.capital)
                    continue
                
                # Фильтр 4: RSI слишком высокий (кроме сильного MACD)
                if rsi_val > RSI_MAX_BUY and macd_hist_atr_ratio < MACD_OVERRIDE_FOR_HIGH_RSI:
                    self.equity_history.append(self.capital + sum(
                        self.positions[s]['qty'] * current_price for s in self.positions
                    ) if self.positions else self.capital)
                    continue
                
                # Фильтр 5: NOISY_SYMBOLS - строже требования для проблемных символов
                if symbol.upper() in (NOISY_SYMBOLS or []):
                    conf = float(analysis.get("confidence", 0) or 0)
                    volume_ratio = float(analysis.get("volume_ratio", 0) or 0)
                    macd_hist_prev = analysis.get("macd_hist_prev")
                    
                    # Проверяем все условия для noisy символов
                    noisy_fail = False
                    if conf < NOISY_MIN_CONF_BUY:
                        noisy_fail = True
                    if NOISY_REQUIRE_TREND_UP and trend != "up":
                        noisy_fail = True
                    if NOISY_VOLUME_RATIO_MIN > 0 and volume_ratio < NOISY_VOLUME_RATIO_MIN:
                        noisy_fail = True
                    if NOISY_MACD_HIST_MIN is not None and macd_hist_val < NOISY_MACD_HIST_MIN:
                        noisy_fail = True
                    if NOISY_REQUIRE_MACD_RISING and macd_hist_prev is not None:
                        try:
                            if float(macd_hist_val) < float(macd_hist_prev):
                                noisy_fail = True
                        except Exception:
                            pass
                    
                    if noisy_fail:
                        self.equity_history.append(self.capital + sum(
                            self.positions[s]['qty'] * current_price for s in self.positions
                        ) if self.positions else self.capital)
                        continue
                # ============================================
                
                # 1) Сначала считаем ATR-стоп/тейк (если ATR доступен), иначе fallback на проценты
                atr = analysis.get('atr')
                if atr is not None:
                    atr_stop_mult = float(os.getenv("ATR_STOP_MULT", "2.0"))
                    atr_take_mult = float(os.getenv("ATR_TAKE_MULT", "3.0"))
                    stop_price = current_price - atr_stop_mult * float(atr)
                    take_price = current_price + atr_take_mult * float(atr)
                else:
                    stop_price = self.risk_manager.calculate_stop_loss(current_price)
                    take_price = self.risk_manager.calculate_take_profit(current_price)

                # 2) Рассчитываем размер позиции по риску (budget/stop_distance) + cap max_position_size
                qty = self.risk_manager.calculate_position_size_by_risk(
                    self.capital,
                    current_price,
                    stop_price,
                    confidence=analysis.get('confidence', 1.0),
                )

                if qty < 1:
                    # Слишком маленький риск-бюджет или слишком широкий стоп.
                    # Для бэктеста можно разрешить "минимальную позицию" (1 акция),
                    # чтобы не получить ноль сделок на дорогих/волатильных бумагах.
                    allow_min_qty = os.getenv("ALLOW_MIN_QTY", "true").lower().strip() == "true"
                    min_conf_for_min_qty = float(os.getenv("MIN_CONFIDENCE_FOR_MIN_QTY", "0.85"))
                    if allow_min_qty and float(analysis.get("confidence", 0.0) or 0.0) >= min_conf_for_min_qty:
                        qty = 1
                    else:
                        continue

                # Проверяем, хватает ли средств
                cost = current_price * qty
                if cost <= self.capital:
                    self.capital -= cost

                    self.positions[symbol] = {
                        'qty': qty,
                        'entry_price': current_price,
                        'entry_date': current_date,
                        'stop_price': stop_price,
                        'take_price': take_price,
                    }
                    
                    self.trades.append({
                        'date': current_date,
                        'symbol': symbol,
                        'action': 'BUY',
                        'qty': qty,
                        'price': current_price,
                        'pnl': 0,
                        'reason': 'signal',
                        'stop_price': stop_price,
                        'take_price': take_price,
                        'confidence': analysis.get('confidence', 0.0),
                        'buy_signals': analysis.get('buy_signals', 0),
                        'sell_signals': analysis.get('sell_signals', 0),
                        'rsi': analysis.get('rsi'),
                        'ma_short': analysis.get('ma_short'),
                        'ma_long': analysis.get('ma_long'),
                        'macd': analysis.get('macd'),
                        'macd_signal': analysis.get('macd_signal'),
                        'trend': analysis.get('trend'),
                        'atr': analysis.get('atr'),
                        'macd_hist': analysis.get('macd_hist'),
                        'macd_hist_prev': analysis.get('macd_hist_prev'),
                    })
            
            # Записываем текущий капитал
            portfolio_value = self.capital
            for pos_symbol, pos_data in self.positions.items():
                if pos_symbol == symbol:
                    portfolio_value += current_price * pos_data['qty']
            self.equity_history.append(portfolio_value)
        
        # Закрываем оставшиеся позиции по последней цене
        if symbol in self.positions:
            position = self.positions[symbol]
            final_price = data['Close'].iloc[-1]
            revenue = final_price * position['qty']
            self.capital += revenue
            pnl = (final_price - position['entry_price']) * position['qty']
            
            self.trades.append({
                'date': data.index[-1],
                'symbol': symbol,
                'action': 'SELL',
                'qty': position['qty'],
                'price': final_price,
                'entry_price': position['entry_price'],
                'entry_date': position.get('entry_date'),
                'pnl': pnl,
                'reason': 'end_of_period'
            })

        # Экспорт сделок в CSV для анализа (по каждому символу)
        try:
            os.makedirs("reports", exist_ok=True)
            trades_df = pd.DataFrame(self.trades)
            safe_symbol = str(symbol).replace("/", "_")
            trades_path = os.path.join("reports", f"trades_{safe_symbol}_{self.strategy_mode}.csv")
            trades_df.to_csv(trades_path, index=False, encoding="utf-8-sig")
        except Exception as e:
            logger.warning(f"Не удалось сохранить сделки в CSV для {symbol}: {e}")
        
        # Рассчитываем статистику
        total_trades = len(self.trades)
        buy_trades = [t for t in self.trades if t['action'] == 'BUY']
        sell_trades = [t for t in self.trades if t['action'] == 'SELL']
        
        profitable_trades = [t for t in sell_trades if t['pnl'] > 0]
        losing_trades = [t for t in sell_trades if t['pnl'] < 0]
        
        total_profit = sum(t['pnl'] for t in profitable_trades)
        total_loss = abs(sum(t['pnl'] for t in losing_trades))
        
        win_rate = len(profitable_trades) / len(sell_trades) * 100 if sell_trades else 0
        final_capital = self.capital
        total_return = (final_capital - self.initial_capital) / self.initial_capital * 100
        
        return {
            'symbol': symbol,
            'original_symbol': symbol,
            'initial_capital': self.initial_capital,
            'final_capital': final_capital,
            'total_return': total_return,
            'total_trades': total_trades,
            'buy_trades': len(buy_trades),
            'sell_trades': len(sell_trades),
            'profitable_trades': len(profitable_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'total_profit': total_profit,
            'total_loss': total_loss,
            'net_profit': total_profit - total_loss,
            'trades': self.trades,
            'equity_history': self.equity_history
        }
    
    def backtest_multiple_symbols(self, symbols: List[str], period: str = '1y') -> Dict:
        """Протестировать стратегию на нескольких символах"""
        results = {}
        failed = {}
        total_final = 0.0
        
        for symbol in symbols:
            result = self.backtest_symbol(symbol, period)
            if 'error' not in result:
                results[symbol] = result
                total_final += result['final_capital']
            else:
                failed[symbol] = result.get('error', 'unknown')

        # ВАЖНО: считаем общую доходность только по успешно протестированным символам,
        # иначе один "нет данных" выглядит как потеря всего капитала по этому символу.
        success_count = len(results)
        total_initial = self.initial_capital * success_count
        
        overall_return = (total_final - total_initial) / total_initial * 100 if total_initial > 0 else 0
        
        return {
            'symbols': results,
            'overall_return': overall_return,
            'total_initial': total_initial,
            'total_final': total_final,
            'failed_symbols': failed,
            'success_count': success_count,
            'attempted_count': len(symbols),
        }


def run_backtest():
    """Запустить бэктест"""
    from config import SYMBOLS, INITIAL_CAPITAL
    
    print("=" * 70)
    print("ТЕСТИРОВАНИЕ СТРАТЕГИИ НА ИСТОРИЧЕСКИХ ДАННЫХ")
    print("=" * 70)
    print()
    print("Этот режим позволяет протестировать стратегию на исторических данных")
    print("перед реальной торговлей.")
    print()
    
    # Проверяем наличие токена
    # Проверяем токен
    token_str = str(TINVEST_TOKEN).strip() if TINVEST_TOKEN else ''
    if not TINVEST_TOKEN or not token_str or 'your_token' in token_str.lower() or 'your_tinvest' in token_str.lower():
        print("=" * 70)
        print("❌ ОШИБКА: TINVEST_TOKEN не настроен")
        print("=" * 70)
        print()
        print("Для тестирования на российских акциях необходимо:")
        print("1. Откройте файл .env")
        print("2. Установите реальный TINVEST_TOKEN")
        print("   Получите токен в настройках Т-Инвестиций:")
        print("   Настройки → Токены T-Bank Invest API → Выпустить токен")
        print("3. Сохраните файл .env")
        print("4. Запустите backtest снова")
        print()
        print("Тестирование отменено.")
        return
    
    if BROKER == 'tinvest':
        print("INFO: Используется T-Invest API для получения данных")
        print("      Данные получаются напрямую от брокера")
        # Используем символы из конфига (для T-Invest API)
        test_symbols = SYMBOLS
        symbol_mapping = {s: s for s in test_symbols}
        # Период бэктеста можно задать через переменную окружения BACKTEST_PERIOD
        # Допустимо: 2024, 1y, 2y, 3y, all
        period = os.getenv('BACKTEST_PERIOD', '2y').strip()
        # Стратегия бэктеста:
        # hybrid | trend | mean | ensemble | all | best
        strategy_mode = os.getenv("BACKTEST_STRATEGY", "ensemble").strip()
        cooldown_days = int(os.getenv("COOLDOWN_DAYS", "10"))
    else:
        print("=" * 70)
        print("❌ ОШИБКА: Брокер не настроен для российских акций")
        print("=" * 70)
        print()
        print("Установите в .env:")
        print("BROKER=tinvest")
        print("TINVEST_TOKEN=ваш_токен")
        print()
        print("Тестирование отменено.")
        return
    
    # Если нужно сравнить стратегии, используйте BACKTEST_STRATEGY=all
    if strategy_mode.lower() == "all":
        modes = ["hybrid", "trend", "mean", "ensemble"]
        all_runs = {}
        for m in modes:
            bt = Backtester(initial_capital=INITIAL_CAPITAL, strategy_mode=m, cooldown_days=cooldown_days)
            all_runs[m] = bt.backtest_multiple_symbols(test_symbols, period=period)

        print("=" * 70)
        print("СРАВНЕНИЕ СТРАТЕГИЙ")
        print("=" * 70)
        for m in modes:
            r = all_runs[m]
            print(f"{m:9s}  return={r['overall_return']:+.2f}%  final=${r['total_final']:,.2f}  ok={r.get('success_count',0)}/{r.get('attempted_count',0)}")
        print("=" * 70)

        # По умолчанию показываем детали ансамбля
        results = all_runs["ensemble"]
        strategy_mode = "ensemble"

    # Best-per-symbol: выбираем лучшую стратегию ОТДЕЛЬНО для каждого тикера
    elif strategy_mode.lower() == "best":
        modes = ["hybrid", "trend", "mean", "ensemble"]
        chosen = {}
        best_results = {}
        total_final = 0.0
        best_min_trades = int(os.getenv("BEST_MIN_TRADES", "1"))

        for sym in test_symbols:
            best_mode = None
            best_final = None
            best_res = None

            for m in modes:
                bt = Backtester(initial_capital=INITIAL_CAPITAL, strategy_mode=m, cooldown_days=cooldown_days)
                r = bt.backtest_symbol(sym, period=period)
                if "error" in r:
                    continue
                # Чтобы best-режим не выбирал "0 сделок = 0 риска" автоматически,
                # можно потребовать минимальное число сделок.
                if best_min_trades > 0 and int(r.get("total_trades", 0) or 0) < best_min_trades:
                    continue
                if best_final is None or r["final_capital"] > best_final:
                    best_final = r["final_capital"]
                    best_mode = m
                    best_res = r

            if best_mode is None:
                # fallback: если ни одна стратегия не прошла фильтр по сделкам — разрешаем выбрать лучшую по капиталу
                for m in modes:
                    bt = Backtester(initial_capital=INITIAL_CAPITAL, strategy_mode=m, cooldown_days=cooldown_days)
                    r = bt.backtest_symbol(sym, period=period)
                    if "error" in r:
                        continue
                    if best_final is None or r["final_capital"] > best_final:
                        best_final = r["final_capital"]
                        best_mode = m
                        best_res = r

            if best_mode is None:
                continue

            chosen[sym] = best_mode
            best_results[sym] = best_res
            total_final += float(best_res["final_capital"])

        total_initial = INITIAL_CAPITAL * len(best_results)
        overall_return = (total_final - total_initial) / total_initial * 100 if total_initial > 0 else 0.0
        results = {
            "symbols": best_results,
            "overall_return": overall_return,
            "total_initial": total_initial,
            "total_final": total_final,
            "failed_symbols": {},
            "success_count": len(best_results),
            "attempted_count": len(test_symbols),
            "chosen_strategy": chosen,
        }

        print("=" * 70)
        print("BEST-PER-SYMBOL (выбор лучшей стратегии по каждому тикеру)")
        print("=" * 70)
        for sym in test_symbols:
            if sym in chosen:
                print(f"{sym}: {chosen[sym]}")
        print("=" * 70)
    else:
        backtester = Backtester(initial_capital=INITIAL_CAPITAL, strategy_mode=strategy_mode, cooldown_days=cooldown_days)
        results = backtester.backtest_multiple_symbols(test_symbols, period=period)

    # Всегда создаём папку отчётов (даже если сделок будет 0)
    try:
        os.makedirs("reports", exist_ok=True)
    except Exception:
        pass
    
    print(f"Начальный капитал: ${INITIAL_CAPITAL:,.2f}")
    print(f"Символы для тестирования: {', '.join(test_symbols)}")
    period_names = {'2024': '2024 год', '1y': '1 год', '2y': '2 года', '3y': '3 года', 'all': 'Все доступные данные'}
    print(f"Период: {period_names.get(period, period)}")
    print()
    print("Запуск тестирования...")
    print()
    
    # results уже рассчитан выше
    
    # Восстанавливаем исходные имена символов в результатах
    if 'symbols' in results:
        new_symbols = {}
        for symbol_key, result in results['symbols'].items():
            original_symbol = symbol_mapping.get(symbol_key, symbol_key)
            result['symbol'] = original_symbol
            new_symbols[original_symbol] = result
        results['symbols'] = new_symbols
    
    print("=" * 70)
    print("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("=" * 70)
    print()
    
    for symbol, result in results['symbols'].items():
        display_symbol = result.get('symbol', symbol)
        print(f"{display_symbol}:")
        print(f"   Начальный капитал: ${result['initial_capital']:,.2f}")
        print(f"   Конечный капитал: ${result['final_capital']:,.2f}")
        print(f"   Доходность: {result['total_return']:+.2f}%")
        print(f"   Всего сделок: {result['total_trades']}")
        print(f"   Покупок: {result['buy_trades']}, Продаж: {result['sell_trades']}")
        print(f"   Прибыльных: {result['profitable_trades']}, Убыточных: {result['losing_trades']}")
        print(f"   Процент побед: {result['win_rate']:.1f}%")
        print(f"   Общая прибыль: ${result['total_profit']:,.2f}")
        print(f"   Общий убыток: ${result['total_loss']:,.2f}")
        print(f"   Чистая прибыль: ${result['net_profit']:,.2f}")
        print()
    
    print("=" * 70)
    print(f"ОБЩИЙ РЕЗУЛЬТАТ")
    print("=" * 70)
    print(f"Общая доходность: {results['overall_return']:+.2f}%")
    print(f"Начальный капитал: ${results['total_initial']:,.2f}")
    print(f"Конечный капитал: ${results['total_final']:,.2f}")
    print(f"Символов успешно: {results.get('success_count', 0)} / {results.get('attempted_count', 0)}")

    failed = results.get('failed_symbols') or {}
    if failed:
        print("Не удалось протестировать:")
        for sym, err in failed.items():
            print(f" - {sym}: {err}")

    print("Подробные сделки сохранены в папку: reports/ (файлы trades_<SYMBOL>_<STRATEGY>.csv)")
    print("=" * 70)


if __name__ == "__main__":
    run_backtest()
