"""Генерация mock-данных продаж (симуляция выгрузки из CRM) в CSV.

Столбцы: date; product_name; category; units; revenue; cost
CSV в кодировке utf-8-sig с разделителем ";" (открывается и в Excel).

Продвинутый уровень: категории товаров (для разрезов в отчёте),
детерминированный seed и увеличенный объём данных (1200 строк за 180 дней).
"""
from __future__ import annotations

import csv
import os
import random
from datetime import date, timedelta

# (название, розничная цена, себестоимость, категория)
PRODUCTS: list[tuple[str, int, int, str]] = [
    ("Смартфон Nova X", 18990, 14200, "Электроника"),
    ("Монитор 27\"", 15990, 11800, "Электроника"),
    ("Ноутбук-станция", 49990, 38500, "Электроника"),
    ("Наушники AirSound Pro", 5990, 3800, "Аудио"),
    ("Портативная колонка BoomBox", 3990, 2300, "Аудио"),
    ("Микрофон Studio", 5490, 3600, "Аудио"),
    ("Умные часы FitTrack", 7490, 5200, "Гаджеты"),
    ("Фитнес-браслет Pulse", 2990, 1700, "Гаджеты"),
    ("Внешний SSD 1TB", 8990, 6100, "Гаджеты"),
    ("Зарядное устройство 65W", 1890, 900, "Аксессуары"),
    ("Кабель USB-C 2м", 590, 210, "Аксессуары"),
    ("Чехол для телефона", 890, 380, "Аксессуары"),
    ("Веб-камера HD", 3490, 2100, "Периферия"),
    ("Клавиатура Mech", 4490, 2900, "Периферия"),
    ("Мышь Ergo", 2490, 1500, "Периферия"),
]

DAYS_BACK = 180
ROWS = 1200
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "sales.csv")


def main(csv_path: str = CSV_PATH) -> None:
    """Генерирует CSV в указанный файл (по умолчанию sales.csv)."""
    random.seed(42)  # воспроизводимость: данные одинаковы между запусками
    today = date.today()
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["date", "product_name", "category", "units", "revenue", "cost"])
        for _ in range(ROWS):
            name, price, unit_cost, category = random.choice(PRODUCTS)
            units = random.randint(1, 15)
            day = today - timedelta(days=random.randint(0, DAYS_BACK))
            writer.writerow(
                [day.isoformat(), name, category, units, units * price, units * unit_cost]
            )
    print(f"Готово: {csv_path} ({ROWS} строк)")


if __name__ == "__main__":
    main()
