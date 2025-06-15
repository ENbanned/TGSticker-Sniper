import asyncio
from decimal import Decimal
from typing import Optional, Tuple
from datetime import datetime

from tonutils.client import ToncenterV3Client
from tonutils.wallet import WalletV5R1

from config import settings
from exceptions import WalletError, TransactionError
from models.wallet import WalletInfo
from utils.logger import logger


class TONWalletManager:
    
    def __init__(self):
        self.mnemonic = settings.ton_seed_phrase.split()
        self.client: Optional[ToncenterV3Client] = None
        self.wallet: Optional[WalletV5R1] = None
        self._initialized = False
    
    async def initialize(self):
        if self._initialized:
            return
        
        try:
            is_testnet = settings.ton_endpoint == "testnet"
            self.client = ToncenterV3Client(
                is_testnet=is_testnet,
                rps=1,
                max_retries=3
            )
            
            self.wallet, _, _, _ = WalletV5R1.from_mnemonic(
                self.client,
                self.mnemonic
            )
            
            self._initialized = True
            logger.info(f"Wallet initialized: {self.wallet.address.to_str(is_bounceable=False)}")
            
        except Exception as e:
            logger.error(f"Failed to initialize wallet: {e}")
            raise WalletError(f"Wallet initialization failed: {e}")
    

    async def get_wallet_info(self) -> WalletInfo:
        await self._ensure_initialized()
        
        try:
            address_str = self.wallet.address.to_str(is_bounceable=False)
            balance = await self.client.get_account_balance(address_str)
            seqno = 0
            
            return WalletInfo(
                address=address_str,
                balance=Decimal(balance),
                seqno=seqno,
                is_active=balance > 0
            )
            
        except Exception as e:
            logger.error(f"Failed to get wallet info: {e}")
            raise WalletError(f"Could not retrieve wallet information: {e}")
    

    async def send_payment(
        self,
        destination: str,
        amount_nano: int,
        comment: str
    ) -> Tuple[str, datetime]:
        await self._ensure_initialized()
        
        try:
            amount_ton = amount_nano / 10**9
            
            logger.info(
                f"Sending {amount_ton:.9f} TON to {destination} "
                f"with payload: {comment}"
            )
            
            tx_hash = await self.wallet.transfer(
                destination=destination,
                amount=amount_ton,
                body=comment
            )
            
            logger.info(f"Transaction sent successfully: {tx_hash}")
            
            await asyncio.sleep(5)
            
            try:
                new_balance = await self.client.get_account_balance(
                    self.wallet.address.to_str(is_bounceable=False)
                )
                new_balance_ton = new_balance / 10**9
                logger.info(f"New balance after transaction: {new_balance_ton:.9f} TON")
            except:
                pass
            
            return tx_hash, datetime.now()
            
        except Exception as e:
            logger.error(f"Failed to send payment: {e}")
            raise TransactionError(f"Payment failed: {e}")
    

    async def _ensure_initialized(self):
        """Ensure wallet is initialized."""
        if not self._initialized:
            await self.initialize()
    

    async def close(self):
        self._initialized = False
        logger.info("Wallet closed")
        