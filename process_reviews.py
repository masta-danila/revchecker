import json
import os
import asyncio
from datetime import datetime
from review_checker import check_review
from logger_config import get_process_logger

logger = get_process_logger()


async def check_review_with_retry(review_text: str, gender: str, model: str, max_retries: int = 3) -> dict:
    """
    Вызывает check_review с повторными попытками при ошибке.
    
    Args:
        review_text: Текст отзыва
        gender: Пол
        model: Модель для обработки
        max_retries: Максимальное количество попыток (по умолчанию 3)
        
    Returns:
        Результат от check_review
        
    Raises:
        Exception: Если все попытки завершились ошибкой
    """
    last_error = None
    
    for attempt in range(1, max_retries + 1):
        try:
            result = await check_review(review_text=review_text, gender=gender, model=model)
            return result
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                wait_time = attempt * 2  # Увеличиваем задержку с каждой попыткой
                logger.warning(f"  [RETRY] Попытка {attempt}/{max_retries} не удалась: {e}. Повтор через {wait_time}с...")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"  [ERROR] Все {max_retries} попытки исчерпаны: {e}")
    
    raise last_error


async def process_single_review(review: dict, sheet_name: str, worksheet_name: str, model: str = "grok-4-1-fast-reasoning", max_retries: int = 3) -> dict:
    """
    Обрабатывает один отзыв через LLM.
    
    Args:
        review: Словарь с полями text, gender, corrected_text
        sheet_name: Название таблицы
        worksheet_name: Название листа
        model: Модель для обработки
        max_retries: Максимальное количество попыток при ошибке (по умолчанию 3)
        
    Returns:
        Обновленный словарь с заполненными corrected_text и gender
    """
    try:
        text = review.get("text", "")
        gender = review.get("gender", "")
        
        if not text:
            logger.warning(f"Пропущен пустой отзыв в {sheet_name}/{worksheet_name}")
            return review
        
        # Вызываем функцию проверки отзыва с повторными попытками
        result = await check_review_with_retry(review_text=text, gender=gender, model=model, max_retries=max_retries)
        
        # Парсим ответ от модели
        content = result.get("content", "{}")
        cost = result.get("cost", 0)
        
        try:
            # Пытаемся распарсить JSON из ответа
            corrected_data = json.loads(content)
            corrected_text = corrected_data.get("text", text)
            corrected_gender = corrected_data.get("gender", gender)
        except json.JSONDecodeError:
            logger.warning(f"Ошибка парсинга JSON для отзыва в {sheet_name}/{worksheet_name}")
            corrected_text = text
            corrected_gender = gender
        
        # Обновляем данные отзыва
        review["corrected_text"] = corrected_text
        review["gender"] = corrected_gender
        review["cost"] = cost
        review["processed_at"] = datetime.now().isoformat()
        
        logger.info(f"Обработан отзыв в {sheet_name}/{worksheet_name} (cost: ${cost:.6f})")
        
        return review
        
    except Exception as e:
        logger.error(f"Ошибка обработки отзыва в {sheet_name}/{worksheet_name}: {e}", exc_info=True)
        return review


async def process_all_reviews(data: dict, model: str, max_concurrent: int, max_retries: int) -> dict:
    """
    Асинхронно обрабатывает все отзывы из структуры данных.
    
    Args:
        data: Структура данных из reviews_data.json
        model: Модель для обработки
        max_concurrent: Максимальное количество параллельных запросов
        max_retries: Максимальное количество попыток при ошибке (по умолчанию 3)
        
    Returns:
        Обновленная структура данных с обработанными отзывами
    """
    logger.info("="*60)
    logger.info("Начинаем обработку отзывов")
    logger.info(f"Модель: {model}")
    logger.info(f"Максимум параллельных запросов: {max_concurrent}")
    logger.info(f"Максимум попыток при ошибке: {max_retries}")
    logger.info("="*60)
    
    # Семафор для ограничения количества параллельных запросов
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_with_semaphore(review, sheet_name, worksheet_name):
        async with semaphore:
            return await process_single_review(review, sheet_name, worksheet_name, model, max_retries)
    
    # Собираем все задачи для асинхронной обработки
    tasks = []
    total_reviews = 0
    
    for sheet_name, worksheets in data.items():
        for worksheet_name, reviews in worksheets.items():
            logger.info(f"Таблица: {sheet_name} / Лист: {worksheet_name}")
            logger.info(f"Количество отзывов: {len(reviews)}")
            
            for i, review in enumerate(reviews):
                task = process_with_semaphore(review, sheet_name, worksheet_name)
                tasks.append((sheet_name, worksheet_name, i, task))
                total_reviews += 1
    
    logger.info("="*60)
    logger.info(f"Всего отзывов к обработке: {total_reviews}")
    logger.info("="*60)
    
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
    
    logger.info("="*60)
    logger.info("[OK] Обработка завершена!")
    logger.info(f"Время выполнения: {duration:.2f} секунд")
    logger.info(f"Обработано отзывов: {total_reviews}")
    logger.info(f"Общая стоимость: ${total_cost:.6f}")
    if total_reviews > 0:
        logger.info(f"Средняя стоимость: ${total_cost/total_reviews:.6f}")
    logger.info("="*60)
    
    return data


def load_reviews(input_file: str) -> dict:
    """Загружает данные отзывов из JSON файла."""
    with open(input_file, "r", encoding="utf-8") as f:
        return json.load(f)


def save_reviews(data: dict, output_file: str):
    """Сохраняет обработанные данные в JSON файл."""
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Результаты сохранены в: {output_file}")


if __name__ == "__main__":
    # Настройки
    MODEL = "gpt-4o"
    MAX_CONCURRENT = 100
    MAX_RETRIES = 3  # Количество попыток при ошибке
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(current_dir, "gsheets", "test_data", "reviews_data.json")
    output_file = os.path.join(current_dir, "gsheets", "test_data", "processed_reviews.json")
    
    reviews_data = load_reviews(input_file)
    processed_data = asyncio.run(process_all_reviews(reviews_data, model=MODEL, max_concurrent=MAX_CONCURRENT, max_retries=MAX_RETRIES))
    save_reviews(processed_data, output_file)

