# Sticker Hunter Bot

Бот для автоматической покупки стикеров на [stickerdom.store](https://stickerdom.store). Мониторит коллекции и покупает, когда появляется нужный персонаж.

## Установка

```bash
pip install -r requirements.txt
```

## Настройка

Отредактируй `config.py`:

```python
# Твой JWT токен (см. раздел ниже)
jwt_token = "eyJ..."

# Seed фраза от TON кошелька (24 слова)
ton_seed_phrase = "word1 word2 ... word24"

# Сколько стикеров покупать за раз (макс 5)
stickers_per_purchase = 5

# TON на газ для каждой транзакции
gas_amount = 0.1
```

## Запуск

Формат: `character_id/collection_id`

```bash
# Мониторить и купить один раз
python main.py 2/19

# Купить сразу если доступно и выйти
python main.py 2/19 --once

# Продолжать покупать пока есть баланс
python main.py 2/19 --continuous
```

## Как работает

1. Бот проверяет коллекцию каждую секунду  
2. Если коллекции ещё нет — ждёт, пока появится  
3. Когда появляется нужный стикер — покупает максимум возможного за текущий баланс  
4. В режиме `--continuous` продолжает мониторить и покупать

## Получение JWT токена

[TODO: инструкция как получить токен]

## Проверка

Запусти тесты, чтобы убедиться, что всё работает:

```bash
python test_integration.py  # Проверка с реальным API
python test_scenarios.py    # Базовые проверки
```

## Структура проекта

```
├── main.py                   # Точка входа
├── config.py                 # Настройки
├── services/                 # API и кошелёк
│   ├── api_client.py         # Работа с stickerdom API
│   ├── ton_wallet.py         # TON транзакции
│   └── purchase_orchestrator.py  # Логика покупки
├── monitoring/               # Мониторинг коллекций
└── models/                   # Модели данных
```
