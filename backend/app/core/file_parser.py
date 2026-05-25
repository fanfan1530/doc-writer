"""文书文件解析：支持 .doc（旧版 OLE 格式）和 .docx（Open XML 格式）的文本提取。"""

import re
import subprocess
import os

from fastapi import UploadFile

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {".doc", ".docx"}
MIN_TEXT_LENGTH = 10

# 中文字符占比阈值：解析出的文本中文字符低于此比例时，认为解析可能失败
_MIN_CHINESE_RATIO = 0.05


def _looks_like_garbled_chinese(text: str) -> bool:
    """检测文本是否包含合理比例的中文字符，用于判断 .doc 解析是否成功。

    如果文本有较多字符但几乎没有中文字符（且没有明显的亚洲语言特征），
    说明 antiword 未能正确处理中文编码。
    若文本中英文/数字/标点占绝大多数且无 CJK 字符 → 可能是乱码。
    """
    if len(text) < 20:
        return False  # 文本太短，不检测
    cjk_chars = sum(1 for ch in text if "一" <= ch <= "鿿" or "㐀" <= ch <= "䶿")
    ratio = cjk_chars / len(text)
    # 如果中文字符占比过低且文本看起来像垃圾字符
    if ratio < _MIN_CHINESE_RATIO:
        # 进一步检查：是否有大量问号或替换字符（乱码特征）
        garbage = text.count("�") + text.count("?")
        if garbage > len(text) * 0.05:
            return True
        # 或者全是低 ASCII + 少数乱码
        if cjk_chars == 0 and len(text) > 50:
            return True
    return False


def validate_file(file: UploadFile) -> None:
    """在保存临时文件前验证文件类型和大小。"""
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"不支持的文件格式 '{ext}'，仅支持 .doc 和 .docx")
    if file.size and file.size > MAX_FILE_SIZE:
        raise ValueError(f"文件过大，最大支持 {MAX_FILE_SIZE // 1024 // 1024} MB")


def parse_doc(file_path: str) -> str:
    """使用 antiword 解析旧版 .doc（OLE 格式）文件。"""
    try:
        result = subprocess.run(
            ["antiword", file_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        raise ValueError("服务器未安装 antiword，无法解析 .doc 文件，请将文件另存为 .docx 格式后重试")
    except subprocess.TimeoutExpired:
        raise ValueError("文件解析超时，请确认文件未损坏")

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "password" in stderr.lower() or "encrypt" in stderr.lower():
            raise ValueError("无法解析加密的 .doc 文件，请先解除文档保护后重试")
        raise ValueError(f"无法解析 .doc 文件，请确认文件未损坏或未加密。错误: {stderr[:200]}")

    text = result.stdout.strip()
    if not text:
        raise ValueError("文件中未提取到文本内容，请确认文件不是纯图片扫描件")
    if _looks_like_garbled_chinese(text):
        raise ValueError(
            "该 .doc 文件的文字解析结果异常（可能为乱码），"
            "请用 Word 将文件另存为 .docx 格式后重新上传"
        )
    return text


def parse_docx(file_path: str) -> str:
    """使用 python-docx 解析 .docx 文件，按文档原始顺序提取段落和表格中的文本。"""
    try:
        from docx import Document
        from docx.oxml.ns import qn
        from docx.text.paragraph import Paragraph
    except ImportError:
        raise ValueError("服务器未安装 python-docx 库，无法解析 .docx 文件")

    try:
        doc = Document(file_path)
    except Exception as e:
        raise ValueError(f"无法解析 .docx 文件，请确认文件格式正确。错误: {str(e)[:200]}")

    parts: list[str] = []

    # 按文档 body 中元素出现顺序遍历（段落和表格交错处理）
    for child in doc.element.body:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "p":
            para = Paragraph(child, doc)
            text = para.text.strip()
            if text:
                parts.append(text)
        elif tag == "tbl":
            for row in child.findall(".//" + qn("w:tr")):
                cells: list[str] = []
                for cell in row.findall(".//" + qn("w:tc")):
                    cell_parts = []
                    for t in cell.findall(".//" + qn("w:t")):
                        if t.text:
                            cell_parts.append(t.text)
                    cell_text = "".join(cell_parts).strip()
                    if cell_text:
                        cells.append(cell_text)
                if cells:
                    parts.append(" | ".join(cells))

    text = "\n".join(parts).strip()
    if not text:
        raise ValueError("文件中未提取到文本内容，请确认文件不是纯图片扫描件")
    return text


def parse_uploaded_file(file_path: str, filename: str) -> str:
    """根据文件扩展名分派到对应的解析函数。"""
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".doc":
        text = parse_doc(file_path)
    elif ext == ".docx":
        text = parse_docx(file_path)
    else:
        raise ValueError(f"不支持的文件格式 '{ext}'，仅支持 .doc 和 .docx")

    if len(text) < MIN_TEXT_LENGTH:
        raise ValueError("文件中提取到的文本内容过短，请确认文件包含有效文字内容")

    return text
