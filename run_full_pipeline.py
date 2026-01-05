"""
Полный цикл обработки отзывов из Google Sheets.

Выполняет три последовательных шага:
1. Получение данных из Google Sheets
2. Проверка и исправление отзывов через LLM
3. Загрузка результатов обратно в Google Sheets
"""

import os
import asyncio
import time

from gsheets.fetch_reviews import fetch_reviews_from_sheets
from process_reviews import process_all_reviews
from gsheets.update_sheets import update_all_sheets


def run_full_pipeline(model: str = "gpt-4o", max_concurrent: int = 100, max_retries: int = 3):
    """Запускает полный цикл обработки отзывов."""
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    gsheets_dir = os.path.join(current_dir, "gsheets")
    sheets_config_file = os.path.join(gsheets_dir, "sheets_config.json")
    credentials_file = os.path.join(gsheets_dir, "credentials.json")
    
    # Шаг 1: Получение данных из Google Sheets
    reviews = fetch_reviews_from_sheets()
    
    # Шаг 2: Проверка отзывов через LLM
    processed_reviews = asyncio.run(process_all_reviews(
        data=reviews,
        model=model,
        max_concurrent=max_concurrent,
        max_retries=max_retries
    ))
    
    # Шаг 3: Загрузка результатов в Google Sheets
    update_all_sheets(
        reviews_data=processed_reviews,
        sheets_config_path=sheets_config_file,
        credentials_path=credentials_file
    )


if __name__ == "__main__":
    MODEL = "grok-4-1-fast-reasoning"
    MAX_CONCURRENT = 100
    MAX_RETRIES = 3
    SLEEP_MINUTES = 5  # Интервал между циклами в минутах
    
    while True:
        try:
            run_full_pipeline(
                model=MODEL,
                max_concurrent=MAX_CONCURRENT,
                max_retries=MAX_RETRIES
            )
            
            print(f"\nСледующий запуск через {SLEEP_MINUTES} минут\n")
            
        except KeyboardInterrupt:
            print("\n\nОСТАНОВЛЕНО ПОЛЬЗОВАТЕЛЕМ\n")
            break
            
        except Exception as e:
            print(f"\n\nОШИБКА: {e}")
            print(f"Следующая попытка через {SLEEP_MINUTES} минут\n")
        
        # Ожидание перед следующим циклом
        sleep_seconds = SLEEP_MINUTES * 60
        time.sleep(sleep_seconds)

