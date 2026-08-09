"""Тесты P3: поточная агрегация, графики, PDF-таблица, CLI, mock-данные.

Запуск: python -m pytest tests -q
"""
import csv

from report import aggregate_sales, build_chart, build_pdf, build_parser

FIXTURE = """date;product_name;category;units;revenue;cost
2026-07-01;Товар A;Кат1;10;10000;6000
2026-07-01;Товар B;Кат2;5;5000;2000
2026-07-02;Товар A;Кат1;7;7000;4200
2026-07-03;Товар C;Кат2;3;3000;1000
"""


def _write_fixture(tmp_path):
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text(FIXTURE, encoding="utf-8")
    return str(csv_path)


def test_aggregate_sales(tmp_path) -> None:
    report = aggregate_sales(_write_fixture(tmp_path))
    assert report.total_revenue == 25000
    assert report.total_margin == 11800
    assert round(report.margin_percent, 1) == 47.2
    assert report.date_min == "2026-07-01"
    assert report.date_max == "2026-07-03"
    assert len(report.top10) <= 10
    assert report.daily_revenue.sum() == 25000          # разрез по дням
    assert report.category_revenue["Кат1"] == 17000     # разрез по категориям
    assert report.category_revenue["Кат2"] == 8000


def test_build_chart_and_pdf(tmp_path) -> None:
    report = aggregate_sales(_write_fixture(tmp_path))
    chart = tmp_path / "top10.png"
    pdf = tmp_path / "report.pdf"
    build_chart(report, str(chart))
    build_pdf(report, str(pdf), str(chart))
    assert chart.exists() and chart.stat().st_size > 1000
    assert pdf.exists() and pdf.stat().st_size > 1000


def test_pdf_contains_table_rows(tmp_path) -> None:
    """PDF-файл не пустой и содержит текст отчёта (таблица Platypus встроена)."""
    report = aggregate_sales(_write_fixture(tmp_path))
    chart = tmp_path / "top10.png"
    pdf = tmp_path / "report.pdf"
    build_chart(report, str(chart))
    build_pdf(report, str(pdf), str(chart))
    assert pdf.stat().st_size > 1500
    # Кириллица в PDF: стандартные шрифты reportlab (Helvetica/WinAnsi)
    # кириллицы не содержат, поэтому в PDF обязан быть встроен TTF DejaVu Sans
    assert b"DejaVuSans" in pdf.read_bytes()


def test_cli_parser() -> None:
    args = build_parser().parse_args(["--input", "data.csv", "--output", "out.pdf"])
    assert args.input == "data.csv"
    assert args.output == "out.pdf"
    assert args.chart.endswith(".png")


def test_mock_data_generator(tmp_path) -> None:
    """Генератор mock-данных пишет CSV с нужными столбцами и детерминирован."""
    import generate_mock_data

    csv_path = tmp_path / "mock.csv"
    generate_mock_data.main(str(csv_path))
    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh, delimiter=";"))
    assert rows[0] == ["date", "product_name", "category", "units", "revenue", "cost"]
    assert len(rows) - 1 == generate_mock_data.ROWS
    assert all(len(r) == 6 for r in rows[1:])


def test_empty_csv_raises_clear_error(tmp_path) -> None:
    """Пустой CSV — понятная ошибка с подсказкой, а не трейсбек pandas."""
    import pytest

    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="пуст"):
        aggregate_sales(str(csv_path))


def test_missing_column_raises_clear_error(tmp_path) -> None:
    """CSV без столбца revenue — ошибка с перечнем ожидаемых столбцов."""
    import pytest

    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("date;product_name;units\n2026-07-01;Товар A;1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="столбца"):
        aggregate_sales(str(csv_path))
