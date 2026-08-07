"""Генерация mock-данных продаж (симуляция выгрузки из CRM) в CSV.

Столбцы: date; product_name; units; revenue; cost
CSV в кодировке utf-8-sig с разделителем ";" (открывается и в Excel).
"""
from __future__ import annotations

import csv
import os
import random
from datetime import date, timedelta

# (название, розничная цена, себестоимость)
PRODUCTS: list[tuple[str, int, int]] = [
    ("Смартфон Nova X", 18990, 14200),
    ("Наушники AirSound Pro", 5990, 3800),
    ("Умные часы FitTrack", 7490, 5200),
    ("Портативная колонка BoomBox", 3990, 2300),
    ("Фитнес-браслет Pulse", 2990, 1700),
    ("Зарядное устройство 65W", 1890, 900),
    ("Кабель USB-C 2м", 590, 210),
    ("Чехол для телефона", 890, 380),
    ("Внешний SSD 1TB", 8990, 6100),
    ("Веб-камера HD", 3490, 2100),
    ("Микрофон Studio", 5490, 3600),
    ("Клавиатура Mech", 4490, 2900),
    ("Мышь Ergo", 2490, 1500),
    ('Монитор 27"', 15990, 11800),
    ("Ноутбук-станция", 49990, 38500),
]

DAYS_BACK = 90
ROWS = 400
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "sales.csv")


def main(csv_path: str = CSV_PATH) -> None:
    """Генерирует CSV в указанный файл (по умолчанию sales.csv)."""
    random.seed(42)  # воспроизводимость
    today = date.today()
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["date", "product_name", "units", "revenue", "cost"])
        for _ in range(ROWS):
            name, price, unit_cost = random.choice(PRODUCTS)
            units = random.randint(1, 15)
            day = today - timedelta(days=random.randint(0, DAYS_BACK))
            writer.writerow([day.isoformat(), name, units, units * price, units * unit_cost])
    print(f"Готово: {csv_path} ({ROWS} строк)")


if __name__ == "__main__":
    main()
