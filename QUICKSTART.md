# Быстрая установка на сервер

## 1. Подготовка архива (локально)

```bash
cd /Users/daniladzhiev/PycharmProjects/revchecker
tar --exclude='venv' --exclude='gsheets/test_data' --exclude='__pycache__' \
    --exclude='.git' --exclude='logs' -czf revchecker.tar.gz .
```

## 2. Копирование на сервер

```bash
# Замените YOUR_SERVER_IP на ваш IP
scp revchecker.tar.gz callchecker@YOUR_SERVER_IP:/home/callchecker/
```

## 3. Установка на сервере

```bash
# Подключитесь к серверу
ssh callchecker@YOUR_SERVER_IP

# Создайте директорию и распакуйте
cd /home/callchecker
mkdir -p revchecker
cd revchecker
tar -xzf ../revchecker.tar.gz
rm ../revchecker.tar.gz

# Сделайте скрипты исполняемыми и запустите установку
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

