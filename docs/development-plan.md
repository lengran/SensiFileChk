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
| Phase 1 | 项目基础 | 2-3 天 | 无 | ✅ 已完成 |
| Phase 2 | 多格式解析 + 并行 | 3-4 天 | Phase 1 | ✅ 已完成 |
| Phase 3 | CLI 完整化 + Web 管理端 | 2-3 天 | Phase 1 | ✅ 已完成 |
| Phase 4 | 集成与文档 | 1-2 天 | Phase 2, Phase 3 | ✅ 已完成 |

Phase 2 和 Phase 3 可部分并行，但推荐按顺序以保持一致性。

---

## Phase 1: 项目基础

### 目标
搭建项目骨架，跑通最简流程：txt 文件扫描 → 关键词匹配 → HTML 报告。

### 任务清单

- [x] 1.1 创建项目目录结构
  - `config/`, `src/`, `src/parsers/`, `web_admin/`, `tests/`
  - 各目录下的 `__init__.py`
  - `requirements.txt`

- [x] 1.2 实现配置模块 `src/config.py`
  - `load_keywords() -> dict` — 加载 `config/keywords.json`，文件不存在则返回空结构
  - `save_keywords(keywords: list, ocr_enabled: bool) -> None` — 保存配置
  - `add_keyword(word: str) -> None` — 添加单个关键词
  - `add_keywords(words: list[str]) -> None` — 批量添加关键词
  - `remove_keyword(word: str) -> bool` — 删除单个关键词
  - 文件锁机制（`threading.Lock` + `fcntl/msvcrt` 文件锁，防止 CLI 和 Web 并发冲突）

- [x] 1.3 实现解析器抽象基类 `src/parsers/base.py`
  - `BaseParser` 类，定义 `parse(file_path: str) -> str` 接口
  - 定义 `ParserError` 异常类

- [x] 1.4 实现 txt 解析器 `src/parsers/txt.py`
  - `TxtParser` 类，读取文本内容
  - 支持 UTF-8 / GBK / GB2312 自动检测编码
  - 编码检测失败时抛出 `ParserError`

- [x] 1.5 实现扫描引擎 `src/checker.py`
  - `_match_keywords(text: str, keywords: list) -> list[Match]` — 逐关键词查找（英文大小写不敏感，中文大小写敏感）
  - `_extract_context(text: str, start: int, end: int, context_chars: int = 50) -> str` — 提取上下文
  - `scan_single_file(file_path: str, keywords: list) -> FileResult` — 单文件扫描
  - `scan_directory(dir_path: str, keywords: list) -> dict` — 扫描入口（支持单进程和多进程，内含 Phase 1 os.walk 文件发现）
  - 支持 `--context N` 参数控制上下文字符数

- [x] 1.6 实现 HTML 报告生成 `src/report.py`
  - `generate_report(results: dict, output_path: str, scan_dir: str) -> None`
  - `_build_tree(results: dict) -> dict` — 扁平结果构建树形结构
  - `_render_tree(node: dict, level: int) -> str` — 递归渲染 HTML
  - 原生 JS 实现目录折叠/展开
  - `<mark>` 标签高亮敏感词（红色背景）
  - 头部显示：检查时间、目录、关键词数量、匹配总数
  - 底部显示：处理文件数、耗时

- [x] 1.7 实现 CLI 骨架 `src/cli.py`
  - `main()` — argparse 入口
  - `check` 子命令：`sensi-check check /path -o report.html [--context 50]`
  - 加载配置 → 调用 checker → 生成报告 → 输出统计信息

- [x] 1.8 编写 Phase 1 测试
  - `tests/test_config.py` — 配置读写、添加/删除关键词、文件锁、并发写（18 条）
  - `tests/test_parsers.py` — txt 解析器（正常文本、GBK/GB2312 编码、编码错误、大文件）
  - `tests/test_report.py` — 报告生成正确性、目录树结构、高亮（13 条）
  - `tests/test_checker.py` — 关键词匹配、上下文提取、文件发现、单/多进程扫描（37 条）

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

- [x] 2.1 实现 PDF 解析器 `src/parsers/pdf.py`
  - `PdfParser` 类
  - 文本 PDF：使用 `pymupdf` 提取文本
  - 图片 PDF：根据 `ocr_enabled` 开关
    - 开启：使用 `pytesseract` + `Pillow` 做 OCR
    - 关闭：跳过或返回空字符串
  - 加密 PDF：捕获异常，返回 `ParserError`
  - OCR 失败时降级为文本模式，记录警告

- [x] 2.2 实现 Office 解析器 `src/parsers/office.py`
  - `OfficeParser` 类，根据扩展名路由
  - 新版格式：
    - `.docx` → `python-docx`
    - `.pptx` → `python-pptx`
    - `.xlsx` → `openpyxl`
  - 旧版格式（跨平台适配）：
    - Linux：`antiword`（通过 `subprocess` 调用）
    - macOS：`catdoc`（通过 `subprocess` 调用）
    - Windows：`win32com.client.Dispatch`（`pywin32`）
  - 平台检测逻辑：运行时 `platform.system()` 检测，动态选择方案
  - 不可用时抛出 `ParserError`

- [x] 2.3 实现压缩包解析器 `src/parsers/archive.py`
  - `ArchiveParser` 类
  - 支持格式：`.zip`、`.tar`、`.tar.gz`/`.tgz`、`.gz`、`.rar`、`.7z`
  - 路由逻辑：
    - zip → `zipfile`（标准库）
    - tar/tgz → `tarfile`（标准库）
    - gz → `gzip`（标准库）
    - rar → `rarfile`（函数内懒导入）
    - 7z → `py7zr`（函数内懒导入）
  - 递归解压：
    - 遍历压缩包内所有条目
    - 目录 → 跳过
    - 支持格式文件 → 提取到临时目录后由 `inner_parser_factory` 回调处理
    - 嵌套压缩包 → 递归解压（depth+1）
  - 安全限制：
    - 最大解压深度：10 层
    - 最大单文件大小：500MB
    - 最大压缩包总大小：500MB
    - 路径安全检查（Zip Slip 防护：拒绝绝对路径和 `..` 路径遍历）
  - 临时目录自动清理（`tempfile.TemporaryDirectory`）
  - 解压失败的文件在结果中内联记录

- [x] 2.4 实现多进程并行 `src/checker.py`
  - 在现有 `scan_directory` 基础上升级
  - 使用 `concurrent.futures.ProcessPoolExecutor`
  - worker 数量：默认 CPU 核心数，可通过 `-w` 参数调整
  - 文件列表在主进程构建，worker 只负责解析和匹配（无共享状态）
  - worker 结果汇总：
    - 有匹配 → 加入结果树
    - 无匹配 → 不显示
    - 解析失败 → 加入失败列表
  - 进度日志输出（`--verbose` 参数）

- [x] 2.5 更新 CLI `src/cli.py`
  - 新增 `-w` / `--workers` 参数
  - 新增 `--context` 参数（Phase 1 已有，确认传递正确）
  - 新增 `--check-archives` 参数（默认开启，`-n` 可关闭）
  - 新增 `--verbose` 参数

- [x] 2.6 更新 `requirements.txt` / `pyproject.toml`
  - 添加所有 Phase 2 依赖（pymupdf, pytesseract, Pillow, python-docx, python-pptx, openpyxl, rarfile, py7zr）

- [x] 2.7 编写 Phase 2 测试
  - `tests/test_parsers.py` — 扩展测试
    - PDF 解析（文本 PDF、多页 PDF、加密 PDF、OCR 开关及降级）
    - Office 解析（docx/pptx/xlsx、空文档、损坏文档、旧版格式跨平台路由）
    - 压缩包解析（zip/tar/gz/rar/7z、嵌套压缩包、深度限制、Zip Slip、大小限制）
  - `tests/test_checker.py` — 扩展测试
    - 多进程并行逻辑（1-worker vs multi-worker 一致性）
    - 失败文件归类
    - verbose 模式输出

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

- [x] 3.1 完善 CLI `src/cli.py`
  - `add` 子命令：`sensi-check add "词1" "词2"`
  - `remove` 子命令：`sensi-check remove "词1"`
  - `list` 子命令：`sensi-check list`（表格输出，支持 `--count` 显示数量）
  - `config show-ocr` 子命令：`sensi-check config show-ocr`
  - `config set-ocr` 子命令：`sensi-check config set-ocr on|off`
  - `--help` 子命令说明

- [x] 3.2 创建 Web 管理端骨架 `web_admin/`
  - `web_admin/__init__.py`
  - `web_admin/main.py` — FastAPI 应用
  - `web_admin/templates/` — HTML 模板目录

- [x] 3.3 实现 Web 后端 API `web_admin/main.py`
  - FastAPI 应用初始化
  - 路由：
    - `GET /` — 管理页面（Jinja2 渲染）
    - `GET /api/keywords` — 获取关键词列表
    - `POST /api/keywords` — 添加关键词（JSON body: `{"word": "xxx"}`）
    - `DELETE /api/keywords/{word}` — 删除关键词
    - `PUT /api/config/ocr` — 设置 OCR 开关（JSON body: `{"enabled": true/false}`）
    - `GET /api/config/ocr` — 获取 OCR 开关状态
    - `GET /api/cli/generate` — 生成 CLI 命令字符串
  - 直接读写 `config/keywords.json`，与 CLI 共享数据
  - 绑定 `127.0.0.1:8000`

- [x] 3.4 实现 Web 前端页面 `web_admin/templates/index.html`
  - 关键词列表展示（滚动列表、每行删除按钮、数量徽章）
  - 添加关键词表单（输入框 + 回车支持）
  - OCR 开关控件（自定义 CSS toggle）
  - CLI 命令生成器（扫描路径、输出路径、worker 数量、自动/手动切换、复制按钮）
  - 原生 HTML/CSS/JS，无前端框架
  - 响应式布局（桌面 + 移动端适配）
  - 暗色主题（深蓝/紫渐变背景 + 毛玻璃卡片）
  - XSS 防护（`escapeHtml()` / `escapeJs()` 辅助函数）

- [x] 3.5 添加 Web 启动命令到 CLI `src/cli.py`
  - `serve` 子命令：`sensi-check serve [--host 127.0.0.1] [--port 8000]`
  - 启动 uvicorn 服务器

- [x] 3.6 编写 Phase 3 测试
  - `tests/test_cli.py` — 所有 CLI 子命令测试（19 条）
  - `tests/test_web.py` — Web API 测试 + 页面测试 + CLI/Web 数据一致性（29 条）

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

- [x] 4.1 集成测试 `tests/test_integration.py`
  - 创建临时目录，放入各类测试文件
  - 执行完整扫描流程
  - 验证报告内容正确性
  - 验证失败文件正确归类
  - CLI/Web 数据一致性验证（12 条）

- [x] 4.2 错误处理完善
  - 损坏文件处理（损坏 PDF/Office/压缩包 → ParserError）
  - 加密文件处理（加密 PDF → ParserError）
  - 权限不足文件处理（无读权限 → 报告失败区域）
  - 所有错误统一归类到报告

- [x] 4.3 性能调优
  - 多进程并行扫描（ProcessPoolExecutor，worker 数可配置）
  - 无共享状态设计（内存隔离，天然线程安全）
  - 压缩包安全限制（深度/大小/路径遍历防护）
  - 两阶段扫描架构：阶段 1 预收集所有文件路径（os.walk，零 stat），阶段 2 扫描检测
  - 阶段 1 零 stat 设计：仅按扩展名过滤，不调用 os.path.getsize()，避免 stat 系统调用拖慢目录遍历
  - 阶段 2 按需 stat：多 worker 提交前调用 getsize() 判断大文件和估算内存；单 worker 无需 stat
  - 内存感知提交：`MAX_CONCURRENT_BYTES=1GB` 限制同时在途文件估算总大小
  - 压缩包内存估算：磁盘大小 × `ARCHIVE_SIZE_MULTIPLIER=5`
  - 大文件内联处理：单文件 > `MAX_SIZE` (500MB) 不提交进程池，走内联 `scan_single_file`
  - BrokenProcessPool 恢复：未完成文件移入 `large_files`，最后内联处理，不调整 worker 数
  - 进度输出：阶段 1 `发现文件中 | 待检测文件: N`，阶段 2 `扫描中 | 已检测: M/N (PP.P%) | 命中: X | 匹配: Y | 失败: Z | 已用时: Ts`

- [x] 4.4 编写 README.md
  - 项目简介
  - 安装说明（Linux、macOS）
  - 快速开始（基本用法）
  - 命令参考（所有子命令说明）
  - 支持格式说明
  - Web 管理端说明
  - 项目结构说明

- [x] 4.5 端到端验证
  - 255 条测试全部通过
  - 新增测试类：TestTwoPhaseProgress, TestLargeFileInline, TestEstimateFileBytes, TestMemoryThrottling, TestBrokenPoolRecovery

### 验收标准

1. 所有测试通过（单元测试 + 集成测试）
2. README 文档完整，各平台安装命令正确
3. 大目录（10000+ 文件）扫描性能可接受
4. 所有边界情况正确处理
5. 三平台基本功能验证通过
