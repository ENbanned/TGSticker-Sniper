import asyncio
from datetime import datetime
from decimal import Decimal
from typing import List, Tuple

from services.api_client import StickerdomAPI
from services.ton_wallet import TONWalletManager
from models import (
    PurchaseRequest, PurchaseResult, PurchaseStatus
)
from exceptions import (
    InsufficientBalanceError, CollectionNotAvailableError
)
from config import settings
from utils.logger import logger


class PurchaseOrchestrator:
    
    def __init__(self, api_client: StickerdomAPI, wallet_manager: TONWalletManager):
        self.api = api_client
        self.wallet = wallet_manager
    

    def calculate_max_purchases(
        self,
        available_balance: float,
        price_per_sticker: float,
        stickers_per_purchase: int = 5
    ) -> Tuple[int, float]:
        cost_per_purchase = price_per_sticker * stickers_per_purchase
        cost_with_gas = cost_per_purchase + settings.gas_amount
        max_purchases = int(available_balance / cost_with_gas)
        
        total_cost = max_purchases * cost_per_purchase
        total_gas = max_purchases * settings.gas_amount
        
        logger.info(
            f"Balance: {available_balance:.2f} TON, "
            f"Can make {max_purchases} purchases "
            f"({max_purchases * stickers_per_purchase} stickers total), "
            f"Total cost: {total_cost:.2f} TON + {total_gas:.2f} TON gas"
        )
        
        return max_purchases, total_cost + total_gas
    

    async def execute_multiple_purchases(
        self,
        collection_id: int,
        character_id: int
    ) -> List[PurchaseResult]:
        results = []
        
        try:
            collection = await self.api.get_collection(collection_id)
            if not collection or not collection.is_active:
                raise CollectionNotAvailableError(f"Collection {collection_id} not available")
            
            character = next((c for c in collection.characters if c.id == character_id), None)
            if not character or not character.is_available:
                raise CollectionNotAvailableError(f"Character {character_id} not available")
            
            character_price_ton = await self.api.get_character_price(collection_id, character_id, "TON")
            if not character_price_ton:
                raise CollectionNotAvailableError(f"Could not get TON price for character {character_id}")

            logger.info(f"Character: {character.name} (stock: {character.left}, price: {character_price_ton} TON per sticker)")

            wallet_info = await self.wallet.get_wallet_info()
            max_purchases, total_required = self.calculate_max_purchases(
                wallet_info.balance_ton,
                character_price_ton,
                settings.stickers_per_purchase
            )
            
            if max_purchases == 0:
                raise InsufficientBalanceError(
                    f"Insufficient balance. Need at least "
                    f"{character_price_ton * settings.stickers_per_purchase + settings.gas_amount:.2f} TON, "  # ← ИСПРАВИТЬ
                    f"have {wallet_info.balance_ton:.2f} TON"
                )
            
            logger.info(f"Starting {max_purchases} purchase(s)...")
            
            for i in range(max_purchases):
                logger.info(f"Processing purchase {i+1}/{max_purchases}...")
                
                try:
                    result = await self.execute_purchase(
                        collection_id,
                        character_id,
                        settings.stickers_per_purchase
                    )
                    results.append(result)
                    
                    if result.is_successful:
                        logger.info(
                            f"Purchase {i+1} completed! "
                            f"Order: {result.request.order_id}, "
                            f"TX: {result.transaction_hash}"
                        )
                    else:
                        logger.error(f"Purchase {i+1} failed: {result.error_message}")
                        break
                        
                except Exception as e:
                    logger.error(f"Purchase {i+1} failed with exception: {e}")
                    break
                
                if i < max_purchases - 1:
                    await asyncio.sleep(settings.purchase_delay)
            
            successful = sum(1 for r in results if r.is_successful)
            total_stickers = successful * settings.stickers_per_purchase
            total_spent = sum(
                float(r.request.total_amount_ton) 
                for r in results 
                if r.is_successful
            )
            
            logger.info(
                f"Purchase session completed: "
                f"{successful}/{max_purchases} successful, "
                f"{total_stickers} stickers bought, "
                f"{total_spent:.2f} TON spent"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Multiple purchase session failed: {e}")
            raise
    

    async def execute_purchase(
        self,
        collection_id: int,
        character_id: int,
        count: int = None
    ) -> PurchaseResult:
        count = count or settings.stickers_per_purchase
        purchase_request = None
        
        try:
            collection = await self.api.get_collection(collection_id)
            if not collection or not collection.is_active:
                raise CollectionNotAvailableError(f"Collection {collection_id} not available")
            
            character = next((c for c in collection.characters if c.id == character_id), None)
            if not character or not character.is_available:
                raise CollectionNotAvailableError(f"Character {character_id} not available")
            
            if character.left < count:
                logger.warning(
                    f"Not enough stock. Requested: {count}, available: {character.left}"
                )
                count = character.left
            
            character_price_ton = await self.api.get_character_price(collection_id, character_id, "TON")
            if not character_price_ton:
                raise CollectionNotAvailableError(f"Could not get TON price for character {character_id}")

            wallet_info = await self.wallet.get_wallet_info()
            required = character_price_ton * count + settings.gas_amount

            if not wallet_info.has_sufficient_balance(required):
                raise InsufficientBalanceError(
                    f"Need {required} TON, have {wallet_info.balance_ton} TON"
                )
            
            purchase_data = await self.api.initiate_purchase(
                collection_id, character_id, count
            )
            
            purchase_request = PurchaseRequest(
                collection_id=collection_id,
                character_id=character_id,
                count=count,
                price_per_item=character_price_ton,
                total_amount=Decimal(purchase_data['total_amount']),
                order_id=purchase_data['order_id'],
                destination_wallet=purchase_data['wallet'],
                created_at=datetime.now()
            )
            
            tx_hash, completed_at = await self.wallet.send_payment(
                destination=purchase_request.destination_wallet,
                amount_nano=int(purchase_request.total_amount),
                comment=purchase_request.order_id
            )
            
            result = PurchaseResult(
                request=purchase_request,
                transaction_hash=tx_hash,
                status=PurchaseStatus.CONFIRMED,
                completed_at=completed_at
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Purchase failed: {e}")
            
            if purchase_request:
                return PurchaseResult(
                    request=purchase_request,
                    transaction_hash=None,
                    status=PurchaseStatus.FAILED,
                    completed_at=datetime.now(),
                    error_message=str(e)
                )
            raise
        