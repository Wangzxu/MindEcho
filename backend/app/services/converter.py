# -*- coding: utf-8 -*-
"""
多格式文档 -> Markdown 统一转换器。

支持的格式及其转换策略：
    PDF  -> pymupdf4llm (保留标题/表格/图片引用), fallback pypdf
    DOCX -> mammoth (保留 Heading 1-6 层级), fallback python-docx
    TXT  -> 直通（视为纯文本 Markdown）
    MD   -> 直通
    HTML -> trafilatura (公众号文章场景去噪提取)
"""

import io
import logging
from typing import Tuple, Dict, Any

logger = logging.getLogger(__name__)


def _fallback_pdf(file_bytes: bytes) -> str:
    """pypdf 纯文本提取（旧逻辑作为降级方案）"""
    import pypdf
    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text)
    return "\n\n".join(text_parts)


def _fallback_docx(file_bytes: bytes) -> str:
    """python-docx 纯段落提取（旧逻辑作为降级方案）"""
    import docx
    doc = docx.Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs)


def convert_pdf(file_bytes: bytes) -> Tuple[str, Dict[str, Any]]:
    """PDF → Markdown，失败时降级到纯文本提取"""
    metadata = {"source_format": "pdf", "page_count": 0, "converter": "pymupdf4llm"}

    try:
        import pymupdf4llm
        import fitz
        # pymupdf4llm.to_markdown 不接受 BytesIO，需先用 stream 打开 Document 再传入
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        try:
            md_text = pymupdf4llm.to_markdown(doc)
            metadata["page_count"] = doc.page_count
        finally:
            doc.close()

        if not md_text or not md_text.strip():
            raise ValueError("pymupdf4llm 返回空结果")
        return md_text.strip(), metadata
    except Exception as e:
        logger.warning(f"pymupdf4llm 转换失败 ({e})，降级到 pypdf 纯文本提取")
        metadata["converter"] = "pypdf_fallback"
        return _fallback_pdf(file_bytes), metadata


def convert_docx(file_bytes: bytes) -> Tuple[str, Dict[str, Any]]:
    """DOCX → Markdown via mammoth，失败时降级"""
    metadata = {"source_format": "docx", "converter": "mammoth"}

    try:
        import mammoth
        result = mammoth.convert_to_markdown(io.BytesIO(file_bytes))
        md_text = result.value
        if result.messages:
            logger.info(f"mammoth 转换消息: {result.messages}")
        if not md_text or not md_text.strip():
            raise ValueError("mammoth 返回空结果")
        return md_text.strip(), metadata
    except Exception as e:
        logger.warning(f"mammoth 转换失败 ({e})，降级到 python-docx 纯文本提取")
        metadata["converter"] = "python-docx_fallback"
        return _fallback_docx(file_bytes), metadata


def convert_txt(file_bytes: bytes) -> Tuple[str, Dict[str, Any]]:
    """TXT/MD 直通"""
    metadata = {"source_format": "txt", "converter": "passthrough"}
    text = file_bytes.decode("utf-8", errors="ignore").strip()
    return text, metadata


def convert_html(file_bytes: bytes) -> Tuple[str, Dict[str, Any]]:
    """HTML → Markdown（公众号文章场景）"""
    metadata = {"source_format": "html", "converter": "trafilatura"}

    try:
        import trafilatura
        html_str = file_bytes.decode("utf-8", errors="ignore")
        md_text = trafilatura.extract(html_str, output_format="markdown",
                                       include_tables=True, include_images=False)
        if not md_text:
            # 降级到 html2text
            import html2text
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = True
            h.body_width = 0
            md_text = h.handle(html_str)
            metadata["converter"] = "html2text_fallback"
        return md_text.strip(), metadata
    except ImportError:
        logger.warning("trafilatura 不可用，使用 html2text")
        metadata["converter"] = "html2text"
        import html2text
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.body_width = 0
        return h.handle(file_bytes.decode("utf-8", errors="ignore")).strip(), metadata


def convert_to_markdown(file_bytes: bytes, filename: str) -> Tuple[str, Dict[str, Any]]:
    """
    根据文件扩展名分发到对应的转换器。

    Args:
        file_bytes: 原始文件二进制内容
        filename: 文件名（含扩展名）

    Returns:
        (markdown_text, conversion_metadata)
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    converters = {
        "pdf":  convert_pdf,
        "docx": convert_docx,
        "doc":  convert_docx,
        "txt":  convert_txt,
        "md":   convert_txt,   # MD 也走直通
        "html": convert_html,
        "htm":  convert_html,
    }

    converter = converters.get(ext)
    if converter is None:
        # 未知格式尝试当文本处理
        logger.info(f"未知格式 .{ext}，尝试作为文本处理")
        return convert_txt(file_bytes)

    return converter(file_bytes)
