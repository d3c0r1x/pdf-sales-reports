"""Конфигурация бота проекта 3 через переменные окружения."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

BOT_TOKEN = os.getenv("WB_BOT_TOKEN", "")
