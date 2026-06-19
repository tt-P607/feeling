"""feeling 事件处理器。

实现两个核心处理器：
1. FeelingPromptInjector：监听 on_prompt_build 事件，计算衰减并向 User Prompt 追加情感提示语。
2. FeelingTurnCounter：监听 ON_MESSAGE_SENT 事件，在 Bot 每次发送消息后对未主动更新情感的流累加 turn_count。
"""

from __future__ import annotations

from typing import Any

from src.app.plugin_system.api.event_api import EventDecision
from src.app.plugin_system.api.log_api import get_logger
from src.app.plugin_system.base import BaseEventHandler
from src.core.models.message import Message

from .config import FeelingConfig
from .store import FeelingStore

logger = get_logger("feeling.event_handler")


class FeelingPromptInjector(BaseEventHandler):
    """情感上下文注入器。

    订阅 ``on_prompt_build`` 事件，在 prompt 构建时计算衰减，
    并把计算后符合强度要求的情感状态以特定格式注入到 user prompt 的 extra 字段中。
    对于低于阈值的情感，注入“平和/常态”的提示。
    """

    handler_name: str = "feeling_prompt_injector"
    handler_description: str = "在目标 user prompt 末尾注入当前的情感状态或平和状态提示"
    weight: int = 12
    intercept_message: bool = False
    init_subscribe: list[str] = ["on_prompt_build"]

    def _get_config(self) -> FeelingConfig:
        """获取插件配置。"""
        config = self.plugin.config
        if isinstance(config, FeelingConfig):
            return config
        return FeelingConfig()

    async def execute(
        self,
        event_name: str,
        params: dict[str, Any],
    ) -> tuple[EventDecision, dict[str, Any]]:
        """处理 on_prompt_build 事件。"""
        config = self._get_config()
        if not config.plugin.enabled:
            return EventDecision.SUCCESS, params

        prompt_name: str = params.get("name", "")
        if prompt_name not in config.plugin.target_prompts:
            return EventDecision.SUCCESS, params

        values = params.get("values", {})
        stream_id = str(values.get("stream_id", "")).strip()
        if not stream_id:
            return EventDecision.SUCCESS, params

        store = FeelingStore.get_instance()
        decayed = await store.get_decayed_state(
            stream_id=stream_id,
            half_life_seconds=config.decay.half_life_seconds,
            turn_decay_factor=config.decay.turn_decay_factor,
        )

        # 构建情绪注入内容
        if decayed and decayed["intensity"] >= config.decay.min_intensity_threshold:
            # 活跃情绪状态注入
            injected_prompt = config.prompt.active_template.format(
                mood=decayed["mood"],
                intensity=decayed["intensity"],
                reason=decayed["reason"],
            )
            # 在日志中调试输出
            if config.plugin.debug_log:
                logger.info(
                    f"[feeling_prompt_injector] 注入活跃情绪到 stream_id={stream_id[:8]}...: "
                    f"[{decayed['mood']}] (强度 {decayed['intensity']:.2f})"
                )
        else:
            # 平和状态注入
            injected_prompt = config.prompt.peace_template
            if config.plugin.debug_log:
                logger.info(f"[feeling_prompt_injector] 注入平和状态到 stream_id={stream_id[:8]}...")

        # 追加注入至 values["extra"] (即 User Prompt 最后的 extra 字段)
        existing_extra = str(values.get("extra", ""))
        values["extra"] = (existing_extra + injected_prompt) if existing_extra else injected_prompt

        return EventDecision.SUCCESS, params


class FeelingTurnCounter(BaseEventHandler):
    """对话轮数计数器。

    订阅 ``ON_MESSAGE_SENT`` 事件。当 Bot 成功发送一条消息时，
    表示本轮对话交互完成。如果本轮内 Bot 没有调用 set_bot_feeling 更新情绪，
    则将其对应的 turn_count +1，从而使得后续衰减计算在下一轮准确。
    """

    handler_name: str = "feeling_turn_counter"
    handler_description: str = "Bot发送消息时累加该会话情感持有的对话轮数"
    weight: int = 13
    intercept_message: bool = False
    init_subscribe: list[str] = ["on_message_sent"]

    def _get_config(self) -> FeelingConfig:
        """获取插件配置。"""
        config = self.plugin.config
        if isinstance(config, FeelingConfig):
            return config
        return FeelingConfig()

    async def execute(
        self,
        event_name: str,
        params: dict[str, Any],
    ) -> tuple[EventDecision, dict[str, Any]]:
        """处理 ON_MESSAGE_SENT 事件。"""
        config = self._get_config()
        if not config.plugin.enabled:
            return EventDecision.SUCCESS, params

        message = params.get("message")
        if not isinstance(message, Message):
            return EventDecision.SUCCESS, params

        stream_id = str(message.stream_id or "").strip()
        if not stream_id:
            return EventDecision.SUCCESS, params

        # 检查本轮是否已经有 set_bot_feeling 工具更新了情感
        plugin: Any = self.plugin
        updated_streams: set[str] = getattr(plugin, "_updated_streams", None) or set()

        store = FeelingStore.get_instance()
        if stream_id in updated_streams:
            # 如果本轮已经主动更新了情绪，则将其从本轮更新集合中剔除（表示本轮消费完毕），不累加 turn_count
            updated_streams.remove(stream_id)
            setattr(plugin, "_updated_streams", updated_streams)
            logger.debug(f"[FeelingTurnCounter] stream_id={stream_id[:8]}... 本轮有情绪主动设置，不增加计数。")
        else:
            # 否则，从 store 加载当前的 state，并将 turn_count +1
            state = await store.get_raw_state(stream_id)
            if state:
                state["turn_count"] += 1
                await store.save_state(stream_id, state)
                logger.debug(
                    f"[FeelingTurnCounter] stream_id={stream_id[:8]}... 情绪轮数自增: {state['turn_count'] - 1} -> {state['turn_count']}"
                )

        return EventDecision.SUCCESS, params
