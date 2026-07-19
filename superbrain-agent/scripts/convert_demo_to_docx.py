#!/usr/bin/env python3
"""
将 AI_Product_Court_Demo验证报告.md 转换为 Word 文档。
样式参照: AI_Product_Court_研究与落地方案_01初版(1).docx
"""

import re
from pathlib import Path
from docx import Document
from docx.shared import Pt, Inches, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parent.parent.parent
INPUT_MD = ROOT / "AI_Product_Court_Demo验证报告.md"
OUTPUT_DOCX = ROOT / "AI_Product_Court_Demo验证报告.docx"


def setup_styles(doc):
    """配置与参考文档一致的样式"""
    style = doc.styles['Normal']
    style.font.name = '等线'
    style.font.size = Pt(11)
    style.paragraph_format.line_spacing = 1.5
    style.paragraph_format.space_after = Pt(6)
    # 设置中文字体
    rPr = style.element.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = rPr.makeelement(qn('w:rFonts'), {})
        rPr.insert(0, rFonts)
    rFonts.set(qn('w:eastAsia'), '等线')

    # Heading 1 - 一级标题 (章节标题)
    for level, size, bold in [(1, 16, True), (2, 14, True), (3, 12, True)]:
        h_style = doc.styles[f'Heading {level}']
        h_style.font.name = '等线'
        h_style.font.size = Pt(size)
        h_style.font.bold = bold
        h_style.font.color.rgb = RGBColor(0, 0, 0)
        h_style.paragraph_format.space_before = Pt(18 if level == 1 else 12)
        h_style.paragraph_format.space_after = Pt(10 if level == 1 else 6)
        rPr = h_style.element.get_or_add_rPr()
        rFonts = rPr.find(qn('w:rFonts'))
        if rFonts is None:
            rFonts = rPr.makeelement(qn('w:rFonts'), {})
            rPr.insert(0, rFonts)
        rFonts.set(qn('w:eastAsia'), '等线')


def add_title_page(doc):
    """封面页"""
    # 空行
    for _ in range(6):
        doc.add_paragraph()

    # 主标题
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("AI Product Court Demo 验证报告")
    run.font.size = Pt(26)
    run.font.bold = True
    run.font.name = '等线'
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = rPr.makeelement(qn('w:rFonts'), {})
        rPr.insert(0, rFonts)
    rFonts.set(qn('w:eastAsia'), '等线')

    # 副标题
    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run("基于多智能体对抗模拟与决策记忆的产品创新验证体系")
    run.font.size = Pt(14)
    run.font.name = '等线'

    doc.add_paragraph()

    # 比赛信息
    info = doc.add_paragraph()
    info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = info.add_run("2026 AI 先锋未来人才大赛 · 安克创新赛道")
    run.font.size = Pt(12)
    run.font.name = '等线'

    # 分页
    doc.add_page_break()


def escape_xml(text):
    """转义特殊字符"""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def add_styled_paragraph(doc, text, style='Normal', bold=False, italic=False):
    """添加段落，处理中文引号和特殊字符"""
    p = doc.add_paragraph(style=style)
    # 把 markdown 的 **bold** 和 *italic* 转为 Word 格式
    parts = re.split(r'(\*\*.*?\*\*|\*.*?\*|`.*?`)', text)
    for part in parts:
        if part.startswith('**') and part.endswith('**'):
            run = p.add_run(part[2:-2])
            run.bold = True
        elif part.startswith('*') and part.endswith('*') and not part.startswith('**'):
            run = p.add_run(part[1:-1])
            run.italic = True
        elif part.startswith('`') and part.endswith('`'):
            run = p.add_run(part[1:-1])
            run.font.name = 'Consolas'
            run.font.size = Pt(10)
        else:
            run = p.add_run(part)
        run.font.name = '等线'
        rPr = run._element.get_or_add_rPr()
        rFonts = rPr.find(qn('w:rFonts'))
        if rFonts is None:
            rFonts = rPr.makeelement(qn('w:rFonts'), {})
            rPr.insert(0, rFonts)
        rFonts.set(qn('w:eastAsia'), '等线')
    return p


def add_code_block(doc, code_text):
    """添加代码块（灰色背景，等宽字体）"""
    for line in code_text.strip().split('\n'):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.0
        # 添加灰色底纹
        pPr = p._element.get_or_add_pPr()
        shd = pPr.makeelement(qn('w:shd'), {
            qn('w:fill'): 'F0F0F0',
            qn('w:val'): 'clear',
        })
        pPr.append(shd)
        run = p.add_run(line)
        run.font.name = 'Consolas'
        run.font.size = Pt(9)
    # 代码块后空一行
    doc.add_paragraph()


def add_table_from_md(doc, header_row, data_rows):
    """从 markdown 表格数据创建 Word 表格"""
    table = doc.add_table(rows=1 + len(data_rows), cols=len(header_row))
    table.style = 'Light Grid Accent 1'
    # 表头
    for i, cell_text in enumerate(header_row):
        cell = table.rows[0].cells[i]
        cell.text = cell_text.strip()
        for p in cell.paragraphs:
            for run in p.runs:
                run.font.bold = True
                run.font.size = Pt(10)
    # 数据行
    for r, row in enumerate(data_rows):
        for c, cell_text in enumerate(row):
            if c < len(header_row):
                cell = table.rows[r + 1].cells[c]
                cell.text = cell_text.strip()
                for p in cell.paragraphs:
                    for run in p.runs:
                        run.font.size = Pt(10)
    doc.add_paragraph()  # 表后空行
    return table


def convert_markdown_to_docx(md_path, docx_path):
    doc = Document()
    setup_styles(doc)

    # 设置默认字体
    doc.styles['Normal'].font.name = '等线'

    # 页面设置
    section = doc.sections[0]
    section.page_width = Cm(21.0)   # A4
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(3.18)
    section.right_margin = Cm(3.18)

    # ── 封面 ──
    add_title_page(doc)

    # ── 读取 markdown ──
    text = Path(md_path).read_text(encoding='utf-8')

    # ── 解析并写入内容 ──
    lines = text.split('\n')
    i = 0
    in_code_block = False
    code_lines = []
    in_table = False
    table_lines = []

    while i < len(lines):
        line = lines[i]

        # 跳过 YAML front matter 和 blockquote 装饰行
        if line.startswith('>') and ('多智能体对抗模拟' in line or '2026 AI' in line):
            i += 1
            continue
        if line.startswith('---'):
            i += 1
            continue
        if line.startswith('> **') and line.strip() == '> **AI Product Court**':
            i += 1
            continue

        # 代码块
        if line.strip().startswith('```'):
            if in_code_block:
                add_code_block(doc, '\n'.join(code_lines))
                code_lines = []
                in_code_block = False
            else:
                in_code_block = True
            i += 1
            continue

        if in_code_block:
            code_lines.append(line)
            i += 1
            continue

        # 表格（markdown 表格行以 | 开头）
        if line.strip().startswith('|') and not line.strip().startswith('|---'):
            if not in_table:
                in_table = True
                table_lines = []
            table_lines.append(line)
            i += 1
            continue
        elif line.strip().startswith('|---'):
            # 分隔行，跳过
            i += 1
            continue
        elif in_table and not line.strip().startswith('|'):
            # 表格结束，处理表格
            in_table = False
            if table_lines:
                # 第一行是表头
                header = [c.strip() for c in table_lines[0].split('|') if c.strip()]
                data = []
                for tl in table_lines[1:]:
                    row = [c.strip() for c in tl.split('|') if c.strip()]
                    data.append(row)
                add_table_from_md(doc, header, data)
                table_lines = []
            # 继续处理当前行
            continue

        # 标题
        if line.startswith('# ') and not line.startswith('## '):
            # 文档主标题，跳过（封面已有）
            i += 1
            continue

        if line.startswith('## '):
            heading_text = line[3:].strip()
            # 判断层级
            if re.match(r'^\d+\.', heading_text):
                doc.add_heading(heading_text, level=1)
            else:
                doc.add_heading(heading_text, level=2)
            i += 1
            continue

        if line.startswith('### '):
            heading_text = line[4:].strip()
            doc.add_heading(heading_text, level=3)
            i += 1
            continue

        # blockquote
        if line.startswith('> '):
            quote_text = line[2:].strip()
            p = doc.add_paragraph()
            run = p.add_run(quote_text)
            run.italic = True
            run.font.color.rgb = RGBColor(80, 80, 80)
            run.font.size = Pt(10)
            i += 1
            continue

        # 列表项
        if re.match(r'^[\s]*[-*]\s', line):
            item_text = re.sub(r'^[\s]*[-*]\s+', '', line)
            p = doc.add_paragraph(style='List Bullet')
            # 清除默认文本，添加格式化文本
            p.clear()
            add_styled_paragraph_content(p, item_text)
            i += 1
            continue

        # 有序列表项
        if re.match(r'^\s*\d+\.\s', line):
            item_text = re.sub(r'^\s*\d+\.\s+', '', line)
            p = doc.add_paragraph(style='List Number')
            p.clear()
            add_styled_paragraph_content(p, item_text)
            i += 1
            continue

        # 空行
        if not line.strip():
            i += 1
            continue

        # 普通段落
        # 处理行内格式
        add_styled_paragraph(doc, line)
        i += 1

    # 处理最后一个表格
    if in_table and table_lines:
        header = [c.strip() for c in table_lines[0].split('|') if c.strip()]
        data = []
        for tl in table_lines[1:]:
            row = [c.strip() for c in tl.split('|') if c.strip()]
            data.append(row)
        add_table_from_md(doc, header, data)

    doc.save(str(docx_path))
    print(f"[OK] Word 文档已生成: {docx_path}")


def add_styled_paragraph_content(p, text):
    """向已有段落添加带格式的文本（处理 **bold** 等）"""
    parts = re.split(r'(\*\*.*?\*\*|`.*?`)', text)
    for part in parts:
        if part.startswith('**') and part.endswith('**'):
            run = p.add_run(part[2:-2])
            run.bold = True
        elif part.startswith('`') and part.endswith('`'):
            run = p.add_run(part[1:-1])
            run.font.name = 'Consolas'
            run.font.size = Pt(10)
        else:
            run = p.add_run(part)
        run.font.name = '等线'
        rPr = run._element.get_or_add_rPr()
        rFonts = rPr.find(qn('w:rFonts'))
        if rFonts is None:
            rFonts = rPr.makeelement(qn('w:rFonts'), {})
            rPr.insert(0, rFonts)
        rFonts.set(qn('w:eastAsia'), '等线')


if __name__ == '__main__':
    convert_markdown_to_docx(INPUT_MD, OUTPUT_DOCX)
