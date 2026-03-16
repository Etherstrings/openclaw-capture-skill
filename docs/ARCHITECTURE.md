# OpenClaw Capture Skill Architecture

这份文档给 GitHub 阅读和视频讲解使用。目标不是解释每一行代码，而是把这套 wrapper 的边界、路由逻辑和平台分流讲清楚。

## 1. 系统边界

`openclaw-capture-skill` 不是新的内容处理引擎，而是现有 `openclaw_capture_workflow` 的 skill 外包裹层。

职责分工：

- `openclaw_capture_workflow`
  - 真正做提取、总结、写笔记
  - 已经有稳定的本地链路
- `openclaw-capture-skill`
  - 接住 OpenClaw / ClawHub 入口
  - 路由 backend mode
  - 决定 STT 策略
  - 决定模型接入 profile
  - 决定 Telegram / Feishu fanout

## 2. 端到端总流程

```mermaid
flowchart LR
    A["用户消息<br/>直接对话 / 群里 @bot"] --> B["OpenClaw / ClawHub"]
    B --> C["openclaw-capture wrapper"]
    C --> D{"backend mode"}
    D -->|library| E["import openclaw_capture_workflow"]
    D -->|http| F["POST /ingest + GET /jobs/<id>"]
    E --> G["证据提取"]
    F --> G
    G --> H["summary / note / metadata"]
    H --> I["统一 envelope"]
    I --> J["Telegram"]
    I --> K["Feishu"]
    H --> L["Obsidian / 本地知识库"]
```

## 3. Backend Mode

### `library`

推荐模式。

特点：

- 不依赖单独启动 legacy HTTP 服务
- 直接复用旧仓库 Python package
- wrapper 自己接管输出扇出

适合：

- 本机部署
- 想快速验证
- 想更容易扩展 Feishu 或其他出口

### `http`

兼容模式。

特点：

- 继续用旧的 `/ingest`
- wrapper 只负责调用和补充 fanout
- 更接近历史系统

适合：

- 旧服务已经在跑
- 你不想调整现有服务进程

## 4. 视频转录平台分流

这部分是最适合录视频讲的重点。

```mermaid
flowchart TD
    A["收到视频 URL"] --> B{"当前系统是不是 macOS?"}
    B -->|是| C["mac_local_first"]
    C --> D["Apple SpeechTranscriber<br/>本地语音转录"]
    D --> E{"本地转录成功?"}
    E -->|是| J["交给 legacy workflow 做总结"]
    E -->|否| F["回退远程 STT"]
    B -->|否| G{"有没有配置本地 CLI?"}
    G -->|是| H["执行 OPENCLAW_CAPTURE_LOCAL_STT_COMMAND"]
    H --> I{"本地 CLI 成功?"}
    I -->|是| J
    I -->|否| F
    G -->|否| F
```

### 你可以这样讲

- 如果是 Mac 用户，这里优先走苹果本地转录，不先消耗外部接口。
- 如果不是 Mac，就看有没有配本地 CLI。
- 配了的话，wrapper 会先执行命令行，负责下载和本地转录。
- 如果本地命令没跑通，再回退到远程 STT。

## 5. 模型接入路由

```mermaid
flowchart LR
    A["提取后的证据"] --> B{"model profile"}
    B -->|openai_direct| C["用户自己的 API Key / Base URL"]
    B -->|aihubmix_gateway| D["AIHubMix / OpenAI-compatible 网关"]
    C --> E["summary generation"]
    D --> E
    E --> F["统一结果 envelope"]
```

### `openai_direct`

- 适合用户自己直接提供模型 Key
- 可以直连 OpenAI-compatible 接口

### `aihubmix_gateway`

- 适合统一走 AIHubMix 一类网关
- 仍按 OpenAI-compatible 方式请求

## 6. 输出 fanout

```mermaid
flowchart LR
    A["统一结果 envelope"] --> B{"输出模块"}
    B -->|telegram| C["Telegram 模板"]
    B -->|feishu| D["Feishu webhook 文本消息"]
    B -->|telegram + feishu| E["双出口 fanout"]
```

这里的关键点不是“两个出口各写一套总结”，而是：

- 先产出一份统一 summary
- Telegram 复用 legacy 的文本组织方式
- Feishu 直接消费同一份 envelope

这样做的好处是：

- 输出一致
- fanout 逻辑简单
- 新增出口时更容易扩展

## 7. 代码映射

如果别人看完图还想追代码，核心入口可以看这些文件：

- `openclaw-capture/scripts/runtime/openclaw_capture_skill/dispatcher.py`
- `openclaw-capture/scripts/runtime/openclaw_capture_skill/video_audio_bridge.py`
- `openclaw-capture/scripts/runtime/openclaw_capture_skill/profiles.py`
- `openclaw-capture/scripts/runtime/openclaw_capture_skill/notifiers.py`
- `openclaw-capture/scripts/runtime/openclaw_capture_skill/config.py`

## 8. 视频讲解建议顺序

建议你按这个顺序讲：

1. 先讲这个项目不是重写旧系统，而是 wrapper。
2. 再讲入口：直接对话 / 群里 @bot。
3. 再讲 backend mode：`library` 和 `http`。
4. 再讲视频平台分流：Mac 本地优先，非 Mac 命令行优先，最后回退云端。
5. 再讲模型 profile：直连 Key 和网关模式。
6. 最后讲 fanout：Telegram / Feishu / 双出口。

## 9. 一段适合口播的话

> 这个 skill 的核心不是替换掉旧工作流，而是在旧工作流外面增加一层路由器。消息进来以后，先决定是直接 import 旧后端，还是调用旧的 HTTP 服务；如果是视频，再看当前是不是 Mac，Mac 优先用苹果本地转录，非 Mac 优先执行本地命令行下载和转录，不行再回退到云端；最后把同一份 summary 同时发到 Telegram 或 Feishu。
