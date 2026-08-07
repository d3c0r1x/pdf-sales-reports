"""Генерация PDF-отчёта.

Стек (строго по ТЗ):
  - pandas  — чтение CSV и расчёт выручки/маржи;
  - matplotlib — график топ-10 товаров;
  - reportlab (Platypus) — сборка PDF с текстом и картинкой графика.

Память: CSV читается ПО ЧАНКАМ (chunksize), агрегаты (суммы, топ-10) копятся
инкрементально — расход памяти не зависит от размера файла, поэтому выгрузка
из CRM на сотни МБ не уронит процесс MemoryError'ом.

Запуск офлайн:  python report.py   (создаст sales.csv при необходимости,
top10.png и report.pdf).
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import matplotlib

matplotlib.use("Agg")  # без GUI-бэкенда — работает на сервере и в Windows
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer  # noqa: E402

# Пути относительно папки проекта, а не текущей директории (CWD) — так бот
# работает при запуске из любого места
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "sales.csv")
CHART_PATH = os.path.join(BASE_DIR, "top10.png")
PDF_PATH = os.path.join(BASE_DIR, "report.pdf")


@dataclass
class SalesReport:
    """Агрегированные показатели (маленький объект, не зависит от размера CSV)."""

    total_revenue: int
    total_margin: int
    margin_percent: float
    date_min: str
    date_max: str
    top10: pd.DataFrame  # колонки: product_name, revenue (не более 10 строк)


def ensure_data(csv_path: str = CSV_PATH) -> None:
    """Если CSV нет — генерируем mock-данные (как в ТЗ: 'Mock-данные (CSV),
    генерируемые скриптом')."""
    if not os.path.exists(csv_path):
        import generate_mock_data

        generate_mock_data.main(csv_path)


def aggregate_sales(csv_path: str = CSV_PATH, chunksize: int = 10_000) -> SalesReport:
    """Поточная агрегация CSV по чанкам (pandas.read_csv chunksize).

    В памяти держатся только итоговые суммы и словарь «товар → выручка»,
    а не весь DataFrame — MemoryError при больших файлах исключён.
    """
    ensure_data(csv_path)

    total_revenue = 0
    total_margin = 0
    date_min: str | None = None
    date_max: str | None = None
    per_product: dict[str, int] = {}

    for chunk in pd.read_csv(csv_path, sep=";", chunksize=chunksize):
        chunk["margin"] = chunk["revenue"] - chunk["cost"]
        total_revenue += int(chunk["revenue"].sum())
        total_margin += int(chunk["margin"].sum())
        # Строки CSV НЕ отсортированы по дате, поэтому min/max считаем по всем
        # чанкам (ISO-даты сравниваются лексикографически корректно)
        chunk_min = str(chunk["date"].min())
        chunk_max = str(chunk["date"].max())
        date_min = chunk_min if date_min is None else min(date_min, chunk_min)
        date_max = chunk_max if date_max is None else max(date_max, chunk_max)
        for name, revenue in chunk.groupby("product_name")["revenue"].sum().items():
            per_product[name] = per_product.get(name, 0) + int(revenue)

    top10 = (
        pd.Series(per_product, name="revenue")
        .sort_values(ascending=True)
        .tail(10)
        .rename_axis("product_name")
        .reset_index()
    )
    margin_percent = total_margin / total_revenue * 100 if total_revenue else 0.0
    return SalesReport(
        total_revenue=total_revenue,
        total_margin=total_margin,
        margin_percent=margin_percent,
        date_min=date_min or "-",
        date_max=date_max or "-",
        top10=top10,
    )


def build_chart(report: SalesReport, chart_path: str = CHART_PATH) -> None:
    """График топ-10 товаров по выручке (matplotlib)."""
    top10 = report.top10  # уже отсортирован по возрастанию
    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    ax.barh(top10["product_name"], top10["revenue"], color="#4C78A8")
    ax.set_title("Топ-10 товаров по выручке")
    ax.set_xlabel("Выручка, руб.")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(chart_path)
    plt.close(fig)
    print(f"Готово: {chart_path}")


def build_pdf(
    report: SalesReport,
    pdf_path: str = PDF_PATH,
    chart_path: str = CHART_PATH,
) -> None:
    """Собирает PDF-отчёт (reportlab): текст + картинка графика."""
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Отчёт по продажам (mock-выгрузка из CRM)", styles["Title"]),
        Spacer(1, 6 * mm),
        Paragraph(
            f"Период: {report.date_min} — {report.date_max}", styles["Normal"]
        ),
        Spacer(1, 4 * mm),
        Paragraph(
            f"<b>Общая выручка:</b> {_fmt(report.total_revenue)} руб.",
            styles["Normal"],
        ),
        Paragraph(
            f"<b>Валовая маржа:</b> {_fmt(report.total_margin)} руб. "
            f"({report.margin_percent:.1f}%)",
            styles["Normal"],
        ),
        Spacer(1, 6 * mm),
        Paragraph("Топ-10 товаров по выручке:", styles["Heading2"]),
        Spacer(1, 4 * mm),
        Image(chart_path, width=170 * mm, height=100 * mm),
    ]
    doc = SimpleDocTemplate(pdf_path, pagesize=A4, title="Отчёт по продажам")
    doc.build(story)
    print(f"Готово: {pdf_path}")


def _fmt(value: int) -> str:
    return f"{value:,}".replace(",", " ")


if __name__ == "__main__":
    report = aggregate_sales()
    build_chart(report)
    build_pdf(report)
    print(
        f"Выручка: {report.total_revenue:,} руб. | Маржа: {report.total_margin:,} руб. "
        f"({report.margin_percent:.1f}%)"
    )
