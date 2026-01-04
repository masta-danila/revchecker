import json
import os
import re
import difflib
import gspread
from google.oauth2.service_account import Credentials
from fetch_reviews import get_sheet_data_with_indices


# Константы для форматирования
RED_COLOR = {"red": 1.0, "green": 0.0, "blue": 0.0}
GREEN_COLOR = {"red": 0.0, "green": 0.6, "blue": 0.0}


def parse_marked_text(text: str):
    """
    Парсит текст с разметкой [[]] и возвращает список сегментов.
    
    Args:
        text: Текст с разметкой вида "пр[[и]]мер"
        
    Returns:
        Список словарей вида [{"text": "пр", "is_error": False}, {"text": "и", "is_error": True}, ...]
    """
    segments = []
    current_pos = 0
    
    # Ищем все вхождения [[...]]
    pattern = r'\[\[(.*?)\]\]'
    
    for match in re.finditer(pattern, text):
        # Добавляем текст до ошибки
        if match.start() > current_pos:
            segments.append({
                "text": text[current_pos:match.start()],
                "is_error": False
            })
        
        # Добавляем ошибку
        segments.append({
            "text": match.group(1),
            "is_error": True
        })
        
        current_pos = match.end()
    
    # Добавляем оставшийся текст
    if current_pos < len(text):
        segments.append({
            "text": text[current_pos:],
            "is_error": False
        })
    
    return segments


def find_text_differences(original: str, corrected_with_markup: str):
    """
    Находит различия между оригинальным и исправленным текстом на уровне слов.
    Возвращает позиции изменений в тексте БЕЗ разметки [[]].
    
    Args:
        original: Оригинальный текст
        corrected_with_markup: Исправленный текст (с разметкой [[]])
        
    Returns:
        Список кортежей (start_idx, end_idx) для зеленого форматирования
    """
    # Убираем разметку [[]] из corrected для сравнения
    clean_corrected = re.sub(r'\[\[(.*?)\]\]', r'\1', corrected_with_markup)
    
    # Если тексты одинаковые, нет различий
    if original == clean_corrected:
        return []
    
    # Разбиваем на слова с сохранением позиций
    def tokenize_with_positions(text):
        """Возвращает список (слово, start_pos, end_pos)"""
        tokens = []
        current_pos = 0
        for match in re.finditer(r'\S+|\s+', text):
            word = match.group()
            start = match.start()
            end = match.end()
            tokens.append((word, start, end))
        return tokens
    
    original_tokens = tokenize_with_positions(original)
    corrected_tokens = tokenize_with_positions(clean_corrected)
    
    # Сравниваем только слова (без пробелов)
    original_words = [t[0] for t in original_tokens if not t[0].isspace()]
    corrected_words = [t[0] for t in corrected_tokens if not t[0].isspace()]
    
    matcher = difflib.SequenceMatcher(None, original_words, corrected_words)
    
    differences = []
    
    # Создаем маппинг индекса слова -> позиция в тексте
    corrected_word_positions = []
    for token, start, end in corrected_tokens:
        if not token.isspace():
            corrected_word_positions.append((start, end))
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ('replace', 'insert'):
            # Находим позиции в тексте для измененных слов
            for word_idx in range(j1, j2):
                if word_idx < len(corrected_word_positions):
                    start, end = corrected_word_positions[word_idx]
                    differences.append((start, end))
    
    return differences


def create_rich_text_value(text: str, original_text: str = None):
    """
    Создает rich text value для Google Sheets API с форматированием.
    
    Args:
        text: Текст с разметкой [[]]
        original_text: Оригинальный текст для сравнения (опционально)
        
    Returns:
        Кортеж (clean_text, runs) для textFormatRuns API
    """
    segments = parse_marked_text(text)
    
    # Формируем чистый текст без разметки
    clean_text = "".join(seg["text"] for seg in segments)
    
    # Создаем список всех форматированных зон: (start, end, color)
    colored_zones = []
    
    # Добавляем красные зоны для [[]] (орфографические ошибки)
    start_index = 0
    for segment in segments:
        segment_length = len(segment["text"])
        if segment["is_error"]:
            colored_zones.append((start_index, start_index + segment_length, RED_COLOR))
        start_index += segment_length
    
    # Если есть оригинальный текст, добавляем зеленые зоны для изменений
    if original_text:
        differences = find_text_differences(original_text, text)
        
        # Создаем множество позиций с красным цветом
        red_positions = set()
        for start, end, color in colored_zones:
            if color == RED_COLOR:
                red_positions.update(range(start, end))
        
        # Добавляем зеленые зоны, избегая красных
        for start_idx, end_idx in differences:
            # Проверяем, не пересекается ли с красными зонами
            has_red = any(i in red_positions for i in range(start_idx, min(end_idx, len(clean_text))))
            
            if not has_red and start_idx < len(clean_text):
                colored_zones.append((start_idx, end_idx, GREEN_COLOR))
    
    # Преобразуем зоны в textFormatRuns
    # В Google Sheets API нужно указывать начало каждого форматирования
    # И после каждой цветной зоны нужно "сбрасывать" формат
    runs = []
    
    # Сортируем зоны по началу
    colored_zones.sort(key=lambda x: x[0])
    
    for start, end, color in colored_zones:
        # Начало форматирования
        runs.append({
            "startIndex": start,
            "format": {
                "foregroundColor": color
            }
        })
        # Конец форматирования - сброс на черный цвет
        if end < len(clean_text):
            runs.append({
                "startIndex": end,
                "format": {
                    "foregroundColor": {"red": 0.0, "green": 0.0, "blue": 0.0}
                }
            })
    
    return clean_text, runs


def authenticate_gspread(credentials_path: str):
    """
    Аутентификация в Google Sheets API.
    
    Args:
        credentials_path: Путь к файлу credentials.json
        
    Returns:
        Авторизованный клиент gspread
    """
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    credentials = Credentials.from_service_account_file(credentials_path, scopes=scopes)
    client = gspread.authorize(credentials)
    
    return client


def find_column_index(headers, possible_names):
    """Находит индекс колонки по возможным названиям."""
    for name in possible_names:
        if name in headers:
            return headers.index(name)
    raise ValueError(f"Не найдена ни одна из колонок: {', '.join(possible_names)}")


def update_sheet_with_reviews(client, sheet_id: str, sheet_name: str, worksheet_name: str, reviews: list):
    """
    Обновляет Google Sheet данными из обработанных отзывов.
    
    Args:
        client: Авторизованный клиент gspread
        sheet_id: ID Google таблицы
        sheet_name: Название таблицы (для логирования)
        worksheet_name: Название листа
        reviews: Список отзывов для обновления
    """
    print(f"\n  Обработка листа: {worksheet_name}")
    
    try:
        # Открываем таблицу и лист
        spreadsheet = client.open_by_key(sheet_id)
        worksheet = spreadsheet.worksheet(worksheet_name)
        
        # Получаем данные листа и индексы колонок через общую функцию из fetch_reviews
        result = get_sheet_data_with_indices(worksheet)
        
        if result is None:
            print(f"    [ERROR] Не найдены нужные колонки в листе {worksheet_name}")
            return
        
        all_values, text_idx, gender_idx, corrected_idx = result
        
        # Создаем словарь для быстрого поиска отзывов из JSON
        # Используем ТУ ЖЕ логику чтения текста, что и в fetch_reviews.py
        reviews_dict = {}
        for review in reviews:
            # Берем текст точно так же, как в fetch_reviews.py
            text = review.get("text", "").strip()
            if text:
                reviews_dict[text] = review
        
        print(f"    [DEBUG] Найдено отзывов в JSON: {len(reviews_dict)}")
        
        # Получаем ID листа для batch update
        worksheet_id = worksheet.id
        
        # Собираем batch запросы
        batch_updates = []
        update_count = 0
        rows_checked = 0
        rows_matched = 0
        
        # Проходим по строкам (начиная со второй, т.к. первая - заголовки) 
        # ИСПОЛЬЗУЕМ ТУ ЖЕ ЛОГИКУ, что и в fetch_reviews.py
        for row_idx, row in enumerate(all_values[1:], start=2):
            rows_checked += 1
            
            # Проверяем, что строка достаточно длинная
            if len(row) <= max(text_idx, gender_idx, corrected_idx):
                continue
            
            # Берем текст ТОЧНО ТАК ЖЕ, как в fetch_reviews.py
            text = row[text_idx].strip() if text_idx < len(row) else ""
            corrected = row[corrected_idx].strip() if corrected_idx < len(row) else ""
            
            if not text:
                continue
            
            # DEBUG: Показываем первые строки
            if rows_checked <= 3:
                print(f"    [DEBUG] Строка {row_idx}: text='{text[:80]}...', corrected_empty={not corrected}")
            
            # Берем только записи с заполненным text и пустым corrected_text
            # ТА ЖЕ ЛОГИКА, что и в fetch_reviews.py
            if not corrected:
                # Ищем соответствующий отзыв из JSON
                review = reviews_dict.get(text)
                
                if not review:
                    if rows_checked <= 3:
                        print(f"    [DEBUG] Строка {row_idx}: НЕ НАЙДЕНО в JSON")
                        if reviews_dict:
                            first_key = list(reviews_dict.keys())[0]
                            print(f"    [DEBUG] Первый ключ из JSON: '{first_key[:80]}...'")
                    continue
                
                rows_matched += 1
                
                # Обновляем пол (всегда, если есть в review)
                if review.get("gender"):
                    batch_updates.append({
                        "range": f"{gspread.utils.rowcol_to_a1(row_idx, gender_idx + 1)}",
                        "values": [[review["gender"]]]
                    })
                
                # Обновляем исправленный текст с форматированием
                if review.get("corrected_text"):
                    corrected_text = review["corrected_text"]
                    # Убираем лишние кавычки в начале и конце, если они есть
                    if corrected_text.startswith('"') and corrected_text.endswith('"'):
                        corrected_text = corrected_text[1:-1]
                    # Передаем оригинальный текст для определения изменений (зеленый цвет)
                    clean_text, text_runs = create_rich_text_value(corrected_text, original_text=text)
                    
                    # Добавляем запрос на обновление значения
                    batch_updates.append({
                        "range": f"{gspread.utils.rowcol_to_a1(row_idx, corrected_idx + 1)}",
                        "values": [[clean_text]]
                    })
                    
                    # Если есть форматирование, добавляем его через API
                    if text_runs:
                        # Формируем запрос для textFormat
                        cell_format_request = {
                            "repeatCell": {
                                "range": {
                                    "sheetId": worksheet_id,
                                    "startRowIndex": row_idx - 1,
                                    "endRowIndex": row_idx,
                                    "startColumnIndex": corrected_idx,
                                    "endColumnIndex": corrected_idx + 1
                                },
                                "cell": {
                                    "userEnteredValue": {
                                        "stringValue": clean_text
                                    },
                                    "textFormatRuns": text_runs
                                },
                                "fields": "userEnteredValue,textFormatRuns"
                            }
                        }
                        batch_updates.append(cell_format_request)
                    
                    update_count += 1
        
        # Выводим статистику
        print(f"    [DEBUG] Проверено строк: {rows_checked}, совпадений: {rows_matched}")
        
        # Выполняем batch update
        if batch_updates:
            # Разделяем на value updates и format updates
            value_updates = [u for u in batch_updates if "range" in u]
            format_updates = [u for u in batch_updates if "repeatCell" in u]
            
            # Обновляем значения
            if value_updates:
                worksheet.batch_update([{
                    "range": u["range"],
                    "values": u["values"]
                } for u in value_updates])
            
            # Обновляем форматирование
            if format_updates:
                spreadsheet.batch_update({"requests": format_updates})
            
            print(f"    [OK] Обновлено строк: {update_count}")
        else:
            print(f"    [INFO] Нет строк для обновления")
            
    except gspread.exceptions.WorksheetNotFound:
        print(f"    [ERROR] Лист '{worksheet_name}' не найден")
    except Exception as e:
        print(f"    [ERROR] Ошибка при обработке листа '{worksheet_name}': {e}")


def update_all_sheets(reviews_data: dict, sheets_config_path: str, credentials_path: str):
    """
    Обновляет все Google Sheets данными из обработанных отзывов.
    
    Args:
        reviews_data: Данные из marked_reviews.json
        sheets_config_path: Путь к sheets_config.json
        credentials_path: Путь к credentials.json
    """
    print(f"\n{'='*60}")
    print(f"ОБНОВЛЕНИЕ GOOGLE SHEETS")
    print(f"{'='*60}\n")
    
    # Загружаем конфигурацию таблиц
    with open(sheets_config_path, "r", encoding="utf-8") as f:
        sheets_config = json.load(f)
    
    # Аутентификация
    print("Аутентификация в Google Sheets...")
    client = authenticate_gspread(credentials_path)
    print("[OK] Аутентификация успешна\n")
    
    # Обрабатываем каждую таблицу
    for sheet_name, sheet_id in sheets_config.items():
        print(f"Таблица: {sheet_name} (ID: {sheet_id})")
        
        if sheet_name not in reviews_data:
            print(f"  [WARN] Нет данных для таблицы {sheet_name}")
            continue
        
        worksheets_data = reviews_data[sheet_name]
        
        for worksheet_name, reviews in worksheets_data.items():
            update_sheet_with_reviews(client, sheet_id, sheet_name, worksheet_name, reviews)
    
    print(f"\n{'='*60}")
    print(f"[OK] ОБНОВЛЕНИЕ ЗАВЕРШЕНО")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Пути к файлам
    reviews_file = os.path.join(current_dir, "test_data", "processed_reviews.json")
    sheets_config_file = os.path.join(current_dir, "sheets_config.json")
    credentials_file = os.path.join(current_dir, "credentials.json")
    
    # Проверяем наличие файлов
    if not os.path.exists(reviews_file):
        print(f"[ERROR] Файл {reviews_file} не найден")
        exit(1)
    
    if not os.path.exists(sheets_config_file):
        print(f"[ERROR] Файл {sheets_config_file} не найден")
        exit(1)
    
    if not os.path.exists(credentials_file):
        print(f"[ERROR] Файл {credentials_file} не найден")
        print("Создайте service account в Google Cloud Console и скачайте credentials.json")
        exit(1)
    
    # Загружаем данные отзывов
    with open(reviews_file, "r", encoding="utf-8") as f:
        reviews_data = json.load(f)
    
    print(f"[INFO] Загружено отзывов из {reviews_file}:")
    for sheet_name, worksheets in reviews_data.items():
        for worksheet_name, reviews in worksheets.items():
            print(f"  - {sheet_name}/{worksheet_name}: {len(reviews)} отзывов")
    
    # Обновляем Google Sheets
    update_all_sheets(reviews_data, sheets_config_file, credentials_file)

