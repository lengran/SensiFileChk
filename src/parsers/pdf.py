import logging

import fitz

from .base import BaseParser, ParserError

logger = logging.getLogger(__name__)


class PdfParser(BaseParser):
    def __init__(self, ocr_enabled: bool = False):
        self.ocr_enabled = ocr_enabled

    def parse(self, file_path: str) -> str:
        try:
            doc = fitz.open(file_path)
        except Exception as e:
            raise ParserError(f"无法打开 PDF: {file_path}: {e}") from e

        if doc.is_encrypted:
            doc.close()
            raise ParserError(f"PDF 文件已加密: {file_path}")

        text_parts = []
        try:
            for page in doc:
                page_text = page.get_text()
                if page_text.strip():
                    text_parts.append(page_text)
                elif self.ocr_enabled:
                    ocr_text = self._ocr_page(page, file_path)
                    if ocr_text:
                        text_parts.append(ocr_text)
        finally:
            doc.close()

        return "\n".join(text_parts)

    def _ocr_page(self, page, file_path: str = "") -> str:
        try:
            import pytesseract
            from PIL import Image
            import io

            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            return pytesseract.image_to_string(img, lang="chi_sim+eng")
        except ImportError:
            logger.warning("OCR 依赖未安装 (pytesseract/Pillow)，跳过 OCR: %s", file_path)
            return ""
        except RuntimeError as e:
            logger.warning("OCR 处理失败 (%s): %s，降级为文本模式", file_path, e)
            return ""
        except Exception as e:
            logger.warning("OCR 未知错误 (%s): %s，降级为文本模式", file_path, e)
            return ""
