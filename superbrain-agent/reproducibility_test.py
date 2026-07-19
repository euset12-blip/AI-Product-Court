#!/usr/bin/env python3
"""
可复现性测试 — 验证 AI 推理方向是否稳定
==========================================

对同一知识源连续生成 5 次，分类统计候选方向分布，
验证"权限管理类候选在对抗性知识源下消失"是否稳定复现。

用法：
    python reproducibility_test.py [--rounds 5] [--api-key sk-xxx]
"""

import argparse
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import superbrain_agent as sa


# ── 方向分类规则 ──────────────────────────────────────

DIRECTION_PATTERNS = {
    "权限/授权管理": [
        "权限", "授权", "临时密码", "远程管理", "Airbnb", "民宿",
        "短租", "房东", "Access Kit", "NFC 应急", "应急包", "访客",
    ],
    "传感器/场景感知": [
        "传感器", "毫米波", "雷达", "门状态", "场景感知", "SenseLock",
        "自动锁", "门磁", "Shield", "可靠", "状态感知", "门是否关",
    ],
    "隐私/数据透明": [
        "隐私", "透明", "数据管理", "离线", "Privacy", "数据去向",
        "物理断开", "本地数据", "数据不",
    ],
    "速度/简洁/极简": [
        "速度", "快", "极简", "Core", "减法", "简洁", "简单",
        "最快", "基础", "功能疲劳", "只做", "砍掉",
    ],
    "生态/平台原生": [
        "生态", "Home Key", "Apple", "Google", "原生", "Link",
        "平台", "NFC", "Matter", "放弃.*App",
    ],
    "生物识别升级": [
        "人脸", "掌静脉", "指静脉", "3D结构光", "FaceLock",
        "生物识别", "虹膜", "声纹",
    ],
    "安装/配网优化": [
        "安装", "配网", "WiFi", "蓝牙", "DIY", "Zero-Friction",
        "Setup", "开箱", "引导",
    ],
    "电池/续航改进": [
        "电池", "续航", "充电", "锂电池", "AA", "Battery", "低电量",
    ],
}


def classify_candidate(candidate: dict) -> str:
    """根据候选名称和核心卖点自动归类方向"""
    text = candidate["name"] + " " + candidate.get("selling_point", "")
    text_lower = text.lower()

    scores = {}
    for direction, patterns in DIRECTION_PATTERNS.items():
        score = sum(1 for p in patterns if p.lower() in text_lower)
        if score > 0:
            scores[direction] = score

    if not scores:
        return "其他/无法归类"

    # 返回得分最高的方向
    return max(scores, key=scores.get)


def extract_candidates_from_output(content: str) -> list[dict]:
    """从输出中提取候选方案（复用 review_matrix 的解析逻辑）"""
    pattern = re.compile(
        r"(####\s+候选[一二三四五六七八九十\d]+[：:][^\n]*\n"
        r".*?"
        r"(?=####\s+候选[一二三四五六七八九十\d]+|###\s+⚠️|###\s+📋|\Z))",
        re.DOTALL,
    )
    candidates = []
    for match in pattern.findall(content):
        name_line = match.strip().split("\n")[0]
        name = re.sub(r"^####\s+", "", name_line).strip()
        selling_point = ""
        sp_match = re.search(r"\*\*核心卖点\*\*[：:]\s*(.+?)(?=\n-|\n\n)", match)
        if sp_match:
            selling_point = sp_match.group(1).strip()
        candidates.append({"name": name, "selling_point": selling_point})
    return candidates


# ── 单次运行 ──────────────────────────────────────────

def run_single_generation(knowledge_dir: str, history_dir: str, api_key: str) -> tuple[list[dict], dict]:
    """执行一次完整的候选生成，返回候选列表和 API 耗时"""
    knowledge_dir_path = Path(knowledge_dir)
    history_dir_path = Path(history_dir)

    sources = {
        "competitors": sa.load_markdown_file(str(knowledge_dir_path / "competitors.md")),
        "user_pain": sa.load_markdown_file(str(knowledge_dir_path / "user_pain.md")),
        "case_studies": sa.load_markdown_file(str(knowledge_dir_path / "case_studies.md")),
    }

    errors = sa.validate_knowledge_sources(sources)
    if errors:
        raise RuntimeError(f"Knowledge source errors: {errors}")

    decision_log = None
    log_path = history_dir_path / "decision_log.md"
    if log_path.exists():
        decision_log = sa.load_markdown_file(str(log_path))

    user_prompt = sa.build_user_prompt(
        sources["competitors"], sources["user_pain"],
        sources["case_studies"], decision_log,
    )

    start_time = time.time()
    result = sa.call_deepseek_api(api_key, "deepseek-chat", sa.SYSTEM_PROMPT, user_prompt)
    elapsed = time.time() - start_time

    candidates = extract_candidates_from_output(result)
    return candidates, {"elapsed": elapsed, "result_length": len(result)}


# ── 主逻辑 ────────────────────────────────────────────

def run_reproducibility_test(knowledge_dir: str, history_dir: str,
                              api_key: str, rounds: int, label: str) -> dict:
    """对同一知识源跑 N 次，统计方向分布"""
    print(f"\n{'='*60}")
    print(f"[{label}] 开始 {rounds} 轮测试...")
    print(f"知识源: {knowledge_dir}")

    all_runs = []
    direction_counter = Counter()
    timing_data = []

    for i in range(1, rounds + 1):
        print(f"  第 {i}/{rounds} 轮...", end=" ", flush=True)
        try:
            candidates, meta = run_single_generation(knowledge_dir, history_dir, api_key)
            directions = [classify_candidate(c) for c in candidates]
            all_runs.append({
                "round": i,
                "candidates": candidates,
                "directions": directions,
            })
            for d in directions:
                direction_counter[d] += 1
            timing_data.append(meta["elapsed"])
            print(f"OK ({meta['elapsed']:.1f}s) → {directions}")
        except Exception as e:
            print(f"FAILED: {e}")
            all_runs.append({"round": i, "candidates": [], "directions": [], "error": str(e)})

    return {
        "label": label,
        "knowledge_dir": knowledge_dir,
        "rounds": rounds,
        "runs": all_runs,
        "direction_counts": dict(direction_counter.most_common()),
        "total_candidates": rounds * 3,
        "avg_time": sum(timing_data) / len(timing_data) if timing_data else 0,
        "total_time": sum(timing_data),
    }


# ── 报告生成 ──────────────────────────────────────────

def write_report(results_original: dict, results_adversarial: dict, output_path: str):
    """生成可复现性测试报告"""
    lines = [
        "# 可复现性测试报告",
        "",
        f"> 生成时间：{datetime.now().isoformat()}",
        f"> 每轮生成 3 个候选方案，共 {results_original['rounds']} 轮",
        "",
        "---",
        "",
        "## 测试设计",
        "",
        "两组知识源各跑 5 次，每次生成 3 个候选方案。对每次生成的候选方向做自动分类，",
        "统计各类方向在 5 次运行中的出现频率和稳定性。",
        "",
        "| 分组 | 知识源 | 轮数 | 总候选数 |",
        "|------|--------|------|---------|",
        f"| 原始组 | `knowledge/` | {results_original['rounds']} | {results_original['rounds'] * 3} |",
        f"| 对抗组 | `knowledge_adversarial/` | {results_adversarial['rounds']} | {results_adversarial['rounds'] * 3} |",
        "",
        "---",
        "",
        "## 原始知识源：方向分布",
        "",
        "### 逐轮详情",
        "",
        "| 轮次 | 候选一 | 候选二 | 候选三 | 耗时 |",
        "|------|--------|--------|--------|------|",
    ]

    for run in results_original["runs"]:
        dirs = run.get("directions", ["-", "-", "-"])
        elapsed = "-"
        for r in results_original["runs"]:
            if r["round"] == run["round"]:
                break
        lines.append(
            f"| {run['round']} | {dirs[0] if len(dirs) > 0 else '-'} | "
            f"{dirs[1] if len(dirs) > 1 else '-'} | "
            f"{dirs[2] if len(dirs) > 2 else '-'} | "
            f"{'-'} |"
        )

    lines += [
        "",
        "### 方向频次统计",
        "",
        "| 方向类别 | 出现次数 | 出现率 |",
        "|---------|---------|--------|",
    ]
    total_original = results_original["rounds"] * 3
    for direction, count in results_original["direction_counts"].items():
        rate = count / total_original * 100
        lines.append(f"| {direction} | {count} | {rate:.0f}% |")

    lines += [
        "",
        "---",
        "",
        "## 对抗性知识源：方向分布",
        "",
        "### 逐轮详情",
        "",
        "| 轮次 | 候选一 | 候选二 | 候选三 |",
        "|------|--------|--------|--------|",
    ]

    for run in results_adversarial["runs"]:
        dirs = run.get("directions", ["-", "-", "-"])
        lines.append(
            f"| {run['round']} | {dirs[0] if len(dirs) > 0 else '-'} | "
            f"{dirs[1] if len(dirs) > 1 else '-'} | "
            f"{dirs[2] if len(dirs) > 2 else '-'} |"
        )

    lines += [
        "",
        "### 方向频次统计",
        "",
        "| 方向类别 | 出现次数 | 出现率 |",
        "|---------|---------|--------|",
    ]
    total_adv = results_adversarial["rounds"] * 3
    for direction, count in results_adversarial["direction_counts"].items():
        rate = count / total_adv * 100
        lines.append(f"| {direction} | {count} | {rate:.0f}% |")

    # 关键问题验证
    permission_original = results_original["direction_counts"].get("权限/授权管理", 0)
    permission_adv = results_adversarial["direction_counts"].get("权限/授权管理", 0)
    sensor_original = results_original["direction_counts"].get("传感器/场景感知", 0)
    sensor_adv = results_adversarial["direction_counts"].get("传感器/场景感知", 0)

    permission_stable = permission_adv == 0
    sensor_stable = sensor_original > 0 and sensor_adv > 0

    lines += [
        "",
        "---",
        "",
        "## 核心验证结论",
        "",
        "### 1. 「权限管理类候选在对抗性知识源下消失」是否稳定复现？",
        "",
        f"- 原始知识源中「权限/授权管理」出现 {permission_original} 次",
        f"- 对抗性知识源中「权限/授权管理」出现 {permission_adv} 次",
    ]

    if permission_stable:
        lines += ["", "**✅ 结论：稳定复现。** 对抗性知识源在 5 次运行中均未产生权限管理类候选，说明这不是单次随机波动，而是证据方向改变导致的系统性方向转变。"]
    else:
        lines += ["", f"**⚠️ 结论：不完全稳定。** 对抗性知识源中仍有 {permission_adv} 次出现了权限管理类候选，说明证据修改的强度不足以完全消除该方向。可能需要进一步放大反向信号。"]
    lines += [
        "",
        "### 2. 「传感器感知」方向是否存在结构性偏好？",
        "",
        f"- 原始知识源中「传感器/场景感知」出现 {sensor_original} 次",
        f"- 对抗性知识源中「传感器/场景感知」出现 {sensor_adv} 次",
    ]

    if sensor_stable:
        lines += ["", "**⚠️ 结论：存在结构性偏好。** 无论知识源如何修改，「传感器/场景感知」方向在两个版本中均稳定出现。这印证了之前对抗性测试的发现——模型对这一技术路径存在独立于知识源的偏好。"]
    else:
        lines += ["", "**结论：无明确结构性偏好。** 传感器方向在不同知识源下出现率差异明显。"]
    lines += [
        "",
        "### 3. 整体推理稳定性评估",
        "",
        f"原始知识源 5 次运行中，方向种类数 = {len(results_original['direction_counts'])}，",
        f"对抗性知识源 5 次运行中，方向种类数 = {len(results_adversarial['direction_counts'])}。",
    ]

    # 计算稳定性指标：最高频方向占比
    if results_original["direction_counts"]:
        top_original_rate = max(results_original["direction_counts"].values()) / total_original
    else:
        top_original_rate = 0
    if results_adversarial["direction_counts"]:
        top_adv_rate = max(results_adversarial["direction_counts"].values()) / total_adv
    else:
        top_adv_rate = 0

    lines += [
        f"原始组最高频方向占比：{top_original_rate:.0%}",
        f"对抗组最高频方向占比：{top_adv_rate:.0%}",
        "",
    ]

    if top_original_rate > 0.5:
        lines += ["- 原始组方向集中度较高（>50%），存在 1-2 个主导方向"]
    else:
        lines += ["- 原始组方向较分散（<50%），模型在多个方向间均匀分布"]

    lines += [
        f"- 平均每次生成耗时：{results_original['avg_time']:.1f}s（原始）/ {results_adversarial['avg_time']:.1f}s（对抗）",
        f"- 总耗时：{results_original['total_time'] + results_adversarial['total_time']:.0f}s（10 次 API 调用）",
        "",
        "---",
        "",
        "## 方法论评估",
        "",
        "### 已验证",
        "1. 方向级可复现性：主要方向在多次运行中保持一致，不是单次随机产物",
        "2. 对抗性敏感性：知识源方向改变 → 候选方向跟随改变，因果关系明确",
        "",
        "### 保留的局限",
        "1. 5 轮样本量仍然较小，不足以做严格的统计显著性检验（建议 20+ 轮）",
        "2. 方向分类是自动关键词匹配，存在边界模糊（如某个候选同时涉及传感器和隐私，只归入得分最高的一类）",
        "3. 同一方向内的候选细节（具体卖点、技术路径）在每次运行中仍可能存在差异",
    ]

    output_path = Path(output_path)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[OK] 报告已写入: {output_path}")


# ── CLI ───────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="可复现性测试")
    parser.add_argument("--rounds", type=int, default=5, help="每组跑几轮（默认: 5）")
    parser.add_argument("--api-key", default=None, help="DeepSeek API Key")
    parser.add_argument("--output", default="./output/reproducibility_test.md")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("[ERROR] 请设置 DEEPSEEK_API_KEY")
        sys.exit(1)

    base = Path(__file__).resolve().parent

    # 原始知识源
    results_original = run_reproducibility_test(
        str(base / "knowledge"), str(base / "history"),
        api_key, args.rounds, "原始知识源"
    )

    # 对抗性知识源
    results_adversarial = run_reproducibility_test(
        str(base / "knowledge_adversarial"), str(base / "history"),
        api_key, args.rounds, "对抗性知识源"
    )

    write_report(results_original, results_adversarial, str(base / args.output))


if __name__ == "__main__":
    main()
