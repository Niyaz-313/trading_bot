"""
Telegram бот для уведомлений и управления торговым ботом
"""
import logging
import asyncio
from typing import Optional, Callable, Awaitable
from datetime import datetime
import pandas as pd

try:
    from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
    from telegram.ext import (
        Application,
        ApplicationBuilder,
        CommandHandler,
        CallbackQueryHandler,
        ContextTypes,
    )
    from telegram.request import HTTPXRequest
    from telegram.error import BadRequest
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logging.warning("python-telegram-bot не установлен. Telegram функции недоступны.")

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)


class TelegramBot:
    """Класс для работы с Telegram ботом"""
    
    def __init__(self):
        """Инициализация Telegram бота"""
        self.bot = None
        chat_id_str = str(TELEGRAM_CHAT_ID).strip() if TELEGRAM_CHAT_ID else ''
        try:
            self.chat_id = int(chat_id_str) if chat_id_str.isdigit() else chat_id_str
        except:
            self.chat_id = chat_id_str
        
        if TELEGRAM_AVAILABLE and TELEGRAM_BOT_TOKEN:
            try:
                self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
                logger.info("Telegram бот инициализирован")
                if not self.chat_id:
                    logger.warning("TELEGRAM_CHAT_ID не указан в .env файле")
            except Exception as e:
                logger.error(f"Ошибка инициализации Telegram бота: {e}")
                self.bot = None
        else:
            logger.warning("Telegram бот не настроен (отсутствует токен)")
    
    async def send_message(self, message: str, parse_mode: Optional[str] = None, reply_markup=None) -> bool:
        """Отправить сообщение в Telegram"""
        if not self.bot or not self.chat_id:
            logger.debug(f"Telegram не настроен. Сообщение: {message}")
            return False

        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
            return True
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Ошибка отправки сообщения в Telegram: {error_msg}")

            if "Chat not found" in error_msg or "chat not found" in error_msg.lower():
                logger.error("РЕШЕНИЕ: Chat not found - убедитесь, что:")
                logger.error("  1. Вы написали боту первое сообщение")
                logger.error("  2. Chat ID правильный (проверьте через @userinfobot)")
                logger.error(f"  3. Текущий Chat ID: {self.chat_id}")
            elif "Unauthorized" in error_msg or "Invalid token" in error_msg:
                logger.error("РЕШЕНИЕ: Неверный токен бота - проверьте TELEGRAM_BOT_TOKEN в .env")
            elif "Forbidden" in error_msg:
                logger.error("РЕШЕНИЕ: Бот заблокирован - разблокируйте бота в Telegram")

            return False

    def build_control_keyboard(self) -> Optional[InlineKeyboardMarkup]:
        """Кнопки управления (inline)."""
        if not TELEGRAM_AVAILABLE:
            return None
        keyboard = [
            [InlineKeyboardButton("▶️ Старт", callback_data="CTL_START"),
             InlineKeyboardButton("⏸ Стоп", callback_data="CTL_STOP")],
            [InlineKeyboardButton("ℹ️ Статус", callback_data="CTL_STATUS"),
             InlineKeyboardButton("💼 Портфель", callback_data="CTL_PORTFOLIO")],
            [InlineKeyboardButton("🧾 Последние сделки", callback_data="CTL_TRADES")],
            [InlineKeyboardButton("📅 Отчёт (/day)", callback_data="CTL_DAY")],
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def format_trade_notification(
        self,
        symbol: str,
        action: str,
        qty: int,
        price: float,
        total: float,
        reason: str = "",
        currency: str = "RUB",
        currency_symbol: Optional[str] = None,
        lot: Optional[int] = None,
        qty_shares: Optional[float] = None,
    ) -> str:
        """Форматировать уведомление о сделке (валюта/лоты учитываются)."""
        emoji = "🟢" if action == "BUY" else "🔴"
        cur = (currency or "RUB").upper()
        if currency_symbol is None:
            currency_symbol = {"RUB": "₽", "USD": "$", "EUR": "€"}.get(cur, cur + " ")

        message = f"{emoji} *{action}* {symbol}\n"
        if lot and lot > 0:
            message += f"Количество: {qty} лот(ов) (лот={lot})\n"
            if qty_shares is not None:
                message += f"Акций: {qty_shares:.0f}\n"
        else:
            message += f"Количество: {qty}\n"

        message += f"Цена: {currency_symbol}{price:.2f} {cur}\n"
        message += f"Сумма: {currency_symbol}{total:.2f} {cur}\n"
        if reason:
            message += f"Причина: {reason}\n"
        message += f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        return message
    
    def format_account_status(
        self,
        account_info: dict,
        positions: list,
        open_orders: Optional[list] = None,
        recent_operations: Optional[list] = None,
        last_order_state: Optional[dict] = None,
    ) -> str:
        """Форматировать статус счета"""
        currency = account_info.get("currency", "RUB") or "RUB"
        message = "📊 *Статус счета*\n\n"
        message += f"Капитал (equity): {account_info.get('equity', 0):.2f} {currency}\n"
        message += f"Наличные (cash): {account_info.get('cash', 0):.2f} {currency}\n"
        message += f"Покупательная способность: {account_info.get('buying_power', 0):.2f} {currency}\n\n"
        
        if positions:
            # Ограничиваем количество позиций для Telegram (лимит 4096 символов)
            # Показываем топ позиций по стоимости или P/L
            MAX_POSITIONS_IN_MESSAGE = 20
            positions_to_show = positions[:MAX_POSITIONS_IN_MESSAGE] if len(positions) <= MAX_POSITIONS_IN_MESSAGE else sorted(
                positions, 
                key=lambda p: float(p.get("current_price", 0) or 0) * float(p.get("qty_shares", p.get("qty_lots", 0) or 0) * (p.get("lot", 1) or 1)),
                reverse=True
            )[:MAX_POSITIONS_IN_MESSAGE]
            
            message += f"*Открытые позиции:* ({len(positions_to_show)} из {len(positions)})\n"
            if len(positions) > MAX_POSITIONS_IN_MESSAGE:
                message += f"_Показаны топ-{MAX_POSITIONS_IN_MESSAGE} позиций по стоимости_\n"
            
            total_entry = 0.0
            total_current = 0.0
            for pos in positions_to_show:
                qty_lots = pos.get("qty_lots", pos.get("qty", 0)) or 0
                lot = pos.get("lot", 1) or 1
                qty_shares = pos.get("qty_shares", None)
                if qty_shares is None:
                    try:
                        qty_shares = float(qty_lots) * float(lot)
                    except Exception:
                        qty_shares = 0.0

                qty_lots = pos.get("qty_lots", pos.get("qty", 0))
                lot = pos.get("lot", 1)

                avg_entry = float(pos.get("avg_entry_price", 0) or 0)
                current_px = float(pos.get("current_price", 0) or 0)

                entry_total = avg_entry * float(qty_shares or 0)
                current_total = current_px * float(qty_shares or 0)
                total_entry += entry_total
                total_current += current_total

                pnl = current_total - entry_total if entry_total > 0 else 0.0
                pnl_pct = (pnl / entry_total * 100.0) if entry_total > 0 else 0.0
                pl_emoji = "🟢" if pnl >= 0 else "🔴"

                sym = pos.get('symbol', '?')
                message += f"{pl_emoji} {sym}: {qty_lots} лот(ов) (лот={lot})\n"
                if avg_entry > 0:
                    src = pos.get("entry_price_source", None)
                    tsb = pos.get("entry_last_buy_ts_utc", "")
                    src_s = " (из T‑Invest)" if src != "audit" else " (из audit‑лога)"
                    ts_s = f", buy_ts={tsb}" if (src == "audit" and tsb) else ""
                    message += f"   Покупка: {avg_entry:.2f} {currency}{src_s}{ts_s} | Пакет (покупка): {entry_total:.2f} {currency}\n"
                else:
                    message += f"   Покупка: (нет данных)\n"
                if current_px > 0:
                    message += f"   Рынок: {current_px:.2f} {currency} | Пакет (рынок): {current_total:.2f} {currency}\n"
                message += f"   P/L: {pnl:.2f} {currency} ({pnl_pct:.2f}%)\n"

            # Пересчитываем итоги по ВСЕМ позициям (не только показанным)
            total_entry_all = 0.0
            total_current_all = 0.0
            for pos in positions:
                qty_lots = pos.get("qty_lots", pos.get("qty", 0)) or 0
                lot = pos.get("lot", 1) or 1
                qty_shares = pos.get("qty_shares", None)
                if qty_shares is None:
                    try:
                        qty_shares = float(qty_lots) * float(lot)
                    except Exception:
                        qty_shares = 0.0
                avg_entry = float(pos.get("avg_entry_price", 0) or 0)
                current_px = float(pos.get("current_price", 0) or 0)
                entry_total = avg_entry * float(qty_shares or 0)
                current_total = current_px * float(qty_shares or 0)
                total_entry_all += entry_total
                total_current_all += current_total
            
            if total_entry_all > 0 or total_current_all > 0:
                total_pnl = total_current_all - total_entry_all
                total_pnl_pct = (total_pnl / total_entry_all * 100.0) if total_entry_all > 0 else 0.0
                message += (
                    f"\n*Итого по всем {len(positions)} позициям:*\n"
                    f"- Покупка (сумма): {total_entry_all:.2f} {currency}\n"
                    f"- Рынок (сумма): {total_current_all:.2f} {currency}\n"
                    f"- P/L: {total_pnl:.2f} {currency} ({total_pnl_pct:.2f}%)"
                )
        else:
            message += "Нет открытых позиций"

        # Активные заявки (часто это причина, почему деньги списались, а позиций ещё нет)
        if open_orders:
            message += "\n\n*Активные заявки:*\n"
            for o in open_orders[:10]:
                sym = o.get("symbol", "?")
                oid = o.get("order_id", "")
                side = o.get("side", "")
                status = o.get("status", "")
                qty_lots = o.get("qty_lots", "")
                lot = o.get("lot", "")
                price = o.get("price", 0)
                price_s = f"{price:.2f} {currency}" if isinstance(price, (int, float)) and price else "market"
                message += f"- {sym}: {side} {qty_lots} лот(ов) (лот={lot}) @ {price_s} | status={status} | id={oid}\n"

        # Статус последней заявки намеренно не показываем в "Портфеле" (по требованию пользователя).

        # recent_operations выводим только там, где это действительно "История сделок".
        # В портфеле этот блок не показываем, чтобы не путать пользователя.
        
        return message


class TelegramControlPanel:
    """
    Панель управления ботом через Telegram кнопки.

    Важно: команды обрабатываются ТОЛЬКО из TELEGRAM_CHAT_ID.
    """

    def __init__(
        self,
        token: str,
        chat_id: int | str,
        keyboard_factory: Callable[[], Optional[InlineKeyboardMarkup]],
        on_start: Callable[[], Awaitable[None]],
        on_stop: Callable[[], Awaitable[None]],
        get_status_text: Callable[[], str],
        get_portfolio_text: Callable[[], str],
        get_trades_text: Callable[[], str],
        get_day_report_text: Optional[Callable[[str], str]] = None,
    ):
        self.token = token
        self.chat_id = int(chat_id) if str(chat_id).lstrip("-").isdigit() else chat_id
        self.keyboard_factory = keyboard_factory
        self.on_start = on_start
        self.on_stop = on_stop
        self.get_status_text = get_status_text
        self.get_portfolio_text = get_portfolio_text
        self.get_trades_text = get_trades_text
        self.get_day_report_text = get_day_report_text
        self.app: Optional[Application] = None
        # хранение последнего запроса диапазона (в рамках одного чата)
        self._pending_range: Optional[tuple[str, str]] = None

    def _authorized(self, update: Update) -> bool:
        try:
            cid = update.effective_chat.id if update.effective_chat else None
            return cid == self.chat_id
        except Exception:
            return False

    async def _cmd_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update):
            try:
                logger.warning(f"Telegram: неавторизованный /menu от chat_id={update.effective_chat.id if update.effective_chat else None}")
            except Exception:
                pass
            return
        try:
            logger.info(f"Telegram: /menu от chat_id={update.effective_chat.id if update.effective_chat else None}")
        except Exception:
            pass
        kb = self.keyboard_factory()
        await update.effective_message.reply_text("Панель управления:", reply_markup=kb)

    async def _cmd_day(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update):
            return
        if not self.get_day_report_text:
            await update.effective_message.reply_text("Отчет /day недоступен в этой сборке.")
            return
        args = getattr(context, "args", None) or []
        if not args:
            await update.effective_message.reply_text(
                "Использование:\n"
                "- /day YYYY-MM-DD\n"
                "- /day YYYY-MM-DD YYYY-MM-DD (диапазон)\n\n"
                "Пример: /day 2026-01-02 2026-01-04"
            )
            return

        # Диапазон: /day 2026-01-02 2026-01-04
        if len(args) >= 2:
            start = str(args[0]).strip()
            end = str(args[1]).strip()
            self._pending_range = (start, end)
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📆 По дням", callback_data=f"DAYR|{start}|{end}|D")],
                [InlineKeyboardButton("📈 Среднее за период", callback_data=f"DAYR|{start}|{end}|A")],
                [InlineKeyboardButton("📆+📈 По дням + среднее", callback_data=f"DAYR|{start}|{end}|B")],
            ])
            await update.effective_message.reply_text(
                f"Вы указали период *{start} → {end}*.\n\n"
                "Что вывести?",
                parse_mode="Markdown",
                reply_markup=kb
            )
            return

        # Один день
        date_str = str(args[0]).strip()
        text = self.get_day_report_text(date_str)
        await update.effective_message.reply_text(text, parse_mode="Markdown")

    async def _on_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update):
            try:
                logger.warning(
                    f"Telegram: неавторизованный callback от chat_id={update.effective_chat.id if update.effective_chat else None}"
                )
            except Exception:
                pass
            return
        query = update.callback_query
        if not query:
            return
        data = query.data or ""
        try:
            mid = getattr(query.message, "message_id", None) if query.message else None
            logger.info(f"Telegram: нажата кнопка {data} (chat_id={self.chat_id}, message_id={mid})")
        except Exception:
            pass
        await query.answer()

        async def _safe_edit(text: str, *, parse_mode: Optional[str] = None):
            """
            Telegram иногда падает на Markdown разметке (Can't parse entities) или Message_too_long.
            Тогда повторяем отправку без parse_mode или сокращаем текст, чтобы кнопка всегда отвечала.
            """
            try:
                # Проверяем длину сообщения (лимит Telegram: 4096 символов)
                if len(text) > 4096:
                    logger.warning(f"Telegram: {data} — сообщение слишком длинное ({len(text)} символов), сокращаем")
                    # Сокращаем до 4000 символов с предупреждением
                    text = text[:4000] + "\n\n⚠️ _Сообщение обрезано (превышен лимит Telegram)_"
                
                await query.edit_message_text(text, reply_markup=self.keyboard_factory(), parse_mode=parse_mode)
            except Exception as e:
                msg = str(e)
                if "Message is not modified" in msg:
                    logger.info(f"Telegram: {data} — сообщение не изменилось (Message is not modified)")
                    return
                if "Message_too_long" in msg or "message is too long" in msg.lower():
                    logger.warning(f"Telegram: {data} — сообщение слишком длинное, отправляем сокращенную версию")
                    # Пытаемся отправить без разметки (может быть короче)
                    try:
                        shortened = text[:3800] + "\n\n⚠️ _Сообщение обрезано (превышен лимит Telegram)_"
                        await query.edit_message_text(shortened, reply_markup=self.keyboard_factory())
                        return
                    except Exception:
                        # Если и это не помогло, отправляем минимальное сообщение
                        await query.edit_message_text(
                            f"⚠️ Сообщение слишком длинное ({len(text)} символов).\n"
                            f"Попробуйте позже или уменьшите количество позиций.",
                            reply_markup=self.keyboard_factory()
                        )
                        return
                if "Can't parse entities" in msg or "can't parse entities" in msg:
                    logger.warning(f"Telegram: {data} — ошибка Markdown, повторяем без разметки: {e}")
                    await query.edit_message_text(text, reply_markup=self.keyboard_factory())
                    return
                logger.error(f"Telegram: ошибка {data}: {e}", exc_info=True)
                raise

        # Выбор режима отчёта по диапазону
        if data.startswith("DAYR|"):
            if not self.get_day_report_text:
                await _safe_edit("Отчет /day недоступен в этой сборке.")
                return
            try:
                _, start, end, mode = data.split("|", 3)
            except Exception:
                await _safe_edit("Некорректный формат запроса периода.")
                return

            # Пробрасываем в get_day_report_text строкой "start..end|mode"
            text = self.get_day_report_text(f"{start}..{end}|{mode}")
            await _safe_edit(text, parse_mode="Markdown")
            return

        if data == "CTL_START":
            await self.on_start()
            await _safe_edit("▶️ Входы (BUY) включены.")
        elif data == "CTL_STOP":
            await self.on_stop()
            await _safe_edit("⏸ Входы (BUY) выключены.")
        elif data == "CTL_STATUS":
            await _safe_edit(self.get_status_text(), parse_mode="Markdown")
        elif data == "CTL_PORTFOLIO":
            await _safe_edit(self.get_portfolio_text(), parse_mode="Markdown")
        elif data == "CTL_TRADES":
            await _safe_edit(self.get_trades_text(), parse_mode="Markdown")
        elif data == "CTL_DAY":
            await _safe_edit(
                "📅 *Отчёт /day*\n\n"
                "Команды:\n"
                "- `/day YYYY-MM-DD`\n"
                "- `/day YYYY-MM-DD YYYY-MM-DD`\n\n"
                "После ввода диапазона бот спросит: вывести *по дням* или *среднее*.\n\n"
                "Пример: `/day 2026-01-02 2026-01-04`",
                parse_mode="Markdown",
            )
        else:
            logger.info(f"Telegram: неизвестный callback data={data}")

    async def _on_error(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Глобальный error handler для python-telegram-bot, чтобы ошибки не терялись в логах."""
        try:
            err = getattr(context, "error", None)
            logger.error(f"Telegram: ошибка обработчика: {err}", exc_info=True)
        except Exception:
            pass

    async def start(self):
        if not TELEGRAM_AVAILABLE or not self.token:
            return

        # Никогда не даем этому корутину "ронять" основной процесс.
        # Если Telegram временно недоступен — просто ретраим.
        while True:
            try:
                req = HTTPXRequest(connect_timeout=15, read_timeout=30, write_timeout=30, pool_timeout=30)
                self.app = ApplicationBuilder().token(self.token).request(req).build()
                self.app.add_handler(CommandHandler("menu", self._cmd_menu))
                self.app.add_handler(CommandHandler("start", self._cmd_menu))
                self.app.add_handler(CommandHandler("day", self._cmd_day))
                self.app.add_handler(CallbackQueryHandler(self._on_callback))
                self.app.add_error_handler(self._on_error)

                await self.app.initialize()
                await self.app.start()
                if self.app.updater:
                    await self.app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
                logger.info("Telegram: polling запущен и готов принимать нажатия кнопок.")
                return
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.warning(f"Telegram панель: ошибка запуска ({e}). Повтор через 10с...")
                try:
                    if self.app:
                        await self.stop()
                except Exception:
                    pass
                await asyncio.sleep(10)

    async def stop(self):
        if not self.app:
            return
        try:
            if self.app.updater:
                await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
        finally:
            self.app = None
