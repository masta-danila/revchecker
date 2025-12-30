import json
import os
import sys
import asyncio
from datetime import datetime

# Добавляем путь к папке llm для корректных импортов
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'llm'))

from llm.llm_router import llm_request  # type: ignore


async def check_review(review_text: str, gender: str, model: str = "grok-4-1-fast-reasoning") -> dict:
    """
    Асинхронно проверяет и корректирует отзыв через LLM модель.
    
    Args:
        review_text: Текст отзыва для проверки
        gender: Текущий пол (М/Ж/Н)
        model: Название модели из списка pricing (по умолчанию "grok-4-1-fast-reasoning")
        
    Returns:
        Словарь с полями:
        - content: Ответ от модели в формате JSON {"text": "...", "gender": "..."}
        - cost: Стоимость запроса в долларах
        
    Raises:
        Exception: Если модель не найдена в pricing или не поддерживается
    """
    # Получаем текущую дату
    current_date = datetime.now().strftime("%d.%m.%Y")
    
    # Формируем промпт с подстановкой параметров
    prompt = f"""
    Ты профессиональный редактор отзывов. Задача проверить отзыв согласно входным данным.
    ВХОДНЫЕ ДАННЫЕ:
    Текст отзыва: "{review_text}"
    Текущий пол: {gender}
    Текущая дата: {current_date}
    ЗАДАЧИ ПРОВЕРКИ:
    ОПРЕДЕЛЕНИЕ И КОРРЕКТИРОВКА ПОЛА
    Исправить пол и окончания, если:
    Текст написан преимущественно от женского лица + указан "М" → изменить пол на "Ж" + скорректировать окончания (м→ж)
    Текст написан преимущественно от мужского лица + указан "Ж" → изменить пол на "М" + скорректировать окончания (ж→м)
    В спорных случаях (признаков м/ж примерно поровну):
    Оставить текущий пол без изменений
    Скорректировать окончания под текущий пол
    Оставить как есть, если:
    Пол соответствует тексту
    Отзыв в нейтральном множественном числе ("обращались", "заказывали", "довольны") — это отзывы от компаний, пол "Н"
    КОРРЕКТИРОВКА ТЕКСТА
    Что ИСПРАВЛЯТЬ:
    Грамматические ошибки (падежи, согласования, времена)
    Логические несоответствия времени года/сезона/праздников относительно текущей даты (осень + 8 марта, лето + ёлки к НГ, зима + выпускной)
    Что НЕ ТРОГАТЬ:
    Опечатки и орфографические ошибки (сохранять как есть)
    Стиль, тон и структуру отзыва
    ФОРМАТ ВЫДАЧИ:
    {{ "text": "исправленный текст отзыва (или оригинал, если не требовалось правок)", "gender": "М/Ж/Н" }}
    """
    
    # Определяем путь к файлу pricing относительно корня проекта
    current_dir = os.path.dirname(os.path.abspath(__file__))
    llm_dir = os.path.join(current_dir, "llm")
    pricing_path = os.path.join(llm_dir, "llm_pricing.json")
    
    # Загружаем список доступных моделей из pricing
    with open(pricing_path, "r", encoding="utf-8") as f:
        pricing = json.load(f)
    
    # Проверяем, что модель есть в pricing
    if model not in pricing:
        available_models = ", ".join(pricing.keys())
        raise Exception(
            f"Модель '{model}' не найдена в pricing.\n"
            f"Доступные модели: {available_models}"
        )
    
    # Формируем список сообщений в формате, который ожидает llm_router
    messages = [
        {"role": "user", "content": prompt}
    ]
    
    # Выполняем запрос через llm_router в отдельном потоке (асинхронно)
    # Это позволяет не блокировать event loop во время выполнения запроса
    # Важно: меняем рабочую директорию на llm, так как внутри функций используются
    # относительные пути к llm_pricing.json
    def _call_llm_request():
        original_cwd = os.getcwd()
        try:
            os.chdir(llm_dir)
            return llm_request(model=model, messages=messages)
        finally:
            os.chdir(original_cwd)
    
    result = await asyncio.to_thread(_call_llm_request)
    
    return result


if __name__ == "__main__":
    # Пример использования
    review_text = "Заказывала метолическую дверь в августе. Очень доволен качеством! Установили быстро, мастера приехали вовремя. Рекомендую всем к Новому году обновить входную дверь, отличный подарок себе на 8 марта!"
    gender = "М"
    model = "grok-4-1-fast-reasoning"
    
    result = asyncio.run(check_review(review_text=review_text, gender=gender, model=model))
    
    print(result)

