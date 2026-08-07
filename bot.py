"""Telegram-бот: генерирует PDF-отчёт и отправляет его (роль — 'директор').

Стек (строго по ТЗ): pandas, matplotlib, reportlab, aiogram.
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
from report import PDF_PATH, aggregate_sales, build_chart, build_pdf

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
        "/report — сгенерировать и отправить отчёт"
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


async def main() -> None:
    if not config.BOT_TOKEN:
        raise SystemExit("Не задан WB_BOT_TOKEN. Скопируйте .env.example и задайте токен.")
    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    logger.info("Бот запущен")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
