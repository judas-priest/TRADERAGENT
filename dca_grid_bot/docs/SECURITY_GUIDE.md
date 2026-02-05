# Руководство по безопасности

**Версия:** 1.0
**Дата:** 2026-02-05

---

## Обзор

Безопасность API ключей критически важна для торгового бота. Этот документ описывает систему шифрования и best practices.

---

## Архитектура безопасности

### Многоуровневая защита

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: Environment Variables (SECRET_KEY)             │
│  └─> Stored in .env file (NOT in git)                   │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 2: Fernet Encryption (AES-128-CBC)               │
│  └─> API keys encrypted before storage                  │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 3: PostgreSQL Database                            │
│  └─> Encrypted credentials stored in exchange_credentials│
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 4: SSL/TLS Transport                              │
│  └─> All API calls over HTTPS                           │
└─────────────────────────────────────────────────────────┘
```

---

## Шифрование API ключей

### Метод шифрования: Fernet

**Характеристики:**
- Симметричное шифрование
- Основано на AES-128-CBC
- HMAC для аутентификации
- Timestamp для защиты от replay attacks
- Библиотека: `cryptography` (Python)

**Преимущества:**
- ✅ Проверенный стандарт (RFC 7748)
- ✅ Простая имплементация
- ✅ Встроенная защита от подделки
- ✅ Не требует управления IV (initialization vector)

---

## Генерация SECRET_KEY

### Шаг 1: Генерация ключа

```bash
# Метод 1: Используя модуль security
python -c "from dca_grid_bot.core.security import generate_secret_key; print(generate_secret_key())"

# Метод 2: Используя cryptography напрямую
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Метод 3: Используя OpenSSL
openssl rand -base64 32
```

**Результат:**
```
MJ8XaKjg5h2TYQ3mVxK4LpNzOqR1StUwVy8YaZbCdEf=
```

### Шаг 2: Сохранение в .env

Создайте файл `.env` в корне проекта:

```bash
# .env
SECRET_KEY=MJ8XaKjg5h2TYQ3mVxK4LpNzOqR1StUwVy8YaZbCdEf=

# Exchange API Keys (testnet)
BINANCE_API_KEY=your_testnet_api_key
BINANCE_API_SECRET=your_testnet_api_secret

# Database
DATABASE_URL=postgresql://user:pass@localhost/dca_grid_bot

# Redis
REDIS_URL=redis://localhost:6379/0
```

### Шаг 3: Добавить .env в .gitignore

**КРИТИЧЕСКИ ВАЖНО!**

```bash
# .gitignore
.env
*.env
config/bot_config.yaml
logs/
```

---

## Использование шифрования

### Базовое использование

```python
from dca_grid_bot.core.security import CredentialsEncryption

# Инициализация (автоматически загружает SECRET_KEY из env)
encryptor = CredentialsEncryption()

# Шифрование
api_key = "binance_test_key_12345"
encrypted_key = encryptor.encrypt(api_key)
print(encrypted_key)
# Output: "gAAAAABh3K..."

# Дешифрование
decrypted_key = encryptor.decrypt(encrypted_key)
assert decrypted_key == api_key
```

### Использование с CredentialsManager

```python
from dca_grid_bot.core.security import CredentialsManager, CredentialsEncryption

# Инициализация
encryptor = CredentialsEncryption()
manager = CredentialsManager(encryptor)

# Сохранение credentials
manager.store_credentials(
    bot_id=1,
    exchange="binance",
    api_key="your_api_key",
    api_secret="your_api_secret",
    is_testnet=True
)

# Получение credentials
credentials = manager.retrieve_credentials(bot_id=1, exchange="binance")
print(credentials['api_key'])     # Расшифрованный ключ
print(credentials['api_secret'])  # Расшифрованный секрет
```

---

## Ротация ключей

### Когда нужна ротация

- 🔄 Регулярно (раз в 3-6 месяцев)
- 🚨 При подозрении на компрометацию
- 👤 При смене персонала
- 💻 После утечки логов/конфигов

### Процесс ротации

```python
from dca_grid_bot.core.security import CredentialsEncryption

# Старый и новый ключи
old_key = "OLD_SECRET_KEY_..."
new_key = "NEW_SECRET_KEY_..."

# Инициализация
encryptor = CredentialsEncryption(old_key)

# Получить все зашифрованные данные из БД
encrypted_credentials = fetch_all_encrypted_credentials_from_db()

# Ротация каждого credential
for cred in encrypted_credentials:
    # Пере-шифрование
    new_encrypted_key = encryptor.rotate_key(
        old_secret_key=old_key,
        new_secret_key=new_key,
        encrypted_data=cred['api_key_encrypted']
    )

    new_encrypted_secret = encryptor.rotate_key(
        old_secret_key=old_key,
        new_secret_key=new_key,
        encrypted_data=cred['api_secret_encrypted']
    )

    # Обновить в БД
    update_credentials_in_db(
        cred['id'],
        new_encrypted_key,
        new_encrypted_secret
    )

# Обновить .env
# SECRET_KEY=NEW_SECRET_KEY_...
```

---

## Best Practices

### 1. Хранение SECRET_KEY

**✅ Правильно:**
- В переменных окружения (.env file)
- В секретах контейнера (Docker secrets)
- В секретах Kubernetes (K8s secrets)
- В AWS Secrets Manager / Azure Key Vault

**❌ Неправильно:**
- В коде (hardcoded)
- В git репозитории
- В конфигурационных файлах (yaml/json)
- В логах

### 2. API ключи бирж

**✅ Правильно:**
- Начинайте с testnet ключей
- Используйте API ключи с ограниченными правами:
  - ✓ Spot Trading
  - ✓ Read Account Info
  - ✗ Withdrawal (НЕ давать!)
- Включите IP whitelist на бирже
- Регулярно ротируйте ключи

**❌ Неправильно:**
- Давать полные права (включая withdrawal)
- Использовать production ключи для тестирования
- Делиться ключами

### 3. Права доступа к файлам

```bash
# .env файл должен быть доступен только владельцу
chmod 600 .env

# Проверка
ls -la .env
# -rw------- 1 user user 234 Feb 05 12:00 .env
```

### 4. Логирование

**Никогда не логируйте:**
- ❌ API ключи (даже часть)
- ❌ API секреты
- ❌ SECRET_KEY
- ❌ Пароли

**Можно логировать:**
- ✅ Exchange name
- ✅ Order IDs
- ✅ Prices и amounts
- ✅ Статусы ордеров

```python
# ❌ Плохо
logger.info(f"Using API key: {api_key}")

# ✅ Хорошо
logger.info(f"Connecting to {exchange_name}")
```

### 5. Резервное копирование

**Зашифрованные данные:**
```bash
# Бэкап базы данных (содержит зашифрованные credentials)
pg_dump dca_grid_bot > backup.sql

# Бэкап .env (храните отдельно и безопасно!)
cp .env backup/.env.$(date +%Y%m%d)
chmod 600 backup/.env.*
```

**Важно:**
- Бэкап БД + бэкап .env должны храниться раздельно
- Без SECRET_KEY бэкап БД бесполезен (credentials не расшифровать)
- Храните бэкапы в безопасном месте

---

## Проверка безопасности

### Checklist перед production

- [ ] SECRET_KEY сгенерирован криптографически стойким методом
- [ ] .env файл в .gitignore
- [ ] .env файл chmod 600
- [ ] API ключи без права withdrawal
- [ ] IP whitelist настроен на бирже
- [ ] Тестирование на testnet завершено
- [ ] Логи не содержат чувствительных данных
- [ ] Резервные копии .env в безопасном месте
- [ ] SSL/TLS для database connection
- [ ] Firewall настроен (только необходимые порты)

### Скрипт проверки

```bash
#!/bin/bash
# security_check.sh

echo "=== Security Checklist ==="

# Check .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found"
else
    echo "✅ .env file exists"

    # Check permissions
    perms=$(stat -c "%a" .env)
    if [ "$perms" = "600" ]; then
        echo "✅ .env permissions correct (600)"
    else
        echo "⚠️  .env permissions: $perms (should be 600)"
        echo "   Run: chmod 600 .env"
    fi
fi

# Check .gitignore
if grep -q ".env" .gitignore 2>/dev/null; then
    echo "✅ .env in .gitignore"
else
    echo "❌ .env NOT in .gitignore"
fi

# Check SECRET_KEY length
if [ -f .env ]; then
    key_length=$(grep SECRET_KEY .env | cut -d'=' -f2 | wc -c)
    if [ $key_length -ge 40 ]; then
        echo "✅ SECRET_KEY length OK ($key_length chars)"
    else
        echo "❌ SECRET_KEY too short ($key_length chars)"
    fi
fi

echo "=== Check Complete ==="
```

---

## Обработка компрометации

### Если API ключ скомпрометирован

**Немедленно:**

1. **Отзовите ключи на бирже**
   - Binance: Account → API Management → Delete
   - Bybit: Account → API Management → Delete

2. **Остановите бота**
   ```bash
   docker-compose down
   # или
   systemctl stop dca-grid-bot
   ```

3. **Проверьте историю торговли**
   - Проверьте все недавние ордера
   - Проверьте withdrawals (если было право)
   - Свяжитесь с поддержкой биржи

4. **Сгенерируйте новые ключи**
   - Создайте новую пару API key/secret
   - Обновите .env
   - Обновите БД

5. **Расследуйте причину**
   - Проверьте логи доступа
   - Проверьте git history
   - Проверьте файловые права

### Если SECRET_KEY скомпрометирован

**Немедленно:**

1. **Остановите все боты**

2. **Сгенерируйте новый SECRET_KEY**
   ```python
   python -c "from dca_grid_bot.core.security import generate_secret_key; print(generate_secret_key())"
   ```

3. **Выполните ротацию всех credentials**
   (см. раздел "Ротация ключей")

4. **Обновите .env на всех серверах**

5. **Перезапустите боты**

---

## FAQ

### Q: Нужно ли шифровать данные в transit?

**A:** Да, все API вызовы к биржам идут через HTTPS (TLS 1.2+). CCXT автоматически использует HTTPS.

### Q: Можно ли хранить SECRET_KEY в git?

**A:** **НЕТ!** Никогда не коммитьте SECRET_KEY. Используйте .env и .gitignore.

### Q: Что делать если потерял SECRET_KEY?

**A:** Без SECRET_KEY невозможно расшифровать credentials из БД. Придется:
1. Сгенерировать новый SECRET_KEY
2. Заново ввести все API ключи бирж

**Поэтому:** Делайте резервные копии .env!

### Q: Безопасно ли использовать Docker?

**A:** Да, но используйте Docker secrets вместо environment variables в production:

```yaml
# docker-compose.yml
services:
  bot:
    secrets:
      - secret_key

secrets:
  secret_key:
    file: ./secrets/secret_key.txt
```

### Q: Нужен ли HTTPS для локальной БД?

**A:** Для production на VPS - **да**. Настройте SSL для PostgreSQL:

```ini
# postgresql.conf
ssl = on
ssl_cert_file = 'server.crt'
ssl_key_file = 'server.key'
```

---

## Ресурсы

**Документация:**
- [Cryptography Library](https://cryptography.io/)
- [Fernet Specification](https://github.com/fernet/spec/)
- [OWASP API Security](https://owasp.org/www-project-api-security/)

**Инструменты:**
- [git-secrets](https://github.com/awslabs/git-secrets) - Предотвращает коммит секретов
- [truffleHog](https://github.com/trufflesecurity/truffleHog) - Поиск секретов в git history

---

**Статус:** ✅ Завершено
**Файлы:**
- `dca_grid_bot/core/security.py` - Реализация шифрования
- `dca_grid_bot/docs/SECURITY_GUIDE.md` - Данный документ
