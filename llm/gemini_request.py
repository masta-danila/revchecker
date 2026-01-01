import json
import google.genai as genai
from dotenv import load_dotenv
from llm_response_cleaner import clean_llm_content


def request_gemini(model: str, messages: list) -> dict:
    """
    Синхронная функция, делающая запрос к Google Gemini.
    Возвращает словарь с очищенным контентом и рассчитанной стоимостью.
    
    :param model: Название модели (например, 'gemini-2.5-flash', 'gemini-2.5-pro')
    :param messages: Список сообщений в формате [{"role": "user", "content": "..."}]
    :return: {"content": str, "cost": float}
    """
    load_dotenv()
    
    # Создаем клиент с API ключом из переменной окружения
    client = genai.Client()
    
    # Преобразуем messages в формат Gemini (просто текст)
    # Gemini API принимает простой текст, объединяем все сообщения
    contents = "\n".join([msg.get("content", "") for msg in messages])
    
    # Генерируем контент через новый API
    result = client.models.generate_content(
        model=model,
        contents=contents
    )
    
    # Извлекаем сгенерированный ответ
    answer = result.text
    
    # Очищаем ответ (удаляем возможные обёртки ```json и т. п.)
    answer = clean_llm_content(answer)
    
    # Извлекаем информацию о токенах из usage_metadata
    usage_metadata = result.usage_metadata
    prompt_tokens = usage_metadata.prompt_token_count
    completion_tokens = usage_metadata.candidates_token_count
    # cached токены появляются только при использовании кэша
    cached_tokens = getattr(usage_metadata, 'cached_content_token_count', 0) or 0
    # thoughts токены (для reasoning моделей типа gemini-2.5-pro)
    thoughts_tokens = getattr(usage_metadata, 'thoughts_token_count', 0) or 0
    
    # Рассчитываем количество некэшированных prompt_tokens
    non_cached_prompt_tokens = prompt_tokens - cached_tokens
    
    # Загрузка тарифов из файла llm_pricing.json
    pricing_path = os.path.join(os.path.dirname(__file__), "llm_pricing.json")
    with open(pricing_path, "r", encoding="utf-8") as f:
        pricing = json.load(f)
    
    # Получаем тарифы для выбранной модели
    model_pricing = pricing.get(model)
    if not model_pricing:
        # Если нет тарифов - возвращаем 0
        total_cost = 0.0
    else:
        input_rate = model_pricing.get("1M input tokens", 0)
        cached_rate = model_pricing.get("1M cached** input tokens", 0)
        output_rate = model_pricing.get("1M output tokens", 0)
        
        # Расчёт стоимости:
        # Стоимость некэшированных prompt_tokens
        cost_non_cached_prompt = (non_cached_prompt_tokens / 1_000_000) * input_rate
        # Стоимость кэшированных prompt_tokens
        cost_cached = (cached_tokens / 1_000_000) * cached_rate
        # Стоимость thoughts токенов (размышления модели - оплачиваются как output)
        cost_thoughts = (thoughts_tokens / 1_000_000) * output_rate
        # Стоимость output токенов
        cost_output = (completion_tokens / 1_000_000) * output_rate
        total_cost = cost_non_cached_prompt + cost_cached + cost_thoughts + cost_output
    
    return {"content": answer, "cost": total_cost}


if __name__ == "__main__":
    completion = request_gemini(
        model='gemini-2.5-flash',  # Платная модель для проверки расчета
        messages=[
            {"role": "user", "content": "Explain how AI works in a few words"}
        ]
    )
    
    print(json.dumps(completion, ensure_ascii=False, indent=2))
