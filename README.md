# 保密检查工具 (SensiFileChk)

一个轻量级、高性能的本地文件敏感词检查工具，支持多格式文件扫描、多核并行处理，检查结果以 HTML 报告输出，配有 Web 敏感词管理界面。

## 功能特性

- **多格式支持**: 支持 .txt, .pdf, .doc/.docx, .xls/.xlsx, .ppt/.pptx 等常见文档格式
- **压缩包扫描**: 支持 .zip, .tar/.tar.gz, .rar, .7z 压缩包的递归解压扫描
- **多核并行**: 使用多进程并行扫描，充分利用多核 CPU
- **英文大小写不敏感**: 英文关键词自动忽略大小写匹配
- **PDF OCR**: 可选的图片 PDF 文字识别（基于 Tesseract）
- **HTML 报告**: 生成美观的 HTML 报告，支持目录折叠、敏感词高亮、行号显示
- **Web 管理端**: 浏览器端管理敏感词库和 OCR 配置

## 安装

### 系统依赖

**Linux (Ubuntu/Debian):**
```bash
sudo apt install antiword unrar tesseract-ocr
# OCR 中文识别需额外安装中文语言包
sudo apt install tesseract-ocr-chi-sim
# 或手动下载到 tessdata 目录
sudo cp chi_sim.traineddata /usr/share/tesseract-ocr/4.00/tessdata/
```

**macOS:**
```bash
brew install catdoc unrar tesseract
# OCR 中文识别需额外安装中文语言包
brew install tesseract-lang
# 或手动下载到 tessdata 目录
cp chi_sim.traineddata $(brew --prefix)/share/tessdata/
```

### Python 环境

```bash
# 创建虚拟环境（推荐）
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS

# 安装依赖
pip install -e .
```

## 快速开始

### 1. 添加敏感词

```bash
# 添加单个关键词
sensi-check add "国家机密"

# 添加多个关键词
sensi-check add "绝密" "内部资料" "敏感信息"

# 查看已有关键词
sensi-check list
```

### 2. 执行扫描

```bash
# 基础扫描
sensi-check check /path/to/scan -o report.html

# 使用多进程加速
sensi-check check /path/to/scan -o report.html -w 4

# 显示扫描过程
sensi-check check /path/to/scan -o report.html --verbose
```

### 3. 启动 Web 管理端

```bash
# 启动 Web 服务
sensi-check serve
```

访问 http://127.0.0.1:8000 管理敏感词

## 命令参考

### 扫描命令 (check)

```
sensi-check check <目录路径> -o <报告路径> [选项]

选项:
  -o, --output       必需，HTML 报告输出路径
  -w, --workers      并行 worker 数量（默认: 1）
  -n, --no-archives  不检查压缩包内容
  --verbose          显示详细扫描过程
```

### 关键词管理 (add/remove/list)

```bash
# 添加关键词
sensi-check add <关键词1> [关键词2] ...

# 删除关键词
sensi-check remove <关键词>

# 列出所有关键词
sensi-check list

# 列出关键词并显示数量
sensi-check list --count
```

### 配置管理 (config)

```bash
# 查看 OCR 状态
sensi-check config show-ocr

# 开启/关闭 OCR
sensi-check config set-ocr on|off
```

## 支持的文件格式

| 格式类型 | 扩展名 | 依赖 |
|----------|--------|------|
| 纯文本 | .txt | 内置 |
| PDF | .pdf | pymupdf |
| Word 新版 | .docx | python-docx |
| Word 旧版 | .doc | antiword |
| Excel 新版 | .xlsx | openpyxl |
| PowerPoint 新版 | .pptx | python-pptx |
| ZIP 压缩包 | .zip | 内置 |
| RAR 压缩包 | .rar | rarfile |
| 7Z 压缩包 | .7z | py7zr |

## 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 覆盖率测试
pytest tests/ --cov=src --cov-report=html
```

## 项目结构

```
├── config/                 # 配置文件目录
├── src/                    # 源代码
│   ├── cli.py              # CLI 入口
│   ├── checker.py          # 扫描引擎
│   ├── config.py           # 配置读写
│   ├── report.py           # 报告生成
│   └── parsers/            # 文件解析器
├── web_admin/              # Web 管理端
└── tests/                  # 测试文件
```

## 许可证

MIT License
