import os
import time
from collections import defaultdict
from html import escape

from .checker import FileResult


def generate_report(scan_result: dict, output_path: str, scan_dir: str, keywords: list[str]) -> None:
    results: list[FileResult] = scan_result.get("results", [])
    failures: list[FileResult] = scan_result.get("failures", [])
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    total_matches = sum(len(r.matches) for r in results)
    total_files = len(results) + len(failures)
    scan_time = time.strftime("%Y-%m-%d %H:%M:%S")

    tree = _build_tree(results, scan_dir)
    tree_html = _render_tree(tree, 0)
    failures_html = _render_failures(failures, scan_dir)

    html = _HTML_TEMPLATE.format(
        scan_time=scan_time,
        scan_dir=escape(scan_dir),
        keyword_count=len(keywords),
        total_files=total_files,
        total_matches=total_matches,
        tree_html=tree_html,
        failures_html=failures_html,
        failure_count=len(failures),
        no_results_style="display:none" if results else "",
        no_results_msg="未发现敏感词" if not results and not failures else "",
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


def _render_tree(node: dict, level: int) -> str:
    html_parts = []
    dirs = sorted(k for k, v in node.items() if isinstance(v, dict))
    files = sorted(k for k, v in node.items() if isinstance(v, FileResult))

    for d in dirs:
        child_html = _render_tree(node[d], level + 1)
        html_parts.append(
            f'<div class="dir" style="margin-left:{level * 20}px">'
            f'<div class="dir-header" onclick="toggle(this)">'
            f'<span class="arrow">&#9654;</span> {escape(d)}/</div>'
            f'<div class="dir-content" style="display:none">{child_html}</div></div>'
        )

    for fname in files:
        fr = node[fname]
        match_html = ""
        for m in fr.matches:
            ctx = _highlight_keyword(escape(m.context), escape(m.keyword))
            match_html += (
                f'<div class="match"><span class="keyword">{escape(m.keyword)}</span>'
                f'<span class="context">…{ctx}…</span></div>'
            )
        html_parts.append(
            f'<div class="file" style="margin-left:{level * 20}px">'
            f'<div class="file-name">&#128196; {escape(fname)}</div>'
            f'<div class="matches">{match_html}</div></div>'
        )

    return "\n".join(html_parts)


def _highlight_keyword(context: str, keyword: str) -> str:
    return context.replace(keyword, f'<mark class="highlight">{keyword}</mark>')


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
<title>保密检查报告</title>
<style>
body {{ font-family: "Microsoft YaHei", "PingFang SC", sans-serif; margin: 20px; background: #f5f5f5; }}
.container {{ max-width: 960px; margin: 0 auto; background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
h1 {{ color: #333; border-bottom: 2px solid #e74c3c; padding-bottom: 10px; }}
.summary {{ background: #f9f9f9; padding: 15px; border-radius: 4px; margin: 15px 0; }}
.summary span {{ margin-right: 20px; color: #555; }}
.summary .num {{ color: #e74c3c; font-weight: bold; }}
.dir-header {{ cursor: pointer; padding: 6px 10px; background: #eef; border-radius: 4px; margin: 4px 0; font-weight: bold; }}
.dir-header:hover {{ background: #dde; }}
.dir-content {{ padding-left: 10px; }}
.arrow {{ display: inline-block; width: 12px; transition: transform 0.2s; }}
.arrow.open {{ transform: rotate(90deg); }}
.file {{ margin: 8px 0; }}
.file-name {{ font-weight: bold; color: #2c3e50; padding: 4px 0; }}
.match {{ padding: 4px 10px; margin: 2px 0; background: #fef9e7; border-left: 3px solid #f39c12; }}
.keyword {{ color: #e74c3c; font-weight: bold; margin-right: 8px; }}
.context {{ color: #555; }}
mark.highlight {{ background: #e74c3c; color: #fff; padding: 1px 3px; border-radius: 2px; }}
.failure-header {{ background: #fee; }}
.failure-header:hover {{ background: #fdd; }}
.failure-item {{ padding: 6px 10px; margin: 2px 0; background: #fff5f5; border-left: 3px solid #e74c3c; }}
.failure-path {{ font-weight: bold; color: #c0392b; }}
.failure-reason {{ color: #888; }}
.no-results {{ text-align: center; color: #999; font-size: 18px; padding: 40px; }}
</style>
</head>
<body>
<div class="container">
<h1>保密检查报告</h1>
<div class="summary">
<span>检查时间: {scan_time}</span>
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
