"""Smoke-тесты: поточная агрегация CSV и генерация PNG/PDF."""
import os
import random
from datetime import date, timedelta

import pandas as pd

from report import aggregate_sales, build_chart, build_pdf


def test_report_pipeline(tmp_path) -> None:
    """CSV (генерится автоматически) -> агрегаты -> график -> PDF."""
    csv_path = str(tmp_path / "sales.csv")
    chart_path = str(tmp_path / "top10.png")
    pdf_path = str(tmp_path / "report.pdf")

    report = aggregate_sales(csv_path)
    assert report.total_revenue > 0
    assert report.total_margin > 0
    assert report.margin_percent > 0
    assert len(report.top10) <= 10

    build_chart(report, chart_path)
    build_pdf(report, pdf_path, chart_path)
    assert os.path.getsize(pdf_path) > 1000
    assert os.path.getsize(chart_path) > 1000


def test_multi_chunk_date_range(tmp_path) -> None:
    """Файл больше chunksize: период должен охватывать ВСЕ даты, а не только
    из первого чанка (регрессия: date_min раньше брался только из чанка №1)."""
    random.seed(1)
    base = date(2026, 1, 1)
    rows = []
    for _ in range(25_000):  # 3 чанка по 10 000
        d = base + timedelta(days=random.randint(0, 90))
        rows.append({"date": d.isoformat(), "product_name": "X",
                     "units": 1, "revenue": 100, "cost": 50})
    csv_path = str(tmp_path / "big.csv")
    pd.DataFrame(rows).to_csv(csv_path, sep=";", index=False)

    report = aggregate_sales(csv_path, chunksize=10_000)
    assert report.total_revenue == 25_000 * 100
    assert report.total_margin == 25_000 * 50
    assert report.date_min == "2026-01-01"
    assert report.date_max == "2026-04-01"
