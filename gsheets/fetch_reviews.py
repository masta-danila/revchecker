import json
import os
import gspread
from google.oauth2.service_account import Credentials


def fetch_reviews_from_sheets() -> dict:
    """
    Читает данные из Google Sheets и возвращает структуру:
    {
        "advertpro": {
            "Лист1": [
                {"text": "текст отзыва", "gender": "М", "corrected_text": ""},
                ...
            ],
            "Лист2": [...]
        }
    }
    
    Берет только те записи, где:
    - поле "text" заполнено
    - поле "corrected_text" пустое
    """
    # Определяем пути к файлам
    current_dir = os.path.dirname(os.path.abspath(__file__))
    credentials_path = os.path.join(current_dir, "credentials.json")
    config_path = os.path.join(current_dir, "sheets_config.json")
    
    # Загружаем конфигурацию с ID таблиц
    with open(config_path, "r", encoding="utf-8") as f:
        sheets_config = json.load(f)
    
    # Настраиваем авторизацию Google Sheets API
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
    client = gspread.authorize(creds)
    
    # Результирующая структура
    all_reviews = {}
    
    # Обрабатываем каждую таблицу из конфига
    for sheet_name, sheet_id in sheets_config.items():
        print(f"Обработка таблицы: {sheet_name}")
        all_reviews[sheet_name] = {}
        
        try:
            # Открываем таблицу по ID
            spreadsheet = client.open_by_key(sheet_id)
            
            # Обрабатываем все листы в таблице
            for worksheet in spreadsheet.worksheets():
                worksheet_title = worksheet.title
                print(f"  Обработка листа: {worksheet_title}")
                
                # Получаем все данные листа
                all_values = worksheet.get_all_values()
                
                if not all_values:
                    continue
                
                # Первая строка - заголовки
                headers = all_values[0]
                
                # Находим индексы нужных колонок
                # Возможные варианты названий колонок
                text_variants = ["Исходный текст", "text", "текст"]
                gender_variants = ["Пол", "gender", "пол"]
                corrected_variants = ["Текст после правок", "corrected_text", "исправленный_текст", "исправленный текст"]
                
                try:
                    # Ищем колонку с текстом
                    text_idx = None
                    for variant in text_variants:
                        if variant in headers:
                            text_idx = headers.index(variant)
                            break
                    
                    # Ищем колонку с полом
                    gender_idx = None
                    for variant in gender_variants:
                        if variant in headers:
                            gender_idx = headers.index(variant)
                            break
                    
                    # Ищем колонку с исправленным текстом
                    corrected_idx = None
                    for variant in corrected_variants:
                        if variant in headers:
                            corrected_idx = headers.index(variant)
                            break
                    
                    # Проверяем, что нашли все нужные колонки
                    if text_idx is None or gender_idx is None or corrected_idx is None:
                        print(f"    Ошибка: не найдены нужные колонки в листе {worksheet_title}")
                        print(f"    Найденные заголовки: {headers}")
                        continue
                        
                except Exception as e:
                    print(f"    Ошибка при обработке заголовков: {e}")
                    continue
                
                # Собираем записи
                reviews = []
                for row in all_values[1:]:  # Пропускаем заголовок
                    # Проверяем, что строка достаточно длинная
                    if len(row) <= max(text_idx, gender_idx, corrected_idx):
                        continue
                    
                    text = row[text_idx].strip() if text_idx < len(row) else ""
                    gender = row[gender_idx].strip() if gender_idx < len(row) else ""
                    corrected = row[corrected_idx].strip() if corrected_idx < len(row) else ""
                    
                    # Берем только записи с заполненным text и пустым corrected_text
                    if text and not corrected:
                        reviews.append({
                            "text": text,
                            "gender": gender,  # Может быть пустым
                            "corrected_text": ""
                        })
                
                if reviews:
                    all_reviews[sheet_name][worksheet_title] = reviews
                    print(f"    Найдено записей: {len(reviews)}")
                else:
                    print(f"    Нет подходящих записей")
        
        except Exception as e:
            print(f"Ошибка при обработке таблицы {sheet_name}: {e}")
    
    return all_reviews


def save_reviews_to_json(reviews: dict, output_file: str = "reviews_data.json"):
    """
    Сохраняет данные отзывов в JSON файл.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(current_dir, output_file)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(reviews, f, ensure_ascii=False, indent=2)
    
    print(f"\nДанные сохранены в: {output_path}")
    return output_path


if __name__ == "__main__":
    print("Начинаем загрузку данных из Google Sheets...\n")
    
    # Загружаем данные
    reviews = fetch_reviews_from_sheets()
    
    # Сохраняем в папку test_data
    current_dir = os.path.dirname(os.path.abspath(__file__))
    test_data_dir = os.path.join(current_dir, "test_data")
    
    # Создаем папку test_data если её нет
    os.makedirs(test_data_dir, exist_ok=True)
    
    # Путь к файлу с данными
    output_file_path = os.path.join(test_data_dir, "reviews_data.json")
    
    # Сохраняем JSON
    with open(output_file_path, "w", encoding="utf-8") as f:
        json.dump(reviews, f, ensure_ascii=False, indent=2)
    
    print(f"\nДанные сохранены в: {output_file_path}")
    
    # Выводим статистику
    print("\n=== Статистика ===")
    total_reviews = 0
    for sheet_name, worksheets in reviews.items():
        sheet_total = sum(len(records) for records in worksheets.values())
        total_reviews += sheet_total
        print(f"{sheet_name}: {sheet_total} записей")
    print(f"\nВсего записей: {total_reviews}")

