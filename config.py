"""feeling 插件配置。

配置文件默认路径：config/plugins/feeling/config.toml
"""

from __future__ import annotations

from typing import ClassVar

from src.app.plugin_system.base import BaseConfig, Field, SectionBase, config_section


class FeelingConfig(BaseConfig):
    """feeling 情感系统插件配置模型。"""

    config_name: ClassVar[str] = "config"
    config_description: ClassVar[str] = "情感系统插件配置"

    @config_section("plugin")
    class PluginSection(SectionBase):
        """插件基础配置。"""

        enabled: bool = Field(
            default=True,
            description="是否启用插件",
        )
        debug_log: bool = Field(
            default=False,
            description="是否在日志中输出每轮实际注入的情感状态，便于调试",
        )
        target_prompts: list[str] = Field(
            default_factory=lambda: ["default_chatter_user_prompt"],
            description=(
                "要注入的提示词模板名称，对应 on_prompt_build 事件的 name 字段。\n"
                "用户可以填写其他 Chatter 的提示词模板名称以实现兼容。"
            ),
        )

    @config_section("decay")
    class DecaySection(SectionBase):
        """衰减机制配置。"""

        half_life_seconds: float = Field(
            default=1200.0,
            description="情感强度的时间衰减半衰期（秒），默认 1200 秒（20 分钟）",
        )
        turn_decay_factor: float = Field(
            default=0.85,
            description="情感强度的单轮对话衰减因子（0.0 到 1.0），默认 0.85",
        )
        min_intensity_threshold: float = Field(
            default=0.15,
            description="强度低于此阈值时，情感被认为回归常态/平和状态，默认 0.15",
        )

    @config_section("prompt")
    class PromptSection(SectionBase):
        """提示词模板配置。"""

        active_template: str = Field(
            default=(
                "\n\n【当前情绪状态】你目前正处于“{mood}”状态（情绪强度：{intensity}/1.0）。\n"
                "【情绪原因】{reason}。\n"
                "【行为要求】请在接下来的对话中，合理、连贯且持续地将此情绪融入到你的语气、措辞及推拉节奏中。"
            ),
            description="活跃情感状态注入模板，会追加注入到 User Prompt 末尾",
        )
        peace_template: str = Field(
            default=(
                "\n\n【当前情绪状态】你目前处于“平和”状态（无特殊剧烈情绪）。\n"
                "【行为要求】请保持你日常的人设性格与说话风格。如果对话中发生了让你产生情感波动的事件，你可以随时调用 `set_bot_feeling` 工具来调整并记录你的新情绪。"
            ),
            description="平和/常态状态注入模板，会追加注入到 User Prompt 末尾",
        )

    plugin: PluginSection = Field(default_factory=PluginSection)
    decay: DecaySection = Field(default_factory=DecaySection)
    prompt: PromptSection = Field(default_factory=PromptSection)
