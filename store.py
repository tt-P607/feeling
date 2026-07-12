"""feeling 情感状态存储与衰减逻辑。

利用 storage_api 将情感数据持久化到本地 JSON 隔离空间中。
"""

from __future__ import annotations

import time
from typing import ClassVar, TypedDict

from src.app.plugin_system.api import storage_api
from src.app.plugin_system.api.log_api import get_logger

logger = get_logger("feeling.store")


class FeelingState(TypedDict):
    """持久化保存的情感状态。"""

    mood: str
    intensity: float
    reason: str
    updated_at: float
    turn_count: int


class FeelingStore:
    """按会话隔离的情感状态管理器。"""

    _instance: ClassVar[FeelingStore | None] = None

    def __init__(self) -> None:
        """初始化。"""
        self.namespace = "feeling"

    @classmethod
    def get_instance(cls) -> FeelingStore:
        """获取单例。"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def get_raw_state(self, stream_id: str) -> FeelingState | None:
        """从隔离的 JSON 存储中直接加载未衰减的原始状态。"""
        try:
            data = await storage_api.load_json(self.namespace, stream_id)
            if data and isinstance(data, dict):
                return FeelingState(
                    mood=str(data.get("mood", "")),
                    intensity=float(data.get("intensity", 1.0)),
                    reason=str(data.get("reason", "")),
                    updated_at=float(data.get("updated_at", time.time())),
                    turn_count=int(data.get("turn_count", 0)),
                )
        except Exception as exc:
            logger.error(f"加载 stream_id={stream_id} 的情感状态失败: {exc}")
            # 如果加载失败（比如 JSON 损坏），清除损坏的文件以恢复默认状态
            try:
                await storage_api.delete_json(self.namespace, stream_id)
                logger.info(f"已清理 stream_id={stream_id} 损坏的情感状态文件")
            except Exception as e:
                logger.error(f"清理损坏的情感状态文件失败: {e}")
        return None

    async def set_state(
        self,
        stream_id: str,
        mood: str,
        intensity: float,
        reason: str,
    ) -> FeelingState:
        """主动设置/更新会话的情感状态。

        设置新情绪时，更新时间戳设为当前，经历的对话轮数 turn_count 重置为 0。
        """
        mood = mood[:10]
        reason = reason[:50]
        intensity = max(0.0, min(1.0, intensity))

        state = FeelingState(
            mood=mood,
            intensity=intensity,
            reason=reason,
            updated_at=time.time(),
            turn_count=0,
        )

        try:
            await storage_api.save_json(self.namespace, stream_id, dict(state))
        except Exception as exc:
            logger.error(f"保存 stream_id={stream_id} 的情感状态失败: {exc}")

        return state

    async def save_state(self, stream_id: str, state: FeelingState) -> None:
        """保存已有的情感状态（例如衰减过后的状态或自增轮数后的状态）。"""
        try:
            await storage_api.save_json(self.namespace, stream_id, dict(state))
        except Exception as exc:
            logger.error(f"增量保存 stream_id={stream_id} 的情感状态失败: {exc}")

    async def get_decayed_state(
        self,
        stream_id: str,
        half_life_seconds: float,
        turn_decay_factor: float,
        now: float | None = None,
    ) -> FeelingState | None:
        """获取并计算经过混合衰减后的情感状态。

        若低于阈值，则视为常态（外部调用决定是否清理或显示平和提示）。
        """
        state = await self.get_raw_state(stream_id)
        if not state:
            return None

        current_time = now if now is not None else time.time()
        
        # 兼容旧版本数据或异常状态（无 updated_at 或格式错误）
        updated_at = state.get("updated_at")
        if updated_at is None or not isinstance(updated_at, (int, float)):
            updated_at = current_time
            state["updated_at"] = updated_at
            
        elapsed_seconds = max(0.0, current_time - updated_at)

        # 1. 时间指数衰减: intensity * (0.5 ^ (elapsed / half_life))
        if half_life_seconds <= 0:
            time_decayed_intensity = state["intensity"]
        else:
            time_decayed_intensity = state["intensity"] * (0.5 ** (elapsed_seconds / half_life_seconds))

        # 2. 对话轮数衰减: intensity * (turn_decay_factor ^ turn_count)
        decay_factor = max(0.0, min(1.0, turn_decay_factor))
        final_intensity = time_decayed_intensity * (decay_factor ** state["turn_count"])

        return FeelingState(
            mood=state.get("mood", ""),
            intensity=round(final_intensity, 3),
            reason=state.get("reason", ""),
            updated_at=updated_at,
            turn_count=state.get("turn_count", 0),
        )

    async def clear_state(self, stream_id: str) -> None:
        """彻底清除某会话的情感状态。"""
        try:
            await storage_api.delete_json(self.namespace, stream_id)
        except Exception as exc:
            logger.error(f"清除 stream_id={stream_id} 的情感状态失败: {exc}")
