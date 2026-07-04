"""生成 RAR 测试固件。

需系统安装 `rar` 压缩器（专有软件）。在已安装 `rar` 的机器上运行：

    python tests/fixtures/generate_rar_fixtures.py

生成的 .rar 文件提交到仓库后，测试端仅需 `unrar` 即可执行真实 RAR 解析用例，
不再依赖专有 `rar` 压缩器。
"""
import os
import shutil
import subprocess
import sys
import tempfile

FIXTURES_DIR = os.path.dirname(os.path.abspath(__file__))


def _build(name, entries):
    rar_path = os.path.join(FIXTURES_DIR, name)
    with tempfile.TemporaryDirectory() as staging:
        for rel, content in entries:
            full = os.path.join(staging, *rel.split("/"))
            parent = os.path.dirname(full)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
        cwd = os.getcwd()
        os.chdir(staging)
        try:
            args = ["rar", "a", "-y", rar_path]
            for rel, _ in entries:
                args.append(rel)
            r = subprocess.run(args, capture_output=True, text=True, timeout=60)
        finally:
            os.chdir(cwd)
        if r.returncode != 0:
            print(f"[FAIL] {name}: rar exit {r.returncode}: {r.stderr}{r.stdout}", file=sys.stderr)
            return False
        print(f"[OK]   {name} ({os.path.getsize(rar_path)} bytes)")
        return True


def main():
    if shutil.which("rar") is None:
        print("rar 压缩器未安装，无法生成固件。", file=sys.stderr)
        print("请安装 rar 后运行: python tests/fixtures/generate_rar_fixtures.py", file=sys.stderr)
        return 1

    ok = True
    ok &= _build("sample.rar", [("inner.txt", "rar内敏感词")])
    ok &= _build("sample_dir.rar", [("subdir/inner.txt", "rar正常内容")])
    ok &= _build("big.rar", [("big.txt", "x" * 200)])
    ok &= _build("per_file.rar", [("inner.txt", "rar内容")])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
