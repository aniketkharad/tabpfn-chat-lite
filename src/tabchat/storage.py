"""Storage engine adapter for tabchat.

Exports the core Store interfaces from tabchat.store, and provides SessionStore
as a backward-compatible adapter with DiskStore and MemoryStore capabilities.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tabchat.config import get_settings
from tabchat.store import (
    DiskStore,
    GatewayStoreStub,
    MemoryStore,
    SessionNotFoundError,
    Store,
)


class SessionStore(DiskStore):
    """Backward-compatible session store maintaining disk persistence when data_dir is provided."""

    def __init__(self, data_dir: Path | str | None = None) -> None:
        if data_dir is None:
            resolved_dir = get_settings().DATA_DIR
        else:
            resolved_dir = Path(data_dir).resolve()
        super().__init__(data_dir=resolved_dir)


__all__ = [
    "Store",
    "MemoryStore",
    "DiskStore",
    "GatewayStoreStub",
    "SessionNotFoundError",
    "SessionStore",
]
