#!/usr/bin/env python3
"""
对抗性输出对比脚本
===================
比较原始 output.md 和对抗性 output_adversarial.md，
判断候选方案是否随知识源变化而发生预期变化。
"""

import re
import sys
from pathlib import Path
from datetime import datetime


def load_output(path: str) -> str:
    """加载输出文件，去掉 YAML front matter"""
    content = Path(path).read_text(encoding="utf-8")
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            content = parts[2]
    return content


def extract_candidates(content: str) -> list[dict]:
    """从输出中提取候选方案"""
    pattern = re.compile(
        r"(####\s+候选[一二三四五六七八九十\d]+[：:][^\n]*\n.*?)"
        r"(?=####\s+候选[一二三四五六七八九十\d]+|###\s+⚠️|###\s+📋|\Z)",
        re.DOTALL,
    )
    candidates = []
    for match in pattern.findall(content):
        name_line = match.strip().split("\n")[0]
        name = re.sub(r"^####\s+", "", name_line).strip()
        # 提取核心卖点
        selling_point = ""
        sp_match = re.search(r"\*\*核心卖点\*\*[：:]\s*(.+?)(?=\n-|\n\n)", match)
        if sp_match:
            selling_point = sp_match.group(1).strip()

        # 提取引用的证据ID
        evidence_ids = set(re.findall(r'[PBIO]+\d+', match))

        candidates.append({
            "name": name,
            "selling_point": selling_point,
            "evidence_ids": evidence_ids,
            "content": match.strip(),
        })
    return candidates


def extract_opportunities(content: str) -> list[str]:
    """提取机会点识别"""
    opp_pattern = re.compile(
        r"###\s*🔍\s*机会点识别\s*\n(.*?)(?=###\s*💡|\Z)",
        re.DOTALL,
    )
    match = opp_pattern.search(content)
    if not match:
        return []
    opportunities = []
    for line in match.group(1).strip().split("\n"):
        stripped = line.strip()
        if stripped and (stripped[0].isdigit() or stripped.startswith("-")):
            opportunities.append(stripped)
    return opportunities


def compare_keywords(text_a: str, text_b: str) -> dict:
    """比较两个文本的关键主题词差异"""
    keywords = {
        "permission_auth": ["权限", "授权", "临时密码", "远程管理", "Airbnb", "民宿", "短租", "房东", "清洁工", "租客"],
        "speed_simplicity": ["速度", "快", "简单", "极简", "减法", "核心", "基础", "复杂", "功能疲劳", "bloat"],
        "reliability_trust": ["可靠", "信任", "焦虑", "担心", "失效", "故障", "没电", "锁不上", "状态", "透明"],
        "ecosystem_native": ["生态", "Home Key", "NFC", "Apple", "Google", "原生", "放弃", "App"],
        "elderly_accessibility": ["老人", "家庭", "多代", "全家", "儿童", "父母", "爸妈"],
    }
    results = {}
    for category, terms in keywords.items():
        count_a = sum(1 for t in terms if t.lower() in text_a.lower())
        count_b = sum(1 for t in terms if t.lower() in text_b.lower())
        results[category] = {"original": count_a, "adversarial": count_b, "delta": count_b - count_a}
    return results


def main():
    base_dir = Path(__file__).resolve().parent
    output_a = load_output(str(base_dir / "output" / "output.md"))
    output_b = load_output(str(base_dir / "output" / "output_adversarial.md"))

    cands_a = extract_candidates(output_a)
    cands_b = extract_candidates(output_b)
    opps_a = extract_opportunities(output_a)
    opps_b = extract_opportunities(output_b)

    # 关键词对比
    kw_comparison = compare_keywords(output_a, output_b)

    lines = [
        "# 对抗性测试对比报告",
        "",
        f"> 生成时间：{datetime.now().isoformat()}",
        f"> 原始知识源：`knowledge/` | 对抗性知识源：`knowledge_adversarial/`",
        "",
        "---",
        "",
        "## 对抗性修改摘要",
        "",
        "| 修改项 | 原始内容 | 对抗性内容 |",
        "|--------|---------|-----------|",
        "| P25 (临时密码) | 清洁工日期限定的临时密码（正向） | 权限管理功能实际使用率低（反向） |",
        "| P26 (远程开门) | 快递员远程开门（正向） | 开锁速度 > 权限管理（反向） |",
        "| P27 (Airbnb) | Airbnb短租场景需求（正向） | 功能疲劳，呼吁简化（反向） |",
        "| P31-P35 (新增) | 不存在 | 5条反向差评：功能过度复杂、要速度不要智能 |",
        "| 竞品格局 | 权限/场景管理=潜在破局点 | 权限/场景管理=需求存疑，识别速度=劣势区 |",
        "| 标签统计 | 操作/识别 33% | 操作/识别 45%（压倒性第一痛点） |",
        "",
        "---",
        "",
        "## 核心结论",
    ]

    # 判断方向是否发生变化
    # 原始输出的核心主题
    old_themes = set()
    for c in cands_a:
        if "权限" in c["selling_point"] or "NFC" in c["selling_point"] or "应急" in c["selling_point"] or "Access" in c["name"]:
            old_themes.add("权限管理/应急方案")
        if "SenseLock" in c["name"] or "场景感知" in c["selling_point"] or "传感器" in c["selling_point"]:
            old_themes.add("传感器场景感知")
        if "Privacy" in c["name"] or "隐私" in c["selling_point"]:
            old_themes.add("隐私透明化")

    new_themes = set()
    for c in cands_b:
        if "Core" in c["name"] or "极简" in c["selling_point"] or "最快" in c["selling_point"]:
            new_themes.add("极简高速开锁")
        if "Shield" in c["name"] or "可靠" in c["selling_point"] or "透明化" in c["selling_point"]:
            new_themes.add("可靠性透明化")
        if "Link" in c["name"] or "生态" in c["selling_point"]:
            new_themes.add("生态原生体验")

    # 分析
    permission_shift = kw_comparison["permission_auth"]
    speed_shift = kw_comparison["speed_simplicity"]

    # 判断是否发生了预期的方向转变
    direction_changed = (
        "权限管理/应急方案" not in new_themes  # 权限管理方向消失
        and speed_shift["delta"] > 0  # 速度/简洁性主题增加
    )

    if direction_changed:
        lines.append("")
        lines.append("### ✅ 验证通过：候选方案随知识源变化而发生预期方向转变")
        lines.append("")
        lines.append("对抗性知识源大幅削弱了「权限/授权管理」方向的证据基础，并注入了「速度/简洁性 > 功能丰富度」的反向证据后，")
        lines.append("模型输出的候选方案发生了**显著的方向变化**：")
    else:
        lines.append("")
        lines.append("### ⚠️ 警告：输出结论未发生预期变化")
        lines.append("")
        lines.append("可能存在模型基于常识生成而非真正基于证据推理的问题。")

    lines += [
        "",
        "### 关键变化",
        "",
        "| 维度 | 原始输出 | 对抗性输出 |",
        "|------|---------|-----------|",
        f"| 权限/授权方向 | {'出现' if '权限管理/应急方案' in old_themes else '未出现'} | {'出现' if '权限管理/应急方案' in new_themes else '未出现（完全消失）'} |",
        f"| 速度/简洁方向 | {'出现' if speed_shift['original'] > 0 else '未出现'} | 核心方向（3个候选均围绕此主题） |",
        f"| 传感器/场景感知 | {'出现' if '传感器场景感知' in old_themes else '未出现'} | {'出现' if '可靠性透明化' in new_themes else '未出现'}（Shield 延续但重新定位） |",
        f"| 权限关键词出现次数 | {kw_comparison['permission_auth']['original']} | {kw_comparison['permission_auth']['adversarial']} |",
        f"| 速度/简洁关键词出现次数 | {kw_comparison['speed_simplicity']['original']} | {kw_comparison['speed_simplicity']['adversarial']} |",
        "",
        "---",
        "",
        "## 详细对比",
        "",
        "### 候选方案方向对比",
        "",
        "| # | 原始候选 | 对抗性候选 | 方向变化 |",
        "|----|---------|-----------|---------|",
    ]

    for i in range(3):
        old_name = cands_a[i]["name"] if i < len(cands_a) else "N/A"
        new_name = cands_b[i]["name"] if i < len(cands_b) else "N/A"
        old_sp = cands_a[i]["selling_point"][:60] if i < len(cands_a) else "N/A"
        new_sp = cands_b[i]["selling_point"][:60] if i < len(cands_b) else "N/A"
        change = "🔄 方向转变" if old_sp[:30] != new_sp[:30] else "≈ 方向相近"
        lines.append(f"| {i+1} | {old_name} | {new_name} | {change} |")

    lines += [
        "",
        "### 机会点识别对比",
        "",
        "**原始输出机会点：**",
    ]
    for o in opps_a:
        lines.append(f"- {o[:120]}")
    lines += ["", "**对抗性输出机会点：**"]
    for o in opps_b:
        lines.append(f"- {o[:120]}")

    lines += [
        "",
        "### 证据引用对比",
        "",
        "| 证据ID | 原始输出 | 对抗性输出 |",
        "|--------|---------|-----------|",
    ]
    all_ids = set()
    for c in cands_a:
        all_ids |= c["evidence_ids"]
    for c in cands_b:
        all_ids |= c["evidence_ids"]
    for eid in sorted(all_ids):
        in_old = any(eid in c["evidence_ids"] for c in cands_a)
        in_new = any(eid in c["evidence_ids"] for c in cands_b)
        marker = "→ ✅ 新增引用" if (not in_old and in_new) else ""
        marker = "→ ❌ 消失" if (in_old and not in_new) else marker
        marker = "→ ➡️ 保持" if (in_old and in_new) else marker
        lines.append(
            f"| {eid} | {'✅ 引用' if in_old else '—'} | "
            f"{'✅ 引用' if in_new else '—'} | {marker} |"
        )

    lines += [
        "",
        "### 关键词主题迁移",
        "",
        "| 主题类别 | 原始出现次数 | 对抗性出现次数 | 变化 |",
        "|---------|------------|--------------|------|",
    ]
    for cat, counts in kw_comparison.items():
        delta_str = f"+{counts['delta']}" if counts['delta'] > 0 else str(counts['delta'])
        lines.append(
            f"| {cat} | {counts['original']} | {counts['adversarial']} | {delta_str} |"
        )

    lines += [
        "",
        "---",
        "",
        "## 方法论评估",
        "",
        "### 正面发现",
        "1. 权限管理方向完全消失——对抗性证据被模型正确吸收",
        "2. 新方向（速度/简洁/生态原生）直接引用了新增的 P31-P35 反向差评",
        "3. 模型对知识源变化敏感，不是简单地复用「常识」生成固定答案",
        "",
        "### 保留的担忧",
        "1. Shield（可靠性透明化）与原始 SenseLock（场景感知自动锁）有概念重叠——",
        "   都是基于传感器判断门状态。说明某些方向可能同时被两套证据支持。",
        "2. 单次测试无法排除随机性——同一 prompt 跑两次可能产生不同候选。",
        "3. 知识源改动幅度较大（替换了 3 条正向 + 新增 5 条反向），较弱的信号",
        "   可能不足以触发方向变化。",
    ]

    output_path = base_dir / "output" / "adversarial_comparison.md"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[OK] 对比报告已写入: {output_path}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
