#!/usr/bin/env python3
"""
直接基于参考文档创建 Demo 验证报告 Word 版。
删除参考文档原有正文，保留样式定义，写入 Demo 报告内容。
"""

import re
import shutil
from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parent.parent.parent
INPUT_MD = ROOT / "AI_Product_Court_Demo验证报告.md"
REF_DOCX = ROOT / "AI_Product_Court_研究与落地方案_01初版(1).docx"
OUTPUT_DOCX = ROOT / "AI_Product_Court_Demo验证报告.docx"


def clear_body(doc):
    """清空文档正文，保留样式定义"""
    body = doc.element.body
    # 删除所有 <w:p> 和 <w:tbl> 元素
    ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    to_remove = []
    for child in body:
        if child.tag in (f'{{{ns}}}p', f'{{{ns}}}tbl',
                         f'{{{ns}}}sectPr'):
            to_remove.append(child)
    for child in to_remove:
        body.remove(child)
    # 重新添加 sectPr（页面设置）
    from lxml import etree
    sect_pr = etree.SubElement(body, f'{{{ns}}}sectPr')
    # 从参考文档复制页面设置
    ref_doc = Document(str(REF_DOCX))
    ref_body = ref_doc.element.body
    ref_sect = ref_body.find(f'{{{ns}}}sectPr')
    if ref_sect is not None:
        for attr, val in ref_sect.attrib.items():
            sect_pr.set(attr, val)
        for child in list(ref_sect):
            sect_pr.append(child)


def add_cover(doc):
    """封面页"""
    for _ in range(6):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("AI Product Court Demo 验证报告")
    r.font.size = Pt(22)
    r.bold = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("基于多智能体对抗模拟与决策记忆的产品创新验证体系").font.size = Pt(14)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("—— 以 eufy 智能门锁为验证场景的 Demo 验证与实验分析 ——").font.size = Pt(12)

    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("2026 AI 先锋未来人才大赛 · 安克创新赛道").font.size = Pt(12)
    doc.add_page_break()


def add_paragraph_text(p, text):
    """向段落添加带格式的文本（处理 **粗体** `代码`）"""
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
        r = p.add_run(line)
        r.font.name = 'Consolas'
        r.font.size = Pt(8.5)


def add_table_md(doc, rows):
    parsed = [[c.strip() for c in r.split('|') if c.strip()] for r in rows]
    if not parsed:
        return
    ncols = len(parsed[0])
    header = parsed[0]
    data = [row[:ncols] for row in parsed[1:]]

    table = doc.add_table(rows=1 + len(data), cols=ncols)
    table.style = 'Table Grid'
    for ci, h in enumerate(header):
        cell = table.rows[0].cells[ci]
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


def build():
    # 从参考文档复制出模板文件
    import tempfile, os
    tmpfd, tmppath = tempfile.mkstemp(suffix='.docx')
    os.close(tmpfd)
    shutil.copy2(str(REF_DOCX), tmppath)
    doc = Document(tmppath)

    # 清空正文
    clear_body(doc)

    # 封面
    add_cover(doc)

    # 解析 markdown
    text = Path(INPUT_MD).read_text(encoding='utf-8')
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
               (line.startswith('> ') and ('多智能体' in line or '2026 AI' in line)):
                i += 1
                continue
            if line.strip() == '---':
                skipped = True
                i += 1
                continue
            i += 1
            continue

        if line.strip() == '---':
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
            # fall through

        # 一级标题 ## 1. → 参考文档样式 "1"
        if line.startswith('## ') and re.match(r'^##\s+\d+\.', line):
            h = line[3:].strip()
            p = doc.add_paragraph()
            # 模仿参考文档的章节标题格式：加粗、字号略大
            r = p.add_run(h)
            r.bold = True
            r.font.size = Pt(14)
            p.paragraph_format.space_before = Pt(18)
            p.paragraph_format.space_after = Pt(10)
            i += 1
            continue

        # 二级标题 ## 非数字开头
        if line.startswith('## '):
            h = line[3:].strip()
            p = doc.add_paragraph()
            r = p.add_run(h)
            r.bold = True
            r.font.size = Pt(13)
            p.paragraph_format.space_before = Pt(12)
            p.paragraph_format.space_after = Pt(6)
            i += 1
            continue

        # 三级标题 ###
        if line.startswith('### '):
            h = line[4:].strip()
            p = doc.add_paragraph()
            r = p.add_run(h)
            r.bold = True
            r.font.size = Pt(12)
            p.paragraph_format.space_before = Pt(10)
            p.paragraph_format.space_after = Pt(4)
            i += 1
            continue

        # blockquote
        if line.startswith('> '):
            p = doc.add_paragraph()
            r = p.add_run(line[2:].strip())
            r.italic = True
            r.font.size = Pt(10)
            i += 1
            continue

        # 无序列表 -**
        m = re.match(r'^(\s*)[-*]\s+(.+)', line)
        if m:
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(1.27)
            p.paragraph_format.first_line_indent = Cm(-0.63)
            add_paragraph_text(p, "• " + m.group(2))
            i += 1
            continue

        # 有序列表
        m = re.match(r'^\s*(\d+)\.\s+(.+)', line)
        if m:
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(1.27)
            p.paragraph_format.first_line_indent = Cm(-0.63)
            add_paragraph_text(p, f"{m.group(1)}. {m.group(2)}")
            i += 1
            continue

        # 空行
        if not line.strip():
            i += 1
            continue

        # 普通段落
        p = doc.add_paragraph()
        p.paragraph_format.first_line_indent = Cm(0.74)  # 首行缩进两字符
        add_paragraph_text(p, line)
        i += 1

    # 末尾表格
    if in_table and table_rows:
        add_table_md(doc, table_rows)

    # 先存到临时文件，再覆盖（避免文件被占用的问题）
    import tempfile, os
    tmpfd, tmppath = tempfile.mkstemp(suffix='.docx', dir=str(ROOT))
    os.close(tmpfd)
    doc.save(tmppath)
    # 删除旧文件并替换
    if Path(OUTPUT_DOCX).exists():
        try:
            Path(OUTPUT_DOCX).unlink()
        except PermissionError:
            alt = str(OUTPUT_DOCX).replace('.docx', '_new.docx')
            shutil.copy2(tmppath, alt)
            print(f"原文件被占用，已保存到: {alt}")
            print("请关闭 Word 后将该文件重命名为原文件名")
            return
    shutil.copy2(tmppath, str(OUTPUT_DOCX))
    Path(tmppath).unlink()
    print(f"Done: {OUTPUT_DOCX}")


if __name__ == '__main__':
    build()
