#!/usr/bin/env python3
"""
两步生成：
1. pandoc md → docx（保证 XML 有效）
2. python-docx 后处理（调整格式匹配参考文档风格）
"""

import subprocess, sys
from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parent.parent.parent
INPUT_MD = ROOT / "AI_Product_Court_Demo验证报告.md"
OUTPUT_DOCX = ROOT / "AI_Product_Court_Demo验证报告.docx"

def step1_pandoc():
    """pandoc 转换（保证有效 XML）"""
    result = subprocess.run([
        'pandoc', str(INPUT_MD),
        '-o', str(OUTPUT_DOCX),
        '--from=markdown', '--to=docx',
    ], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Pandoc error: {result.stderr}")
        sys.exit(1)

def step2_reformat():
    """python-docx 后处理格式"""
    doc = Document(str(OUTPUT_DOCX))

    # ── 全局：设置默认字体 ──
    style = doc.styles['Normal']
    style.font.name = '等线'
    style.font.size = Pt(11)
    style.paragraph_format.line_spacing = 1.5
    style.paragraph_format.space_after = Pt(6)
    # 中文字体回退
    rPr = style.element.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        from lxml import etree
        rFonts = etree.SubElement(rPr, qn('w:rFonts'))
    rFonts.set(qn('w:eastAsia'), '等线')

    # ── 页面设置 A4 ──
    for sec in doc.sections:
        sec.page_width = Cm(21.0)
        sec.page_height = Cm(29.7)
        sec.top_margin = Cm(2.54)
        sec.bottom_margin = Cm(2.54)
        sec.left_margin = Cm(3.18)
        sec.right_margin = Cm(3.18)

    # ── 遍历所有段落调整样式 ──
    first_real_heading = True
    for p in doc.paragraphs:
        text = p.text.strip()

        # 主标题（第一个非空段落，通常是 Title 样式）→ 封面样式
        if p.style.name == 'Title' and first_real_heading:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for r in p.runs:
                r.font.size = Pt(22)
                r.bold = True
                r.font.name = '等线'
            first_real_heading = False
            continue

        # 一级标题 (Heading 1) → 参考文档 "1" 样式 ≈ 15pt bold
        if p.style.name.startswith('Heading 1'):
            p.paragraph_format.space_before = Pt(18)
            p.paragraph_format.space_after = Pt(10)
            for r in p.runs:
                r.font.size = Pt(15)
                r.bold = True
                r.font.name = '等线'
                r.font.color.rgb = RGBColor(0, 0, 0)
            continue

        # 二级标题 (Heading 2) → 参考文档 "21" 样式 ≈ 13pt bold
        if p.style.name.startswith('Heading 2'):
            p.paragraph_format.space_before = Pt(14)
            p.paragraph_format.space_after = Pt(8)
            for r in p.runs:
                r.font.size = Pt(13)
                r.bold = True
                r.font.name = '等线'
                r.font.color.rgb = RGBColor(0, 0, 0)
            continue

        # 三级标题 (Heading 3)
        if p.style.name.startswith('Heading 3'):
            p.paragraph_format.space_before = Pt(10)
            p.paragraph_format.space_after = Pt(6)
            for r in p.runs:
                r.font.size = Pt(12)
                r.bold = True
                r.font.name = '等线'
                r.font.color.rgb = RGBColor(0, 0, 0)
            continue

        # 代码块（Source Code 样式或等宽字体段落）
        if p.style.name == 'Source Code' or any(
            r.font.name and 'Consolas' in r.font.name for r in p.runs
        ):
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.0
            for r in p.runs:
                r.font.size = Pt(9)
            continue

        # Blockquote（Block Text 样式）
        if p.style.name == 'Block Text' or any(
            r.italic for r in p.runs if r.italic
        ):
            for r in p.runs:
                r.font.size = Pt(10)
            continue

        # 列表项：继承正文字体
        if 'List' in p.style.name or 'Bullet' in p.style.name:
            for r in p.runs:
                r.font.size = Pt(11)
                r.font.name = '等线'
            continue

        # 普通段落：首行缩进 + 统一字体
        if text:
            p.paragraph_format.first_line_indent = Cm(0.74)
            for r in p.runs:
                r.font.name = '等线'
                r.font.size = Pt(11)

    doc.save(str(OUTPUT_DOCX))
    print(f"Done: {OUTPUT_DOCX}")

if __name__ == '__main__':
    print("Step 1/2: pandoc md → docx ...")
    step1_pandoc()
    print("Step 2/2: reformat with python-docx ...")
    step2_reformat()
