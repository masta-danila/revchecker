import asyncio
import json
import os
import sys
from datetime import datetime

# Добавляем путь к папке llm для корректных импортов
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'llm'))

from llm.llm_router import llm_request  # type: ignore


async def check_spelling(text: str, model: str = "grok-4-1-fast-reasoning") -> dict:
    """
    Асинхронно находит и помечает орфографические ошибки в тексте.
    
    Args:
        text: Текст для проверки орфографии
        model: Название модели из списка pricing (по умолчанию "grok-4-1-fast-reasoning")
        
    Returns:
        Словарь с полями:
        - content: Текст с помеченными ошибками в формате [[]]
        - cost: Стоимость запроса в долларах
        
    Raises:
        Exception: Если модель не найдена в pricing или не поддерживается
    """
    # Формируем промпт
    prompt = f"""
    Ты профессиональный корректор текстов. Твоя задача — найти ВСЕ орфографические ошибки в тексте и пометить ТОЛЬКО неправильные буквы.
    
    ТЕКСТ ДЛЯ ПРОВЕРКИ:
    "{text}"
    
    ЗАДАЧА:
    Найди все орфографические ошибки и опечатки в тексте.
    Заключи КАЖДУЮ неправильную букву в двойные квадратные скобки [[]].
    
    ПРАВИЛА РАЗМЕТКИ:
    1. Неправильная буква → заключить в [[]]
       "малоко" → "м[[а]]локо" (неправильная "а" вместо "о")
       
    2. Лишняя буква → заключить в [[]]
       "крассивый" → "крас[[с]]ивый" (удвоенная "с" лишняя, помечаем лишнюю "с")
       
    3. Недостающая буква → пометить букву, после которой она должна быть
       "металический" → "мета[[л]]ический" (не хватает "л", добавлять недостающую букву нельзя!)
       
    
    ЧТО НЕ ПОМЕЧАТЬ:
    - Букву "е" вместо "ё" (это не ошибка)
    - Грамматические окончания (это не орфографические ошибки)
    
    ВАЖНО: Верни ТОЛЬКО текст с пометками. Никаких дополнительных объяснений или комментариев.
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
    result = await asyncio.to_thread(llm_request, model, messages)
    
    return result


if __name__ == "__main__":
    # Пример использования
    test_text = "Отличный салон. Ноль стреса. Первый раз заказали с мужем машшину из-за гроницы, конечно, очень переживали, но тьфу-тьфу все прошло спокойно. Меннеджеры подобрали для нас Audi A5 с пробегом 78 тыс. Машина в отличном состоянии, прошла ТО, в оригинальной комплектации. Берите лучше сопровождение под ключ. Услуга дороже, но удобнее в сто раз."
    model = "grok-4-1-fast-reasoning"
    
    result = asyncio.run(check_spelling(text=test_text, model=model))
    
    print("\n" + "="*60)
    print("РЕЗУЛЬТАТ ПРОВЕРКИ ОРФОГРАФИИ")
    print("="*60)
    print(f"Модель: {model}")
    print(f"Исходный текст: {test_text}")
    print(f"\nРезультат: {result['content']}")
    print(f"Стоимость: ${result['cost']:.6f}")
    print("="*60 + "\n")

