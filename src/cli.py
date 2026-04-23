import argparse
import sys
import time

from .checker import scan_directory
from .config import load_keywords, add_keyword, remove_keyword, save_keywords
from .report import generate_report


def main():
    parser = argparse.ArgumentParser(prog="sensi-check", description="保密检查工具")
    subparsers = parser.add_subparsers(dest="command")

    check_parser = subparsers.add_parser("check", help="扫描目录中的敏感词")
    check_parser.add_argument("dir", help="要扫描的目录路径")
    check_parser.add_argument("-o", "--output", required=True, help="HTML 报告输出路径")
    check_parser.add_argument("-w", "--workers", type=int, default=1, help="并行 worker 数量")
    check_parser.add_argument("--context", type=int, default=50, help="上下文字符数")
    check_parser.add_argument("-n", "--no-archives", action="store_true", help="不检查压缩包内容")
    check_parser.add_argument("--verbose", action="store_true", help="显示详细扫描过程")

    add_parser = subparsers.add_parser("add", help="添加关键词")
    add_parser.add_argument("words", nargs="+", help="要添加的关键词")

    remove_parser = subparsers.add_parser("remove", help="删除关键词")
    remove_parser.add_argument("word", help="要删除的关键词")

    subparsers.add_parser("list", help="列出所有关键词")

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


def _cmd_check(args):
    config = load_keywords()
    keywords = config["keywords"]
    if not keywords:
        print("错误: 关键词列表为空，请先添加关键词", file=sys.stderr)
        sys.exit(1)

    start = time.time()
    result = scan_directory(
        args.dir,
        keywords,
        context_chars=args.context,
        num_workers=args.workers,
        ocr_enabled=config["ocr_enabled"],
        check_archives=not args.no_archives,
        verbose=args.verbose,
    )
    elapsed = time.time() - start

    generate_report(result, args.output, args.dir, keywords)

    total_matches = sum(len(r.matches) for r in result["results"])
    total_files = len(result["results"]) + len(result["failures"])
    print(f"扫描完成: 共扫描 {total_files} 个文件, 发现 {total_matches} 处匹配, 耗时 {elapsed:.2f}s")
    print(f"报告已生成: {args.output}")


def _cmd_add(args):
    for word in args.words:
        add_keyword(word)
        print(f"已添加: {word}")


def _cmd_remove(args):
    remove_keyword(args.word)
    print(f"已删除: {args.word}")


def _cmd_list(args):
    config = load_keywords()
    keywords = config["keywords"]
    if not keywords:
        print("关键词列表为空")
        return
    for kw in keywords:
        print(kw)


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


if __name__ == "__main__":
    main()
