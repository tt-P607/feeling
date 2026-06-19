"""feeling 情感调节工具。

允许 Bot (LLM) 在生成过程中根据当前对话的冲击，主动设置并长期维护自己的情感/情绪状态。
"""

from __future__ import annotations

from typing import Annotated, Any

from src.app.plugin_system.base import BaseTool
from src.app.plugin_system.api.log_api import get_logger

from .store import FeelingStore

logger = get_logger("feeling.tool")

_TOOL_DESCRIPTION = """设置你自身的情绪与情感状态。
当你从当前的对话上下文、用户的态度、被捉弄/被夸奖等交互中感受到情绪波动时，你可以调用该工具设置或更新你当前持有的主导情感。
这会改变你接下来（以及未来几轮对话中）说话的语气、态度以及言语拉扯的风格，直到情绪随时间或对话自然消退。
"""


class SetBotFeelingTool(BaseTool):
    """设置 Bot 情感状态的工具类。"""

    tool_name: str = "set_bot_feeling"
    tool_description: str = _TOOL_DESCRIPTION

    async def execute(
        self,
        mood: Annotated[
            str,
            "当前情感/情绪的关键词名称（例如：委屈、羞涩、傲娇、生气、得意、失落、任性）。限 10 字以内。",
        ],
        intensity: Annotated[
            float,
            "情绪的强度。数值范围为 0.0（极其微弱，近乎平静）到 1.0（极其强烈，占据主导地位）。",
        ],
        reason: Annotated[
            str,
            "产生该情感的直观原因或上下文背景。请简明扼要，直接说明，限 50 字以内。",
        ],
    ) -> tuple[bool, str | dict]:
        """执行情感状态更新。

        利用绑定在 Tool 实例上的 stream_id 将新的情感持久化。
        """
        stream_id = getattr(self, "stream_id", "")
        if not stream_id:
            logger.warning("在 execute 中无法获取 stream_id，取消更新情感状态。")
            return False, "未能获取当前聊天会话ID，无法设置情绪。"

        # 10字与50字字数及强度限制
        mood = mood[:10].strip()
        reason = reason[:50].strip()
        intensity = max(0.0, min(1.0, float(intensity)))

        store = FeelingStore.get_instance()
        await store.set_state(
            stream_id=stream_id,
            mood=mood,
            intensity=intensity,
            reason=reason,
        )

        # 绕过 Pylance 属性校验使用 setattr 动态记录本轮已主动情绪更新的会话
        plugin: Any = self.plugin
        updated_streams: set[str] = getattr(plugin, "_updated_streams", None) or set()
        updated_streams.add(stream_id)
        setattr(plugin, "_updated_streams", updated_streams)

        logger.info(
            f"[set_bot_feeling] 成功为 stream_id={stream_id[:8]}... "
            f"设置情绪: [{mood}] (强度: {intensity:.2f}), 原因: {reason}"
        )

        return True, {
            "status": "success",
            "mood": mood,
            "intensity": intensity,
            "reason": reason,
            "message": f"情绪已成功更新为【{mood}】（强度 {intensity:.2f}），将影响接下来的对话风味。"
        }
