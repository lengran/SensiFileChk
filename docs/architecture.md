# 保密检查工具 - 架构设计文档

## 1. 项目概述

一个轻量级、高性能的本地文件敏感词检查工具。支持多格式文件扫描、多核并行处理、CLI 操作和独立的 Web 敏感词管理界面，检查结果以 HTML 报告输出。

## 2. 技术栈

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| 语言 | Python 3.10+ | 跨平台，生态丰富 |
| 并行框架 | `concurrent.futures.ProcessPoolExecutor` | 多核并行，避免 GIL 限制 |
| PDF 解析（文本） | `pymupdf` | 比 PyPDF2 更稳定，支持文本提取 |
| PDF 解析（图片/OCR） | `pytesseract` + `Pillow` | 可选 OCR 开关 |
| Office 文档 | `python-docx` / `python-pptx` / `openpyxl` | 新版 .docx/.pptx/.xlsx |
| 旧版 Office (.doc/.xls/.ppt) | `antiword` (Linux) / `pywin32` (Windows) | 平台自动检测 |
| 压缩包解析 | `zipfile` / `tarfile` / `gzip` (标准库) + `rarfile` / `py7zr` (第三方) | 支持 zip/tar/tgz/gz/rar/7z |
| Web 管理端 | FastAPI + Jinja2 | 轻量、异步 |
| HTML 报告 | 原生 HTML + CSS + JS | 零依赖，目录折叠 |
| 配置存储 | JSON 文件 | 敏感词库 + OCR 开关配置 |

## 3. 目录结构

```
sensi-check/
├── config/
│   └── keywords.json              # 敏感词库 + OCR 开关
├── src/
│   ├── __init__.py
│   ├── cli.py                     # CLI 入口
│   ├── checker.py                 # 扫描引擎 + 并行调度
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── base.py                # 解析器抽象基类
│   │   ├── txt.py                 # 纯文本解析
│   │   ├── pdf.py                 # PDF 解析（含 OCR）
│   │   ├── office.py              # Office 文档解析
│   │   └── archive.py             # 压缩包解析（zip/tar/gz）
│   ├── report.py                  # HTML 报告生成
│   └── config.py                  # 配置读写
├── web-admin/
│   ├── __init__.py
│   ├── main.py                    # FastAPI 应用
│   └── templates/
│       └── index.html             # 敏感词管理页面
├── tests/
│   ├── __init__.py
│   ├── test_checker.py
│   ├── test_parsers.py
│   └── test_report.py
├── requirements.txt
└── README.md
```

## 4. 核心模块设计

### 4.1 配置模块 (`src/config.py`)

**职责**: 管理 `config/keywords.json` 的读写。

**数据结构**:
```json
{
  "keywords": ["国家机密", "绝密", "内部资料"],
  "ocr_enabled": false
}
```

**关键函数**:
- `load_keywords() -> dict` — 加载配置，文件不存在则返回空结构
- `save_keywords(keywords: list, ocr_enabled: bool) -> None` — 保存配置
- `add_keyword(word: str) -> None` — 添加单个关键词
- `remove_keyword(word: str) -> None` — 删除单个关键词

### 4.2 解析器模块 (`src/parsers/`)

**统一接口** — 所有解析器继承 `BaseParser`，实现 `parse(file_path: str) -> str` 返回文件纯文本。

```
BaseParser (抽象基类)
├── TxtParser
├── PdfParser
│   └── 根据 OCR 开关选择文本提取或 Tesseract OCR
└── OfficeParser
    ├── .docx → python-docx
    ├── .pptx → python-pptx
    ├── .xlsx → openpyxl
    ├── .doc  → antiword (Linux) / win32com (Windows)
    ├── .xls  → antiword (Linux) / win32com (Windows)
    └── .ppt  → antiword (Linux) / win32com (Windows)
```

**关键设计**:
- 解析器通过文件扩展名路由，不依赖魔法数字
- 解析异常（损坏文件、加密文件）统一返回空字符串，由上层记录日志
- OCR 开关从 `config/keywords.json` 读取，由 `PdfParser` 初始化时传入

### 4.2.1 压缩包解析器 (`src/parsers/archive.py`)

**职责**: 递归解压并提取压缩包内支持格式的文件。

**支持的格式**: `.zip`、`.tar`、`.tar.gz`/`.tgz`、`.gz`、`.rar`、`.7z`

**解析流程**:
```
1. 根据扩展名选择解压方式（zipfile / tarfile / gzip / rarfile / py7zr）
2. 遍历压缩包内所有条目
3. 对每个条目:
   - 如果是目录，递归进入
   - 如果是支持格式的文件，提取到临时目录后由对应解析器处理
   - 如果是嵌套压缩包，递归解压
4. 返回 (relative_path, parsed_text) 对
5. 处理完成后清理临时目录
```

**关键设计**:
- 限制解压深度（默认 10 层），防止 Zip Slip 攻击
- 限制压缩包总大小（默认 500MB），防止资源耗尽
- 压缩包内文件路径用 `/` 分隔显示在报告中
- 解压失败的文件在报告中单独列出

### 4.3 扫描引擎 (`src/checker.py`)

**职责**: 文件发现 + 多进程并行扫描 + 结果汇总。

**扫描流程**:
```
1. 递归遍历指定目录，仅收集支持格式的文件列表（.txt/.pdf/.doc/.docx/.ppt/.pptx/.xls/.xlsx/.zip/.tar/.tgz/.gz）
2. 对压缩包文件，先递归展开内部文件，合并到文件列表
3. 按文件路径分组，提交给 ProcessPoolExecutor
4. 每个 worker 进程:
   a. 根据扩展名加载对应解析器
   b. 解析文件获取文本
   c. 在文本中匹配所有关键词
   d. 对每个匹配项，提取关键词前后 N 个字符的上下文
   e. 返回 MatchResult(file_path, matches, error)
5. 主进程汇总所有结果:
   - 有匹配: 按目录构建树形结构
   - 无匹配: 不显示
   - 解析失败（已识别格式但无法读取）: 单独归类到"检查失败"区域
   - 不支持的格式: 直接跳过，不记录
```

**关键函数**:
- `discover_files(dir_path: str) -> list[str]` — 发现目标文件
- `scan_directory(dir_path: str, keywords: list, ocr_enabled: bool, num_workers: int) -> dict` — 执行扫描
- `_match_keywords(text: str, keywords: list) -> list[Match]` — 关键词匹配（支持子串匹配）
- `_extract_context(text: str, start: int, end: int, context_chars: int = 50) -> str` — 提取上下文

**匹配策略**:
- 逐关键词在文本中查找（`str.find()` 循环），简单高效
- 匹配不区分大小写（对英文文本）
- 同一位置多个关键词命中分别记录

### 4.4 报告生成 (`src/report.py`)

**职责**: 将扫描结果生成为 HTML 文件。

**HTML 结构**:
```
├── 头部: 检查时间、检查目录、关键词数量、结果统计
├── 按目录折叠树
│   ├── 目录1 [折叠/展开]
│   │   ├── 文件1.docx
│   │   │   ├── [敏感词A] 上下文...（敏感词红色高亮）
│   │   │   └── [敏感词B] 上下文...
│   │   └── 文件2.pdf
│   └── 目录2 [折叠/展开]
│       └── 文件3.txt
├── 检查失败 [折叠/展开]
│   ├── 文件4破损.pdf — "解析失败: 文件已损坏"
│   └── 子目录/文件5.doc — "权限不足"
└── 底部: 总匹配数、处理文件数、跳过文件数、耗时
```

**关键设计**:
- 原生 JavaScript 实现目录树折叠/展开，无外部依赖
- 敏感词在上下文中用 `<mark>` 标签高亮（红色背景）
- 每个匹配项显示文件名、行号、上下文
- 支持按文件数/匹配数排序

**关键函数**:
- `generate_report(results: dict, failures: list, output_path: str, scan_dir: str) -> None`
- `_build_tree(results: dict) -> dict` — 将扁平结果构建树形结构
- `_render_tree(node: dict, level: int) -> str` — 递归渲染 HTML
- `_render_failures(failures: list) -> str` — 渲染检查失败区域

### 4.5 CLI 入口 (`src/cli.py`)

**职责**: 提供命令行接口。

**命令**:
```bash
# 执行检查
sensi-check check /path/to/scan -o report.html [-w 4] [--context 50]

# 执行检查（同时检查压缩包，默认开启）
sensi-check check /path/to/scan -o report.html [--check-archives]

# 添加关键词
sensi-check add "敏感词1" "敏感词2"

# 删除关键词
sensi-check remove "敏感词1"

# 列出所有关键词
sensi-check list

# 查看 OCR 开关状态
sensi-check config show-ocr

# 切换 OCR 开关
sensi-check config set-ocr on|off
```

**关键函数**:
- `main()` — argparse 入口，分发子命令
- `_cmd_check(args)` — 调用 checker.scan_directory
- `_cmd_add(args)` / `_cmd_remove(args)` / `_cmd_list(args)` — 关键词管理
- `_cmd_config(args)` — OCR 配置管理

### 4.6 Web 管理端 (`web-admin/`)

**职责**: 提供浏览器端的敏感词管理界面。

**功能**:
- 关键词列表展示（表格，支持搜索过滤）
- 添加关键词（表单输入）
- 删除关键词（每行一个删除按钮）
- OCR 开关切换（开关控件）
- 生成 CLI 命令（显示当前配置对应的 `sensi-check` 命令）

**技术实现**:
- FastAPI 提供 REST API
- Jinja2 渲染前端页面
- 前端用原生 HTML/CSS/JS，无前端框架
- API 直接读写 `config/keywords.json`，与 CLI 共享数据

**API 端点**:
```
GET  /              — 管理页面
GET  /api/keywords  — 获取关键词列表
POST /api/keywords  — 添加关键词
DELETE /api/keywords/<word> — 删除关键词
PUT  /api/config/ocr — 设置 OCR 开关
```

## 5. 数据流

```
用户执行 check 命令
       │
       ▼
  cli.py: 解析参数，加载配置
       │
       ▼
  checker.py: discover_files() 收集文件
       │
       ▼
  ProcessPoolExecutor: 分发任务到各 worker
       │
       ├── worker 1 → parsers/TxtParser → 匹配关键词
       ├── worker 2 → parsers/PdfParser → OCR? → 匹配关键词
       ├── worker 3 → parsers/OfficeParser → 匹配关键词
       │    ...
       │
       ▼
  checker.py: 汇总结果
       │
       ▼
  report.py: 生成 HTML 报告
       │
       ▼
  输出到指定文件
```

## 6. 并行设计

- 使用 `ProcessPoolExecutor`，worker 数量默认等于 CPU 核心数，可通过 `-w` 参数调整
- 每个文件独立处理，无共享状态，天然安全
- 文件列表在主进程构建，worker 只负责解析和匹配
- 大目录自动分片，避免单个任务过重

## 7. 错误处理

| 场景 | 处理方式 |
|------|---------|
| 文件被占用/权限不足 | 跳过，在报告中记录 "跳过" 文件列表 |
| 文件损坏/格式错误 | 跳过，记录日志 |
| 加密 PDF/Office 文件 | 跳过，标注 "加密文件" |
| OCR 失败 | 降级为文本模式，记录 "OCR 不可用" |
| 关键词为空 | 提示用户，退出 |
| 输出目录不存在 | 自动创建 |

## 8. 依赖清单

```
# 核心依赖
pymupdf>=1.23.0          # PDF 文本提取
pytesseract>=0.3.10      # OCR（可选）
Pillow>=10.0.0           # OCR 图像处理
python-docx>=0.8.11      # .docx 解析
python-pptx>=0.6.23      # .pptx 解析
openpyxl>=3.1.0          # .xlsx 解析
antiword>=0.37           # .doc/.xls/.ppt 旧格式（Linux）
rarfile>=4.0             # .rar 解压
py7zr>=0.20.0            # .7z 解压
fastapi>=0.104.0         # Web 管理端
jinja2>=3.1.2            # Web 模板
uvicorn>=0.24.0          # Web 服务器
```

## 9. 跨平台说明

| 功能 | Linux | macOS | Windows |
|------|-------|-------|---------|
| TXT/PDF/新版 Office | 支持 | 支持 | 支持 |
| 旧版 Office (.doc/.xls/.ppt) | `antiword` | `catdoc` | `pywin32` |
| RAR 解压 | `rarfile` + `unrar` | `rarfile` + `unrar` | `rarfile` + `unrar.exe` |
| 7Z 解压 | `py7zr`（纯 Python） | `py7zr`（纯 Python） | `py7zr`（纯 Python） |
| OCR | `pytesseract` + `tesseract-ocr` | `pytesseract` + `tesseract-ocr` | `pytesseract` + `tesseract-ocr` |

**各平台安装命令**:
- **Linux**: `apt install antiword unrar tesseract-ocr` 或 `yum install antiword unrar tesseract`
- **macOS**: `brew install catdoc unrar tesseract`
- **Windows**: 手动安装 `unrar.exe` 和 `tesseract-ocr`，`pywin32` 通过 `pip install pywin32` 安装

**纯 Python 优先**: `py7zr` 是纯 Python 实现，无需系统安装；`pywin32` 仅 Windows 可用；macOS 下使用 `catdoc` 替代 `antiword`。

## 10. 安全考虑

- 所有文件操作仅限本地，不涉及网络传输
- OCR 处理在本地完成，图片不上传
- 敏感词库存储在本地 JSON 文件，不加密（用户可自行加密存储）
- Web 管理端仅绑定 `127.0.0.1`，不暴露到外部网络
