"""
敏感词 Web 管理端 - FastAPI 应用
提供关键词管理和 OCR 配置的管理界面
"""
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# 调整导入路径，使 web-admin 可以独立运行或作为模块被导入
if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.config import load_keywords, save_keywords, add_keyword, remove_keyword
else:
    from src.config import load_keywords, save_keywords, add_keyword, remove_keyword

# 获取模板目录路径
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

# 创建 FastAPI 应用
app = FastAPI(title="敏感词管理端", description="Web 界面管理敏感词库")

# 配置 Jinja2 模板
templates = Jinja2Templates(directory=TEMPLATE_DIR)


# ============= 数据模型 =============
class KeywordRequest(BaseModel):
    """添加关键词请求体"""
    word: str


class OcrConfigRequest(BaseModel):
    """OCR 配置请求体"""
    enabled: bool


class KeywordListResponse(BaseModel):
    """关键词列表响应"""
    keywords: list[str]
    count: int
    ocr_enabled: bool


class CliCommandResponse(BaseModel):
    """CLI 命令生成响应"""
    command: str


# ============= 前端页面路由 =============
@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    """
    管理页面主页
    渲染敏感词管理 HTML 页面
    """
    from fastapi.responses import HTMLResponse
    template = templates.get_template("index.html")
    content = template.render(request=request)
    return HTMLResponse(content=content)


# ============= API 路由 - 关键词管理 =============
@app.get("/api/keywords", response_model=KeywordListResponse)
async def get_keywords():
    """
    获取关键词列表
    返回所有敏感词和 OCR 开关状态
    """
    config = load_keywords()
    return KeywordListResponse(
        keywords=config["keywords"],
        count=len(config["keywords"]),
        ocr_enabled=config["ocr_enabled"]
    )


@app.post("/api/keywords")
async def add_keyword_api(request: KeywordRequest):
    """
    添加关键词
    添加成功后返回更新后的关键词列表
    """
    if not request.word or not request.word.strip():
        raise HTTPException(status_code=400, detail="关键词不能为空")

    word = request.word.strip()
    add_keyword(word)

    config = load_keywords()
    return KeywordListResponse(
        keywords=config["keywords"],
        count=len(config["keywords"]),
        ocr_enabled=config["ocr_enabled"]
    )


@app.delete("/api/keywords/{word}")
async def remove_keyword_api(word: str):
    """
    删除关键词
    删除成功后返回更新后的关键词列表
    """
    if not word:
        raise HTTPException(status_code=400, detail="关键词不能为空")

    remove_keyword(word)

    config = load_keywords()
    return KeywordListResponse(
        keywords=config["keywords"],
        count=len(config["keywords"]),
        ocr_enabled=config["ocr_enabled"]
    )


# ============= API 路由 - 配置管理 =============
@app.put("/api/config/ocr")
async def set_ocr_config(request: OcrConfigRequest):
    """
    设置 OCR 开关
    启用或禁用 PDF 图片 OCR 识别功能
    """
    config = load_keywords()
    save_keywords(config["keywords"], request.enabled)

    return {
        "ocr_enabled": request.enabled,
        "message": f"OCR 已{'开启' if request.enabled else '关闭'}"
    }


@app.get("/api/config/ocr")
async def get_ocr_config():
    """
    获取 OCR 开关状态
    """
    config = load_keywords()
    return {
        "ocr_enabled": config["ocr_enabled"],
        "status": "开启" if config["ocr_enabled"] else "关闭"
    }


# ============= CLI 命令生成器 =============
@app.get("/api/cli/generate")
async def generate_cli_command():
    """
    生成 CLI 命令
    根据当前配置生成对应的 sensi-check 命令示例
    """
    config = load_keywords()
    keywords = config["keywords"]

    if keywords:
        # 根据关键词数量决定使用哪种命令形式
        if len(keywords) <= 3:
            keyword_args = " ".join(f'"{kw}"' for kw in keywords)
            command = f"sensi-check check /path/to/scan -o report.html -n"
            setup_cmd = f"sensi-check add {keyword_args}"
        else:
            command = f"sensi-check check /path/to/scan -o report.html -n"
            setup_cmd = f"# 已通过配置文件设置 {len(keywords)} 个关键词"
    else:
        command = "sensi-check check /path/to/scan -o report.html -n"
        setup_cmd = "# 请先添加关键词"

    return CliCommandResponse(
        command=f"# 设置关键词\n{setup_cmd}\n\n# 执行扫描\n{command}"
    )


# ============= 应用入口 =============
def run_server(host: str = "127.0.0.1", port: int = 8000):
    """
    启动 Web 管理端服务器
    """
    import uvicorn
    print(f"启动敏感词 Web 管理端...")
    print(f"访问地址: http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
