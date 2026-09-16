# Just Translate Windows 智能翻译、润色与词典工作台

<div align="center">

![Just Translate Logo](resources/icon.png)

**专为 Windows 高频语言处理与深度文本打磨打造的现代化桌面 AI 生产力工具**

[![Platform](https://img.shields.io/badge/Platform-Windows-blue.svg)](#)
[![Python](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](#)
[![GUI](https://img.shields.io/badge/GUI-PySide6%20(Qt%206)-orange.svg)](#)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

</div>

---

## 📖 产品简介

**Just Translate Windows** 是一款面向 Windows 10/11 的桌面 AI 工作台，适合学者、工程师、跨语言写作者及重度多语种用户。它可连接本地开源模型服务（如 `Hy-MT2`、`Ollama`、`llama.cpp server`）和兼容 OpenAI API 的服务，提供翻译、润色与结构化卡片词典功能。

软件摒弃了传统翻译软件臃肿复杂、广告频扰的弊端，专注于高响应度、视觉纯粹感以及极致的键盘操作流。

---

## ✨ 核心功能与特性全景

### 1. 三大独立工作空间 (Three Core Workspaces)

Just Translate 采用双栈独立工作区（`Dual QStackedWidget`）设计，各个模式拥有完全隔离的输入输出状态、滚动进度与历史上下文：

- 🌐 **精准翻译 (Translate)**
  - **语境深度感知**：不仅是简单的逐词替换，更能完整理解长文本段落、逻辑连接词与隐喻，输出自然、通顺且忠实于原文的高质量译文。
  - **智能语种检测**：源语言支持 `Auto (自动检测)`，智能识别中、英、日等语言并根据使用习惯自动推荐最佳目标语。
  - **语言一键互换**：快捷键 `Alt+X` 或点击顶栏 `⇄` 按钮瞬时互换源语言与目标语言。
- ✍️ **母语级润色 (Polish)**
  - **严格同语种增强**：输入何种语言即以何种母语标准进行润色，绝不发生误翻译。
  - **智能正文提纯**：润色结果包含高质量正文与优化要点说明；点击“📋 复制润色正文”即可**自动剥离解释与说明**，仅提取纯净正文至剪贴板。
  - **沉浸式防闪烁排版**：润色流式打字结束后直接保持纯文本高保真展示，消除因 HTML 重新解析带来的版面跳变与光标失焦。
- 📖 **现代结构化卡片词典 (Dictionary)**
  - 告别枯燥的纯文本堆叠，自动将大模型输出解析为规范易读的视觉卡片：
    - **词头与假名/音标**：标准国际音标（IPA）或日语假名注音，配有专属复制与高保真语音朗读。
    - **核心释义（严格双语对照）**：按照顶栏选择的语言严格对照输出（如中文 ➔ 日文严格输出日文母语释义与中文对照释义，绝不混入无关语言）。
    - **典型双语例句**：每条例句均配备独立发音按钮（🔊）与一键复制按钮（📋），并伴随即时视觉交互特效。
    - **短语搭配与同/反义词流式卡片**：基于自适应流式网格（`FlowLayout`）自动折行呈现，随窗口缩放灵活重排。
    - **渐进式动态填充**：后台流式传输时，前端卡片容器固定展示并动态平滑填充，告别原始 Markdown 字符晃眼。

---

### 2. 双引擎语音朗读 (Neural & SAPI TTS Engine)

- 🎙️ **微软 Edge Neural 神经语音**
  - 在线接入微软高质量 Edge Neural 语音合成技术，音色自然、抑扬顿挫，媲美真人发音。
  - 覆盖丰富的主流发音人：
    - 中文：`zh-CN-XiaoxiaoNeural`（晓晓）
    - 英语：`en-US-AriaNeural` / `en-US-ChristopherNeural`
    - 日语：`ja-JP-NanamiNeural`（七海）
    - 韩语：`ko-KR-SunHiNeural`
    - 法语、德语等更多语种自动智能映射。
- 🛡️ **本地 SAPI5 离线容灾回退**
  - 当处于离线环境或网络受阻时，系统可使用 Windows 本地 SAPI5 语音引擎回退；该功能依赖 Windows 语音包。
  - 内置语音引擎健康自检与安装指引对话框。
- 🎯 **语言严格定向路由**
  - 朗读引擎严格遵循控制栏当前设定的目标语种（如中译日模式下，即使词头含有日文汉字，亦严格调用日语引擎与注音发音，彻底杜绝汉字优先误读中文问题）。

---

### 3. 视觉识图与流水线联动 (GLM-OCR Vision Engine)

- 📸 **图片文字一键提取**
  - 支持直接 `Ctrl+V` 从系统剪贴板粘贴截图，或点击输入区图片图标加载本地图片（PNG、JPG、WEBP 等）。
  - 内置内存级无损压缩与尺寸自适应计算，保障快速上传。
- 🔄 **两阶段流水线自动联动**
  - **阶段一 (OCR)**：利用 OpenAI 视觉协议 / GLM-OCR 模型秒级解析图中文字；
  - **阶段二 (联动)**：自动将提取出的纯文本回填至输入框，并无缝触发翻译/润色/词典处理流，无需手动二次复制。

---

### 4. 极致交互与防塌陷布局 (BalancedSplitter)

- 🛡️ **永久防折叠与防挤压保护**
  - 解决原生 Qt `QSplitter` 拖动至极端边缘导致某一侧面板永久折叠塌陷的痛点。
  - 左右面板强制设置 **280px 最小安全宽度**，无论如何拖动均无法压塌面板。
- ⚖️ **双击中线 1:1 对等复位**
  - 鼠标双击中央分隔条手柄，左右分栏瞬间平滑复位至 50%:50% 等宽布局。
  - 分隔条具有呼吸感悬浮动效与清晰的拖拽指示光标。

---

### 5. 逐句精准对照与独立重译 (Sentence Aligner)

- 🔍 **多语种断句与悬浮高亮**
  - 针对 CJK（中文、日文）与西方拉美语系的标点、换行与缩写规则进行分词断句。
  - 鼠标悬停在原文任一句子时，右侧对应译文句子自动同步高亮，实现长篇文档的高效对照校对。
- ✏️ **单句独立重译**
  - 右键单击任意单个句子，呼出独立重译菜单，可针对该句单独微调重译，并就地更新替换至全局文本中，大幅降低长文重修成本。

---

### 6. 流式抗闪烁沉浸阅读 (Anti-Flicker Streaming)

- 🌊 **智能文本特征探测**
  - 区分纯文本排版与富富文本 Markdown 表格/数学公式：
    - 普通文本与润色结果：流式打字结束后直接保持纯文本排版，**严禁使用强制重绘（`setHtml`）**，彻底消除视觉抖动与选择焦点丢失。
    - 富文本（含代码块、复杂 Markdown 语法）：流式完成后平滑过渡到富文本渲染器。

---

### 7. 现代视觉与主题体系 (Modern UI & Themes)

- 🎨 **双主题无缝切换**：
  - **暗黑极客 (Dark Theme)**：深空灰底色配以微光青色高亮，夜间阅读护眼专注。
  - **明亮纯净 (Light Theme)**：纸实质感、柔和白灰搭配高对比度文字，日间办公清晰锐利。
  - **跟随系统 (System Auto)**：自动侦测 Windows 浅色/深色模式并热重载切换。
- 🖼️ **32位透明通道图标**：
  - 严格遵循现代设计规范，全应用图标均完成黑色底板抠除，边缘平滑抗锯齿，完美融入各类系统壁纸与任务栏。

---

### 8. 历史记忆与本地持久化 (History Management)

- 💾 **本地 SQLite 原生数据库 (`data/history.db`)**
  - 翻译、润色与查词历史自动写入本地数据库，数据完全归属于用户本地磁盘，绝不上云。
  - 快捷键 `Ctrl+H` 随时呼出记忆管理器，支持按模式过滤、关键词全文模糊搜索、元数据查看以及一键导入回填。
  - 支持自定义记忆容量上限（50 / 100 / 500 / 无限制），自动遵循 LRU 原则修剪历史。

### 9. 智能状态感知与操作流清晰化 (Context-Aware Action & Stale Warning)

- 🎯 **按模式动态明确主按钮文案**
  - 输入区主操作按钮根据当前选中的工作区动态自适应更新文案：
    - 翻译模式：显示 `🚀 翻译`
    - 润色模式：显示 `✨ 润色`
    - 词典模式：显示 `🔎 查询`
  - 载入图片进入 OCR 模式时，按钮自动切换为 `🔍 识别并处理 (Ctrl+Enter)`；点击清除图片或退出图片状态后，即时无缝恢复当前模式的原生主按钮文案。
  - 切换模式时即时响应刷新，保持 `Ctrl+Enter` 快捷键全生命周期一致性。
- ⚠️ **原文修改检测与结果过期琥珀色预警**
  - 在用户发起提交时精确记录当前输入文本的请求快照版本。
  - 若在模型生成中或生成完毕后用户编辑、修改了输入区原文，输出面板（译文区及词典卡片区）顶部控制栏即刻呈现醒目的琥珀色（`#F59E0B`）常驻标签：
    `⚠ 原文已修改，结果可能不准确`
  - 若用户撤销修改还原为请求快照，或重新点击执行/按 `Ctrl+Enter` 触发新请求，该标签即刻平滑隐去。
  - 严格隔离程序性回填（如双向互换 `Alt+X`、历史记录导入、回译、OCR 提取回填等），绝不发生虚假预警。

---

### 10. 本地环境智能代理绕过与任务并发治理 (Loopback Bypass & Concurrency Control)

- 🌐 **本地 Loopback 环境显式绕过代理**
  - 针对 `127.0.0.1`、`localhost`、`::1` 等本地大模型服务（如 Ollama、llama.cpp、vLLM、Hy-MT2），自动显式绕过系统 `HTTP_PROXY` / `HTTPS_PROXY`，直连本地回环地址，彻底根除 VPN/代理开启时本地端口被代理劫持导致的 502/连接中断/超时故障。
  - 普通远程商业 API（DeepSeek、OpenAI、智谱 GLM 等）继续平滑尊重代理路由。
  - 统一覆盖 `/models` 自动拉取、连通性探测、流式生成和 OCR 识图请求。
- ⚡ **毫秒级即时停止与旧任务防串写机制**
  - **模式级严格单调递增 `task_id`**：每个工作区维护独立的全局流水号，所有后台工作线程的回调携带唯一任务 ID，强行拦截并丢弃已被替换或中止的旧任务残留信号，杜绝脏数据串写。
  - **连续提交无缝替换**：高频点击执行或连按快捷键时，自动非阻塞中止前序任务并立即启动新任务，彻底移除主线程 `wait(500)` 同步阻塞卡死。
  - **跨线程 `StreamController` 强断 Socket**：在用户主动按 `Esc` 或点击“停止”按钮时，瞬间直接断开活跃网络连接与响应流，解除底层 Socket 阻塞，毫秒级实现界面“已停止”响应，不报错且不产生无效历史记录。

---

### 11. 独立「关于」与应用元数据 (About & Metadata)

- ℹ️ **设置面板全景关于选项卡**
  - 在【⚙ 设置】对话框中新增独立 **【关于】** 选项卡；
  - 核心展示软件专属高清矢量品牌图标、应用主标题与产品定位；
  - 明确标注软件作者为 **Kutori**，当前版本号为 **1.0.0**；
  - 详细汇总运行环境栈（Python 3.10+ / PySide6 / Edge Neural TTS / GLM-OCR）与开源协议（MIT License）；
  - 完整适配暗黑与明亮双主题的高品质卡片质感排版。

---

## ⌨️ 常用快捷键速查

| 快捷键 | 功能动作 | 适用范围 |
| :--- | :--- | :--- |
| `Ctrl + Enter` | **立即触发当前模式生成**（翻译 / 润色 / 查词） | 全局输入面板 |
| `Esc` | **立即停止当前流式生成** | 流式生成中 |
| `Alt + X` | **互换源语言与目标语言 (⇄)** | 全局控制栏 |
| `Ctrl + H` | **打开翻译历史记录对话框** | 全局主窗口 |
| `Ctrl + V` | **粘贴剪贴板文本或直接粘贴截图图片** | 输入面板 |
| `Alt + C` | **快速复制右侧输出正文** | 输出面板 |
| **双击中线** | **左右分栏 1:1 对称复位** | 中央分隔条 |

---

## 🛠️ 模型服务配置指南

点击右上角 **【⚙ 设置】** 即可打开配置面板，Just Translate 支持各类主流推理框架：

### 1. 本地 llama.cpp server（推荐）
- **Base URL**: `http://127.0.0.1:8080/v1`
- **API Key**: `sk-no-key`（本地服务通常不校验，填任意非空字符串即可）
- **模型名称**: `default`（或点击“获取模型列表”自动加载）

### 2. 本地 Ollama
- **Base URL**: `http://127.0.0.1:11434/v1`
- **API Key**: `ollama`
- **模型名称**: `qwen2.5:7b`、`llama3.3:70b`、`deepseek-r1:8b` 等

### 3. 本地 Hy-MT2 专用翻译模型
- **Base URL**: `http://127.0.0.1:8001/v1`
- **API Key**: `sk-no-key`
- **模型名称**: `Hy-MT2-7B`

### 4. 外部商业 API（如 DeepSeek / OpenAI）
- **Base URL**: `https://api.deepseek.com/v1`
- **API Key**: `sk-xxxxxxxxxxxxxxxxxxxxxxxx`
- **模型名称**: `deepseek-chat` / `deepseek-reasoner`

> [!TIP]
> 填写完成后可点击 **【🔍 测试连接】**，系统将在 30 秒超时阈值内发起真实握手，并反馈实时 HTTP 状态码与延迟。

## ⚙️ 配置文件说明 (Configuration)
项目启动时若未检测到 `settings.json`，将自动生成默认初始配置。你也可以参考根目录提供的示例配置文件：

```powershell
# 复制示例配置
Copy-Item settings.example.json settings.json
```

在 `settings.json` 中配置你的本地模型端点或商业 API Key（如 DeepSeek、OpenAI 等）。`settings.json` 已被 `.gitignore` 包含，绝不会被意外提交到版本控制中。

---

## 💻 开发者与构建指引

### 1. Windows 环境准备
支持 Windows 10/11，推荐使用 Python 3.10+：
```powershell
# 1. 克隆源码并进入项目根目录
git clone https://github.com/<your-username>/JustTranslate.git
cd JustTranslate

# 2. 创建虚拟环境并安装运行依赖
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. 启动开发态程序
```powershell
.\.venv\Scripts\python.exe main.py
```

### 3. 运行完整自动化测试套件
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

### 4. 打包为单目录独立可执行程序
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m PyInstaller "Just Translate.spec" --noconfirm --clean
```
编译产物将生成在 `dist/Just Translate/` 目录下，可直接运行 `Just Translate.exe`。

---

## 📁 项目目录结构 (Project Structure)

```text
JustTranslate/
├── main.py                     # 应用主入口，注册高 DPI、系统托盘与主题引擎
├── Just Translate.spec         # PyInstaller 打包构建定义规范
├── requirements.txt            # 项目依赖声明
├── requirements-dev.txt        # 打包所需开发依赖
├── settings.example.json       # 样例配置文件 (含占位符)
├── LICENSE                     # MIT 开源许可证
├── runtime_hooks/              # PyInstaller 运行时 DLL 搜索路径修正
├── config/                     # 配置与全局定义（语言注册表、系统提示词、设置管理）
├── core/                       # 核心业务引擎（LLM流式客户端、TTS管理器、OCR流水线、词典解析器、分词对齐）
├── ui/                         # 现代化 PySide6 界面组件库与样式引擎
│   ├── components/             # 控制栏、防塌陷分栏、卡片词典、输入/输出面板、设置对话框等
│   └── styles/                 # 暗黑与明亮主题 QSS 样式表
├── resources/                  # 32位透明通道高清图标等静态资源
└── tests/                      # 92 项自动化单元测试用例
```

---

## 📌 开发状态 (Development Status)

本项目处于积极维护与迭代状态 (**Actively Developed**)。

---

## 📄 开源许可证 (License)

本项目基于 [MIT License](LICENSE) 开源。
