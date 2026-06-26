from .base import BaseParser, ParserError


class TxtParser(BaseParser):
    _ENCODINGS = ["utf-8", "gbk", "gb2312"]

    def parse(self, file_path: str) -> str:
        for encoding in self._ENCODINGS:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    return f.read()
            except (UnicodeDecodeError, UnicodeError):
                continue
            except OSError as e:
                raise ParserError(f"无法读取文件 {file_path}: {e}") from e
        raise ParserError(f"无法检测文件编码: {file_path}")
