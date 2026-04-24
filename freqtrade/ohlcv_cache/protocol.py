"""
Newline-delimited JSON protocol between bots (clients) and the daemon.

Phase 0 uses JSON for easy debugging; a later phase will switch to msgpack
for throughput.

Messages are one JSON object per line, UTF-8 encoded, terminated by `\\n`.
"""

import json
from dataclasses import asdict, dataclass, field
from typing import Any


PROTOCOL_VERSION = 1


@dataclass
class FetchRequest:
    req_id: str
    exchange: str
    trading_mode: str           # "spot" | "futures"
    pair: str
    timeframe: str
    candle_type: str            # CandleType string value
    since_ms: int | None = None
    limit: int | None = None
    op: str = "fetch"


@dataclass
class PingRequest:
    op: str = "ping"
    req_id: str = ""


@dataclass
class FetchResponse:
    req_id: str
    ok: bool
    pair: str = ""
    timeframe: str = ""
    candle_type: str = ""
    data: list = field(default_factory=list)     # list of [ts, o, h, l, c, v]
    drop_incomplete: bool = True
    served_from: str = ""                         # "cache" | "fetch" | "fallback"
    latency_ms: float = 0.0
    error_type: str = ""
    error_message: str = ""


@dataclass
class PongResponse:
    req_id: str = ""
    ok: bool = True
    daemon_version: int = PROTOCOL_VERSION
    uptime_s: float = 0.0


def dumps(obj: Any) -> bytes:
    if hasattr(obj, "__dataclass_fields__"):
        payload = asdict(obj)
    elif isinstance(obj, dict):
        payload = obj
    else:
        raise TypeError(f"Cannot serialize {type(obj)!r}")
    return (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")


def loads_request(line: bytes) -> dict:
    return json.loads(line.decode("utf-8"))


def loads_response(line: bytes) -> dict:
    return json.loads(line.decode("utf-8"))
