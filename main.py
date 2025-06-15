import asyncio
import signal
import argparse

from services import StickerdomAPI, TONWalletManager, PurchaseOrchestrator
from monitoring import CollectionWatcher
from models import CollectionInfo
from utils.logger import logger
from config import settings


class StickerHunterBot:
    
    def __init__(self):
        self.api = StickerdomAPI()
        self.wallet = TONWalletManager()
        self.orchestrator = PurchaseOrchestrator(self.api, self.wallet)
        self.watcher = CollectionWatcher(self.api)
        self._running = False
        self._purchase_in_progress = False
    

    async def initialize(self):
        logger.info("Initializing Sticker Hunter Bot...")
        
        if not await self.api.test_connection():
            raise RuntimeError("Failed to connect to API")
        
        await self.wallet.initialize()
        wallet_info = await self.wallet.get_wallet_info()
        logger.info(f"Wallet: {wallet_info.address} (Balance: {wallet_info.balance_ton} TON)")
        
        logger.info("Bot initialized successfully!")
    

    async def run(self, collection_id: int, character_id: int, continuous: bool = False):
        self._running = True
        
        try:
            await self.initialize()
            
            logger.info(f"🔍 Checking collection {collection_id}...")
            collection = await self.api.get_collection(collection_id)
            
            if collection is None:
                logger.info(
                    f"⏳ Collection {collection_id} not found. "
                    f"This is normal for upcoming drops. "
                    f"Bot will wait for it to appear..."
                )
            else:
                logger.info(
                    f"✅ Found collection: {collection.name} "
                    f"(Status: {collection.status}, Total: {collection.total_count})"
                )
            
            await self.watcher.watch_collection(
                collection_id,
                character_id,
                lambda col, char_id: asyncio.create_task(
                    self._on_collection_available(col, char_id, continuous)
                )
            )
            
            logger.info(f"👀 Monitoring collection {collection_id}, character {character_id}...")
            if continuous:
                logger.info("♾️  Continuous mode: Will keep buying while balance and stock available")
            
            while self._running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Bot error: {e}")
            raise
        finally:
            await self.shutdown()
    

    async def _on_collection_available(self, collection: CollectionInfo, character_id: int, continuous: bool):
        if self._purchase_in_progress:
            logger.info("Purchase already in progress, skipping...")
            return
        
        self._purchase_in_progress = True
        
        try:
            logger.info(f"Collection {collection.name} is available for purchase!")
            
            results = await self.orchestrator.execute_multiple_purchases(collection.id, character_id)
            
            successful_count = sum(1 for r in results if r.is_successful)
            
            if successful_count > 0:
                total_stickers = successful_count * settings.stickers_per_purchase
                logger.info(f"Successfully completed {successful_count} purchases ({total_stickers} stickers)!")
                
                if not continuous:
                    logger.info("Single purchase mode: stopping monitoring")
                    self.watcher.stop_watching(collection.id)
                    self._running = False
                else:
                    wallet_info = await self.wallet.get_wallet_info()
                    logger.info(
                        f"Continuous mode: Remaining balance {wallet_info.balance_ton:.2f} TON. "
                        f"Will continue monitoring..."
                    )
            else:
                logger.error("All purchase attempts failed")
                
        except Exception as e:
            logger.error(f"Failed to purchase: {e}")
        finally:
            self._purchase_in_progress = False
    

    async def shutdown(self):
        logger.info("Shutting down bot...")
        self._running = False
        await self.watcher.stop_all()
        await self.wallet.close()
        logger.info("Bot shutdown complete")
    
    def stop(self):
        self._running = False


def parse_collection_character(arg: str) -> tuple[int, int]:
    try:
        parts = arg.split('/')
        if len(parts) != 2:
            raise ValueError("Invalid format")
            
        character_id, collection_id = int(parts[0]), int(parts[1])
        
        if character_id <= 0 or collection_id <= 0:
            raise ValueError("IDs must be positive")
            
        return collection_id, character_id
    except (ValueError, IndexError):
        raise ValueError(f"Invalid format '{arg}'. Use: character_id/collection_id (e.g., 2/15)")


async def main():
    parser = argparse.ArgumentParser(description="Sticker Hunter Bot")
    parser.add_argument(
        "target",
        help="Character and collection in format: character_id/collection_id (e.g., 2/19)"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Purchase once and exit (buys maximum possible with current balance)"
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Continue monitoring and buying after successful purchases (keeps buying while balance available)"
    )
    
    args = parser.parse_args()
    
    try:
        collection_id, character_id = parse_collection_character(args.target)
    except ValueError as e:
        logger.error(f"Error: {e}")
        return
    
    bot = StickerHunterBot()
    
    def signal_handler(sig, frame):
        logger.info("Received shutdown signal")
        bot.stop()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        if args.once:
            await bot.initialize()
            
            try:
                results = await bot.orchestrator.execute_multiple_purchases(collection_id, character_id)
                successful = sum(1 for r in results if r.is_successful)
                
                if successful > 0:
                    logger.info(f"Purchase session successful! Completed {successful} purchases")
                else:
                    logger.error("All purchase attempts failed")
            except Exception as e:
                logger.error(f"Purchase failed: {e}")
                    
            await bot.wallet.close()
        else:
            await bot.run(collection_id, character_id, continuous=args.continuous)
            
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
    