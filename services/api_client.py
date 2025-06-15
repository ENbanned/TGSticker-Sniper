
from typing import Optional, Dict, Any
from curl_cffi import requests

from config import settings
from exceptions import APIError
from models import CollectionInfo, CharacterInfo
from utils.logger import logger


class StickerdomAPI:
    
    def __init__(self):
        self.api_base = settings.api_base_url
        self.jwt_token = settings.jwt_token
        
        self.session = requests.Session(impersonate="chrome120")
        self.session.headers.update({
            'accept': 'application/json',
            'accept-language': 'ru,en;q=0.9',
            'authorization': f'Bearer {self.jwt_token}',
            'origin': 'https://stickerdom.store',
            'referer': 'https://stickerdom.store/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        logger.info("API client initialized")
    

    async def test_connection(self) -> bool:
        try:
            response = self.session.get(
                f"{self.api_base}/api/v1/shop/settings",
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"API connection test failed: {e}")
            return False
        

    async def get_character_price(
        self, 
        collection_id: int, 
        character_id: int, 
        currency: str = "TON"
    ) -> Optional[float]:
        try:
            response = self.session.get(
                f"{self.api_base}/api/v1/shop/price/crypto",
                params={
                    'collection': collection_id,
                    'character': character_id
                },
                timeout=20
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            if not data.get('ok'):
                return None
            
            # Найти цену для указанной валюты
            for price_data in data['data']:
                if price_data.get('token_symbol') == currency:
                    return float(price_data['price'])
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get price for {collection_id}/{character_id}: {e}")
            return None
    

    async def get_collection(self, collection_id: int) -> Optional[CollectionInfo]:
        try:
            response = self.session.get(
                f"{self.api_base}/api/v1/collection/{collection_id}",
                timeout=settings.request_timeout
            )
            
            if response.status_code == 404:
                return None
                
            if response.status_code != 200:
                logger.debug(f"Collection API returned {response.status_code}")
                return None
            
            data = response.json()
            
            if not data.get('ok'):
                return None
            
            collection_data = data['data']['collection']
            characters_data = data['data'].get('characters', [])
            
            characters = [
                CharacterInfo(
                    id=char['id'],
                    name=char['name'],
                    left=char.get('left', 0),
                    price=float(char.get('price', 0))
                )
                for char in characters_data
            ]
            
            return CollectionInfo(
                id=collection_data['id'],
                name=collection_data['title'],
                status=collection_data.get('status', 'inactive'),
                total_count=collection_data.get('total_count', 0),
                sold_count=collection_data.get('sold_count', 0),
                characters=characters
            )
            
        except Exception as e:
            logger.debug(f"Failed to get collection {collection_id}: {e}")
            return None
    

    async def initiate_purchase(
        self,
        collection_id: int,
        character_id: int,
        count: int = 5
    ) -> Dict[str, Any]:
        try:
            response = self.session.post(
                f"{self.api_base}/api/v1/shop/buy/crypto",
                params={
                    'collection': collection_id,
                    'character': character_id,
                    'currency': 'TON',
                    'count': count
                },
                timeout=20
            )
            
            if response.status_code != 200:
                raise APIError(f"Purchase initiation failed: {response.text}")
            
            data = response.json()
            if not data.get('ok'):
                raise APIError(f"Purchase initiation failed: {data}")
            
            purchase_data = data['data']
            logger.info(
                f"Purchase initiated: order_id={purchase_data['order_id']}, "
                f"amount={purchase_data['total_amount']/10**9} TON"
            )
            
            return purchase_data
            
        except Exception as e:
            logger.error(f"Failed to initiate purchase: {e}")
            raise APIError(str(e))
        