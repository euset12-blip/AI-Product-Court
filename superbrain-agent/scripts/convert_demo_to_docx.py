#!/usr/bin/env python3
"""
Markdown → Word 转换脚本。
生成 AI_Product_Court_Demo验证报告.docx
"""

import re
from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH

ROOT = Path(__file__).resolve().parent.parent.parent
INPUT_MD = ROOT / "AI_Product_Court_Demo验证报告.md"
OUTPUT_DOCX = ROOT / "AI_Product_Court_Demo验证报告.docx"


def add_cover(doc):
    """封面页"""
    for _ in range(6):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("AI Product Court Demo 验证报告")
    run.font.size = Pt(26)
    run.bold = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("基于多智能体对抗模拟与决策记忆的产品创新验证体系").font.size = Pt(14)

    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("2026 AI 先锋未来人才大赛 · 安克创新赛道").font.size = Pt(12)

    doc.add_page_break()


def add_formatted_paragraph(doc, text, style='Normal'):
    """添加段落，支持行内 **粗体** 和 `等宽`"""
    p = doc.add_paragraph(style=style)
    parts = re.split(r'(\*\*.*?\*\*|`.*?`)', text)
    for part in parts:
        if part.startswith('**') and part.endswith('**'):
            p.add_run(part[2:-2]).bold = True
        elif part.startswith('`') and part.endswith('`'):
            p.add_run(part[1:-1]).font.name = 'Consolas'
        else:
            p.add_run(part)
    return p


def add_code_block(doc, lines):
    """灰色背景代码块"""
    for line in lines:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        run = p.add_run(line)
        run.font.name = 'Consolas'
        run.font.size = Pt(9)
    doc.add_paragraph()


def add_blockquote(doc, text):
    """引用块"""
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.italic = True
    run.font.size = Pt(10)
    return p


def add_table(doc, rows_data):
    """rows_data[0] = header, rows_data[1:] = body"""
    if not rows_data:
        return
    header = [c.strip() for c in rows_data[0] if c.strip()]
    ncols = len(header)
    data = [[c.strip() for c in row if c.strip()][:ncols] for row in rows_data[1:]]

    table = doc.add_table(rows=1 + len(data), cols=ncols)
    table.style = 'Light Grid Accent 1'
    for i, h in enumerate(header):
        cell = table.rows[0].cells[i]
        cell.text = h
        for p in cell.paragraphs:
            for r in p.runs:
                r.bold = True
                r.font.size = Pt(10)
    for ri, row in enumerate(data):
        for ci, val in enumerate(row):
            if ci < ncols:
                cell = table.rows[ri + 1].cells[ci]
                cell.text = val
                for p in cell.paragraphs:
                    for r in p.runs:
                        r.font.size = Pt(10)
    doc.add_paragraph()


def convert():
    doc = Document()

    # 页面设置 A4
    sec = doc.sections[0]
    sec.page_width = Cm(21.0)
    sec.page_height = Cm(29.7)
    sec.top_margin = Cm(2.54)
    sec.bottom_margin = Cm(2.54)
    sec.left_margin = Cm(3.18)
    sec.right_margin = Cm(3.18)

    add_cover(doc)

    text = Path(INPUT_MD).read_text(encoding='utf-8')
    lines = text.split('\n')

    i = 0
    code_buf = []
    table_buf = []
    in_code = False
    in_table = False
    skip_until_separator = False  # skip YAML front matter

    while i < len(lines):
        line = lines[i]

        # 跳过 YAML front matter
        if i == 0 and line.strip() == '# AI Product Court · AI 原生产品决策评审系统':
            skip_until_separator = True
            i += 1
            continue
        if skip_until_separator:
            if line.strip() == '---':
                skip_until_separator = False
            i += 1
            continue

        # 跳过装饰性 ---
        if line.strip() == '---':
            i += 1
            continue

        # 跳过 blockquote 标题行
        if line.startswith('> 基于多智能体') or line.startswith('> 2026 AI'):
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

        # 表格收集
        if line.strip().startswith('|') and not line.strip().startswith('|---'):
            if not in_table:
                in_table = True
                table_buf = []
            table_buf.append([c.strip() for c in line.split('|')])
            i += 1
            continue
        elif line.strip().startswith('|---'):
            i += 1
            continue
        elif in_table:
            in_table = False
            if table_buf:
                add_table(doc, table_buf)
                table_buf = []
            # 继续处理当前行

        # 标题
        if line.startswith('## ') and not line.startswith('### '):
            add_formatted_paragraph(doc, line[3:].strip(), style='Heading 1')
            i += 1
            continue
        if line.startswith('### '):
            add_formatted_paragraph(doc, line[4:].strip(), style='Heading 2')
            i += 1
            continue
        if line.startswith('#### '):
            add_formatted_paragraph(doc, line[5:].strip(), style='Heading 3')
            i += 1
            continue

        # blockquote
        if line.startswith('> '):
            add_blockquote(doc, line[2:].strip())
            i += 1
            continue

        # 无序列表
        m = re.match(r'^(\s*)[-*]\s+(.+)', line)
        if m:
            add_formatted_paragraph(doc, m.group(2), style='List Bullet')
            i += 1
            continue

        # 有序列表
        m = re.match(r'^\s*\d+\.\s+(.+)', line)
        if m:
            add_formatted_paragraph(doc, m.group(1), style='List Number')
            i += 1
            continue

        # 空行
        if not line.strip():
            i += 1
            continue

        # 普通段落
        add_formatted_paragraph(doc, line)
        i += 1

    # 清理最后的表格
    if in_table and table_buf:
        add_table(doc, table_buf)

    doc.save(str(OUTPUT_DOCX))
    print(f"Done: {OUTPUT_DOCX}")


if __name__ == '__main__':
    convert()
