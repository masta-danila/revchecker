import json
import os
import asyncio
from datetime import datetime
from spelling_checker import check_spelling


async def check_spelling_with_retry(text: str, model: str, max_retries: int = 3) -> dict:
    """
    Вызывает check_spelling с повторными попытками при ошибке.
    
    Args:
        text: Текст для проверки орфографии
        model: Модель для обработки
        max_retries: Максимальное количество попыток (по умолчанию 3)
        
    Returns:
        Результат от check_spelling
        
    Raises:
        Exception: Если все попытки завершились ошибкой
    """
    last_error = None
    
    for attempt in range(1, max_retries + 1):
        try:
            result = await check_spelling(text=text, model=model)
            return result
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                wait_time = attempt * 2
                print(f"  [RETRY] Попытка {attempt}/{max_retries} не удалась: {e}. Повтор через {wait_time}с...")
                await asyncio.sleep(wait_time)
            else:
                print(f"  [ERROR] Все {max_retries} попытки исчерпаны: {e}")
    
    raise last_error


async def mark_single_review(review: dict, sheet_name: str, worksheet_name: str, model: str, max_retries: int = 3) -> dict:
    """
    Размечает орфографические ошибки в одном отзыве.
    
    Args:
        review: Словарь с полями text, corrected_text
        sheet_name: Название таблицы
        worksheet_name: Название листа
        model: Модель для разметки
        max_retries: Максимальное количество попыток при ошибке
        
    Returns:
        Обновленный словарь с размеченным corrected_text
    """
    try:
        corrected_text = review.get("corrected_text", "")
        
        if not corrected_text:
            print(f"  [WARN] Пропущен отзыв без corrected_text в {sheet_name}/{worksheet_name}")
            return review
        
        # Размечаем орфографические ошибки
        result = await check_spelling_with_retry(text=corrected_text, model=model, max_retries=max_retries)
        marked_text = result.get("content", corrected_text)
        cost = result.get("cost", 0)
        
        # Обновляем данные отзыва
        review["corrected_text"] = marked_text
        review["spelling_cost"] = cost
        review["marked_at"] = datetime.now().isoformat()
        
        print(f"  [OK] Размечены ошибки в отзыве в {sheet_name}/{worksheet_name} (cost: ${cost:.6f})")
        
        return review
        
    except Exception as e:
        print(f"  [ERROR] Ошибка разметки ошибок в отзыве в {sheet_name}/{worksheet_name}: {e}")
        return review


async def mark_all_reviews(data: dict, model: str = "grok-4-1-fast-reasoning", max_concurrent: int = 50, max_retries: int = 3) -> dict:
    """
    Асинхронно размечает орфографические ошибки во всех отзывах.
    
    Args:
        data: Структура данных из processed_reviews.json
        model: Модель для разметки
        max_concurrent: Максимальное количество параллельных запросов
        max_retries: Максимальное количество попыток при ошибке
        
    Returns:
        Обновленная структура данных с размеченными отзывами
    """
    print(f"\n{'='*60}")
    print(f"Начинаем разметку орфографических ошибок")
    print(f"Модель: {model}")
    print(f"Максимум параллельных запросов: {max_concurrent}")
    print(f"Максимум попыток при ошибке: {max_retries}")
    print(f"{'='*60}\n")
    
    # Семафор для ограничения количества параллельных запросов
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def mark_with_semaphore(review, sheet_name, worksheet_name):
        async with semaphore:
            return await mark_single_review(review, sheet_name, worksheet_name, model, max_retries)
    
    # Собираем все задачи для асинхронной обработки
    tasks = []
    total_reviews = 0
    
    for sheet_name, worksheets in data.items():
        for worksheet_name, reviews in worksheets.items():
            print(f"\nТаблица: {sheet_name} / Лист: {worksheet_name}")
            print(f"Количество отзывов: {len(reviews)}")
            
            for i, review in enumerate(reviews):
                task = mark_with_semaphore(review, sheet_name, worksheet_name)
                tasks.append((sheet_name, worksheet_name, i, task))
                total_reviews += 1
    
    print(f"\n{'='*60}")
    print(f"Всего отзывов к обработке: {total_reviews}")
    print(f"{'='*60}\n")
    
    # Выполняем все задачи параллельно
    start_time = datetime.now()
    results = await asyncio.gather(*[task for _, _, _, task in tasks])
    end_time = datetime.now()
    
    # Обновляем данные результатами
    for (sheet_name, worksheet_name, index, _), result in zip(tasks, results):
        data[sheet_name][worksheet_name][index] = result
    
    # Статистика
    duration = (end_time - start_time).total_seconds()
    total_cost = sum(
        review.get("spelling_cost", 0)
        for worksheets in data.values()
        for reviews in worksheets.values()
        for review in reviews
    )
    
    print(f"\n{'='*60}")
    print(f"[OK] Разметка завершена!")
    print(f"Время выполнения: {duration:.2f} секунд")
    print(f"Обработано отзывов: {total_reviews}")
    print(f"Общая стоимость: ${total_cost:.6f}")
    print(f"Средняя стоимость: ${total_cost/total_reviews:.6f}" if total_reviews > 0 else "")
    print(f"{'='*60}\n")
    
    return data


def load_reviews(input_file: str) -> dict:
    """Загружает данные отзывов из JSON файла."""
    with open(input_file, "r", encoding="utf-8") as f:
        return json.load(f)


def save_reviews(data: dict, output_file: str):
    """Сохраняет обработанные данные в JSON файл."""
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Результаты сохранены в: {output_file}")


if __name__ == "__main__":
    # Настройки
    MODEL = "grok-4-1-fast-reasoning"
    MAX_CONCURRENT = 100
    MAX_RETRIES = 3
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(current_dir, "gsheets", "test_data", "processed_reviews.json")
    output_file = os.path.join(current_dir, "gsheets", "test_data", "marked_reviews.json")
    
    reviews_data = load_reviews(input_file)
    marked_data = asyncio.run(mark_all_reviews(reviews_data, model=MODEL, max_concurrent=MAX_CONCURRENT, max_retries=MAX_RETRIES))
    save_reviews(marked_data, output_file)

