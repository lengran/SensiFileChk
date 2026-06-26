# 构建与部署指南

## 1. 环境准备

### 1.1 系统依赖

| 功能 | Linux (Debian/Ubuntu) | Linux (RHEL/CentOS) | macOS | Windows |
|------|----------------------|---------------------|-------|---------|
| 旧版 Office | `apt install antiword` | `yum install antiword` | `brew install catdoc` | `pip install pywin32` |
| RAR 解压 | `apt install unrar` | `yum install unrar` | `brew install unrar` | 安装 UnRAR for Windows |
| OCR | `apt install tesseract-ocr` + `tesseract-ocr-chi-sim` | `yum install tesseract` + 语言包 | `brew install tesseract` + `tesseract-lang` | 安装 Tesseract OCR + 中文语言包 |

### 1.2 Python 环境

```bash
python3 -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows
pip install -e .
```

开发模式额外依赖：

```bash
pip install -e ".[dev]"
```

## 2. PyInstaller 打包

### 2.1 安装 PyInstaller

```bash
pip install pyinstaller
```

### 2.2 单文件模式

```bash
pyinstaller --onefile \
  --name sensi-check \
  --add-data "web_admin/templates:web_admin/templates" \
  --hidden-import=fitz \
  --hidden-import=pytesseract \
  --hidden-import=PIL \
  --hidden-import=docx \
  --hidden-import=pptx \
  --hidden-import=openpyxl \
  --hidden-import=rarfile \
  --hidden-import=py7zr \
  src/__main__.py
```

生成的可执行文件位于 `dist/sensi-check`。

### 2.3 目录模式（推荐，启动更快）

```bash
pyinstaller --onedir \
  --name sensi-check \
  --add-data "web_admin/templates:web_admin/templates" \
  --hidden-import=fitz \
  --hidden-import=pytesseract \
  --hidden-import=PIL \
  --hidden-import=docx \
  --hidden-import=pptx \
  --hidden-import=openpyxl \
  --hidden-import=rarfile \
  --hidden-import=py7zr \
  src/__main__.py
```

生成的目录位于 `dist/sensi-check/`，主可执行文件为 `dist/sensi-check/sensi-check`。

### 2.4 注意事项

- 打包后的程序仍需要系统安装 `unrar`、`tesseract-ocr`、`antiword`/`catdoc` 等外部工具
- `py7zr` 为纯 Python 实现，会被自动打包
- `pywin32` 仅 Windows 可用，跨平台打包时需排除
- 建议在目标平台上构建，避免交叉编译问题

## 3. 部署方案

### 3.1 直接部署（虚拟环境）

```bash
# 1. 克隆仓库
git clone <repo-url> /opt/sensi-check
cd /opt/sensi-check

# 2. 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# 3. 验证安装
sensi-check --help
sensi-check list

# 4. 执行扫描
sensi-check check /path/to/scan -o report.html
```

### 3.2 PyInstaller 部署

```bash
# 1. 在构建机上打包
pyinstaller --onefile --name sensi-check ...

# 2. 复制到目标机器
scp dist/sensi-check user@target:/usr/local/bin/

# 3. 确保系统依赖已安装
apt install antiword unrar tesseract-ocr

# 4. 执行
sensi-check check /path/to/scan -o report.html
```

### 3.3 systemd 服务（Web 管理端）

创建 `/etc/systemd/system/sensi-check-web.service`：

```ini
[Unit]
Description=SensiFileChk Web 管理端
After=network.target

[Service]
Type=simple
User=sensi-check
Group=sensi-check
WorkingDirectory=/opt/sensi-check
ExecStart=/opt/sensi-check/.venv/bin/sensi-check serve --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启用并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable sensi-check-web
sudo systemctl start sensi-check-web
sudo systemctl status sensi-check-web
```

### 3.4 Nginx 反向代理（可选）

如需通过域名或 HTTPS 访问 Web 管理端：

```nginx
server {
    listen 443 ssl;
    server_name sensi-check.example.com;

    ssl_certificate     /etc/ssl/certs/sensi-check.pem;
    ssl_certificate_key /etc/ssl/private/sensi-check.key;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

> **安全提示**：Web 管理端默认绑定 `127.0.0.1`，不直接暴露到外部网络。通过 Nginx 反向代理时，建议添加访问认证（HTTP Basic Auth 或 SSO）。

## 4. 配置文件管理

### 4.1 敏感词库位置

默认路径：`<安装目录>/config/keywords.json`

```json
{
  "keywords": ["敏感词1", "敏感词2"],
  "ocr_enabled": false
}
```

### 4.2 多实例共享词库

多个实例共享同一词库时，需确保：

1. 所有实例指向同一个 `config/keywords.json` 文件路径
2. 配置模块已使用文件锁（`fcntl`/`msvcrt`）+ `threading.Lock` 保护并发安全
3. 避免同时通过 CLI 和 Web 修改同一关键词

## 5. 常见问题

### 5.1 PyInstaller 打包后运行报 ModuleNotFoundError

添加 `--hidden-import` 参数，或将缺失模块加入 `.spec` 文件的 `hiddenimports` 列表。

### 5.2 RAR 文件解压失败

确保系统已安装 `unrar` 命令行工具（非 `unrar-free`，需 RARLAB 官方版本）：

```bash
# Ubuntu
sudo apt install unrar
# macOS
brew install unrar
```

### 5.3 OCR 中文识别效果差

安装中文语言包并确认 Tesseract 可用：

```bash
tesseract --list-langs  # 应包含 chi_sim
```

### 5.4 旧版 Office 文件解析失败

- Linux：确认 `antiword` 已安装（`which antiword`）
- macOS：确认 `catdoc` 已安装（`which catdoc`）
- Windows：确认 `pywin32` 已安装（`pip show pywin32`）
