from typing import TypedDict


class PlayerIndexEntry(TypedDict):
    """Compact player-index entry contract.

    id is the array position, which equals the player's rank (sorted by total
    debit desc). Plain dict contract: no validation dataclass, no import-time
    dependencies. Importable from both src/ingest/ and src/dashboard/ scripts.
    """

    id: int        # array position == rank
    pid: str
    country: str
    arch: str
    debit: float
    winlose: float
    bets: int
    avg_bet: float
    whale: bool
    chaser: bool
    op: str
    spike: float
