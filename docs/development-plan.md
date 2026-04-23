# 开发计划

## 概览

**开发环境要求**: 使用虚拟环境（venv 或 conda），详见 `docs/architecture.md` 8.1 节。

```bash
# venv 方式
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# conda 方式
conda create -n sensi-check python=3.10
conda activate sensi-check
pip install -e .
```

| 阶段 | 内容 | 预计工作量 | 前置依赖 |
|------|------|-----------|---------|
| Phase 1 | 项目基础 | 2-3 天 | 无 |
| Phase 2 | 多格式解析 + 并行 | 3-4 天 | Phase 1 |
| Phase 3 | CLI 完整化 + Web 管理端 | 2-3 天 | Phase 1 |
| Phase 4 | 集成与文档 | 1-2 天 | Phase 2, Phase 3 |

Phase 2 和 Phase 3 可部分并行，但推荐按顺序以保持一致性。

---

## Phase 1: 项目基础

### 目标
搭建项目骨架，跑通最简流程：txt 文件扫描 → 关键词匹配 → HTML 报告。

### 任务清单

- [ ] 1.1 创建项目目录结构
  - `config/`, `src/`, `src/parsers/`, `web-admin/`, `tests/`
  - 各目录下的 `__init__.py`
  - `requirements.txt`

- [ ] 1.2 实现配置模块 `src/config.py`
  - `load_keywords() -> dict` — 加载 `config/keywords.json`，文件不存在则返回空结构
  - `save_keywords(keywords: list, ocr_enabled: bool) -> None` — 保存配置
  - `add_keyword(word: str) -> None` — 添加单个关键词
  - `remove_keyword(word: str) -> None` — 删除单个关键词
  - 文件锁机制（读写时加锁，防止 CLI 和 Web 并发冲突）

- [ ] 1.3 实现解析器抽象基类 `src/parsers/base.py`
  - `BaseParser` 类，定义 `parse(file_path: str) -> str` 接口
  - 定义 `ParserError` 异常类

- [ ] 1.4 实现 txt 解析器 `src/parsers/txt.py`
  - `TxtParser` 类，读取文本内容
  - 支持 UTF-8 / GBK / GB2312 自动检测编码
  - 编码检测失败时抛出 `ParserError`

- [ ] 1.5 实现扫描引擎 `src/checker.py`
  - `discover_files(dir_path: str) -> list[str]` — 递归遍历目录，过滤支持格式
  - `_match_keywords(text: str, keywords: list) -> list[Match]` — 逐关键词查找
  - `_extract_context(text: str, start: int, end: int, context_chars: int = 50) -> str` — 提取上下文
  - `scan_single_file(file_path: str, keywords: list) -> MatchResult` — 单文件扫描
  - `scan_directory(dir_path: str, keywords: list) -> dict` — 单进程扫描入口
  - 支持 `--context N` 参数控制上下文字符数

- [ ] 1.6 实现 HTML 报告生成 `src/report.py`
  - `generate_report(results: dict, output_path: str, scan_dir: str) -> None`
  - `_build_tree(results: dict) -> dict` — 扁平结果构建树形结构
  - `_render_tree(node: dict, level: int) -> str` — 递归渲染 HTML
  - 原生 JS 实现目录折叠/展开
  - `<mark>` 标签高亮敏感词（红色背景）
  - 头部显示：检查时间、目录、关键词数量、匹配总数
  - 底部显示：处理文件数、耗时

- [ ] 1.7 实现 CLI 骨架 `src/cli.py`
  - `main()` — argparse 入口
  - `check` 子命令：`sensi-check check /path -o report.html [--context 50]`
  - 加载配置 → 调用 checker → 生成报告 → 输出统计信息

- [ ] 1.8 编写 Phase 1 测试
  - `tests/test_config.py` — 配置读写、添加/删除关键词、文件锁
  - `tests/test_parsers.py` — txt 解析器（正常文本、GBK 编码、编码错误）
  - `tests/test_report.py` — 报告生成正确性、目录树结构
  - `tests/test_checker.py` — 关键词匹配、上下文提取

### 验收标准

1. 能扫描包含敏感词的 txt 文件，生成 HTML 报告
2. 报告中敏感词正确高亮，上下文完整
3. 能按目录折叠/展开结果
4. 配置模块读写正确，CLI 能 add/remove/list 关键词
5. 所有 Phase 1 测试通过

---

## Phase 2: 多格式解析 + 并行

### 目标
支持所有目标文件格式，启用多核并行扫描。

### 任务清单

- [ ] 2.1 实现 PDF 解析器 `src/parsers/pdf.py`
  - `PdfParser` 类
  - 文本 PDF：使用 `pymupdf` 提取文本
  - 图片 PDF：根据 `ocr_enabled` 开关
    - 开启：使用 `pytesseract` + `Pillow` 做 OCR
    - 关闭：跳过或返回空字符串
  - 加密 PDF：捕获异常，返回 `ParserError`
  - OCR 失败时降级为文本模式，记录警告

- [ ] 2.2 实现 Office 解析器 `src/parsers/office.py`
  - `OfficeParser` 类，根据扩展名路由
  - 新版格式：
    - `.docx` → `python-docx`
    - `.pptx` → `python-pptx`
    - `.xlsx` → `openpyxl`
  - 旧版格式（跨平台适配）：
    - Linux：`antiword`（通过 `subprocess` 调用）
    - macOS：`catdoc`（通过 `subprocess` 调用）
    - Windows：`win32com.client.Dispatch`（`pywin32`）
  - 平台检测逻辑：导入时检测可用库，选择最优方案
  - 不可用时抛出 `ParserError`

- [ ] 2.3 实现压缩包解析器 `src/parsers/archive.py`
  - `ArchiveParser` 类
  - 支持格式：`.zip`、`.tar`、`.tar.gz`/`.tgz`、`.gz`、`.rar`、`.7z`
  - 路由逻辑：
    - zip → `zipfile`（标准库）
    - tar/tgz → `tarfile`（标准库）
    - gz → `gzip`（标准库）
    - rar → `rarfile`
    - 7z → `py7zr`
  - 递归解压：
    - 遍历压缩包内所有条目
    - 目录 → 递归进入
    - 支持格式文件 → 提取到临时目录后由对应解析器处理
    - 嵌套压缩包 → 递归解压
  - 安全限制：
    - 最大解压深度：10 层
    - 最大压缩包总大小：500MB
    - 路径安全检查（防止 Zip Slip）
  - 临时目录自动清理（`tempfile.TemporaryDirectory`）
  - 解压失败的文件返回 `ParserError`

- [ ] 2.4 实现多进程并行 `src/checker.py`
  - 在现有 `scan_directory` 基础上升级
  - 使用 `concurrent.futures.ProcessPoolExecutor`
  - worker 数量：默认 CPU 核心数，可通过 `-w` 参数调整
  - 文件列表在主进程构建，worker 只负责解析和匹配
  - 大目录自动分片（每批 100 个文件）
  - worker 结果汇总：
    - 有匹配 → 加入结果树
    - 无匹配 → 不显示
    - 解析失败 → 加入失败列表
  - 进度日志输出（可选 `--verbose` 参数）

- [ ] 2.5 更新 CLI `src/cli.py`
  - 新增 `-w` / `--workers` 参数
  - 新增 `--context` 参数（Phase 1 已有，确认传递正确）
  - 新增 `--check-archives` 参数（默认开启，`-n` 可关闭）
  - 新增 `--verbose` 参数

- [ ] 2.6 更新 `requirements.txt`
  - 添加所有 Phase 2 依赖

- [ ] 2.7 编写 Phase 2 测试
  - `tests/test_parsers.py` — 扩展测试
    - PDF 解析（文本 PDF、加密 PDF、OCR 开关）
    - Office 解析（docx/pptx/xlsx/doc/xls/ppt）
    - 压缩包解析（zip/tar/gz/rar/7z、嵌套压缩包、深度限制）
  - `tests/test_checker.py` — 扩展测试
    - 多进程并行逻辑
    - 分片策略
    - 失败文件归类

### 验收标准

1. 能扫描 .txt/.pdf/.doc/.docx/.xls/.xlsx/.ppt/.pptx 文件
2. 能扫描 .zip/.tar/.gz/.rar/.7z 压缩包，包括嵌套压缩
3. 多进程扫描速度显著优于单进程（至少 2 核提升）
4. 解析失败/加密文件/权限不足的文件正确归类到报告
5. 所有 Phase 2 测试通过

---

## Phase 3: CLI 完整化 + Web 管理端

### 目标
完整的命令行接口 + 独立的 Web 敏感词管理界面。

### 任务清单

- [ ] 3.1 完善 CLI `src/cli.py`
  - `add` 子命令：`sensi-check add "词1" "词2"`
  - `remove` 子命令：`sensi-check remove "词1"`
  - `list` 子命令：`sensi-check list`（表格输出，支持 `--count` 显示数量）
  - `config show-ocr` 子命令：`sensi-check config show-ocr`
  - `config set-ocr` 子命令：`sensi-check config set-ocr on|off`
  - `--help` 子命令说明

- [ ] 3.2 创建 Web 管理端骨架 `web-admin/`
  - `web-admin/__init__.py`
  - `web-admin/main.py` — FastAPI 应用
  - `web-admin/templates/` — HTML 模板目录

- [ ] 3.3 实现 Web 后端 API `web-admin/main.py`
  - FastAPI 应用初始化
  - 路由：
    - `GET /` — 管理页面
    - `GET /api/keywords` — 获取关键词列表
    - `POST /api/keywords` — 添加关键词（JSON body: `{"word": "xxx"}`）
    - `DELETE /api/keywords/{word}` — 删除关键词
    - `PUT /api/config/ocr` — 设置 OCR 开关（JSON body: `{"enabled": true/false}`）
  - 直接读写 `config/keywords.json`，与 CLI 共享数据
  - 绑定 `127.0.0.1:8000`

- [ ] 3.4 实现 Web 前端页面 `web-admin/templates/index.html`
  - 关键词列表表格（搜索过滤、分页）
  - 添加关键词表单
  - 删除按钮（每行一个）
  - OCR 开关控件（toggle）
  - CLI 命令生成器（显示当前配置对应的 `sensi-check` 命令）
  - 原生 HTML/CSS/JS，无前端框架
  - 响应式布局（适配桌面浏览器）

- [ ] 3.5 添加 Web 启动命令到 CLI `src/cli.py`
  - `serve` 子命令：`sensi-check serve`
  - 启动 uvicorn 服务器
  - 显示访问地址

- [ ] 3.6 编写 Phase 3 测试
  - `tests/test_cli.py` — 所有 CLI 子命令测试
  - `tests/test_web.py` — Web API 测试（使用 FastAPI TestClient）

### 验收标准

1. CLI 所有子命令正常工作
2. Web 管理端能启动，页面正常渲染
3. Web 端添加/删除关键词后，CLI 能立即看到更新
4. Web 端 OCR 开关能正确读写
5. Web 端能生成当前配置的 CLI 命令
6. 所有 Phase 3 测试通过

---

## Phase 4: 集成与文档

### 目标
端到端测试、性能调优、错误处理完善、完整文档。

### 任务清单

- [ ] 4.1 集成测试 `tests/test_integration.py`
  - 创建临时目录，放入各类测试文件
  - 执行完整扫描流程
  - 验证报告内容正确性
  - 验证失败文件正确归类
  - 清理临时目录

- [ ] 4.2 错误处理完善
  - 大文件处理（超过 100MB 的文件）
  - 损坏文件处理
  - 加密文件处理
  - 符号链接处理（默认跟随，`--no-follow-links` 可关闭）
  - 权限不足文件处理
  - 所有错误统一归类到报告

- [ ] 4.3 性能调优
  - 大目录扫描性能验证
  - 内存占用监控
  - 文件分片策略优化
  - 并行度自适应（根据 CPU 核心数和文件数量）

- [ ] 4.4 编写 README.md
  - 项目简介
  - 安装说明（各平台）
    - Linux: `apt install antiword unrar tesseract-ocr && pip install -r requirements.txt`
    - macOS: `brew install catdoc unrar tesseract && pip install -r requirements.txt`
    - Windows: `pip install -r requirements.txt` + 手动安装 unrar/tesseract
  - 快速开始（基本用法）
  - 命令参考（所有子命令说明）
  - 配置说明
  - Web 管理端说明
  - 常见问题 FAQ
  - 贡献指南

- [ ] 4.5 端到端验证
  - 在 Linux/macOS/Windows 各平台验证基本功能
  - 验证所有格式文件扫描
  - 验证压缩包递归扫描
  - 验证 Web 管理端功能

### 验收标准

1. 所有测试通过（单元测试 + 集成测试）
2. README 文档完整，各平台安装命令正确
3. 大目录（10000+ 文件）扫描性能可接受
4. 所有边界情况正确处理
5. 三平台基本功能验证通过
