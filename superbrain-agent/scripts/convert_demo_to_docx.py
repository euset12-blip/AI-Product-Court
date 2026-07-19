#!/usr/bin/env python3
"""
纯 python-docx 原生 API，不碰底层 XML。
参考文档仅用于复制样式名定义，不做任何 XML 层面的修改。
"""

import re
from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parent.parent.parent
INPUT_MD = ROOT / "AI_Product_Court_Demo验证报告.md"
OUTPUT_DOCX = ROOT / "AI_Product_Court_Demo验证报告.docx"


def add_cover(doc):
    for _ in range(6):
        doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("AI Product Court Demo 验证报告")
    r.font.size = Pt(22)
    r.bold = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("基于多智能体对抗模拟与决策记忆的产品创新验证体系")
    r.font.size = Pt(14)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("—— 以 eufy 智能门锁为验证场景的 Demo 验证与实验分析 ——")
    r.font.size = Pt(12)

    doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("2026 AI 先锋未来人才大赛 · 安克创新赛道")
    r.font.size = Pt(12)

    doc.add_page_break()


def add_run_text(p, text):
    """处理 **粗体** `代码` 的行内格式"""
    parts = re.split(r'(\*\*.*?\*\*|`.*?`)', text)
    for part in parts:
        if part.startswith('**') and part.endswith('**'):
            r = p.add_run(part[2:-2])
            r.bold = True
        elif part.startswith('`') and part.endswith('`'):
            r = p.add_run(part[1:-1])
            r.font.name = 'Consolas'
            r.font.size = Pt(9)
        else:
            p.add_run(part)


def add_code_block(doc, lines):
    for line in lines:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.0
        r = p.add_run(line)
        r.font.name = 'Consolas'
        r.font.size = Pt(8.5)


def add_table_md(doc, rows):
    """rows: markdown 表格行，| 分隔"""
    parsed = []
    for r in rows:
        cells = [c.strip() for c in r.split('|')]
        cells = [c for c in cells if c]  # 去首尾空
        if cells:
            parsed.append(cells)
    if len(parsed) < 2:
        return
    header = parsed[0]
    data = parsed[1:]
    ncols = len(header)

    table = doc.add_table(rows=1 + len(data), cols=ncols)
    table.style = 'Table Grid'

    for ci, h in enumerate(header):
        cell = table.rows[0].cells[ci]
        cell.text = h
        for p in cell.paragraphs:
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(1)
            for r in p.runs:
                r.bold = True
                r.font.size = Pt(10)

    for ri, row in enumerate(data):
        for ci in range(min(len(row), ncols)):
            cell = table.rows[ri + 1].cells[ci]
            cell.text = row[ci] if ci < len(row) else ''
            for p in cell.paragraphs:
                p.paragraph_format.space_before = Pt(1)
                p.paragraph_format.space_after = Pt(1)
                for r in p.runs:
                    r.font.size = Pt(10)
    doc.add_paragraph()


def build():
    doc = Document()

    # 页面设置 A4
    sec = doc.sections[0]
    sec.page_width = Cm(21.0)
    sec.page_height = Cm(29.7)
    sec.top_margin = Cm(2.54)
    sec.bottom_margin = Cm(2.54)
    sec.left_margin = Cm(3.18)
    sec.right_margin = Cm(3.18)

    # 设置默认字体
    style = doc.styles['Normal']
    style.font.name = '等线'
    style.font.size = Pt(11)
    style.paragraph_format.line_spacing = 1.5

    add_cover(doc)

    text = INPUT_MD.read_text(encoding='utf-8')
    lines = text.split('\n')

    i = 0
    code_buf = []
    table_rows = []
    in_code = False
    in_table = False
    skipped = False

    while i < len(lines):
        line = lines[i]

        # 跳过 YAML front matter
        if not skipped:
            if (line.strip().startswith('# ') and not line.startswith('## ')) or \
               (line.startswith('> ') and ('多智能体' in line or '2026 AI' in line or '基于多智能体' in line)):
                i += 1
                continue
            if line.strip() == '---':
                skipped = True
                i += 1
                continue
            i += 1
            continue

        # 跳过装饰线
        if line.strip() == '---':
            i += 1
            continue

        # 跳过主标题
        if line.strip().startswith('# ') and not line.startswith('## '):
            i += 1
            continue

        # 代码块
        if line.strip().startswith('```'):
            if in_code:
                add_code_block(doc, code_buf)
                code_buf = []
                in_code = False
            else:
                in_code = True
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue

        # 表格
        if line.strip().startswith('|') and not line.strip().startswith('|---'):
            if not in_table:
                in_table = True
                table_rows = []
            table_rows.append(line)
            i += 1
            continue
        elif line.strip().startswith('|---'):
            i += 1
            continue
        elif in_table:
            in_table = False
            if table_rows:
                add_table_md(doc, table_rows)
                table_rows = []
            # 继续处理当前行

        # 一级标题 ## 数字开头
        if line.startswith('## ') and re.match(r'^##\s+\d+\.', line):
            h = line[3:].strip()
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(18)
            p.paragraph_format.space_after = Pt(10)
            r = p.add_run(h)
            r.bold = True
            r.font.size = Pt(15)
            i += 1
            continue

        # 二级标题 ## 非数字
        if line.startswith('## ') and not line.startswith('### '):
            h = line[3:].strip()
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(14)
            p.paragraph_format.space_after = Pt(8)
            r = p.add_run(h)
            r.bold = True
            r.font.size = Pt(13)
            i += 1
            continue

        # 三级标题 ###
        if line.startswith('### '):
            h = line[4:].strip()
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(10)
            p.paragraph_format.space_after = Pt(6)
            r = p.add_run(h)
            r.bold = True
            r.font.size = Pt(12)
            i += 1
            continue

        # blockquote
        if line.startswith('> '):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(1)
            r = p.add_run(line[2:].strip())
            r.italic = True
            r.font.size = Pt(10)
            r.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
            i += 1
            continue

        # 无序列表
        m = re.match(r'^(\s*)[-*]\s+(.+)', line)
        if m:
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(1.27)
            p.paragraph_format.first_line_indent = Cm(-0.63)
            add_run_text(p, "• " + m.group(2))
            i += 1
            continue

        # 有序列表
        m = re.match(r'^\s*(\d+)\.\s+(.+)', line)
        if m:
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(1.27)
            p.paragraph_format.first_line_indent = Cm(-0.63)
            add_run_text(p, f"{m.group(1)}. {m.group(2)}")
            i += 1
            continue

        # 空行
        if not line.strip():
            i += 1
            continue

        # 普通段落
        p = doc.add_paragraph()
        p.paragraph_format.first_line_indent = Cm(0.74)
        add_run_text(p, line)
        i += 1

    # 收尾表格
    if in_table and table_rows:
        add_table_md(doc, table_rows)

    doc.save(str(OUTPUT_DOCX))
    print(f"Done: {OUTPUT_DOCX}")


if __name__ == '__main__':
    build()
