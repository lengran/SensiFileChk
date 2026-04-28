import argparse
import os
import sys
import time

from .checker import scan_directory
from .config import load_keywords, add_keyword, add_keywords, remove_keyword, save_keywords
from .report import generate_report


def main():
    parser = argparse.ArgumentParser(prog="sensi-check", description="保密检查工具")
    subparsers = parser.add_subparsers(dest="command")

    check_parser = subparsers.add_parser("check", help="扫描目录中的敏感词")
    check_parser.add_argument("dir", help="要扫描的目录路径")
    check_parser.add_argument("-o", "--output", required=True, help="HTML 报告输出路径")
    check_parser.add_argument("-w", "--workers", type=int, default=None, help="并行 worker 数量（默认: CPU 核心数）")
    check_parser.add_argument("--context", type=int, default=50, help="上下文字符数")
    check_parser.add_argument("-n", "--no-archives", action="store_true", help="不检查压缩包内容")
    check_parser.add_argument("--verbose", action="store_true", help="显示详细扫描过程")

    add_parser = subparsers.add_parser("add", help="添加关键词")
    add_parser.add_argument("words", nargs="+", help="要添加的关键词")

    remove_parser = subparsers.add_parser("remove", help="删除关键词")
    remove_parser.add_argument("word", help="要删除的关键词")

    list_parser = subparsers.add_parser("list", help="列出所有关键词")
    list_parser.add_argument("--count", action="store_true", help="显示关键词数量")

    serve_parser = subparsers.add_parser("serve", help="启动 Web 管理端")
    serve_parser.add_argument("--host", default="127.0.0.1", help="绑定地址 (默认: 127.0.0.1)")
    serve_parser.add_argument("--port", type=int, default=8000, help="端口 (默认: 8000)")

    config_parser = subparsers.add_parser("config", help="配置管理")
    config_sub = config_parser.add_subparsers(dest="config_command")
    config_sub.add_parser("show-ocr", help="查看 OCR 开关状态")
    set_ocr = config_sub.add_parser("set-ocr", help="设置 OCR 开关")
    set_ocr.add_argument("value", choices=["on", "off"], help="on 或 off")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "check":
        _cmd_check(args)
    elif args.command == "add":
        _cmd_add(args)
    elif args.command == "remove":
        _cmd_remove(args)
    elif args.command == "list":
        _cmd_list(args)
    elif args.command == "config":
        _cmd_config(args)
    elif args.command == "serve":
        _cmd_serve(args)


def _cmd_check(args):
    config = load_keywords()
    keywords = config["keywords"]
    if not keywords:
        print("错误: 关键词列表为空，请先添加关键词", file=sys.stderr)
        sys.exit(1)

    start = time.time()
    num_workers = args.workers if args.workers is not None else os.cpu_count() or 1
    result = scan_directory(
        args.dir,
        keywords,
        context_chars=args.context,
        num_workers=num_workers,
        ocr_enabled=config["ocr_enabled"],
        check_archives=not args.no_archives,
        verbose=args.verbose,
    )
    elapsed = time.time() - start

    generate_report(result, args.output, args.dir, keywords, elapsed)

    total_matches = sum(len(r.matches) for r in result["results"])
    total_files = len(result["results"]) + len(result["failures"])
    print(f"扫描完成: 共扫描 {total_files} 个文件, 发现 {total_matches} 处匹配, 耗时 {elapsed:.2f}s")
    print(f"报告已生成: {args.output}")
    sys.exit(0)


def _cmd_add(args):
    add_keywords(args.words)
    for word in args.words:
        print(f"已添加: {word}")
    sys.exit(0)


def _cmd_remove(args):
    removed = remove_keyword(args.word)
    if removed:
        print(f"已删除: {args.word}")
    else:
        print(f"关键词不存在: {args.word}")
    sys.exit(0)


def _cmd_list(args):
    config = load_keywords()
    keywords = config["keywords"]
    if not keywords:
        print("关键词列表为空")
    else:
        for kw in keywords:
            print(kw)
        if args.count:
            print(f"\n共 {len(keywords)} 个关键词")
    sys.exit(0)


def _cmd_config(args):
    config = load_keywords()
    if args.config_command == "show-ocr":
        status = "开启" if config["ocr_enabled"] else "关闭"
        print(f"OCR 状态: {status}")
    elif args.config_command == "set-ocr":
        ocr_enabled = args.value == "on"
        save_keywords(config["keywords"], ocr_enabled)
        print(f"OCR 已{'开启' if ocr_enabled else '关闭'}")
    else:
        print("请指定配置命令: show-ocr 或 set-ocr", file=sys.stderr)
        sys.exit(1)


def _cmd_serve(args):
    import uvicorn

    print(f"启动敏感词 Web 管理端...")
    print(f"访问地址: http://{args.host}:{args.port}")
    print("按 Ctrl+C 停止服务")

    config = uvicorn.Config(
        "web_admin.main:app",
        host=args.host,
        port=args.port,
        log_level="info",
        reload=False,
    )
    server = uvicorn.Server(config)
    server.run()


if __name__ == "__main__":
    main()
