# 修复计划

> 基于代码审查生成，记录所有已识别缺陷及对应修复方案。
>
> - 整体评估：⚠️ **Risky**
> - 审查范围：`src/`、`web_admin/`、`tests/`、`docs/`、`README.md`、`AGENTS.md`
> - 审查时间：2026-06-26

## 优先级说明

| 标记 | 含义 | 处理建议 |
| --- | --- | --- |
| 🔴 | 高优先级（安全/功能性缺陷） | 立即修复 |
| 🟡 | 中优先级（文档不一致/代码质量） | 计划内修复 |
| 🟢 | 低优先级（建议优化） | 视情况修复 |

---

## Issue 清单

### 1. 并发安全 — `save_keywords` 先截断后加锁导致竞态条件 🔴

**Location:** `src/config.py#L62-L71`

**Analysis:** `save_keywords` 使用 `open(CONFIG_PATH, "w")` 打开文件，`"w"` 模式在 `open()` 调用时**立即将文件截断为 0 字节**，而排他锁 `_lock_file_exclusive(f)` 在截断**之后**才获取。如果在 `open` 和 `_lock_file_exclusive` 之间有另一个进程调用 `load_keywords`，该进程会读取到空文件或半截文件，`json.load` 抛出 `JSONDecodeError`，返回空配置——导致敏感词库"丢失"。对比同文件的 `_atomic_read_write`（L79-90）使用 `"r+"` 模式并在加锁后才 `truncate()`，是正确的做法。

**Fix:**

```python
# FILEPATH: d:\Files\CMCCSI\Codes\SensiFileChk\src\config.py

# ------ ORIGINAL CODE ------
def save_keywords(keywords: list, ocr_enabled: bool) -> None:
    _ensure_config_dir()
    unique_keywords = list(dict.fromkeys(keywords))
    data = {"keywords": unique_keywords, "ocr_enabled": ocr_enabled}
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        _lock_file_exclusive(f)
        try:
            json.dump(data, f, ensure_ascii=False, indent=2)
        finally:
            _unlock_file(f)
# --------------------------
# ------ NEW CODE ----------
def save_keywords(keywords: list, ocr_enabled: bool) -> None:
    _ensure_config_dir()
    unique_keywords = list(dict.fromkeys(keywords))
    data = {"keywords": unique_keywords, "ocr_enabled": ocr_enabled}
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(dict(_DEFAULT_CONFIG), f, ensure_ascii=False, indent=2)
    with open(CONFIG_PATH, "r+", encoding="utf-8") as f:
        _lock_file_exclusive(f)
        try:
            f.seek(0)
            f.truncate()
            json.dump(data, f, ensure_ascii=False, indent=2)
        finally:
            _unlock_file(f)
# --------------------------
```

---

### 2. 安全 — Windows `msvcrt.locking` 仅锁 1 字节，文件锁形同虚设 🔴

**Location:** `src/config.py#L13-L26`

**Analysis:** `msvcrt.locking(fd, mode, 1)` 的第三个参数 `1` 表示仅锁定从当前文件位置起 1 个字节。由于文件刚打开时位置为 0，实际只锁定了第 0 个字节。`keywords.json` 通常远超 1 字节，其他进程可以正常读写第 1 字节之后的内容，文件锁无法保护完整的 read-modify-write 事务。这导致 `add_keyword`/`remove_keyword`/`save_keywords` 在 Windows 上的并发安全保证失效。此外，`_lock_file_shared` 和 `_lock_file_exclusive` 使用相同的 `LK_NBLCK`（非阻塞排他锁），共享读锁实际不存在。

**Fix:**

```python
# FILEPATH: d:\Files\CMCCSI\Codes\SensiFileChk\src\config.py

# ------ ORIGINAL CODE ------
if sys.platform == "win32":
    import msvcrt

    def _lock_file_shared(f):
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)

    def _lock_file_exclusive(f):
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)

    def _unlock_file(f):
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
# --------------------------
# ------ NEW CODE ----------
if sys.platform == "win32":
    import msvcrt

    def _lock_file_shared(f):
        f.seek(0, 2)
        size = f.tell()
        f.seek(0)
        if size == 0:
            size = 1
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, size)

    def _lock_file_exclusive(f):
        f.seek(0, 2)
        size = f.tell()
        f.seek(0)
        if size == 0:
            size = 1
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, size)

    def _unlock_file(f):
        try:
            f.seek(0, 2)
            size = f.tell()
            f.seek(0)
            if size == 0:
                size = 1
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, size)
        except OSError:
            pass
# --------------------------
```

---

### 3. 安全 — Web 端自定义 `tojson` 过滤器未转义 HTML 字符，导致 XSS 🔴

**Location:** `web_admin/main.py#L21`

**Analysis:** 代码用 `lambda value: Markup(json.dumps(value, ensure_ascii=False))` 覆盖了 Jinja2 内置的 `tojson` 过滤器。Jinja2 内置 `tojson` 会将 `<`、`>`、`&`、`'` 转义为 Unicode 转义序列（`\u003c` 等），专门防止在 `<script>` 标签内嵌入 JSON 时的 XSS。自定义版本不做任何 HTML 转义。模板 `index.html#L297` 中 `const initialKeywords = {{ initial_keywords | tojson }};` 将关键词数组直接嵌入 `<script>` 块。若关键词包含 `</script><script>alert(1)</script>`，浏览器 HTML 解析器会在字符串中的 `</script>` 处提前关闭脚本块，导致后续 `<script>alert(1)</script>` 执行。

**Fix:**

```python
# FILEPATH: d:\Files\CMCCSI\Codes\SensiFileChk\web_admin\main.py

# ------ ORIGINAL CODE ------
templates = Jinja2Templates(directory=TEMPLATE_DIR)
templates.env.filters['tojson'] = lambda value: Markup(json.dumps(value, ensure_ascii=False))
# --------------------------
# ------ NEW CODE ----------
templates = Jinja2Templates(directory=TEMPLATE_DIR)
# Jinja2 内置 tojson 已做 HTML 安全转义，无需覆盖；
# 如需 ensure_ascii=False，可扩展而非替换安全行为
def _safe_tojson(value):
    import json as _json
    raw = _json.dumps(value, ensure_ascii=False)
    raw = raw.replace('<', '\\u003c').replace('>', '\\u003e')
    raw = raw.replace('&', '\\u0026').replace("'", '\\u0027')
    return Markup(raw)
templates.env.filters['tojson'] = _safe_tojson
# --------------------------
```

---

### 4. 功能缺陷 — Linux/macOS 下 `.xls`/`.ppt` 使用错误的解析工具 🔴

**Location:** `src/parsers/office.py#L95-L104`

**Analysis:** `_parse_legacy` 对所有旧版 Office 格式（`.doc`/`.xls`/`.ppt`）在 Linux 上统一调用 `_parse_with_antiword`，在 macOS 上统一调用 `_parse_with_catdoc`。但 `antiword` **仅支持 `.doc`**（Word 文档），不支持 `.xls` 和 `.ppt`；`catdoc` 命令也仅处理 `.doc`。`.xls` 需要 `xls2csv`，`.ppt` 需要 `catppt`（来自 `catdoc` 包）。这意味着 Linux/macOS 上 `.xls` 和 `.ppt` 文件解析会失败（`antiword`/`catdoc` 返回非零退出码），被归入报告的"检查失败"区域。文档 `architecture.md#L96-L98` 也错误地声称 `antiword` 处理 `.xls`/`.ppt`。

**Fix:**

```python
# FILEPATH: d:\Files\CMCCSI\Codes\SensiFileChk\src\parsers\office.py

# ------ ORIGINAL CODE ------
    def _parse_legacy(self, file_path: str, ext: str) -> str:
        current_platform = self._platform
        if current_platform == "Linux":
            return self._parse_with_antiword(file_path)
        elif current_platform == "Darwin":
            return self._parse_with_catdoc(file_path)
        elif current_platform == "Windows":
            return self._parse_with_pywin32(file_path, ext)
        else:
            raise ParserError(f"不支持的平台: {current_platform}")
# --------------------------
# ------ NEW CODE ----------
    def _parse_legacy(self, file_path: str, ext: str) -> str:
        current_platform = self._platform
        if current_platform == "Linux" or current_platform == "Darwin":
            return self._parse_legacy_unix(file_path, ext, current_platform)
        elif current_platform == "Windows":
            return self._parse_with_pywin32(file_path, ext)
        else:
            raise ParserError(f"不支持的平台: {current_platform}")

    def _parse_legacy_unix(self, file_path: str, ext: str, current_platform: str) -> str:
        tool_map = {
            "doc": "antiword" if current_platform == "Linux" else "catdoc",
            "xls": "xls2csv",
            "ppt": "catppt",
        }
        tool = tool_map.get(ext)
        if not tool:
            raise ParserError(f"不支持的旧格式: {ext}")
        try:
            result = subprocess.run(
                [tool, file_path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                raise ParserError(f"{tool} 解析失败: {result.stderr.strip()}")
            return result.stdout
        except FileNotFoundError:
            raise ParserError(f"{tool} 未安装")
        except subprocess.TimeoutExpired:
            raise ParserError(f"{tool} 解析超时")
# --------------------------
```

**关联文档修复：** 同步更新 `docs/architecture.md#L96-L98`，修正 `antiword`/`catdoc` 的适用范围说明，补充 `xls2csv`/`catppt`。

---

### 5. 文档不一致 — README 声称 `--workers` 默认为 1，实际为 CPU 核心数 🟡

**Location:** `README.md#L84` 与 `src/cli.py#L18,L70`

**Analysis:** README 第 84 行写 `-w, --workers  并行 worker 数量（默认: 1）`，但 `cli.py` 第 18 行 `default=None`，第 70 行 `num_workers = args.workers if args.workers is not None else os.cpu_count() or 1`——实际默认是 CPU 核心数。`architecture.md#L326` 和 `development-plan.md#L150` 均正确描述为"默认 CPU 核心数"。README 与代码及其他文档矛盾，会误导用户以为默认单进程。

**Fix:**

```markdown
# FILEPATH: d:\Files\CMCCSI\Codes\SensiFileChk\README.md

# ------ ORIGINAL CODE ------
  -w, --workers      并行 worker 数量（默认: 1）
# --------------------------
# ------ NEW CODE ----------
  -w, --workers      并行 worker 数量（默认: CPU 核心数）
# --------------------------
```

---

### 6. 文档不一致 — `scan_directory` 函数签名与代码不符 🟡

**Location:** `docs/architecture.md#L179` 与 `src/checker.py#L184-L192`

**Analysis:** 文档记录签名为 `scan_directory(dir_path, keywords, ocr_enabled, num_workers, check_archives) -> dict`，实际签名为 `scan_directory(dir_path, keywords, context_chars=50, num_workers=1, ocr_enabled=False, check_archives=True, verbose=False) -> dict`。参数顺序不同（`ocr_enabled` 和 `num_workers` 位置颠倒），且缺少 `context_chars` 和 `verbose` 参数。若开发者按文档顺序以位置参数调用，`ocr_enabled` 的布尔值会传给 `context_chars`（int），`num_workers` 的 int 会传给 `ocr_enabled`（bool），导致运行时错误。

**Fix:**

```markdown
# FILEPATH: d:\Files\CMCCSI\Codes\SensiFileChk\docs\architecture.md

# ------ ORIGINAL CODE ------
- `scan_directory(dir_path: str, keywords: list, ocr_enabled: bool, num_workers: int, check_archives: bool) -> dict` — 执行扫描
# --------------------------
# ------ NEW CODE ----------
- `scan_directory(dir_path: str, keywords: list, context_chars: int = 50, num_workers: int = 1, ocr_enabled: bool = False, check_archives: bool = True, verbose: bool = False) -> dict` — 执行扫描
# --------------------------
```

---

### 7. 文档不一致 — `generate_report` 及相关函数签名与代码不符 🟡

**Location:** `docs/architecture.md#L225-L228` 与 `src/report.py#L10,L44,L64,L124`

**Analysis:** 文档记录 `generate_report(results: dict, failures: list, output_path: str, scan_dir: str) -> None`，实际签名为 `generate_report(scan_result: dict, output_path: str, scan_dir: str, keywords: list[str], elapsed: float = 0.0) -> None`——第一个参数是包含 `results` 和 `failures` 的 `scan_result` 字典（非分开的两个参数），且缺少 `keywords` 和 `elapsed`。此外 `_build_tree`、`_render_tree`、`_render_failures` 的签名也均缺少参数（`scan_dir`、`breadcrumb`）。

**Fix:**

```markdown
# FILEPATH: d:\Files\CMCCSI\Codes\SensiFileChk\docs\architecture.md

# ------ ORIGINAL CODE ------
- `generate_report(results: dict, failures: list, output_path: str, scan_dir: str) -> None`
- `_build_tree(results: dict) -> dict` — 将扁平结果构建树形结构
- `_render_tree(node: dict, level: int) -> str` — 递归渲染 HTML
- `_render_failures(failures: list) -> str` — 渲染检查失败区域
# --------------------------
# ------ NEW CODE ----------
- `generate_report(scan_result: dict, output_path: str, scan_dir: str, keywords: list[str], elapsed: float = 0.0) -> None`
- `_build_tree(results: list[FileResult], scan_dir: str) -> dict` — 将扁平结果构建树形结构
- `_render_tree(node: dict, level: int, breadcrumb: list = None) -> str` — 递归渲染 HTML
- `_render_failures(failures: list[FileResult], scan_dir: str) -> str` — 渲染检查失败区域
# --------------------------
```

---

### 8. 文档不一致 — README 支持格式表缺少 `.xls`/`.ppt` 行 🟡

**Location:** `README.md#L113-L123`

**Analysis:** README 的"支持的文件格式"表格列出了 `.doc`（Word 旧版）但缺少 `.xls`（Excel 旧版）和 `.ppt`（PowerPoint 旧版）行。`AGENTS.md` 明确列出支持的文件类型包含 `.xls` 和 `.ppt`，`office.py` 也实现了这两种格式的解析。用户从 README 无法得知 `.xls`/`.ppt` 被支持。

**Fix:**

```markdown
# FILEPATH: d:\Files\CMCCSI\Codes\SensiFileChk\README.md

# ------ ORIGINAL CODE ------
| Word 旧版 | .doc | antiword |
| Excel 新版 | .xlsx | openpyxl |
| PowerPoint 新版 | .pptx | python-pptx |
# --------------------------
# ------ NEW CODE ----------
| Word 旧版 | .doc | antiword / catdoc / pywin32 |
| Excel 新版 | .xlsx | openpyxl |
| Excel 旧版 | .xls | pywin32 (Windows) / xls2csv (Linux/macOS) |
| PowerPoint 新版 | .pptx | python-pptx |
| PowerPoint 旧版 | .ppt | pywin32 (Windows) / catppt (Linux/macOS) |
# --------------------------
```

> 注：该修复依赖 Issue #4 先落地，确保 `xls2csv`/`catppt` 实际可用。

---

### 9. 功能缺陷 — `total_files` 统计不包含无匹配文件，输出信息误导 🟡

**Location:** `src/cli.py#L84-L86` 与 `src/report.py#L17-L18`

**Analysis:** `result["results"]` 仅包含**有匹配**的文件（`_process_result` 中 `elif fr.matches: results.append(fr)`），`result["failures"]` 包含失败文件。成功扫描但无匹配的文件不入任何列表。因此 `total_files = len(result["results"]) + len(result["failures"])` 实际是"命中文件数 + 失败文件数"，而非"总扫描文件数"。CLI 输出 `共扫描 {total_files} 个文件` 和报告中 `扫描文件数: {total_files}` 均具有误导性。`scan_directory` 内部 `checked` 变量记录了真实总数但未返回。

**Fix:**

```python
# FILEPATH: d:\Files\CMCCSI\Codes\SensiFileChk\src\checker.py

# ------ ORIGINAL CODE ------
    results.sort(key=lambda r: r.file_path)
    failures.sort(key=lambda r: r.file_path)
    return {"results": results, "failures": failures}
# --------------------------
# ------ NEW CODE ----------
    results.sort(key=lambda r: r.file_path)
    failures.sort(key=lambda r: r.file_path)
    return {"results": results, "failures": failures, "total_scanned": checked}
# --------------------------
```

然后在 `cli.py` 中：

```python
# ------ ORIGINAL CODE ------
    total_matches = sum(len(r.matches) for r in result["results"])
    total_files = len(result["results"]) + len(result["failures"])
    print(f"扫描完成: 共扫描 {total_files} 个文件, 发现 {total_matches} 处匹配, 耗时 {elapsed:.2f}s")
# --------------------------
# ------ NEW CODE ----------
    total_matches = sum(len(r.matches) for r in result["results"])
    total_files = result.get("total_scanned", len(result["results"]) + len(result["failures"]))
    print(f"扫描完成: 共扫描 {total_files} 个文件, 发现 {total_matches} 处匹配, 耗时 {elapsed:.2f}s")
# --------------------------
```

并同步修正 `src/report.py#L17-L18` 中 `total_files` 的取值方式，使用 `scan_result.get("total_scanned", ...)`。

---

### 10. 代码质量 — `_atomic_read_write` 存在未使用参数与 TOCTOU 竞态 🟡

**Location:** `src/config.py#L74-L91`

**Analysis:** 两个问题：（1）`read_data` 参数从未被使用，所有调用处均传 `None`（L102, L112, L126），是死参数；（2）L76 `if not os.path.exists(CONFIG_PATH)` 与 L79 `open(CONFIG_PATH, "r+")` 之间存在 TOCTOU 竞态——若另一进程在检查后删除文件，`open("r+")` 会抛 `FileNotFoundError`。此外 L91 `return config` 在 `with` 块外部，若 `modify_fn` 抛异常则 `config` 未定义（异常会传播，功能不受影响，但可读性差）。

**Fix:**

```python
# FILEPATH: d:\Files\CMCCSI\Codes\SensiFileChk\src\config.py

# ------ ORIGINAL CODE ------
def _atomic_read_write(read_data, modify_fn):
    _ensure_config_dir()
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(dict(_DEFAULT_CONFIG), f, ensure_ascii=False, indent=2)
    with open(CONFIG_PATH, "r+", encoding="utf-8") as f:
        _lock_file_exclusive(f)
        try:
            raw = json.load(f)
            if not isinstance(raw, dict) or "keywords" not in raw or "ocr_enabled" not in raw:
                raw = dict(_DEFAULT_CONFIG)
            config = modify_fn(raw)
            f.seek(0)
            f.truncate()
            json.dump(config, f, ensure_ascii=False, indent=2)
        finally:
            _unlock_file(f)
    return config
# --------------------------
# ------ NEW CODE ----------
def _atomic_read_write(modify_fn):
    _ensure_config_dir()
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(dict(_DEFAULT_CONFIG), f, ensure_ascii=False, indent=2)
    with open(CONFIG_PATH, "r+", encoding="utf-8") as f:
        _lock_file_exclusive(f)
        try:
            raw = json.load(f)
            if not isinstance(raw, dict) or "keywords" not in raw or "ocr_enabled" not in raw:
                raw = dict(_DEFAULT_CONFIG)
            config = modify_fn(raw)
            f.seek(0)
            f.truncate()
            json.dump(config, f, ensure_ascii=False, indent=2)
            return config
        finally:
            _unlock_file(f)
# --------------------------
```

同时需更新三处调用：`_atomic_read_write(None, _modify)` → `_atomic_read_write(_modify)`（L102, L112, L126）。

---

### 11. 并发安全 — 释放排他锁前未 flush+fsync，跨进程读到空文件触发 JSONDecodeError 🔴

**Location:** `src/config.py#L93-L112`（`_atomic_read_write`）、`src/config.py#L76-L92`（`save_keywords`）

**Analysis:** `_atomic_read_write` 与 `save_keywords` 在 `f.truncate()` 后调用 `json.dump(...)`，但 `json.dump` 仅写入 Python 层缓冲区，尚未落盘。`return config` 后 `finally: _unlock_file(f)` 释放排他锁时，磁盘文件仍为 0 字节（新数据停留在缓冲区中）。阻塞在 `flock(LOCK_EX)` 的进程 B 此时获得锁，`json.load(f)` 读到空文件，抛 `JSONDecodeError: Expecting value: line 1 column 1 (char 0)`，进程崩溃（exitcode=1）。进程 A 的 `with` 语句随后 `close()` 才真正 flush 落盘，但为时已晚。该竞态导致 `test_multiprocess_concurrent_write` 间歇性失败（10 进程中 1 个崩溃）。此前的 Issue #1（加锁前截断）与 #2（Windows 锁范围）解决的是锁的获取时机，本次是锁释放与数据落盘的顺序，属同文件内新缺陷。`load_keywords`（只读）虽不崩溃，但其共享读锁期间可能读到写者截断后未落盘的空文件，`except JSONDecodeError` 会静默返回默认空配置——表现为"敏感词库偶发丢失"，随本次修复一并消除。

**Fix:** 在 `_atomic_read_write` 与 `save_keywords` 的 `json.dump` 之后、`finally` 释放锁之前，插入 `f.flush()`（把 Python 缓冲写入操作系统，保证其他进程可见）+ `os.fsync(f.fileno())`（保证崩溃持久性）。`os` 已在 `config.py` 顶部导入，无需新增 import。

```python
# FILEPATH: d:\Files\CMCCSI\Codes\SensiFileChk\src\config.py
# _atomic_read_write 与 save_keywords 的 json.dump 之后、释放锁之前均插入：
            json.dump(config, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
            return config
```

**验收:**
- `test_multiprocess_concurrent_write` 单次及连续 ≥5 次执行均通过；
- 新增 `test_multiprocess_high_concurrency_no_decode_error`（20 进程并发）无进程异常退出、20 词全部写入成功；
- 全量套件 0 failed，日志中不再出现 `JSONDecodeError: Expecting value: line 1 column 1 (char 0)`。

---

## 补充说明（非阻塞）

### A. 测试数量分项过时 🟢

`development-plan.md#L292` 声称"262 条测试全部通过"，实际统计 `test_checker(67) + test_cli(20) + test_config(20) + test_integration(12) + test_parsers(100) + test_report(14) + test_web(29) = 262`，总数一致。但 Phase 1 的分项估计（test_config 18 条、test_report 13 条、test_checker 37 条）已过时，与当前实际数量不符，建议更新。

**Fix:** 更新 `docs/development-plan.md` 中 Phase 1 各模块测试数量估计，使其与实际一致。

### B. `requirements.txt` 混入测试依赖 🟢

`requirements.txt` 包含 `pytest`/`pytest-cov` 测试依赖，而 `pyproject.toml` 已正确将其放入 `[project.optional-dependencies] dev`。`requirements.txt` 通常用于生产依赖，建议移除测试依赖或注明用途。

### C. `markupsafe` 未显式声明依赖 🟢

`pyproject.toml` 未显式声明 `markupsafe` 依赖（`web_admin/main.py#L11` 导入了 `Markup`），目前靠 Jinja2 传递依赖引入，建议显式声明。

**Fix:** 在 `pyproject.toml` 的 `[project.dependencies]` 中添加 `markupsafe>=2.0`。

---

## 实施顺序建议

为降低回归风险，建议按以下顺序实施修复：

1. **第一批（安全并发，互相关联）**：Issue #2（Windows 文件锁）→ #1（`save_keywords` 竞态）→ #10（`_atomic_read_write` 清理）
2. **第二批（安全）**：Issue #3（Web tojson XSS）
3. **第三批（功能）**：Issue #4（`.xls`/`.ppt` 解析）→ #9（`total_files` 统计）
4. **第四批（文档对齐）**：Issue #5、#6、#7、#8、A
5. **第五批（依赖清理）**：B、C

每批完成后运行 `pytest tests/ -v` 全量回归，重点关注 `tests/test_config.py`（第一批）、`tests/test_web.py`（第二批）、`tests/test_parsers.py`（第三批）。

---

## 验收清单

- [ ] Issue #1：`save_keywords` 使用 `r+` 模式，加锁后再 truncate
- [ ] Issue #2：`msvcrt.locking` 锁定整个文件大小
- [ ] Issue #3：`tojson` 过滤器对 `<>&'` 做 Unicode 转义
- [ ] Issue #4：`.xls` 使用 `xls2csv`，`.ppt` 使用 `catppt`
- [ ] Issue #5：README `--workers` 默认值改为 CPU 核心数
- [ ] Issue #6：`architecture.md` 中 `scan_directory` 签名更新
- [ ] Issue #7：`architecture.md` 中 `generate_report` 等签名更新
- [ ] Issue #8：README 格式表补充 `.xls`/`.ppt` 行
- [ ] Issue #9：`scan_directory` 返回 `total_scanned`，CLI/报告使用该值
- [ ] Issue #10：`_atomic_read_write` 移除 `read_data` 参数，`return` 移入 `try` 块
- [x] Issue #11：`_atomic_read_write`/`save_keywords` 释放排他锁前 `f.flush()` + `os.fsync()` 落盘
- [ ] 补充 A：`development-plan.md` 测试分项数量更新
- [ ] 补充 B：`requirements.txt` 移除测试依赖或注明
- [ ] 补充 C：`pyproject.toml` 显式声明 `markupsafe`
- [ ] 全量测试通过：`pytest tests/ -v`
