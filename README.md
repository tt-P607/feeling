# Feeling - Bot 情感与情绪维持系统插件

为 Neo-MoFox 框架中的机器人提供一个长期维护且具备延续性的情感与情绪控制层。通过**时间+对话轮数双重混合衰减算法**，实现更符合人类特征的情感流转、延续与淡化。

## 功能特性

1. **会话隔离的情感存储**：不同会话（根据 `stream_id` 隔离）拥有独立的情绪状态，互不干扰。
2. **混合衰减算法**：
   - **时间指数衰减**：基于配置的半衰期（如 20 分钟），情感强度随时间流逝呈指数下降。
   - **轮数幂次衰减**：每一轮对话完成时，情感强度会按比例（如 $0.85$ 衰减因子）自然耗损。
3. **LLM 主动调节能力**：向 LLM 暴露 `set_bot_feeling` 工具，允许其根据当前的交互冲击（如受到夸奖、捉弄或吵架）主动给自己打上情绪标签，并记录具体原因。
4. **长效上下文注入**：
   - 当情感强度较高时，自动在 User Prompt 末尾追加注入活跃状态的情感提示，要求 LLM 在接下来几轮中合理延续并融入语气。
   - 当情感衰减至平和线（默认 `0.15`）以下时，注入平和常态提示，提醒 LLM 保持日常人设风格，并在情绪波动时主动更新。
5. **高度兼容**：默认支持 `default_chatter_user_prompt`，并支持通过配置添加任意其它 Chatter 插件的目标注入提示词模板名称。

---

## 插件结构

```text
plugins/feeling/
├── manifest.json       # 插件元数据声明
├── __init__.py         # 插件包入口定义
├── plugin.py           # 插件注册与装配
├── config.py           # 插件 TOML 配置模型
├── store.py            # 按会话隔离的情感持久化及衰减逻辑
├── tool.py             # 供 LLM 调用调节情绪的 set_bot_feeling 工具
└── event_handler.py    # 监听 prompt 构建和消息发送事件的处理器
```

---

## 配置说明

配置文件路径：`config/plugins/feeling/config.toml`

```toml
[plugin]
enabled = true          # 是否启用插件
debug_log = false       # 是否在日志中输出每轮实际注入的情感状态
target_prompts = ["default_chatter_user_prompt"] # 目标注入提示词列表

[decay]
half_life_seconds = 1200.0        # 情感时间衰减半衰期（秒），默认 20 分钟
turn_decay_factor = 0.85          # 情感对话轮数衰减因子（0.0 到 1.0）
min_intensity_threshold = 0.15    # 低于此强度时自动回归“平和”常态

[prompt]
# 活跃状态提示模板（支持 {mood}, {intensity}, {reason} 格式化）
active_template = "\n\n【当前情绪状态】你目前正处于“{mood}”状态（情绪强度：{intensity}/1.0）。\n【情绪原因】{reason}。\n【行为要求】请在接下来的对话中，合理、连贯且持续地将此情绪融入到你的语气、措辞及推拉节奏中。"

# 平和常态提示模板
peace_template = "\n\n【当前情绪状态】你目前处于“平和”状态（无特殊剧烈情绪）。\n【行为要求】请保持你日常的人设性格与说话风格。如果对话中发生了让你产生情感波动的事件，你可以随时调用 `set_bot_feeling` 工具来调整并记录你的新情绪。"
```

---

## 工具接口

### `set_bot_feeling`
允许 Bot 自身设置和更新主导情感：
- `mood` (Annotated[str]): 情感/情绪的关键词名称（例如：`委屈`、`羞涩`、`傲娇`、`生气`），最长 10 字。
- `intensity` (Annotated[float]): 情感强度，范围为 `0.0` 至 `1.0`。
- `reason` (Annotated[str]): 产生该情感的直观原因，最长 50 字。
