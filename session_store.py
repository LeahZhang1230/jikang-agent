"""
嵇康智能体 — 会话存储层
支持单机内存存储 和 Redis 分布式存储，自动降级
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from typing import Optional


class SessionStore(ABC):
    """会话存储抽象基类"""

    @abstractmethod
    def get(self, session_id: str) -> Optional[dict]:
        """获取会话数据，不存在返回 None"""
        ...

    @abstractmethod
    def set(self, session_id: str, data: dict, ttl: int) -> None:
        """保存会话数据，ttl 为秒"""
        ...

    @abstractmethod
    def delete(self, session_id: str) -> None:
        """删除会话数据"""
        ...

    @abstractmethod
    def touch(self, session_id: str, ttl: int) -> None:
        """刷新会话 TTL"""
        ...


class MemoryStore(SessionStore):
    """单机内存存储（带 TTL 自动清理）"""

    def __init__(self):
        self._data: dict[str, dict] = {}
        self._expires: dict[str, float] = {}

    def _cleanup(self, session_id: str):
        now = time.time()
        if session_id in self._expires and now > self._expires[session_id]:
            self.delete(session_id)
            return True
        return False

    def get(self, session_id: str) -> Optional[dict]:
        if self._cleanup(session_id):
            return None
        return self._data.get(session_id)

    def set(self, session_id: str, data: dict, ttl: int) -> None:
        self._data[session_id] = data
        self._expires[session_id] = time.time() + ttl

    def delete(self, session_id: str) -> None:
        self._data.pop(session_id, None)
        self._expires.pop(session_id, None)

    def touch(self, session_id: str, ttl: int) -> None:
        if session_id in self._data:
            self._expires[session_id] = time.time() + ttl


class RedisStore(SessionStore):
    """Redis 分布式存储"""

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        import redis
        self._client = redis.from_url(redis_url, decode_responses=True)
        self._key_prefix = "jikang:session:"

    def get(self, session_id: str) -> Optional[dict]:
        key = self._key_prefix + session_id
        raw = self._client.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    def set(self, session_id: str, data: dict, ttl: int) -> None:
        key = self._key_prefix + session_id
        self._client.setex(key, ttl, json.dumps(data, ensure_ascii=False))

    def delete(self, session_id: str) -> None:
        key = self._key_prefix + session_id
        self._client.delete(key)

    def touch(self, session_id: str, ttl: int) -> None:
        key = self._key_prefix + session_id
        self._client.expire(key, ttl)


def create_store(redis_url: Optional[str] = None) -> SessionStore:
    """
    创建会话存储实例。
    优先尝试 Redis，若连接失败则自动降级为内存存储。
    """
    if redis_url is not None:
        try:
            store = RedisStore(redis_url)
            # 验证连接
            store._client.ping()
            print(f"[系统] Redis 存储已连接: {redis_url}")
            return store
        except Exception as e:
            print(f"[警告] Redis 连接失败 ({e})，已降级为内存存储")
            return MemoryStore()

    # 尝试默认 Redis 连接
    try:
        store = RedisStore()
        store._client.ping()
        print("[系统] Redis 存储已连接: redis://localhost:6379/0")
        return store
    except Exception:
        print("[系统] Redis 未配置，使用内存存储（仅支持单机）")
        return MemoryStore()
