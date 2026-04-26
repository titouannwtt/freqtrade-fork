"""
Tests for the pairlist cache daemon and client.

Uses a temporary Unix socket to spawn a real daemon in-process,
then exercises the client against it.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from freqtrade.pairlist_cache.client import PairlistCacheClient
from freqtrade.pairlist_cache.daemon import PairlistCacheDaemon


@pytest.fixture()
def tmp_socket(tmp_path):
    return str(tmp_path / "test-ftpairlist.sock")


@pytest.fixture()
def tmp_persistence(tmp_path):
    return tmp_path / "pairlist_cache.json"


_daemon_loops: dict[int, asyncio.AbstractEventLoop] = {}


def _run_daemon(daemon: PairlistCacheDaemon):
    loop = asyncio.new_event_loop()
    _daemon_loops[id(daemon)] = loop
    loop.run_until_complete(daemon.serve())
    loop.close()


def _shutdown_daemon(daemon: PairlistCacheDaemon):
    """Thread-safe shutdown: schedule event.set() on the daemon's loop."""
    loop = _daemon_loops.get(id(daemon))
    if loop and loop.is_running():
        loop.call_soon_threadsafe(daemon._shutdown.set)
    else:
        daemon._shutdown.set()


@pytest.fixture()
def daemon_and_client(tmp_socket, tmp_persistence):
    """Start a real daemon in a background thread, return (daemon, client)."""
    daemon = PairlistCacheDaemon(
        tmp_socket, idle_shutdown_s=300, persistence_path=tmp_persistence,
    )
    thread = threading.Thread(target=_run_daemon, args=(daemon,), daemon=True)
    thread.start()

    # Wait for socket to become available
    for _ in range(50):
        if Path(tmp_socket).exists():
            try:
                client = PairlistCacheClient(tmp_socket, timeout=5.0)
                resp = client._request({"op": "ping"})
                if resp.get("ok"):
                    yield daemon, client
                    _shutdown_daemon(daemon)
                    thread.join(timeout=5)
                    return
            except Exception:
                pass
        time.sleep(0.1)

    pytest.fail("Daemon did not start in time")


class TestPairlistCacheDaemon:
    def test_ping(self, daemon_and_client):
        _, client = daemon_and_client
        resp = client._request({"op": "ping"})
        assert resp["ok"] is True
        assert "uptime_s" in resp
        assert resp["version"] == 1

    def test_put_and_get(self, daemon_and_client):
        _, client = daemon_and_client
        # Put a value
        client._request({
            "op": "put", "method": "VolatilityFilter",
            "params_hash": "abc123", "pair": "BTC/USDT",
            "value": {"volatility_avg": 0.05}, "ttl": 60,
        })
        # Get it back
        resp = client._request({
            "op": "get", "method": "VolatilityFilter",
            "params_hash": "abc123", "pair": "BTC/USDT",
        })
        assert resp["ok"] is True
        assert resp["hit"] is True
        assert resp["value"]["volatility_avg"] == 0.05

    def test_get_miss(self, daemon_and_client):
        _, client = daemon_and_client
        resp = client._request({
            "op": "get", "method": "VolatilityFilter",
            "params_hash": "nonexistent", "pair": "BTC/USDT",
        })
        assert resp["ok"] is True
        assert resp["hit"] is False

    def test_mput_and_mget(self, daemon_and_client):
        _, client = daemon_and_client
        # Batch put
        client._request({
            "op": "mput", "method": "TrendRegularity",
            "params_hash": "def456",
            "entries": {
                "BTC/USDT": {"exclude": False},
                "ETH/USDT": {"exclude": True},
                "SOL/USDT": {"exclude": False},
            },
            "ttl": 120,
        })
        # Batch get
        resp = client._request({
            "op": "mget", "method": "TrendRegularity",
            "params_hash": "def456",
            "pairs": ["BTC/USDT", "ETH/USDT", "SOL/USDT", "DOGE/USDT"],
        })
        assert resp["ok"] is True
        results = resp["results"]
        assert results["BTC/USDT"]["hit"] is True
        assert results["BTC/USDT"]["value"]["exclude"] is False
        assert results["ETH/USDT"]["hit"] is True
        assert results["ETH/USDT"]["value"]["exclude"] is True
        assert results["SOL/USDT"]["hit"] is True
        assert results["DOGE/USDT"]["hit"] is False

    def test_client_mget_mput(self, daemon_and_client):
        """Test the high-level client mget/mput methods."""
        _, client = daemon_and_client
        # mput
        client.mput(
            method="VolumePairList",
            params_hash="vol789",
            entries={
                "BTC/USDT": {"quoteVolume": 1000000},
                "ETH/USDT": {"quoteVolume": 500000},
            },
            ttl=60,
        )
        # mget
        results = client.mget(
            method="VolumePairList",
            params_hash="vol789",
            pairs=["BTC/USDT", "ETH/USDT", "XRP/USDT"],
        )
        assert results["BTC/USDT"] == {"quoteVolume": 1000000}
        assert results["ETH/USDT"] == {"quoteVolume": 500000}
        assert results["XRP/USDT"] is None

    def test_ttl_expiry(self, daemon_and_client):
        _, client = daemon_and_client
        # Put with 1 second TTL
        client._request({
            "op": "put", "method": "Test",
            "params_hash": "ttl", "pair": "BTC/USDT",
            "value": {"data": 1}, "ttl": 1,
        })
        # Should be a hit immediately
        resp = client._request({
            "op": "get", "method": "Test",
            "params_hash": "ttl", "pair": "BTC/USDT",
        })
        assert resp["hit"] is True

        # Wait for expiry
        time.sleep(1.5)

        resp = client._request({
            "op": "get", "method": "Test",
            "params_hash": "ttl", "pair": "BTC/USDT",
        })
        assert resp["hit"] is False

    def test_stats(self, daemon_and_client):
        _, client = daemon_and_client
        # Do some operations
        client._request({
            "op": "put", "method": "A",
            "params_hash": "h", "pair": "X",
            "value": {"v": 1}, "ttl": 60,
        })
        client._request({
            "op": "get", "method": "A",
            "params_hash": "h", "pair": "X",
        })
        client._request({
            "op": "get", "method": "A",
            "params_hash": "h", "pair": "Y",
        })

        resp = client._request({"op": "stats"})
        assert resp["ok"] is True
        assert resp["puts"] >= 1
        assert resp["gets"] >= 2
        assert resp["hits"] >= 1
        assert resp["entries"] >= 1

    def test_params_hash_invalidation(self, daemon_and_client):
        _, client = daemon_and_client
        # Same method, same pair, different params_hash
        client._request({
            "op": "put", "method": "Filter",
            "params_hash": "config_v1", "pair": "BTC/USDT",
            "value": {"result": "old"}, "ttl": 60,
        })
        client._request({
            "op": "put", "method": "Filter",
            "params_hash": "config_v2", "pair": "BTC/USDT",
            "value": {"result": "new"}, "ttl": 60,
        })

        # v1 still returns old value
        resp = client._request({
            "op": "get", "method": "Filter",
            "params_hash": "config_v1", "pair": "BTC/USDT",
        })
        assert resp["value"]["result"] == "old"

        # v2 returns new value
        resp = client._request({
            "op": "get", "method": "Filter",
            "params_hash": "config_v2", "pair": "BTC/USDT",
        })
        assert resp["value"]["result"] == "new"


class TestComputeParamsHash:
    def test_deterministic(self):
        config = {"method": "VolatilityFilter", "lookback_days": 10, "min_volatility": 0.01}
        h1 = PairlistCacheClient.compute_params_hash(config)
        h2 = PairlistCacheClient.compute_params_hash(config)
        assert h1 == h2

    def test_excludes_method(self):
        config1 = {"method": "FilterA", "param": 1}
        config2 = {"method": "FilterB", "param": 1}
        assert PairlistCacheClient.compute_params_hash(config1) == \
            PairlistCacheClient.compute_params_hash(config2)

    def test_different_params_different_hash(self):
        config1 = {"method": "Filter", "param": 1}
        config2 = {"method": "Filter", "param": 2}
        assert PairlistCacheClient.compute_params_hash(config1) != \
            PairlistCacheClient.compute_params_hash(config2)

    def test_hash_length(self):
        config = {"method": "Test", "x": 1}
        h = PairlistCacheClient.compute_params_hash(config)
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)


class TestPersistence:
    def test_save_and_reload(self, tmp_socket, tmp_persistence):
        """Test that daemon saves on shutdown and reloads on startup."""
        # Start daemon, put data, shutdown
        daemon1 = PairlistCacheDaemon(
            tmp_socket, idle_shutdown_s=300, persistence_path=tmp_persistence,
        )
        thread1 = threading.Thread(target=_run_daemon, args=(daemon1,), daemon=True)
        thread1.start()

        for _ in range(50):
            if Path(tmp_socket).exists():
                break
            time.sleep(0.1)

        client1 = PairlistCacheClient(tmp_socket, timeout=5.0)
        client1._request({
            "op": "put", "method": "Test",
            "params_hash": "persist", "pair": "BTC/USDT",
            "value": {"data": 42}, "ttl": 3600,
        })

        # Shutdown daemon (triggers _save_to_disk)
        _shutdown_daemon(daemon1)
        thread1.join(timeout=5)

        # Verify persistence file exists
        assert tmp_persistence.exists()
        saved = json.loads(tmp_persistence.read_text())
        assert saved["version"] == 1
        assert "Test" in saved["data"]

        # Start new daemon on different socket (old one is cleaned up)
        sock2 = tmp_socket + ".2"
        daemon2 = PairlistCacheDaemon(
            sock2, idle_shutdown_s=300, persistence_path=tmp_persistence,
        )
        thread2 = threading.Thread(target=_run_daemon, args=(daemon2,), daemon=True)
        thread2.start()

        for _ in range(50):
            if Path(sock2).exists():
                break
            time.sleep(0.1)

        client2 = PairlistCacheClient(sock2, timeout=5.0)
        resp = client2._request({
            "op": "get", "method": "Test",
            "params_hash": "persist", "pair": "BTC/USDT",
        })
        assert resp["hit"] is True
        assert resp["value"]["data"] == 42

        # Persistence file should be deleted after load
        assert not tmp_persistence.exists()

        _shutdown_daemon(daemon2)
        thread2.join(timeout=5)
