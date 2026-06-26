import gzip
import os
import shutil
import tarfile
import tempfile
import zipfile

from .base import BaseParser, ParserError

MAX_DEPTH = 10
MAX_SIZE = 500 * 1024 * 1024
MAX_TOTAL_SIZE = 500 * 1024 * 1024


class ArchiveParser(BaseParser):
    def __init__(self, inner_parser_factory=None, depth: int = 0):
        self._inner_parser_factory = inner_parser_factory
        self._depth = depth

    def parse(self, file_path: str) -> str:
        if self._depth >= MAX_DEPTH:
            raise ParserError(f"压缩包嵌套深度超限 ({MAX_DEPTH} 层)")

        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        if ext == ".zip":
            return self._parse_zip(file_path)
        elif ext == ".tar":
            return self._parse_tar(file_path)
        elif ext in (".tgz", ".gz"):
            if file_path.endswith(".tar.gz") or file_path.endswith(".tgz"):
                return self._parse_tar(file_path)
            return self._parse_gz(file_path)
        elif ext == ".rar":
            return self._parse_rar(file_path)
        elif ext == ".7z":
            return self._parse_7z(file_path)
        else:
            raise ParserError(f"不支持的压缩格式: {ext}")

    def _parse_zip(self, file_path: str) -> str:
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                return self._extract_archive(zf, file_path)
        except zipfile.BadZipFile as e:
            raise ParserError(f"损坏的 zip 文件: {file_path}: {e}") from e

    def _parse_tar(self, file_path: str) -> str:
        try:
            with tarfile.open(file_path, "r:*") as tf:
                return self._extract_tar_archive(tf, file_path)
        except (tarfile.TarError, OSError) as e:
            raise ParserError(f"损坏的 tar 文件: {file_path}: {e}") from e

    def _parse_gz(self, file_path: str) -> str:
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                base_name = os.path.basename(file_path)
                if base_name.endswith(".gz"):
                    base_name = base_name[:-3]
                if base_name.endswith(".tar"):
                    base_name = base_name[:-4]
                if not base_name:
                    base_name = "decompressed"

                out_path = os.path.join(tmpdir, base_name)
                with gzip.open(file_path, "rb") as f_in:
                    with open(out_path, "wb") as f_out:
                        total = 0
                        while True:
                            chunk = f_in.read(8192)
                            if not chunk:
                                break
                            total += len(chunk)
                            if total > MAX_SIZE:
                                raise ParserError(f"gz 解压后文件过大: {file_path}")
                            f_out.write(chunk)

                _, ext = os.path.splitext(base_name)
                ext = ext.lower()

                archive_exts = {".zip", ".tar", ".tgz", ".gz", ".rar", ".7z"}
                if ext in archive_exts:
                    inner_parser = ArchiveParser(
                        inner_parser_factory=self._inner_parser_factory,
                        depth=self._depth + 1,
                    )
                    return inner_parser.parse(out_path)

                if self._inner_parser_factory:
                    parser = self._inner_parser_factory(ext)
                    if parser:
                        return parser.parse(out_path)

                with open(out_path, "r", encoding="utf-8", errors="replace") as f:
                    return f.read()
        except ParserError:
            raise
        except OSError as e:
            raise ParserError(f"解压 gz 失败: {file_path}: {e}") from e

    def _parse_rar(self, file_path: str) -> str:
        try:
            import rarfile
        except ImportError:
            raise ParserError("rarfile 未安装，请执行: pip install rarfile")
        try:
            with rarfile.RarFile(file_path, "r") as rf:
                return self._extract_rar_archive(rf, file_path)
        except rarfile.BadRarFile as e:
            raise ParserError(f"损坏的 rar 文件: {file_path}: {e}") from e
        except rarfile.NeedFirstVolume:
            raise ParserError(f"分卷 RAR，需要第一卷: {file_path}")

    def _parse_7z(self, file_path: str) -> str:
        try:
            import py7zr
        except ImportError:
            raise ParserError("py7zr 未安装，请执行: pip install py7zr")
        try:
            with py7zr.SevenZipFile(file_path, "r") as sz:
                return self._extract_7z_archive(sz, file_path)
        except Exception as e:
            raise ParserError(f"解压 7z 失败: {file_path}: {e}") from e

    def _check_zip_path(self, name: str):
        normalized = name.replace("\\", "/")
        if normalized.startswith("/"):
            raise ParserError(f"Zip Slip 检测: 不安全路径 {name}")
        parts = normalized.split("/")
        for part in parts:
            if part == "..":
                raise ParserError(f"Zip Slip 检测: 不安全路径 {name}")

    def _check_tar_path(self, name: str):
        normalized = name.replace("\\", "/")
        if normalized.startswith("/"):
            raise ParserError(f"不安全路径: {name}")
        parts = normalized.split("/")
        for part in parts:
            if part == "..":
                raise ParserError(f"不安全路径: {name}")

    def _extract_archive(self, zf: zipfile.ZipFile, archive_path: str) -> str:
        results = []
        total_size = 0
        with tempfile.TemporaryDirectory() as tmpdir:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                self._check_zip_path(info.filename)
                if info.file_size > MAX_SIZE:
                    raise ParserError(f"压缩包内文件过大: {info.filename}")
                total_size += info.file_size
                if total_size > MAX_TOTAL_SIZE:
                    raise ParserError(f"压缩包总大小超限 ({MAX_TOTAL_SIZE // (1024*1024)}MB)")
                try:
                    extracted = zf.extract(info, tmpdir)
                    result = self._process_inner_file(extracted, info.filename)
                    if result:
                        results.append(f"[{info.filename}]\n{result}")
                except ParserError as e:
                    results.append(f"[{info.filename}] 解析失败: {e}")
                except Exception as e:
                    results.append(f"[{info.filename}] 解压失败: {e}")
        return "\n\n".join(results)

    def _extract_tar_archive(self, tf: tarfile.TarFile, archive_path: str) -> str:
        results = []
        total_size = 0
        with tempfile.TemporaryDirectory() as tmpdir:
            for member in tf.getmembers():
                if not member.isfile():
                    continue
                self._check_tar_path(member.name)
                if member.size > MAX_SIZE:
                    raise ParserError(f"压缩包内文件过大: {member.name}")
                total_size += member.size
                if total_size > MAX_TOTAL_SIZE:
                    raise ParserError(f"压缩包总大小超限 ({MAX_TOTAL_SIZE // (1024*1024)}MB)")
                try:
                    tf.extract(member, tmpdir, filter="data")
                    extracted = os.path.join(tmpdir, member.name)
                    result = self._process_inner_file(extracted, member.name)
                    if result:
                        results.append(f"[{member.name}]\n{result}")
                except ParserError as e:
                    results.append(f"[{member.name}] 解析失败: {e}")
                except Exception as e:
                    results.append(f"[{member.name}] 解压失败: {e}")
        return "\n\n".join(results)

    def _extract_rar_archive(self, rf, archive_path: str) -> str:
        results = []
        total_size = 0
        with tempfile.TemporaryDirectory() as tmpdir:
            for info in rf.infolist():
                if info.is_dir():
                    continue
                if hasattr(info, 'file_size') and info.file_size > MAX_SIZE:
                    raise ParserError(f"压缩包内文件过大: {info.filename}")
                if hasattr(info, 'file_size'):
                    total_size += info.file_size
                    if total_size > MAX_TOTAL_SIZE:
                        raise ParserError(f"压缩包总大小超限 ({MAX_TOTAL_SIZE // (1024*1024)}MB)")
                try:
                    rf.extract(info, tmpdir)
                    extracted = os.path.join(tmpdir, info.filename)
                    result = self._process_inner_file(extracted, info.filename)
                    if result:
                        results.append(f"[{info.filename}]\n{result}")
                except ParserError as e:
                    results.append(f"[{info.filename}] 解析失败: {e}")
                except Exception as e:
                    results.append(f"[{info.filename}] 解压失败: {e}")
        return "\n\n".join(results)

    def _extract_7z_archive(self, sz, archive_path: str) -> str:
        results = []
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                sz.extractall(tmpdir)
            except Exception as e:
                raise ParserError(f"7z 解压失败: {e}") from e
            total_size = 0
            for root, _dirs, files in os.walk(tmpdir):
                for fname in files:
                    extracted = os.path.join(root, fname)
                    fsize = os.path.getsize(extracted)
                    if fsize > MAX_SIZE:
                        raise ParserError(f"压缩包内文件过大: {fname}")
                    total_size += fsize
                    if total_size > MAX_TOTAL_SIZE:
                        raise ParserError(f"压缩包总大小超限 ({MAX_TOTAL_SIZE // (1024*1024)}MB)")
                    rel = os.path.relpath(extracted, tmpdir)
                    result = self._process_inner_file(extracted, rel)
                    if result:
                        results.append(f"[{rel}]\n{result}")
        return "\n\n".join(results)

    def _process_inner_file(self, file_path: str, display_name: str) -> str:
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        archive_exts = {".zip", ".tar", ".tgz", ".gz", ".rar", ".7z"}
        if ext in archive_exts:
            try:
                inner_parser = ArchiveParser(
                    inner_parser_factory=self._inner_parser_factory,
                    depth=self._depth + 1,
                )
                return inner_parser.parse(file_path)
            except ParserError as e:
                return f"[嵌套解压失败] {e}"

        if self._inner_parser_factory:
            parser = self._inner_parser_factory(ext)
            if parser:
                try:
                    return parser.parse(file_path)
                except ParserError as e:
                    return f"[解析失败] {e}"
        return ""
