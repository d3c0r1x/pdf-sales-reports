"""Генерация PDF-отчёта.

Стек (строго по ТЗ):
  - pandas  — чтение CSV и расчёт выручки/маржи;
  - matplotlib — графики (топ-10 товаров + динамика выручки по дням);
  - reportlab (Platypus) — сборка PDF: текст + таблица топ-10 + графика.

Память: CSV читается ПО ЧАНКАМ (chunksize), агрегаты копятся инкрементально —
расход памяти не зависит от размера файла.

Продвинутый уровень:
  - два разреза: топ-10 товаров и выручка по дням, категории товаров;
  - таблица топ-10 в PDF (reportlab Table) с итоговой строкой;
  - CLI: python report.py --input sales.csv --output report.pdf --chart top10.png.

Запуск офлайн:  python report.py   (создаст sales.csv при необходимости).
"""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass

import matplotlib

matplotlib.use("Agg")  # без GUI-бэкенда — работает на сервере и в Windows
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Пути относительно папки проекта, а не текущей директории (CWD) — так бот
# работает при запуске из любого места
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "sales.csv")
CHART_PATH = os.path.join(BASE_DIR, "top10.png")
PDF_PATH = os.path.join(BASE_DIR, "report.pdf")


def _register_cyrillic_font() -> str:
    """Подключает TTF с кириллицей и возвращает имя базового шрифта.

    Стандартные шрифты reportlab (Helvetica и др.) кириллицы не содержат:
    русский текст молча превращается в «?». Берём DejaVu Sans — он уже идёт
    в поставке matplotlib, поэтому ничего дополнительно устанавливать не нужно.
    """
    try:
        mpl_dir = os.path.dirname(matplotlib.__file__)
        ttf_dir = os.path.join(mpl_dir, "mpl-data", "fonts", "ttf")
        pdfmetrics.registerFont(
            TTFont("DejaVuSans", os.path.join(ttf_dir, "DejaVuSans.ttf"))
        )
        pdfmetrics.registerFont(
            TTFont("DejaVuSans-Bold", os.path.join(ttf_dir, "DejaVuSans-Bold.ttf"))
        )
        pdfmetrics.registerFontFamily(
            "DejaVuSans",
            normal="DejaVuSans",
            bold="DejaVuSans-Bold",
            italic="DejaVuSans",
            boldItalic="DejaVuSans-Bold",
        )
        return "DejaVuSans"
    except Exception:
        # Теоретический фолбэк: PDF соберётся, но без кириллицы
        return "Helvetica"


FONT_NORMAL = _register_cyrillic_font()
# Для Helvetica "Helvetica" + "-Bold" — тоже правильное имя, условие не нужно
FONT_BOLD = FONT_NORMAL + "-Bold"


@dataclass
class SalesReport:
    """Агрегированные показатели (маленький объект, не зависит от размера CSV)."""

    total_revenue: int
    total_margin: int
    margin_percent: float
    date_min: str
    date_max: str
    top10: pd.DataFrame        # колонки: product_name, revenue (не более 10 строк)
    daily_revenue: pd.Series   # выручка по дням (для графика динамики)
    category_revenue: pd.Series  # выручка по категориям


def ensure_data(csv_path: str = CSV_PATH) -> None:
    """Если CSV нет — генерируем mock-данные (как в ТЗ: 'Mock-данные (CSV),
    генерируемые скриптом')."""
    if not os.path.exists(csv_path):
        import generate_mock_data

        generate_mock_data.main(csv_path)


def aggregate_sales(csv_path: str = CSV_PATH, chunksize: int = 10_000) -> SalesReport:
    """Поточная агрегация CSV по чанкам (pandas.read_csv chunksize).

    В памяти держатся только итоговые суммы и словари «товар → выручка»,
    «день → выручка», «категория → выручка» — MemoryError исключён.
    """
    ensure_data(csv_path)

    total_revenue = 0
    total_margin = 0
    date_min: str | None = None
    date_max: str | None = None
    per_product: dict[str, int] = {}
    per_day: dict[str, int] = {}
    per_category: dict[str, int] = {}

    for chunk in pd.read_csv(csv_path, sep=";", chunksize=chunksize):
        chunk["margin"] = chunk["revenue"] - chunk["cost"]
        total_revenue += int(chunk["revenue"].sum())
        total_margin += int(chunk["margin"].sum())
        # ISO-даты сравниваются лексикографически корректно
        chunk_min = str(chunk["date"].min())
        chunk_max = str(chunk["date"].max())
        date_min = chunk_min if date_min is None else min(date_min, chunk_min)
        date_max = chunk_max if date_max is None else max(date_max, chunk_max)

        for name, revenue in chunk.groupby("product_name")["revenue"].sum().items():
            per_product[name] = per_product.get(name, 0) + int(revenue)
        for day, revenue in chunk.groupby("date")["revenue"].sum().items():
            per_day[str(day)] = per_day.get(str(day), 0) + int(revenue)
        if "category" in chunk.columns:
            for cat, revenue in chunk.groupby("category")["revenue"].sum().items():
                per_category[str(cat)] = per_category.get(str(cat), 0) + int(revenue)

    top10 = (
        pd.Series(per_product, name="revenue")
        .sort_values(ascending=True)
        .tail(10)
        .rename_axis("product_name")
        .reset_index()
    )
    daily = pd.Series(per_day, name="revenue").sort_index()
    categories = pd.Series(per_category, name="revenue").sort_values(ascending=False)
    margin_percent = total_margin / total_revenue * 100 if total_revenue else 0.0
    return SalesReport(
        total_revenue=total_revenue,
        total_margin=total_margin,
        margin_percent=margin_percent,
        date_min=date_min or "-",
        date_max=date_max or "-",
        top10=top10,
        daily_revenue=daily,
        category_revenue=categories,
    )


def build_chart(report: SalesReport, chart_path: str = CHART_PATH) -> None:
    """Два графика в одной фигуре: топ-10 товаров и динамика выручки по дням."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), dpi=150)
    fig.suptitle("Аналитика продаж", fontsize=14, fontweight="bold")

    top10 = report.top10  # уже отсортирован по возрастанию
    ax1.barh(top10["product_name"], top10["revenue"], color="#4C78A8")
    ax1.set_title("Топ-10 товаров по выручке")
    ax1.set_xlabel("Выручка, руб.")
    ax1.grid(axis="x", alpha=0.3)

    daily = report.daily_revenue
    ax2.plot(daily.index, daily.values, color="#E45756", linewidth=1.5)
    ax2.fill_between(daily.index, daily.values, alpha=0.15, color="#E45756")
    ax2.set_title("Выручка по дням")
    ax2.set_ylabel("Выручка, руб.")
    ax2.grid(alpha=0.3)
    # Не захламляем ось X десятками дат
    if len(daily) > 12:
        step = max(1, len(daily) // 8)
        ax2.set_xticks(daily.index[::step])
        ax2.tick_params(axis="x", rotation=30)

    fig.tight_layout()
    fig.savefig(chart_path)
    plt.close(fig)
    print(f"Готово: {chart_path}")


def build_pdf(
    report: SalesReport,
    pdf_path: str = PDF_PATH,
    chart_path: str = CHART_PATH,
) -> None:
    """Собирает PDF-отчёт (reportlab): заголовок, показатели, таблица, график."""
    styles = getSampleStyleSheet()
    if FONT_NORMAL != "Helvetica":
        styles["Title"].fontName = FONT_BOLD
        styles["Heading2"].fontName = FONT_BOLD
        styles["Normal"].fontName = FONT_NORMAL
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
        Spacer(1, 2 * mm),
        Paragraph(_fmt_category_line(report), styles["Normal"]),
        Spacer(1, 6 * mm),
        Paragraph("Топ-10 товаров по выручке:", styles["Heading2"]),
        Spacer(1, 4 * mm),
        _build_table(report),
        Spacer(1, 6 * mm),
        Paragraph("Графики:", styles["Heading2"]),
        Spacer(1, 4 * mm),
        Image(chart_path, width=180 * mm, height=77 * mm),
    ]
    doc = SimpleDocTemplate(pdf_path, pagesize=A4, title="Отчёт по продажам")
    doc.build(story)
    print(f"Готово: {pdf_path}")


def _build_table(report: SalesReport) -> Table:
    """Таблица топ-10 (reportlab Table) с итоговой строкой — продвинутый приём."""
    header = ["#", "Товар", "Выручка, руб.", "Доля"]
    rows = [list(header)]  # шапка — ОДНА строка слева направо
    total = report.total_revenue or 1
    for i, (name, revenue) in enumerate(
        zip(report.top10["product_name"], report.top10["revenue"]), start=1
    ):
        share = revenue / total * 100
        rows.append([str(i), str(name), _fmt(int(revenue)), f"{share:.1f}%"])
    rows.append(["", "<b>Итого (топ-10)</b>", _fmt(int(report.top10["revenue"].sum())), ""])

    table = Table(rows, colWidths=[10 * mm, 70 * mm, 40 * mm, 30 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4C78A8")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.whitesmoke]),
                ("FONTNAME", (0, -1), (-1, -1), FONT_BOLD),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E8F0FA")),
                ("ALIGN", (2, 1), (3, -1), "RIGHT"),
            ]
        )
    )
    return table


def _fmt_category_line(report: SalesReport) -> str:
    if report.category_revenue.empty:
        return ""
    parts = [f"{cat}: {_fmt(int(rev))} руб." for cat, rev in report.category_revenue.items()]
    return "<b>Выручка по категориям:</b> " + "; ".join(parts)


def _fmt(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def build_parser() -> argparse.ArgumentParser:
    """CLI: python report.py --input sales.csv --output report.pdf --chart top10.png."""
    parser = argparse.ArgumentParser(description="Генерация PDF-отчёта по продажам")
    parser.add_argument("--input", default=CSV_PATH, help="путь к CSV (по умолчанию sales.csv)")
    parser.add_argument("--output", default=PDF_PATH, help="путь к PDF-отчёту")
    parser.add_argument("--chart", default=CHART_PATH, help="путь к PNG-графику")
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    report = aggregate_sales(args.input)
    build_chart(report, args.chart)
    build_pdf(report, args.output, args.chart)
    print(
        f"Выручка: {_fmt(report.total_revenue)} руб. | Маржа: {_fmt(report.total_margin)} руб. "
        f"({report.margin_percent:.1f}%)"
    )
