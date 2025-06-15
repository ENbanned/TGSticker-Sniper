
class StickerHunterError(Exception):
    pass


class APIError(StickerHunterError):
    pass


class WalletError(StickerHunterError):
    pass


class TransactionError(StickerHunterError):
    pass


class CollectionNotAvailableError(StickerHunterError):
    pass


class InsufficientBalanceError(WalletError):
    pass

class ConfigError(StickerHunterError):
    pass
