# Инструкция по развертыванию RevChecker на сервере

## Предварительные требования

- Ubuntu/Debian сервер
- Python 3.11+
- Доступ по SSH
- Права sudo

## Структура на сервере

Проект будет развернут в директории:
```
/home/callchecker/revchecker/
```

Рядом с существующим проектом:
```
/home/callchecker/callchecker/
/home/callchecker/revchecker/  ← новый проект
```

## Шаг 1: Подготовка на локальной машине

### 1.1. Убедитесь, что у вас есть необходимые файлы:
- `.env` - API ключи для LLM (OpenAI, Anthropic, Google, DeepSeek, Grok)
- `gsheets/credentials.json` - credentials из Google Cloud Console
- `gsheets/sheets_config.json` - ID Google таблиц

### 1.2. Создайте архив проекта:
```bash
cd /Users/daniladzhiev/PycharmProjects/revchecker
tar --exclude='venv' --exclude='gsheets/test_data' --exclude='__pycache__' \
    --exclude='.git' --exclude='logs' -czf revchecker.tar.gz .
```

## Шаг 2: Копирование на сервер

### 2.1. Скопируйте архив на сервер:
```bash
scp revchecker.tar.gz callchecker@YOUR_SERVER_IP:/home/callchecker/
```

### 2.2. Подключитесь к серверу:
```bash
ssh callchecker@YOUR_SERVER_IP
```

### 2.3. Распакуйте проект:
```bash
cd /home/callchecker
mkdir -p revchecker
cd revchecker
tar -xzf ../revchecker.tar.gz
rm ../revchecker.tar.gz
```

## Шаг 3: Установка зависимостей и проверка

### 3.1. Сделайте скрипты исполняемыми:
```bash
chmod +x deploy_server.sh
chmod +x setup_systemd_service.sh
```

### 3.2. Запустите скрипт развертывания:
```bash
./deploy_server.sh
```

Этот скрипт:
- Создаст виртуальное окружение
- Установит зависимости из requirements.txt
- Проверит наличие .env и credentials.json
- Проверит подключение к Google Sheets
- Создаст необходимые директории

## Шаг 4: Настройка systemd службы

### 4.1. Установите службу:
```bash
./setup_systemd_service.sh
```

Этот скрипт:
- Скопирует `revchecker.service` в `/etc/systemd/system/`
- Включит автозапуск при перезагрузке сервера
- Запустит службу

### 4.2. Проверьте статус:
```bash
sudo systemctl status revchecker
```

## Управление службой

### Основные команды:
```bash
# Статус
sudo systemctl status revchecker

# Перезапуск
sudo systemctl restart revchecker

# Остановка
sudo systemctl stop revchecker

# Запуск
sudo systemctl start revchecker

# Отключить автозапуск
sudo systemctl disable revchecker

# Включить автозапуск
sudo systemctl enable revchecker
```

### Просмотр логов:
```bash
# Логи в реальном времени
sudo journalctl -u revchecker -f

# Логи за сегодня
sudo journalctl -u revchecker --since today

# Последние 100 строк
sudo journalctl -u revchecker -n 100

# Логи приложения (из папки logs/)
tail -f /home/callchecker/revchecker/logs/pipeline.log
tail -f /home/callchecker/revchecker/logs/process_reviews.log
```

## Обновление проекта

### Способ 1: Через Git (рекомендуется)

На сервере:
```bash
cd /home/callchecker/revchecker
source venv/bin/activate
git pull origin main
pip install -r requirements.txt
sudo systemctl restart revchecker
```

### Способ 2: Через архив

На локальной машине:
```bash
cd /Users/daniladzhiev/PycharmProjects/revchecker
tar --exclude='venv' --exclude='gsheets/test_data' --exclude='__pycache__' \
    --exclude='.git' --exclude='logs' -czf revchecker.tar.gz .
scp revchecker.tar.gz callchecker@YOUR_SERVER_IP:/home/callchecker/
```

На сервере:
```bash
cd /home/callchecker/revchecker
sudo systemctl stop revchecker
tar -xzf ../revchecker.tar.gz
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl start revchecker
```

## Мониторинг

### Проверка работы всех служб:
```bash
# Обе службы (callchecker + revchecker)
sudo systemctl status callchecker-* revchecker

# Проверка процессов
ps aux | grep -E 'callchecker|revchecker'
```

### Логи обеих систем:
```bash
# Все логи systemd
sudo journalctl -u "callchecker-*" -u revchecker -f

# Логи приложений
tail -f /home/callchecker/*/logs/*.log
```

## Настройка параметров

Параметры работы настраиваются в `run_full_pipeline.py`:

```python
MODEL = "grok-4-1-fast-reasoning"  # Модель для обработки
MAX_CONCURRENT = 100                # Одновременных запросов
MAX_RETRIES = 3                     # Попыток при ошибке
SLEEP_MINUTES = 5                   # Интервал между циклами
```

После изменения параметров:
```bash
sudo systemctl restart revchecker
```

## Troubleshooting

### Служба не запускается
```bash
# Проверьте логи
sudo journalctl -u revchecker -n 50

# Проверьте конфигурацию
sudo systemctl cat revchecker

# Попробуйте запустить вручную
cd /home/callchecker/revchecker
source venv/bin/activate
python run_full_pipeline.py
```

### Ошибки с Google Sheets
```bash
# Проверьте credentials
ls -la gsheets/credentials.json

# Проверьте подключение
cd /home/callchecker/revchecker
source venv/bin/activate
python -c "import gspread; from google.oauth2.service_account import Credentials; \
    creds = Credentials.from_service_account_file('gsheets/credentials.json'); \
    client = gspread.authorize(creds); print('OK')"
```

### Ошибки с LLM API
```bash
# Проверьте .env
cat .env | grep -E 'API_KEY'

# Проверьте подключение
cd /home/callchecker/revchecker
source venv/bin/activate
python -c "from dotenv import load_dotenv; import os; load_dotenv(); \
    print('OpenAI:', 'OK' if os.getenv('OPENAI_API_KEY') else 'MISSING')"
```

## Структура файлов на сервере

```
/home/callchecker/
├── callchecker/                    # Существующий проект
│   ├── venv/
│   ├── bitrix24/
│   ├── logs/
│   └── ...
└── revchecker/                     # Новый проект
    ├── venv/
    ├── llm/
    ├── gsheets/
    │   ├── credentials.json        ← Важно!
    │   ├── sheets_config.json      ← Важно!
    │   └── test_data/
    ├── logs/
    ├── .env                        ← Важно!
    ├── run_full_pipeline.py
    └── ...
```

## Безопасность

1. **Файлы с секретами не должны попадать в Git:**
   - `.env`
   - `gsheets/credentials.json`
   - `gsheets/test_data/*`

2. **Права на файлы:**
```bash
chmod 600 .env
chmod 600 gsheets/credentials.json
chmod 755 *.sh
```

3. **Логи могут содержать чувствительные данные:**
```bash
# Регулярно чистите старые логи
find logs/ -name "*.log.*" -mtime +30 -delete
```

