import json
import os
import asyncio
from datetime import datetime
from review_checker import check_review


async def process_single_review(review: dict, sheet_name: str, worksheet_name: str, model: str = "grok-4-1-fast-reasoning") -> dict:
    """
    Обрабатывает один отзыв через LLM.
    
    Args:
        review: Словарь с полями text, gender, corrected_text
        sheet_name: Название таблицы
        worksheet_name: Название листа
        model: Модель для обработки
        
    Returns:
        Обновленный словарь с заполненными corrected_text и gender
    """
    try:
        text = review.get("text", "")
        gender = review.get("gender", "")
        
        if not text:
            print(f"  [WARN] Пропущен пустой отзыв в {sheet_name}/{worksheet_name}")
            return review
        
        # Вызываем функцию проверки отзыва
        result = await check_review(review_text=text, gender=gender, model=model)
        
        # Парсим ответ от модели
        content = result.get("content", "{}")
        cost = result.get("cost", 0)
        
        try:
            # Пытаемся распарсить JSON из ответа
            corrected_data = json.loads(content)
            corrected_text = corrected_data.get("text", text)
            corrected_gender = corrected_data.get("gender", gender)
        except json.JSONDecodeError:
            print(f"  [WARN] Ошибка парсинга JSON для отзыва в {sheet_name}/{worksheet_name}")
            corrected_text = text
            corrected_gender = gender
        
        # Обновляем данные отзыва
        review["corrected_text"] = corrected_text
        review["gender"] = corrected_gender
        review["cost"] = cost
        review["processed_at"] = datetime.now().isoformat()
        
        print(f"  [OK] Обработан отзыв в {sheet_name}/{worksheet_name} (cost: ${cost:.6f})")
        
        return review
        
    except Exception as e:
        print(f"  [ERROR] Ошибка обработки отзыва в {sheet_name}/{worksheet_name}: {e}")
        return review


async def process_all_reviews(data: dict, model: str = "grok-4-1-fast-reasoning", max_concurrent: int = 50) -> dict:
    """
    Асинхронно обрабатывает все отзывы из структуры данных.
    
    Args:
        data: Структура данных из reviews_data.json
        model: Модель для обработки
        max_concurrent: Максимальное количество параллельных запросов
        
    Returns:
        Обновленная структура данных с обработанными отзывами
    """
    print(f"\n{'='*60}")
    print(f"Начинаем обработку отзывов")
    print(f"Модель: {model}")
    print(f"Максимум параллельных запросов: {max_concurrent}")
    print(f"{'='*60}\n")
    
    # Семафор для ограничения количества параллельных запросов
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_with_semaphore(review, sheet_name, worksheet_name):
        async with semaphore:
            return await process_single_review(review, sheet_name, worksheet_name, model)
    
    # Собираем все задачи для асинхронной обработки
    tasks = []
    total_reviews = 0
    
    for sheet_name, worksheets in data.items():
        for worksheet_name, reviews in worksheets.items():
            print(f"\nТаблица: {sheet_name} / Лист: {worksheet_name}")
            print(f"Количество отзывов: {len(reviews)}")
            
            for i, review in enumerate(reviews):
                task = process_with_semaphore(review, sheet_name, worksheet_name)
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
        review.get("cost", 0)
        for worksheets in data.values()
        for reviews in worksheets.values()
        for review in reviews
    )
    
    print(f"\n{'='*60}")
    print(f"[OK] Обработка завершена!")
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
    MAX_CONCURRENT = 50
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(current_dir, "gsheets", "test_data", "reviews_data.json")
    output_file = os.path.join(current_dir, "gsheets", "test_data", "processed_reviews.json")
    
    reviews_data = load_reviews(input_file)
    processed_data = asyncio.run(process_all_reviews(reviews_data, model=MODEL, max_concurrent=MAX_CONCURRENT))
    save_reviews(processed_data, output_file)

