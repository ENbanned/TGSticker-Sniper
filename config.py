from dataclasses import dataclass


@dataclass
class Config:
    
    # JWT токен из браузера
    jwt_token: str = "eyJhbGciOiJIUzI1N"
    
    # ton сид-фраза из 24 слов (например из TonKeeper)
    ton_seed_phrase: str = "word1 word2 ... word24"
    
    stickers_per_purchase: int = 5  # Максимально количество за 1 order
    gas_amount: float = 0.1  # Газ для отправки транзакции
    purchase_delay: int = 1  # Задержка между отдельными покупками
    
    collection_check_interval: int = 1  # Задержка между проверками на появление стикеров
    collection_not_found_retry: int = 3  # Задержка между повторными проверками, пока стикеров еще нету
    max_retries_per_request: int = 5  # Количество повторных запросов, если запрос завершился с ошибкой
    request_timeout: int = 10  # Таймаут обращения к stickerdom api
    
    # Не менять
    api_base_url: str = "https://api.stickerdom.store"
    ton_endpoint: str = "mainnet"


settings = Config()