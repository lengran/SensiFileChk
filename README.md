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

### 1. 启动 Web 管理端

```bash
sensi-check serve
```

浏览器访问 http://127.0.0.1:8000

### 2. 通过 Web 管理敏感词

- **添加关键词**：在输入框中输入关键词，点击添加或按回车
- **删除关键词**：点击每个关键词右侧的删除按钮
- **OCR 开关**：通过页面上的开关控件开启/关闭 PDF 图片文字识别

### 3. 通过 Web 生成扫描命令

在页面的"CLI 命令生成器"区域：
1. 填写扫描目录路径和报告输出路径
2. 选择 worker 数量（或勾选"自动"使用 CPU 核心数）
3. 点击复制按钮，将命令粘贴到终端执行

### 4. 执行扫描

扫描完成后在指定路径生成 HTML 报告，包含敏感词高亮、上下文、行号和目录折叠。

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
sensi-check add <关键词1> [关键词2] ...
sensi-check remove <关键词>
sensi-check list
sensi-check list --count
```

### 配置管理 (config)

```bash
sensi-check config show-ocr
sensi-check config set-ocr on|off
```

### Web 管理端 (serve)

```bash
sensi-check serve [--host 127.0.0.1] [--port 8000]
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
