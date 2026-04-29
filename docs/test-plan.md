# 测试验收方案

## 测试策略

每个开发阶段配套对应测试，确保阶段产出符合预期。测试分为：
- **单元测试** — 测试单个函数/类的正确性
- **集成测试** — 测试多模块协作
- **端到端测试** — 模拟真实用户使用场景

---

## Phase 1 测试验收

### 1.1 配置模块测试 (`tests/test_config.py`)

| 用例 ID | 测试内容 | 输入 | 预期输出 | 验收标准 |
|---------|---------|------|---------|---------|
| TC-CFG-001 | 加载空配置 | 无 `keywords.json` | 返回 `{"keywords": [], "ocr_enabled": false}` | 不抛异常，返回默认值 |
| TC-CFG-002 | 加载已有配置 | 含关键词和 OCR 开关的 JSON | 正确返回关键词列表和 OCR 状态 | 数据完整，类型正确 |
| TC-CFG-003 | 添加关键词 | `add_keyword("测试词")` | JSON 中新增该词 | 列表长度 +1，词存在 |
| TC-CFG-004 | 删除关键词 | `remove_keyword("测试词")` | JSON 中移除该词 | 列表长度 -1，词不存在 |
| TC-CFG-005 | 删除不存在的词 | `remove_keyword("不存在的词")` | 不抛异常，忽略 | 静默处理 |
| TC-CFG-006 | 添加重复关键词 | `add_keyword("已存在词")` | 不重复添加 | 列表无重复项 |
| TC-CFG-007 | 并发写入保护 | 两个进程同时调用 `save_keywords` | 不丢失数据 | 文件锁机制生效 |
| TC-CFG-008 | JSON 格式错误 | 损坏的 `keywords.json` | 返回默认空配置 | 容错处理，不崩溃 |

### 1.2 TXT 解析器测试 (`tests/test_parsers.py`)

| 用例 ID | 测试内容 | 输入 | 预期输出 | 验收标准 |
|---------|---------|------|---------|---------|
| TC-TXT-001 | 正常 UTF-8 文本 | UTF-8 编码的 txt 文件 | 返回完整文本内容 | 文本完整，无乱码 |
| TC-TXT-002 | GBK 编码文本 | GBK 编码的 txt 文件 | 返回正确解码的文本 | 中文内容正确 |
| TC-TXT-003 | GB2312 编码文本 | GB2312 编码的 txt 文件 | 返回正确解码的文本 | 中文内容正确 |
| TC-TXT-004 | 未知编码文件 | 二进制数据作为 txt | 抛出 `ParserError` | 错误信息包含编码检测失败 |
| TC-TXT-005 | 空文件 | 0 字节 txt 文件 | 返回空字符串 | 不抛异常 |
| TC-TXT-006 | 超大文件 | 50MB txt 文件 | 返回完整文本 | 内存占用合理 |

### 1.3 扫描引擎测试 (`tests/test_checker.py`)

| 用例 ID | 测试内容 | 输入 | 预期输出 | 验收标准 |
|---------|---------|------|---------|---------|
| TC-CHK-001 | 单文件扫描 | 含敏感词的 txt | `MatchResult` 含匹配项 | 匹配内容正确 |
| TC-CHK-002 | 多关键词匹配 | 含 3 个不同敏感词 | 返回 3 个匹配项 | 无遗漏 |
| TC-CHK-003 | 关键词重叠匹配 | 文本含 "国家机密信息"，关键词 "国家机密" 和 "机密信息" | 返回 2 个匹配项 | 重叠匹配正确 |
| TC-CHK-004 | 上下文提取 | 匹配位置在文本中间 | 前后 50 字符上下文 | 上下文完整，不越界 |
| TC-CHK-005 | 上下文边界处理 | 匹配位置在文本开头/结尾 | 上下文截断但不报错 | 不抛异常 |
| TC-CHK-006 | 目录发现 | 含 txt/pdf/docx 的目录树 | 返回所有支持格式文件路径 | 路径正确，无遗漏 |
| TC-CHK-007 | 不支持格式过滤 | 目录含 .jpg/.mp3 等 | 不支持格式不在文件列表中 | 不扫描非目标格式 |
| TC-CHK-008 | 空目录扫描 | 空目录 | 返回空结果 | 不抛异常 |

### 1.4 报告生成测试 (`tests/test_report.py`)

| 用例 ID | 测试内容 | 输入 | 预期输出 | 验收标准 |
|---------|---------|------|---------|---------|
| TC-RPT-001 | 基本报告生成 | 含匹配的扫描结果 | 生成有效 HTML 文件 | HTML 可正常打开 |
| TC-RPT-002 | 敏感词高亮 | 匹配项 | 上下文中标签 `<mark class="highlight">敏感词</mark>` | 高亮样式正确 |
| TC-RPT-003 | 目录树结构 | 多目录多文件结果 | 按目录层级嵌套 | 树形结构正确 |
| TC-RPT-004 | 头部信息 | 扫描参数 | 显示检查时间、目录、关键词数 | 信息准确 |
| TC-RPT-005 | 底部统计 | 扫描结果 | 显示处理文件数、匹配数、耗时 | 统计正确 |
| TC-RPT-006 | 无匹配结果 | 无敏感词匹配 | 显示 "未发现敏感词" | 友好提示 |
| TC-RPT-007 | 失败文件列表 | 含解析失败文件 | 在"检查失败"区域列出 | 文件名和错误信息正确 |
| TC-RPT-008 | 目录折叠 | 多级目录 | 原生 JS 折叠/展开 | 交互正常 |

---

## Phase 2 测试验收

### 2.1 PDF 解析器测试 (`tests/test_parsers.py`)

| 用例 ID | 测试内容 | 输入 | 预期输出 | 验收标准 |
|---------|---------|------|---------|---------|
| TC-PDF-001 | 文本 PDF | 含文本的 PDF | 提取全部文本 | 文本完整 |
| TC-PDF-002 | 多页 PDF | 5 页 PDF | 提取全部页面文本 | 无遗漏 |
| TC-PDF-003 | 空 PDF | 空 PDF 文件 | 返回空字符串 | 不抛异常 |
| TC-PDF-004 | 加密 PDF | 密码保护的 PDF | 抛出 `ParserError` | 错误信息含 "加密" |
| TC-PDF-005 | OCR 关闭 | 图片 PDF + `ocr_enabled=false` | 返回空字符串 | 不执行 OCR |
| TC-PDF-006 | OCR 开启 | 图片 PDF + `ocr_enabled=true` | 返回 OCR 识别文本 | 文本可读 |
| TC-PDF-007 | OCR 失败降级 | 图片 PDF + OCR 不可用 | 返回空字符串 + 警告日志 | 不崩溃 |

### 2.2 Office 解析器测试 (`tests/test_parsers.py`)

| 用例 ID | 测试内容 | 输入 | 预期输出 | 验收标准 |
|---------|---------|------|---------|---------|
| TC-OFF-001 | .docx 解析 | 含文本的 docx | 提取全部文本 | 文本完整 |
| TC-OFF-002 | .pptx 解析 | 含文本的 pptx | 提取全部幻灯片文本 | 文本完整 |
| TC-OFF-003 | .xlsx 解析 | 含文本的 xlsx | 提取全部单元格文本 | 文本完整 |
| TC-OFF-004 | .doc 解析 (Linux) | 含文本的 doc | antiword 提取文本 | 中文内容正确 |
| TC-OFF-005 | .xls 解析 (Linux) | 含文本的 xls | antiword 提取文本 | 文本正确 |
| TC-OFF-006 | .ppt 解析 (Linux) | 含文本的 ppt | antiword 提取文本 | 文本正确 |
| TC-OFF-007 | 损坏的 Office 文件 | 随机二进制数据 | 抛出 `ParserError` | 错误信息含格式错误 |
| TC-OFF-008 | 加密 Office 文件 | 密码保护的 docx | 抛出 `ParserError` | 错误信息含加密 |
| TC-OFF-009 | 空 Office 文件 | 空 docx | 返回空字符串 | 不抛异常 |

### 2.3 压缩包解析器测试 (`tests/test_parsers.py`)

| 用例 ID | 测试内容 | 输入 | 预期输出 | 验收标准 |
|---------|---------|------|---------|---------|
| TC-ARC-001 | zip 解压 | 含 txt 的 zip | 提取内部文件文本 | 文本正确 |
| TC-ARC-002 | tar 解压 | 含 txt 的 tar | 提取内部文件文本 | 文本正确 |
| TC-ARC-003 | tar.gz 解压 | 含 txt 的 tgz | 提取内部文件文本 | 文本正确 |
| TC-ARC-004 | gz 解压 | gz 压缩的 txt | 提取文本 | 文本正确 |
| TC-ARC-005 | rar 解压 | 含 txt 的 rar | 提取内部文件文本 | 文本正确 |
| TC-ARC-006 | 7z 解压 | 含 txt 的 7z | 提取内部文件文本 | 文本正确 |
| TC-ARC-007 | 嵌套压缩包 | zip 内含 zip | 递归解压两层 | 内部文件正确提取 |
| TC-ARC-008 | 三层嵌套 | zip→zip→zip | 达到深度限制后停止 | 不无限递归 |
| TC-ARC-009 | 深度超限 | 11 层嵌套 | 抛出 `ParserError` | 错误信息含 "深度超限" |
| TC-ARC-010 | 路径安全 | 含 `../` 的条目 | 拒绝解压 | 防止 Zip Slip |
| TC-ARC-011 | 大压缩包 | 600MB zip | 抛出 `ParserError` | 错误信息含 "大小超限" |
| TC-ARC-012 | 损坏压缩包 | 随机二进制数据 | 抛出 `ParserError` | 不崩溃 |
| TC-ARC-013 | 空压缩包 | 空 zip | 返回空结果 | 不抛异常 |

### 2.4 并行扫描测试 (`tests/test_checker.py`)

| 用例 ID | 测试内容 | 输入 | 预期输出 | 验收标准 |
|---------|---------|------|---------|---------|
| TC-PAR-001 | 1 worker | 100 个文件，worker=1 | 全部扫描完成 | 结果与单进程一致 |
| TC-PAR-002 | 4 worker | 100 个文件，worker=4 | 全部扫描完成 | 结果与单进程一致 |
| TC-PAR-003 | 并行加速 | 1000 个文件，worker=1 vs worker=4 | worker=4 耗时显著更短 | 至少 2 倍加速 |
| TC-PAR-004 | 结果汇总 | 多 worker 结果 | 无遗漏，无重复 | 结果完整 |
| TC-PAR-005 | 分片策略 | 10000 个文件 | 分批处理，无内存溢出 | 内存稳定 |

### 2.5 两阶段扫描测试 (`tests/test_checker.py` — `TestTwoPhaseProgress`)

| 用例 ID | 测试内容 | 输入 | 预期输出 | 验收标准 |
|---------|---------|------|---------|---------|
| TC-PHASE-001 | 阶段 1 输出 | 3 个 txt 文件 | stdout 含 "发现文件中" | 阶段 1 进度可见 |
| TC-PHASE-002 | 阶段 2 百分比 | 3 个含敏感词的 txt 文件 | stdout 含 "已检测: 3/3" 和 "100.0%" | 百分比格式正确 |
| TC-PHASE-003 | 多 worker 两阶段 | 3 个 txt 文件 + worker=2 | 两个阶段进度均输出 | 多 worker 模式正确 |

### 2.6 大文件内联处理测试 (`tests/test_checker.py` — `TestLargeFileInline`)

| 用例 ID | 测试内容 | 输入 | 预期输出 | 验收标准 |
|---------|---------|------|---------|---------|
| TC-LARGE-001 | 大文件多 worker | 小文件 + 大文件 (>500MB)，worker=2 | 两个文件均被检测 | 大文件内联处理不丢失 |
| TC-LARGE-002 | 大文件单 worker | 大文件 (>500MB)，worker=1 | 正常匹配 | 单 worker 模式正确 |

### 2.7 文件内存估算测试 (`tests/test_checker.py` — `TestEstimateFileBytes`)

| 用例 ID | 测试内容 | 输入 | 预期输出 | 验收标准 |
|---------|---------|------|---------|---------|
| TC-EST-001 | 普通文件 | 5 字节 txt 文件 | 返回 5 | 大小等于磁盘大小 |
| TC-EST-002 | 压缩包文件 | 100 字节 zip 文件 | 返回 500 | 磁盘大小 × ARCHIVE_SIZE_MULTIPLIER |
| TC-EST-003 | 不存在的文件 | 不存在的路径 | 返回 0 | 不抛异常 |

### 2.8 内存感知提交测试 (`tests/test_checker.py` — `TestMemoryThrottling`)

| 用例 ID | 测试内容 | 输入 | 预期输出 | 验收标准 |
|---------|---------|------|---------|---------|
| TC-MEM-001 | 低预算节流 | 5 个文件 + MAX_CONCURRENT_BYTES=1，worker=2 | 全部扫描完成 | 节流逻辑不影响正确性 |

### 2.9 BrokenProcessPool 恢复测试 (`tests/test_checker.py` — `TestBrokenPoolRecovery`)

| 用例 ID | 测试内容 | 输入 | 预期输出 | 验收标准 |
|---------|---------|------|---------|---------|
| TC-BPP-001 | 进程池崩溃恢复 | 3 个文件，第 3 次 submit 抛 BrokenProcessPool | results + failures 总数 = 3 | 所有文件被内联处理，无遗漏 |

---

## Phase 3 测试验收

### 3.1 CLI 命令测试 (`tests/test_cli.py`)

| 用例 ID | 测试内容 | 输入 | 预期输出 | 验收标准 |
|---------|---------|------|---------|---------|
| TC-CLI-001 | check 命令 | `sensi-check check /dir -o report.html` | 生成报告 | 文件存在，内容有效 |
| TC-CLI-002 | check + workers | `sensi-check check /dir -o r.html -w 2` | 使用 2 worker | 扫描完成 |
| TC-CLI-003 | check + context | `sensi-check check /dir -o r.html --context 20` | 上下文 20 字符 | 报告中上下文长度正确 |
| TC-CLI-004 | check + no archives | `sensi-check check /dir -o r.html -n` | 不检查压缩包 | 压缩包被跳过 |
| TC-CLI-005 | add 命令 | `sensi-check add "词1" "词2"` | 添加 2 个关键词 | 配置中新增 |
| TC-CLI-006 | remove 命令 | `sensi-check remove "词1"` | 删除关键词 | 配置中移除 |
| TC-CLI-007 | list 命令 | `sensi-check list` | 输出关键词列表 | 文本输出正确 |
| TC-CLI-008 | config show-ocr | `sensi-check config show-ocr` | 输出 OCR 状态 | 显示 on/off |
| TC-CLI-009 | config set-ocr on | `sensi-check config set-ocr on` | 开启 OCR | 配置更新 |
| TC-CLI-010 | 空关键词 | `sensi-check check /dir -o r.html` 无关键词 | 提示错误，退出 | 不执行扫描 |
| TC-CLI-011 | 未知子命令 | `sensi-check foo` | 提示帮助信息 | 退出码非 0 |
| TC-CLI-012 | --help | `sensi-check --help` | 显示帮助 | 包含所有子命令 |

### 3.2 Web API 测试 (`tests/test_web.py`)

| 用例 ID | 测试内容 | 输入 | 预期输出 | 验收标准 |
|---------|---------|------|---------|---------|
| TC-WEB-001 | 页面加载 | GET / | 200 OK，HTML 内容 | 页面正常渲染 |
| TC-WEB-002 | 获取关键词 | GET /api/keywords | 200 OK，JSON 列表 | 数据正确 |
| TC-WEB-003 | 添加关键词 | POST /api/keywords `{"word": "测试"}` | 200 OK | 配置更新 |
| TC-WEB-004 | 添加空关键词 | POST /api/keywords `{"word": ""}` | 400 Bad Request | 拒绝空词 |
| TC-WEB-005 | 删除关键词 | DELETE /api/keywords/测试 | 200 OK | 配置更新 |
| TC-WEB-006 | 删除不存在的词 | DELETE /api/keywords/不存在的 | 404 Not Found | 正确响应 |
| TC-WEB-007 | 设置 OCR | PUT /api/config/ocr `{"enabled": true}` | 200 OK | 配置更新 |
| TC-WEB-008 | 绑定地址 | 启动服务 | 绑定 127.0.0.1:8000 | 不暴露外部 |
| TC-WEB-009 | CLI 与 Web 共享 | Web 添加关键词 → CLI list | CLI 能看到新词 | 数据一致 |

---

## Phase 4 测试验收

### 4.1 集成测试 (`tests/test_integration.py`)

| 用例 ID | 测试内容 | 输入 | 预期输出 | 验收标准 |
|---------|---------|------|---------|---------|
| TC-INT-001 | 全格式扫描 | 各格式文件各 1 个 | 全部扫描完成 | 报告包含所有匹配 |
| TC-INT-002 | 混合目录 | txt/pdf/docx/zip 混合 | 正确分类结果和失败文件 | 报告结构正确 |
| TC-INT-003 | 大目录 | 10000 个文件 | 扫描完成，结果正确 | 内存稳定，无崩溃 |
| TC-INT-004 | 边界文件 | 0 字节文件、超大文件(100MB)、符号链接 | 正确处理 | 报告中有对应记录 |
| TC-INT-005 | 权限不足 | 受限目录 | 跳过并记录 | 不崩溃 |
| TC-INT-6 | 端到端流程 | 完整扫描 → 报告生成 | 报告有效 | 人工可验证 |
| TC-INT-007 | Web + CLI 完整流程 | Web 管理关键词 → CLI 扫描 | 结果正确 | 全流程贯通 |

### 4.2 错误处理测试

| 用例 ID | 测试内容 | 输入 | 预期输出 | 验收标准 |
|---------|---------|------|---------|---------|
| TC-ERR-001 | 目录不存在 | 不存在的目录 | 提示错误 | 退出码非 0 |
| TC-ERR-002 | 输出路径无权限 | 只读目录 | 提示错误 | 退出码非 0 |
| TC-ERR-003 | 关键词文件损坏 | 损坏的 keywords.json | 使用默认空配置 | 不崩溃 |
| TC-ERR-004 | 磁盘空间不足 | 磁盘满 | 提示错误 | 清理临时文件 |

### 4.3 性能验收

| 用例 ID | 测试内容 | 指标 | 验收标准 |
|---------|---------|------|---------|
| TC-PERF-001 | 1000 个 txt 文件扫描 | 耗时 | ≤ 30 秒（4 核） |
| TC-PERF-002 | 100 个 PDF 文件扫描 | 耗时 | ≤ 60 秒（4 核） |
| TC-PERF-003 | 100 个 docx 文件扫描 | 耗时 | ≤ 30 秒（4 核） |
| TC-PERF-004 | 内存占用 | 峰值内存 | ≤ 500MB |
| TC-PERF-005 | 并行加速比 | 1 worker vs 4 worker | ≥ 2.5x |

---

## 测试执行命令

```bash
# 运行所有测试
pytest tests/ -v

# 仅运行单元测试
pytest tests/ -v -m unit

# 仅运行集成测试
pytest tests/ -v -m integration

# 覆盖率报告
pytest tests/ --cov=src --cov-report=html

# 单文件单用例
pytest tests/test_checker.py::test_match_keywords -v
```
