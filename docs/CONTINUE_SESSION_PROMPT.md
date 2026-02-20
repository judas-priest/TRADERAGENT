# Prompt для продолжения настройки ByBit API

## Контекст проекта

Работаем над настройкой **TRADERAGENT DCA-Grid торгового бота** для подключения к **ByBit API** на продакшн сервере.

---

## Информация о серверах

### Продакшн сервер (где работает бот):
- **IP:** `185.233.200.13`
- **Пользователь:** `ai-agent`
- **Путь:** `/home/ai-agent/TRADERAGENT`
- **SSH:** `ssh ai-agent@185.233.200.13`

### Тестовый сервер (для разработки):
- **IP:** `173.249.2.184`
- **Пользователь:** `hive`
- **Путь:** `/home/hive/TRADERAGENT`

---

## Что уже сделано

### ✅ Подготовка инфраструктуры:
1. **PostgreSQL** - запущена и работает (19+ часов uptime)
2. **Redis** - запущен и работает
3. **.env файл** настроен:
   - `DATABASE_URL=postgresql+asyncpg://traderagent:ZbcU9AJSFICuUHuacy0ZOw@localhost:5432/traderagent`
   - `ENCRYPTION_KEY=GCUcFBXAXGlcvelZ1eONGPIH3_N-oDWvjyd235TiwTY=`
   - Telegram bot token настроен

### ✅ Созданные скрипты (на обоих серверах):
1. **add_bybit_credentials.py** - добавление API ключей в БД с шифрованием
2. **test_bybit_connection.py** - тестирование подключения к ByBit
3. **configs/bybit_example.yaml** - примеры конфигураций для Grid/DCA/Hybrid
4. **BYBIT_PRODUCTION_SETUP.md** - полная документация по настройке

### ✅ Credentials в базе данных:
- **ID:** 2
- **Name:** `bybit_production`
- **Exchange:** `bybit`
- **Sandbox:** `False` (последнее состояние)
- **Active:** `True`

---

## ⚠️ Текущая проблема

### API ключи не проходят аутентификацию на ByBit

**Ошибка:** ByBit API возвращает `retCode: 10003` - "API key is invalid"

**Проверенные ключи (все недействительны):**
1. `a27YMIF3Hx5g7BdbtM` / `1llqUpv0XON5MF7M9QmlSomb50IoH5xeAstl`
2. `1a27YMIF3Hx5g7BdbtM` / `1llqUpv0XON5MF7M9QmlSomb50IoH5xeAstl`
3. `shosapyYyukVfvWf6j` / `qGuQqDWQzsYUno26r0U16z8l5CIlDLFKEnGZ`

**Проверено:**
- ✅ Public API ByBit работает (протестировано)
- ✅ IP whitelist настроен на ByBit: `185.233.200.13`
- ✅ Разрешения: Read + Contract Trading (видно на скриншоте)
- ❌ Но **Spot Trading** разрешения могут отсутствовать
- ❌ Прямые запросы к ByBit V5 API возвращают ошибку 10003

### Особенности аккаунта:
- **Тип:** Unified Trading Account
- **Режим:** Demo Trading (Paper Trading) - виртуальные средства
- **Субаккаунт:** Используется субаккаунт (возможно, это проблема)
- **Цель:** Spot торговля (BTC/USDT, ETH/USDT)

---

## 🎯 Что нужно сделать дальше

### 1. Получить валидные API ключи от ByBit

**Пользователю нужно:**

a) **Проверить текущий ключ на ByBit:**
   - URL: https://www.bybit.com/user/assets/api-management
   - Убедиться, что ключ **активен**
   - Проверить, что это **основной аккаунт** (не субаккаунт)
   - Проверить **Spot Trading** разрешения (не только Contract!)

b) **Или создать НОВЫЙ ключ:**
   ```
   Key Name: TRADERAGENT_SPOT
   Account Type: Unified Trading Account
   Permissions:
     ✅ Read
     ✅ Spot Trading (обязательно!)
   IP Restriction: 185.233.200.13 (или отключить)
   ```

c) **Скопировать ключи кнопкой "Copy"** (не вручную!)

### 2. После получения рабочих ключей

**Команды для обновления credentials:**

```bash
# SSH на продакшн сервер
ssh ai-agent@185.233.200.13
cd /home/ai-agent/TRADERAGENT

# Обновить credentials в БД (создать скрипт)
cat > update_new_keys.py << 'EOF'
#!/usr/bin/env python3
import asyncio, os, sys
sys.path.insert(0, '/app')
from cryptography.fernet import Fernet
from bot.database.manager import DatabaseManager

async def update():
    api_key = "НОВЫЙ_API_KEY"
    api_secret = "НОВЫЙ_API_SECRET"

    db = DatabaseManager(os.getenv("DATABASE_URL"))
    await db.initialize()

    cred = await db.get_credentials_by_name("bybit_production")
    fernet = Fernet(os.getenv("ENCRYPTION_KEY").encode())

    cred.api_key_encrypted = fernet.encrypt(api_key.encode()).decode()
    cred.api_secret_encrypted = fernet.encrypt(api_secret.encode()).decode()
    cred.is_sandbox = True  # True для Demo Trading

    await db.update(cred)
    print(f"✅ Updated! API Key: {api_key}")
    await db.close()

asyncio.run(update())
EOF

# Запустить обновление
docker run --rm -v $(pwd):/app -w /app --network host --env-file .env \
  python:3.12-slim bash -c 'pip install -q -r requirements.txt && python /app/update_new_keys.py'

# Проверить подключение
docker run --rm -v $(pwd):/app -w /app --network host --env-file .env \
  python:3.12-slim bash -c 'pip install -q -r requirements.txt && python /app/test_bybit_connection.py --credentials bybit_production'
```

### 3. Настроить и запустить бота

**После успешного теста подключения:**

```bash
# Создать production конфигурацию
cp configs/bybit_example.yaml configs/production_bybit.yaml

# Отредактировать конфиг
nano configs/production_bybit.yaml
```

**Обязательные параметры:**
```yaml
exchange:
  credentials_name: bybit_production
  sandbox: true  # для Demo Trading

grid:
  amount_per_grid: "10"  # малые суммы для начала!

risk_management:
  max_position_size: "500"
  stop_loss_percentage: "0.15"

dry_run: true  # ОБЯЗАТЕЛЬНО true для первых тестов!
```

**Запустить бота:**
```bash
# В dry_run режиме (без реальных ордеров)
python -m bot.main --config configs/production_bybit.yaml

# Или в фоне
nohup python -m bot.main --config configs/production_bybit.yaml > bot.log 2>&1 &

# Просмотр логов
tail -f bot.log
```

---

## 📚 Важные файлы и документация

### На продакшн сервере (185.233.200.13):
- `/home/ai-agent/TRADERAGENT/.env` - переменные окружения
- `/home/ai-agent/TRADERAGENT/add_bybit_credentials.py` - добавление ключей
- `/home/ai-agent/TRADERAGENT/test_bybit_connection.py` - тест подключения
- `/home/ai-agent/TRADERAGENT/configs/bybit_example.yaml` - пример конфигурации
- `/home/ai-agent/TRADERAGENT/BYBIT_PRODUCTION_SETUP.md` - полная документация

### На тестовом сервере (173.249.2.184):
- `/home/hive/TRADERAGENT/` - те же файлы для разработки

### Docker контейнеры:
- `traderagent-postgres` - PostgreSQL (Up 20+ hours)
- `traderagent-redis` - Redis (Up 20+ hours)
- `traderagent-bot` - Docker образ бота (существует)

---

## 🔍 Диагностические команды

### Проверить статус:
```bash
ssh ai-agent@185.233.200.13

# PostgreSQL
docker ps | grep postgres

# Credentials в БД
docker exec traderagent-postgres psql -U traderagent -d traderagent \
  -c "SELECT id, name, exchange_id, is_sandbox, is_active FROM exchange_credentials;"

# Переменные окружения
cat .env | grep -E "(DATABASE_URL|ENCRYPTION_KEY)"
```

### Прямой тест API ключей:
```bash
ssh ai-agent@185.233.200.13

python3 << 'EOF'
import hmac, hashlib, time, requests

api_key = "ВАШ_API_KEY"
api_secret = "ВАШ_API_SECRET"

timestamp = str(int(time.time() * 1000))
recv_window = '5000'
query_string = 'accountType=UNIFIED'
param_str = f'{timestamp}{api_key}{recv_window}{query_string}'
signature = hmac.new(api_secret.encode(), param_str.encode(), hashlib.sha256).hexdigest()

headers = {
    'X-BAPI-API-KEY': api_key,
    'X-BAPI-SIGN': signature,
    'X-BAPI-SIGN-TYPE': '2',
    'X-BAPI-TIMESTAMP': timestamp,
    'X-BAPI-RECV-WINDOW': recv_window
}

url = 'https://api.bybit.com/v5/account/wallet-balance?accountType=UNIFIED'
response = requests.get(url, headers=headers)
result = response.json()

print(f"RetCode: {result.get('retCode')}")
print(f"RetMsg: {result.get('retMsg')}")
print("✅ SUCCESS!" if result.get('retCode') == 0 else "❌ FAILED!")
EOF
```

---

## ⚠️ Критические предупреждения

1. **ВСЕГДА начинайте с `dry_run: true`** - без реальных ордеров!
2. **Demo Trading** использует виртуальные средства - идеально для тестов
3. **Малые суммы:** `amount_per_grid: "10"` для начала
4. **Stop-loss обязателен:** `stop_loss_percentage: "0.15"`
5. **IP whitelist:** `185.233.200.13` должен быть в списке на ByBit
6. **Spot Trading разрешения** должны быть включены (не только Contract!)

---

## 📞 Следующие шаги при продолжении

1. **Спросить пользователя:** Получены ли новые валидные API ключи от ByBit?

2. **Если да:**
   - Обновить credentials в БД
   - Проверить подключение
   - Настроить и запустить бота

3. **Если нет:**
   - Помочь с получением правильных ключей
   - Убедиться, что Spot Trading разрешения включены
   - Проверить, что используется основной аккаунт (не субаккаунт)

---

## 🎯 Цель

Запустить TRADERAGENT бота на продакшн сервере (185.233.200.13) с подключением к ByBit Demo Trading аккаунту для спотовой торговли (Grid/DCA стратегии).

---

Дата создания: 2026-02-11
Статус: Ожидание валидных API ключей от ByBit
