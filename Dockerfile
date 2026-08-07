FROM python:3.11-slim

WORKDIR /app

# Шрифты matplotlib для графиков (кириллица)
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# CLI без бота: docker run --rm -v $(pwd):/app python report.py --input /app/sales.csv
CMD ["python", "bot.py"]
