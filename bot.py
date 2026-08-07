"""Telegram-бот: генерирует PDF-отчёт и отправляет его (роль — 'директор').

Стек (строго по ТЗ): pandas, matplotlib, reportlab, aiogram.

Продвинутый уровень:
  - middlewares: троттлинг и логирование;
  - /stats — текстовая сводка показателей без генерации PDF;
  - /chart — отправка графика PNG отдельно;
  - /report — полный отчёт (графики + таблица топ-10) в одном PDF.

Запуск:  python bot.py  (задайте WB_BOT_TOKEN).
"""
from __future__ import annotations

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import FSInputFile, Message

import config
from middlewares import LoggingMiddleware, ThrottlingMiddleware
from report import CHART_PATH, PDF_PATH, aggregate_sales, build_chart, build_pdf

# Логирование в консоль и в файл bot.log рядом с ботом
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(config.BASE_DIR, "bot.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет! Я генерирую PDF-отчёты по продажам.\n\n"
        "/report — сгенерировать и отправить PDF-отчёт\n"
        "/stats — текстовая сводка показателей\n"
        "/chart — график топ-10 и динамики (PNG)"
    )


@router.message(Command("report"))
async def cmd_report(message: Message) -> None:
    status = await message.answer("⏳ Генерирую отчёт…")
    try:
        report = aggregate_sales()
        build_chart(report)
        build_pdf(report)
    except Exception as exc:
        logger.exception("Ошибка генерации отчёта")
        await status.edit_text(f"⚠️ Ошибка генерации: {exc}")
        return

    pdf = FSInputFile(PDF_PATH, filename="sales_report.pdf")
    await message.answer_document(pdf, caption="📄 Отчёт по продажам (PDF)")
    await status.delete()


@router.message(Command("chart"))
async def cmd_chart(message: Message) -> None:
    status = await message.answer("⏳ Строю график…")
    try:
        report = aggregate_sales()
        build_chart(report)
    except Exception as exc:
        logger.exception("Ошибка построения графика")
        await status.edit_text(f"⚠️ Ошибка: {exc}")
        return
    png = FSInputFile(CHART_PATH, filename="sales_chart.png")
    await message.answer_document(png, caption="📊 График: топ-10 товаров и динамика выручки")
    await status.delete()


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    status = await message.answer("⏳ Считаю показатели…")
    try:
        report = aggregate_sales()
    except Exception as exc:
        logger.exception("Ошибка агрегации")
        await status.edit_text(f"⚠️ Ошибка: {exc}")
        return
    cat_line = "; ".join(
        f"{cat}: {report.total_revenue and round(rev / report.total_revenue * 100, 1)}%"
        for cat, rev in report.category_revenue.items()
    ) if not report.category_revenue.empty else "—"
    await status.edit_text(
        f"📊 <b>Сводка по продажам</b>\n\n"
        f"Период: {report.date_min} — {report.date_max}\n"
        f"Общая выручка: <b>{_fmt(report.total_revenue)} руб.</b>\n"
        f"Валовая маржа: <b>{_fmt(report.total_margin)} руб.</b> "
        f"({report.margin_percent:.1f}%)\n"
        f"Категории (доля выручки): {cat_line}\n\n"
        "Полный отчёт: /report"
    )


def _fmt(value: int) -> str:
    return f"{value:,}".replace(",", " ")


async def main() -> None:
    if not config.BOT_TOKEN:
        raise SystemExit("Не задан WB_BOT_TOKEN. Скопируйте .env.example и задайте токен.")
    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    dp.message.middleware(ThrottlingMiddleware(min_interval=config.THROTTLE_MIN_INTERVAL))
    dp.update.middleware(LoggingMiddleware())
    logger.info("Бот запущен")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
