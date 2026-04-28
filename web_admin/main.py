"""
敏感词 Web 管理端 - FastAPI 应用
提供关键词管理和 OCR 配置的管理界面
"""
import json
import os
import platform
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from src.config import load_keywords, save_keywords, add_keyword, remove_keyword

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

app = FastAPI(title="敏感词管理端", description="Web 界面管理敏感词库")

templates = Jinja2Templates(directory=TEMPLATE_DIR)
templates.env.filters['tojson'] = lambda value: json.dumps(value, ensure_ascii=False)


class KeywordRequest(BaseModel):
    word: str


class OcrConfigRequest(BaseModel):
    enabled: bool


class KeywordListResponse(BaseModel):
    keywords: list[str]
    count: int
    ocr_enabled: bool


class CliCommandResponse(BaseModel):
    command: str


@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    config = load_keywords()
    os_type = "windows" if platform.system() == "Windows" else "linux"
    template = templates.get_template("index.html")
    content = template.render(
        request=request,
        initial_keywords=config["keywords"],
        initial_ocr_enabled=config["ocr_enabled"],
        os_type=os_type,
    )
    return HTMLResponse(content=content)


@app.get("/api/keywords", response_model=KeywordListResponse)
async def get_keywords():
    config = load_keywords()
    return KeywordListResponse(
        keywords=config["keywords"],
        count=len(config["keywords"]),
        ocr_enabled=config["ocr_enabled"]
    )


@app.post("/api/keywords")
async def add_keyword_api(request: KeywordRequest):
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
    if not word:
        raise HTTPException(status_code=400, detail="关键词不能为空")

    removed = remove_keyword(word)
    if not removed:
        raise HTTPException(status_code=404, detail=f"关键词 '{word}' 不存在")

    config = load_keywords()
    return KeywordListResponse(
        keywords=config["keywords"],
        count=len(config["keywords"]),
        ocr_enabled=config["ocr_enabled"]
    )


@app.put("/api/config/ocr")
async def set_ocr_config(request: OcrConfigRequest):
    config = load_keywords()
    save_keywords(config["keywords"], request.enabled)

    return {
        "ocr_enabled": request.enabled,
        "message": f"OCR 已{'开启' if request.enabled else '关闭'}"
    }


@app.get("/api/config/ocr")
async def get_ocr_config():
    config = load_keywords()
    return {
        "ocr_enabled": config["ocr_enabled"],
        "status": "开启" if config["ocr_enabled"] else "关闭"
    }


@app.get("/api/cli/generate")
async def generate_cli_command(
    auto_workers: bool = True,
    workers: int = 0,
    scan_path: str = "",
    output_path: str = "",
):
    def _quote_if_needed(p: str) -> str:
        if " " in p and not (p.startswith('"') and p.endswith('"')):
            return f'"{p}"'
        return p

    scan = _quote_if_needed(scan_path) if scan_path else "/path/to/scan"
    output = _quote_if_needed(output_path) if output_path else "report.html"
    command = f"sensi-check check {scan} -o {output}"
    if not auto_workers and workers > 0:
        command += f" -w {workers}"
    return CliCommandResponse(command=command)


def run_server(host: str = "127.0.0.1", port: int = 8000):
    import uvicorn
    print(f"启动敏感词 Web 管理端...")
    print(f"访问地址: http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
