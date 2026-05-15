import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import chardet
import docx
import structlog
from pypdf import PdfReader

logger = structlog.get_logger(__name__)


class DocumentParser(ABC):
    """
    Abstract base class for document parsers.
    """

    @abstractmethod
    def extract_text(self, path: Path) -> str:
        """
        Extracts plain text from the document at the given path.
        """
        pass


class PDFParser(DocumentParser):
    """
    Parser for PDF files using pypdf.
    """

    def extract_text(self, path: Path) -> str:
        logger.debug("parsing_pdf", path=str(path))
        try:
            reader = PdfReader(path)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text.strip()
        except Exception as e:
            logger.error("pdf_parsing_failed", path=str(path), error=str(e))
            raise


class DOCXParser(DocumentParser):
    """
    Parser for Word documents using python-docx.
    """

    def extract_text(self, path: Path) -> str:
        logger.debug("parsing_docx", path=str(path))
        try:
            doc = docx.Document(path)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            return text.strip()
        except Exception as e:
            logger.error("docx_parsing_failed", path=str(path), error=str(e))
            raise


class TXTParser(DocumentParser):
    """
    Parser for plain text files with encoding detection.
    """

    def extract_text(self, path: Path) -> str:
        logger.debug("parsing_txt", path=str(path))
        try:
            raw_data = path.read_bytes()
            detection = chardet.detect(raw_data)
            encoding = detection["encoding"] or "utf-8"
            return raw_data.decode(encoding).strip()
        except Exception as e:
            logger.error("txt_parsing_failed", path=str(path), error=str(e))
            raise


class MDParser(DocumentParser):
    """
    Parser for Markdown files that strips Markdown syntax.
    """

    def extract_text(self, path: Path) -> str:
        logger.debug("parsing_md", path=str(path))
        try:
            # Use TXTParser logic for initial read
            txt_parser = TXTParser()
            raw_text = txt_parser.extract_text(path)

            # Simple regex-based markdown stripping
            # This is a basic implementation; more complex markdown might need a proper library
            # but following the prompt's "strips Markdown syntax" instruction:

            # Remove headers (### Header)
            text = re.sub(r"#+\s+", "", raw_text)
            # Remove bold/italic (*bold*, _italic_, **bold**)
            text = re.sub(r"[*_]{1,3}(.*?)[*_]{1,3}", r"\1", text)
            # Remove links [text](url) -> text
            text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
            # Remove code blocks and inline code
            text = re.sub(r"`{1,3}.*?`{1,3}", "", text, flags=re.DOTALL)
            # Remove images ![alt](url)
            text = re.sub(r"!\[.*?\]\(.*?\)", "", text)

            return text.strip()
        except Exception as e:
            logger.error("md_parsing_failed", path=str(path), error=str(e))
            raise


def get_parser(path: Path) -> Optional[DocumentParser]:
    """
    Factory function that returns the appropriate parser for a given file extension.
    """
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return PDFParser()
    elif suffix == ".docx":
        return DOCXParser()
    elif suffix in (".txt", ".log", ".csv"):
        return TXTParser()
    elif suffix in (".md", ".markdown"):
        return MDParser()
    else:
        logger.warning("no_parser_found", suffix=suffix, path=str(path))
        return None
