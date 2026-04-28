import os
import re
import time
from collections import defaultdict
from html import escape

from .checker import FileResult


def generate_report(scan_result: dict, output_path: str, scan_dir: str, keywords: list[str], elapsed: float = 0.0) -> None:
    results: list[FileResult] = scan_result.get("results", [])
    failures: list[FileResult] = scan_result.get("failures", [])
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    total_matches = sum(len(r.matches) for r in results)
    total_files = len(results) + len(failures)
    scan_time = time.strftime("%Y-%m-%d %H:%M:%S")
    elapsed_str = f"{elapsed:.2f}s"

    tree = _build_tree(results, scan_dir)
    tree_html = _render_tree(tree, 0)
    failures_html = _render_failures(failures, scan_dir)

    html = _HTML_TEMPLATE.format(
        scan_time=scan_time,
        elapsed_str=elapsed_str,
        scan_dir=escape(scan_dir),
        keyword_count=len(keywords),
        total_files=total_files,
        total_matches=total_matches,
        tree_html=tree_html,
        failures_html=failures_html,
        failure_count=len(failures),
        no_results_style="display:none" if results else "",
        no_results_msg="未发现敏感词" if not results else "",
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


def _build_tree(results: list[FileResult], scan_dir: str) -> dict:
    tree = {}
    for fr in results:
        rel = os.path.relpath(fr.file_path, scan_dir)
        parts = rel.replace("\\", "/").split("/")
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = fr
    return tree


def _has_matches(node) -> bool:
    if isinstance(node, FileResult):
        return bool(node.matches)
    if isinstance(node, dict):
        return any(_has_matches(v) for v in node.values())
    return False


def _render_tree(node: dict, level: int, breadcrumb: list = None) -> str:
    if breadcrumb is None:
        breadcrumb = []
    html_parts = []
    dirs = sorted(k for k, v in node.items() if isinstance(v, dict))
    files = sorted(k for k, v in node.items() if isinstance(v, FileResult))

    indent = min(level * 16, 64)

    for d in dirs:
        child_breadcrumb = breadcrumb + [d]
        has = _has_matches(node[d])
        display = "block" if has else "none"
        arrow_cls = "open" if has else ""
        if level >= 3:
            child_html = _render_tree(node[d], level, child_breadcrumb)
            crumb = " › ".join(escape(p) for p in child_breadcrumb)
            html_parts.append(
                f'<div class="dir" style="padding-left:{indent}px">'
                f'<div class="dir-header" onclick="toggle(this)">'
                f'<span class="arrow {arrow_cls}">&#9654;</span> {crumb}/</div>'
                f'<div class="dir-content" style="display:{display}">{child_html}</div></div>'
            )
        else:
            child_html = _render_tree(node[d], level + 1, child_breadcrumb)
            html_parts.append(
                f'<div class="dir" style="padding-left:{indent}px">'
                f'<div class="dir-header" onclick="toggle(this)">'
                f'<span class="arrow {arrow_cls}">&#9654;</span> {escape(d)}/</div>'
                f'<div class="dir-content" style="display:{display}">{child_html}</div></div>'
            )

    for fname in files:
        fr = node[fname]
        match_html = ""
        for m in fr.matches:
            ctx = _highlight_keyword(escape(m.context), escape(m.keyword))
            line_info = f'行 {m.line_number}' if m.line_number else ''
            match_html += (
                f'<div class="match">'
                f'<span class="line-num">{escape(line_info)}</span>'
                f'<span class="keyword">{escape(m.keyword)}</span>'
                f'<span class="context">…{ctx}…</span></div>'
            )
        html_parts.append(
            f'<div class="file" style="padding-left:{indent}px">'
            f'<div class="file-name">&#128196; {escape(fname)}</div>'
            f'<div class="matches">{match_html}</div></div>'
        )

    return "\n".join(html_parts)


def _highlight_keyword(context: str, keyword: str) -> str:
    if not keyword:
        return context
    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
    return pattern.sub(f'<mark class="highlight">{keyword}</mark>', context)


def _render_failures(failures: list[FileResult], scan_dir: str) -> str:
    if not failures:
        return ""
    items = []
    for fr in failures:
        rel = os.path.relpath(fr.file_path, scan_dir)
        items.append(
            f'<div class="failure-item">'
            f'<span class="failure-path">{escape(rel)}</span>'
            f' — <span class="failure-reason">{escape(fr.error)}</span></div>'
        )
    header = (
        '<div class="dir"><div class="dir-header failure-header" onclick="toggle(this)">'
        f'<span class="arrow">&#9654;</span> 检查失败 ({len(failures)})</div>'
        f'<div class="dir-content" style="display:none">'
    )
    return header + "\n".join(items) + "</div></div>"


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>保密检查报告</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans SC", sans-serif; background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%); color: #e1e1e6; margin: 20px; }}
.container {{ max-width: 100%; margin: 0 auto; background: rgba(30, 30, 46, 0.85); padding: 30px; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.06); box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3); backdrop-filter: blur(10px); }}
h1 {{ background: linear-gradient(90deg, #60a5fa, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; border-bottom: 1px solid rgba(255, 255, 255, 0.06); padding-bottom: 10px; }}
.summary {{ background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.06); padding: 15px; border-radius: 8px; margin: 15px 0; }}
.summary span {{ margin-right: 20px; color: #8b8ba0; }}
.summary .num {{ color: #60a5fa; font-weight: bold; }}
.dir-header {{ cursor: pointer; padding: 8px 12px; background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 8px; margin: 4px 0; font-weight: bold; color: #c4c4d8; transition: background 0.2s; }}
.dir-header:hover {{ background: rgba(255, 255, 255, 0.06); }}
.dir-content {{ padding-left: 16px; }}
.arrow {{ display: inline-block; width: 12px; transition: transform 0.2s; color: #60a5fa; }}
.arrow.open {{ transform: rotate(90deg); }}
.file {{ margin: 8px 0; }}
.file-name {{ font-weight: bold; color: #e1e1e6; padding: 4px 0; overflow-wrap: break-word; }}
.match {{ padding: 6px 12px; margin: 4px 0; background: rgba(255, 255, 255, 0.03); border-left: 3px solid #f39c12; border-radius: 0 4px 4px 0; overflow-x: auto; }}
.keyword {{ color: #f87171; font-weight: bold; margin-right: 8px; }}
.line-num {{ color: #8b8ba0; font-size: 0.85em; margin-right: 8px; }}
.context {{ color: #c4c4d8; overflow-wrap: break-word; }}
mark.highlight {{ background: rgba(248, 113, 113, 0.25); color: #f87171; padding: 1px 4px; border-radius: 3px; }}
.failure-header {{ background: rgba(239, 68, 68, 0.1); border-color: rgba(239, 68, 68, 0.3); }}
.failure-header:hover {{ background: rgba(239, 68, 68, 0.2); }}
.failure-item {{ padding: 6px 12px; margin: 4px 0; background: rgba(239, 68, 68, 0.05); border-left: 3px solid #f87171; border-radius: 0 4px 4px 0; }}
.failure-path {{ font-weight: bold; color: #f87171; overflow-wrap: break-word; }}
.failure-reason {{ color: #8b8ba0; }}
.no-results {{ text-align: center; color: #5a5a72; font-size: 18px; padding: 40px; }}
@media (max-width: 600px) {{ .container {{ padding: 16px; }} }}
</style>
</head>
<body>
<div class="container">
<h1>保密检查报告</h1>
<div class="summary">
<span>检查时间: {scan_time}</span>
<span>检查用时: <span class="num">{elapsed_str}</span></span>
<span>检查目录: {scan_dir}</span>
<span>关键词数量: <span class="num">{keyword_count}</span></span>
<span>扫描文件数: <span class="num">{total_files}</span></span>
<span>匹配总数: <span class="num">{total_matches}</span></span>
<span>失败文件数: <span class="num">{failure_count}</span></span>
</div>
<div class="no-results" style="{no_results_style}">{no_results_msg}</div>
<div class="results">{tree_html}</div>
<div class="failures">{failures_html}</div>
</div>
<script>
function toggle(el) {{
    var content = el.nextElementSibling;
    var arrow = el.querySelector('.arrow');
    if (content.style.display === 'none') {{
        content.style.display = 'block';
        arrow.classList.add('open');
    }} else {{
        content.style.display = 'none';
        arrow.classList.remove('open');
    }}
}}
</script>
</body>
</html>"""
