# Быстрая установка на сервер

## 1. Клонирование проекта

```bash
# Подключитесь к серверу
ssh callchecker@YOUR_SERVER_IP

# Клонируйте проект из GitHub
cd /home/callchecker
git clone https://github.com/masta-danila/revchecker.git
cd revchecker
```

## 2. Настройка окружения

**ВАЖНО:** Перед запуском скриптов нужно добавить на сервер:
- `.env` - файл с API ключами для LLM
- `gsheets/credentials.json` - credentials из Google Cloud Console
- `gsheets/sheets_config.json` - ID Google таблиц

Скопируйте эти файлы с локальной машины:
```bash
# На локальной машине
scp .env callchecker@YOUR_SERVER_IP:/home/callchecker/revchecker/
scp gsheets/credentials.json callchecker@YOUR_SERVER_IP:/home/callchecker/revchecker/gsheets/
scp gsheets/sheets_config.json callchecker@YOUR_SERVER_IP:/home/callchecker/revchecker/gsheets/
```

## 3. Установка на сервере

```bash
# На сервере (в /home/callchecker/revchecker)
chmod +x deploy_server.sh setup_systemd_service.sh
./deploy_server.sh
```

## 4. Настройка службы

```bash
# Установите systemd службу
./setup_systemd_service.sh
```

## 5. Проверка

```bash
# Статус службы
sudo systemctl status revchecker

# Логи в реальном времени
sudo journalctl -u revchecker -f
```

## Готово! 🎉

Теперь на сервере работают две службы:
- `callchecker-*` - существующие службы Callchecker
- `revchecker` - новая служба RevChecker

Обе службы работают независимо друг от друга.

---

📖 **Подробная инструкция:** см. [DEPLOY.md](DEPLOY.md)

