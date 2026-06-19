"""feeling 情感系统插件入口。

通过 `@register_plugin` 注册到框架，动态装配 config 和包含的组件。
"""

from __future__ import annotations

from src.app.plugin_system.base import BasePlugin, register_plugin

from .config import FeelingConfig
from .tool import SetBotFeelingTool
from .event_handler import FeelingPromptInjector, FeelingTurnCounter


@register_plugin
class FeelingPlugin(BasePlugin):
    """情感状态管理插件。

    引入混合衰减机制（时间+轮数），通过 set_bot_feeling 工具允许 Bot 主动设定自己的情绪状态，
    并通过订阅 on_prompt_build 将情感提示词追加注入到 user prompt 中以维系人设与语气连贯性。
    """

    plugin_name = "feeling"
    plugin_description = "Bot 情感与情绪维持系统。支持时间与轮数双重衰减并注入上下文。"
    plugin_version = "1.0.0"

    configs: list[type] = [FeelingConfig]

    def get_components(self) -> list[type]:
        """获取插件包含的所有组件类。"""
        config = self.config
        if isinstance(config, FeelingConfig) and not config.plugin.enabled:
            return []
        return [
            SetBotFeelingTool,
            FeelingPromptInjector,
            FeelingTurnCounter,
        ]
