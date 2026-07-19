#!/usr/bin/env python3
"""
评审矩阵 — AI Product Court 的第二个核心组件
=============================================

读取超级智囊生成的候选方案，由 6 个 Agent（3 行业专家 + 3 用户替身）
对每个候选进行独立评审，输出结构化评审意见 + 综合投票判定。

用法：
    python review_matrix.py [--input ./output/output.md] [--output ./output/review_output.md]

复用模块：
    - superbrain_agent.call_deepseek_api()    API 调用
    - superbrain_agent.load_markdown_file()   知识源加载
    - superbrain_agent.check_history_overlap()  历史相似检测
"""

import argparse
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import superbrain_agent as sa

# ── Agent 定义 ────────────────────────────────────────

EXPERT_AGENTS = [
    {
        "name": "成本专家",
        "role": "expert",
        "system_prompt": """你是 AI Product Court 的「成本专家」Agent。你的职责是从 BOM 成本、供应链成熟度、利润空间角度评审产品候选方案。

你的判断准则：
- 消费电子智能门锁的合理 BOM 增量区间：纯软件方案 $0-2/台（开发人力另计），传感器/模组类 $2-8/台，新型生物识别模组 $15-40/台
- 如果候选方案未明确给出成本估算，从技术路径推断成本量级
- 参考 case_studies.md：掌静脉（BIO-001）BOM增加$35+被否决——可作为高成本方案的参照基准
- 参考 case_studies.md：Ring Doorbell 成功证明了「降低门槛」的 ROI 高于「堆硬件」

输出格式（严格遵守）：
**立场**：支持/反对/中立
**理由**：[2-4句，包含成本量级判断和参照基准]
**依据**：[引用自哪个知识源文件的具体内容]""",
        "evidence_tags": ["competitors", "case_studies"],
    },
    {
        "name": "安全专家",
        "role": "expert",
        "system_prompt": """你是 AI Product Court 的「安全合规专家」Agent。你的职责是从数据安全、隐私合规、物理安全角度评审产品候选方案。

你的判断准则：
- 涉及生物特征（指纹/掌静脉/人脸/虹膜）采集 → 自动标注 GDPR/CCPA 合规风险
- 涉及云端数据传输/存储 → 检查是否设计了本地处理兜底
- 涉及权限管理/远程控制 → 检查是否有防滥用机制
- 参考 user_pain.md：P14（冬季锁不上=物理安全风险）、P17（数据存储不透明=隐私风险）、P18（面板失效=硬件可靠性风险）
- 参考 case_studies.md：掌静脉案例中"合规成本被低估"是核心反对理由

输出格式（严格遵守）：
**立场**：支持/反对/中立
**理由**：[2-4句，指明具体风险点和严重程度]
**依据**：[引用自哪个知识源文件的具体内容]""",
        "evidence_tags": ["user_pain", "case_studies"],
    },
    {
        "name": "市场专家",
        "role": "expert",
        "system_prompt": """你是 AI Product Court 的「市场专家」Agent。你的职责是从竞品格局、差异化窗口、市场规模角度评审产品候选方案。

你的判断准则：
- 参考 competitors.md：检查候选方向是否已被竞品覆盖（Yale/Schlage/August/Aqara/鹿客等）
- 判断差异化窗口期：竞品未覆盖=18个月+，已覆盖但未主推=12个月，已主推=窗口关闭
- 参考 case_studies.md：UWB案例中"生态就绪度>技术就绪度"是核心反对理由
- 关注「看不见的竞品」：不是只有同品类算竞品——比如传统钥匙+人工管理也是短租权限管理的竞品

输出格式（严格遵守）：
**立场**：支持/反对/中立
**理由**：[2-4句，包含竞品覆盖分析和窗口期判断]
**依据**：[引用自哪个知识源文件的具体内容]""",
        "evidence_tags": ["competitors", "case_studies"],
    },
]

USER_PERSONA_AGENTS = [
    {
        "name": "独居女性用户",
        "role": "user_persona",
        "persona": "28岁女性，独居城市公寓，对安全极度敏感，有过被尾随经历",
        "concerns": ["夜间安全", "断电/断网后门锁是否仍能正常工作", "异常开锁实时告警", "隐私数据不被滥用"],
        "system_prompt": """你是 AI Product Court 的「用户替身」Agent。你现在代表「独居女性用户」的利益发声。

你的画像：28岁女性，独居城市公寓，对安全极度敏感（有过被尾随经历）。你不是科技爱好者，但愿意为「安全感」付出合理溢价。

你评审时的关注点：
- 这个候选方案能让我晚上睡得更安心吗？还是增加了我对「锁会不会坏/被黑/没电」的焦虑？
- 断网断电后还能不能用？有没有机械钥匙兜底？
- 如果有人在门口反复尝试开锁，我会立刻知道吗？
- 我的开锁记录会不会被上传到我不认识的第三方？
- 参考 user_pain.md 中对应标签的真实差评内容来表达我的担忧

输出格式（严格遵守）：
**立场**：支持/反对/中立
**理由**：[2-4句，以第一人称表达，基于我的画像和关注点]
**依据**：[引用 user_pain.md 中哪条差评具体印证了我的担忧]""",
        "evidence_tags": ["user_pain"],
    },
    {
        "name": "多代同住家庭用户",
        "role": "user_persona",
        "persona": "40岁家长，与65+岁父母和10岁孩子同住，兼顾全家需求",
        "concerns": ["老人操作门槛", "儿童安全管控", "不同家庭成员的不同解锁方式", "可靠性（老人被锁门外=大问题）"],
        "system_prompt": """你是 AI Product Court 的「用户替身」Agent。你现在代表「多代同住家庭用户」的利益发声。

你的画像：40岁家长，与65+岁父母和10岁孩子同住。你的核心焦虑不是"最酷的开门方式"，而是"全家老小都能顺利进门"。

你评审时的关注点：
- 我爸妈（手指干燥指纹难识别、不太会用智能手机）能用这个吗？会不会被锁在门外？
- 我孩子放学回家我能知道吗？能不能限制他只能特定时段开门？
- 每个人用不同的开锁方式（我用人脸、爸妈用密码/卡片、孩子用指纹）——这个锁能同时支持吗？
- 参考 user_pain.md：P07（老人无法使用指纹）、P08（老人建议用密码替代）和 P06（指纹角度敏感）

输出格式（严格遵守）：
**立场**：支持/反对/中立
**理由**：[2-4句，以第一人称表达，基于我的家庭情况]
**依据**：[引用 user_pain.md 中哪条差评具体印证了我的担忧]""",
        "evidence_tags": ["user_pain"],
    },
    {
        "name": "短租房东用户",
        "role": "user_persona",
        "persona": "管理5套Airbnb房源的海外房东，核心痛点是权限管理的效率",
        "concerns": ["远程授权效率", "多房源统一管理", "租客权限到期自动失效", "纠纷时可远程冻结"],
        "system_prompt": """你是 AI Product Court 的「用户替身」Agent。你现在代表「短租房东用户」的利益发声。

你的画像：管理5套Airbnb房源的海外房东。你对门锁的需求不是「能开门」——那个用钥匙也能做到——而是「能远程管理不断换人的权限」。

你评审时的关注点：
- 每换一个租客，我需要手动删旧密码、设新密码吗？这个过程能不能自动化？
- 租客到了门口但密码不生效——我人在另一个城市怎么办？有没有离线应急方案？
- 我的清洁工、维修工也需要进门——能不能给不同角色设不同的权限策略？
- 参考 user_pain.md：P25（清洁工日期限定的临时密码）、P26（快递员远程开门）、P27（Airbnb场景需求）

输出格式（严格遵守）：
**立场**：支持/反对/中立
**理由**：[2-4句，以第一人称表达，基于我的房源管理场景]
**依据**：[引用 user_pain.md 中哪条差评具体印证了我的担忧]""",
        "evidence_tags": ["user_pain"],
    },
]


def get_all_agents() -> list[dict]:
    """返回全部 6 个 Agent 定义"""
    return EXPERT_AGENTS + USER_PERSONA_AGENTS


def get_expert_agents() -> list[dict]:
    """返回 3 个行业专家 Agent"""
    return EXPERT_AGENTS


def get_user_persona_agents() -> list[dict]:
    """返回 3 个用户替身 Agent"""
    return USER_PERSONA_AGENTS


# ── 候选方案解析 ──────────────────────────────────────

def parse_candidates_from_output(content: str) -> list[dict]:
    """
    从 output.md 的内容中解析候选方案列表。

    返回: [{"name": "候选一：eufy SenseLock", "content": "该候选的原始 markdown 文本"}, ...]
    """
    if not content:
        return []

    candidates = []
    # 匹配 #### 候选一/二/三/四... 到下一个 #### 候选 或 ### 章节之间
    pattern = re.compile(
        r"(####\s+候选[一二三四五六七八九十\d]+[：:][^\n]*\n"
        r".*?"
        r"(?=####\s+候选[一二三四五六七八九十\d]+|###\s+⚠️|###\s+📋|\Z))",
        re.DOTALL,
    )
    matches = pattern.findall(content)

    for match in matches:
        # 提取名称（第一行）
        name_line = match.strip().split("\n")[0]
        name = re.sub(r"^####\s+", "", name_line).strip()
        candidates.append({
            "name": name,
            "content": match.strip(),
        })

    return candidates


# ── 评审 Prompt 构建 ──────────────────────────────────

def build_review_prompt(agent: dict, candidate: dict, knowledge_sources: dict[str, str]) -> tuple[str, str]:
    """
    为指定 Agent 构建评审 prompt。

    返回: (system_prompt, user_prompt)
    """
    system_prompt = agent["system_prompt"]

    # 用户 prompt：候选方案 + 相关知识源
    user_parts = [
        f"## 待评审候选方案：{candidate['name']}\n\n{candidate['content']}",
    ]

    # 根据 Agent 的 evidence_tags 注入相关知识源
    for tag in agent.get("evidence_tags", []):
        if tag in knowledge_sources and knowledge_sources[tag]:
            tag_labels = {
                "competitors": "竞品知识库",
                "user_pain": "用户差评证据库",
                "case_studies": "产品案例库",
            }
            label = tag_labels.get(tag, tag)
            user_parts.append(f"## {label}\n\n{knowledge_sources[tag]}")

    user_parts.append(
        "## 评审指令\n\n"
        "请以你被赋予的角色身份，对上述候选方案进行独立评审。\n"
        "严格遵守输出格式：\n"
        "**立场**：支持/反对/中立\n"
        "**理由**：[2-4句具体理由]\n"
        "**依据**：[引用上述知识源中的具体内容]\n\n"
        "重要提醒：\n"
        "- 你的判断必须基于提供的知识源证据，而非个人偏好\n"
        "- 如果你支持，说明为什么在「你的优化目标」下这个方案是好的\n"
        "- 如果你反对，说明具体风险和知识源中哪条证据支持你的担忧\n"
        "- 不要给出模棱两可的判断——必须选择支持/反对/中立中的一个"
    )

    user_prompt = "\n\n".join(user_parts)
    return system_prompt, user_prompt


# ── 评审响应解析 ──────────────────────────────────────

def parse_review_response(response: str) -> dict:
    """
    解析 Agent 返回的评审文本，提取结构化字段。

    返回: {"stance": "support"|"oppose"|"neutral", "reason": "...", "evidence_source": "..."}
    """
    response = response.strip()

    stance = "neutral"
    reason = ""
    evidence_source = None

    # 解析立场
    stance_pattern = re.compile(r"\*\*立场\*\*[：:]\s*(.+)")
    stance_match = stance_pattern.search(response)
    if stance_match:
        stance_text = stance_match.group(1).strip().lower()
        if "反对" in stance_text:
            stance = "oppose"
        elif "支持" in stance_text:
            stance = "support"
        else:
            stance = "neutral"

    # 解析理由
    reason_pattern = re.compile(r"\*\*理由\*\*[：:]\s*(.+?)(?=\*\*依据\*\*|\Z)", re.DOTALL)
    reason_match = reason_pattern.search(response)
    if reason_match:
        reason = reason_match.group(1).strip()

    # 如果没匹配到 **理由** 字段，从整体文本中取关键句
    if not reason:
        # 取第一段非空文本作为理由（fallback）
        lines = [l.strip() for l in response.split("\n") if l.strip() and not l.startswith("**")]
        if lines:
            reason = lines[0][:300]

    # 解析依据
    evidence_pattern = re.compile(r"\*\*依据\*\*[：:]\s*(.+?)(?=\n\n|\Z)", re.DOTALL)
    evidence_match = evidence_pattern.search(response)
    if evidence_match:
        evidence_source = evidence_match.group(1).strip()

    return {
        "stance": stance,
        "reason": reason,
        "evidence_source": evidence_source,
    }


# ── API 调用（复用 superbrain_agent） ─────────────────

def call_deepseek_api(api_key: str, model: str, system_prompt: str, user_prompt: str) -> str:
    """复用 superbrain_agent 的 DeepSeek API 调用（向后兼容）"""
    return sa.call_deepseek_api(api_key, model, system_prompt, user_prompt)


def call_deepseek_api_with_stats(api_key: str, model: str, system_prompt: str,
                                  user_prompt: str, label: str = "") -> tuple[str, dict]:
    """带统计的 API 调用"""
    import time
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=sa.DEEPSEEK_BASE_URL)
    start = time.time()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=2048,
    )
    elapsed = time.time() - start
    usage = response.usage
    stats = {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
        "elapsed_seconds": elapsed,
    }
    sa._usage_tracker.record(
        label=label,
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        elapsed_seconds=elapsed,
        model=model,
    )
    return response.choices[0].message.content, stats


# ── 编排评审 ──────────────────────────────────────────

def run_single_review(
    agent: dict, candidate: dict, knowledge_sources: dict[str, str], api_key: str
) -> dict:
    """执行单个 Agent 对单个候选的评审"""
    system_prompt, user_prompt = build_review_prompt(agent, candidate, knowledge_sources)
    raw_response, api_stats = call_deepseek_api_with_stats(
        api_key, "deepseek-chat", system_prompt, user_prompt,
        label=f"review:{agent['name']}:{candidate['name'][:30]}"
    )
    parsed = parse_review_response(raw_response)
    parsed["agent"] = agent["name"]
    parsed["candidate"] = candidate["name"]
    parsed["raw_response"] = raw_response
    parsed["_stats"] = api_stats
    return parsed


def run_review_matrix(
    candidates: list[dict],
    knowledge_sources: dict[str, str],
    decision_log: str | None,
    api_key: str,
) -> dict:
    """
    编排全部评审：3 个候选 × 6 个 Agent = 最多 18 次并行 API 调用。

    返回:
      {
        "candidates": [
          {
            "name": "...",
            "content": "...",
            "reviews": [{agent, stance, reason, evidence_source}, ...],
            "verdict": "pass"|"discuss"|"block",
            ...
          }, ...
        ],
        "meta": {...}
      }
    """
    agents = get_all_agents()
    results_per_candidate = []

    # 为每个候选做评审
    for candidate in candidates:
        reviews = []
        # 并行调用 6 个 Agent
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {
                executor.submit(run_single_review, agent, candidate, knowledge_sources, api_key): agent["name"]
                for agent in agents
            }
            for future in as_completed(futures):
                agent_name = futures[future]
                try:
                    review = future.result()
                    reviews.append(review)
                except Exception as e:
                    reviews.append({
                        "agent": agent_name,
                        "candidate": candidate["name"],
                        "stance": "neutral",
                        "reason": f"[评审出错: {str(e)}]",
                        "evidence_source": None,
                    })

        # 历史相似性检查
        history_context = None
        history_result = {"has_warning": False, "matched_ids": []}
        if decision_log:
            # 构造一个临时"输出"文本来检查历史相似
            temp_output = "### ⚠️ 历史相似性检查\n"
            # 把候选内容和 reviews 拼起来让 check_history_overlap 分析
            candidate_text_for_check = candidate["content"]
            combined = candidate_text_for_check + "\n" + temp_output
            history_result = sa.check_history_overlap(combined)

            # 如果候选本身没触发，尝试从 reviews 中检测
            if not history_result["has_warning"]:
                for r in reviews:
                    if r.get("raw_response"):
                        combined += "\n" + r["raw_response"]
                # 用包含所有 reviews 的文本再检查一次
                combined += "\n### ⚠️ 历史相似性检查\n"
                full_history_check = sa.check_history_overlap(combined)
                if full_history_check["has_warning"]:
                    history_result = full_history_check

        # 综合判定
        aggregate = aggregate_results(reviews, decision_log)
        aggregate["history_warning"] = history_result["has_warning"]
        aggregate["history_detail"] = (
            f"匹配历史记录: {', '.join(history_result['matched_ids'])}"
            if history_result["matched_ids"]
            else ""
        )

        results_per_candidate.append({
            "name": candidate["name"],
            "content": candidate["content"],
            "reviews": reviews,
            **aggregate,
        })

    return {
        "candidates": results_per_candidate,
        "meta": {
            "date": datetime.now().isoformat(),
            "model": "deepseek-chat",
            "total_agents": len(agents),
            "total_candidates": len(candidates),
            "decision_log_used": decision_log is not None,
        },
    }


# ── 综合判定 ──────────────────────────────────────────

def aggregate_results(reviews: list[dict], decision_log: str | None) -> dict:
    """
    基于 6 方评审结果做综合投票判定。

    规则：
      - 反对票 ≤1 → pass（建议通过）
      - 反对票 2-3 → discuss（建议进一步讨论）
      - 反对票 ≥4 → block（建议搁置）
      - 中立票不计入反对票

    返回: {verdict, support_count, oppose_count, neutral_count, total_agents,
            oppose_reasons, history_warning, history_detail}
    """
    oppose_count = sum(1 for r in reviews if r["stance"] == "oppose")
    support_count = sum(1 for r in reviews if r["stance"] == "support")
    neutral_count = sum(1 for r in reviews if r["stance"] == "neutral")
    total_agents = len(reviews)

    if total_agents == 0:
        return {
            "verdict": "discuss",
            "support_count": 0,
            "oppose_count": 0,
            "neutral_count": 0,
            "total_agents": 0,
            "oppose_reasons": [],
            "history_warning": False,
            "history_detail": "",
        }

    if oppose_count <= 1:
        verdict = "pass"
    elif oppose_count <= 3:
        verdict = "discuss"
    else:
        verdict = "block"

    oppose_reasons = [
        f"{r['agent']}: {r['reason'][:100]}"
        for r in reviews
        if r["stance"] == "oppose"
    ]

    # 历史相似检测 - 合并所有 review 文本检查
    history_warning = False
    history_detail = ""
    if decision_log:
        # 先检查 decision_log 本身是否包含警告文本
        combined_text = decision_log + "\n"
        combined_text += "\n".join([
            r.get("raw_response", "") for r in reviews if r.get("raw_response")
        ])
        history_result = sa.check_history_overlap(combined_text)
        if history_result["has_warning"]:
            history_warning = True
            history_detail = "匹配历史记录: " + ", ".join(history_result["matched_ids"])

    return {
        "verdict": verdict,
        "support_count": support_count,
        "oppose_count": oppose_count,
        "neutral_count": neutral_count,
        "total_agents": total_agents,
        "oppose_reasons": oppose_reasons,
        "history_warning": history_warning,
        "history_detail": history_detail,
    }


# ── 输出写入 ──────────────────────────────────────────

VERDICT_LABELS = {
    "pass": "✅ 建议通过",
    "discuss": "⚠️ 建议进一步讨论",
    "block": "❌ 建议搁置",
}


def write_review_output(results: dict, output_path: str):
    """将评审结果写入 markdown 文件"""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# AI Product Court — 评审矩阵输出",
        "",
        f"> 生成日期：{results['meta'].get('date', '')} | 模型：{results['meta'].get('model', '')}",
        f"> Agent 总数：{results['meta'].get('total_agents', 'N/A')}"
        f"（{results['meta'].get('total_candidates', len(results['candidates']))} 个候选"
        f" × {results['meta'].get('agents_per_candidate', 6)} 方评审）",
        f"> 历史裁决：{'已启用' if results['meta'].get('decision_log_used') else '未启用'}",
        "",
        "---",
        "",
    ]

    for i, candidate in enumerate(results["candidates"], 1):
        verdict_label = VERDICT_LABELS.get(candidate["verdict"], candidate["verdict"])
        history_note = ""
        if candidate.get("history_warning"):
            history_note = f"\n> 🔶 **历史裁决警告**：{candidate.get('history_detail', '')}"

        lines += [
            f"## 候选 {i}：{candidate['name']}",
            "",
            f"### 综合判定：{verdict_label}",
            f"",
            f"| 投票统计 | 数量 |",
            f"|---------|------|",
            f"| 支持 | {candidate.get('support_count', 0)} |",
            f"| 反对 | {candidate.get('oppose_count', 0)} |",
            f"| 中立 | {candidate.get('neutral_count', 0)} |",
            f"| 总计 | {candidate.get('total_agents', len(candidate.get('reviews', [])))} |",
            history_note,
            "",
        ]

        if candidate.get("oppose_reasons"):
            lines.append("**反对意见摘要：**")
            for reason in candidate["oppose_reasons"]:
                lines.append(f"- {reason}")
            lines.append("")

        lines.append("### 各方评审意见")
        lines.append("")

        for review in candidate["reviews"]:
            stance_icon = {"support": "🟢 支持", "oppose": "🔴 反对", "neutral": "🟡 中立"}
            icon = stance_icon.get(review["stance"], "⚪")

            lines += [
                f"#### {icon} — {review['agent']}",
                "",
                f"**理由**：{review['reason']}",
            ]
            if review.get("evidence_source"):
                lines.append(f"**依据**：{review['evidence_source']}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # 全局总结
    lines += [
        "## 评审总结",
        "",
        "| 候选方案 | 判定 | 支持 | 反对 | 中立 | 历史警告 |",
        "|---------|------|------|------|------|----------|",
    ]
    for c in results["candidates"]:
        v = VERDICT_LABELS.get(c["verdict"], c["verdict"])
        hw = "⚠️ 有" if c.get("history_warning") else "无"
        lines.append(
            f"| {c['name']} | {v} | {c.get('support_count', 0)} | "
            f"{c.get('oppose_count', 0)} | {c.get('neutral_count', 0)} | {hw} |"
        )

    lines += [
        "",
        "---",
        "",
        "> 🤖 本文件由 AI Product Court 评审矩阵自动生成",
        "> 所有评审意见的「依据」字段均引用自知识源文件，非凭空生成",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[OK] 评审输出已写入: {path.resolve()}")


# ── CLI 入口 ──────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="评审矩阵 — AI Product Court 多角色评审",
    )
    parser.add_argument("--input", default="./output/output.md",
                        help="超级智囊输出文件路径（默认: ./output/output.md）")
    parser.add_argument("--output", default="./output/review_output.md",
                        help="评审输出文件路径（默认: ./output/review_output.md）")
    parser.add_argument("--knowledge-dir", default="./knowledge",
                        help="知识源目录（默认: ./knowledge）")
    parser.add_argument("--history-dir", default="./history",
                        help="历史裁决记录目录（默认: ./history）")
    parser.add_argument("--api-key", default=None,
                        help="DeepSeek API Key（也可用环境变量 DEEPSEEK_API_KEY）")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅解析候选和构建 prompt，不调用 API")
    parser.add_argument("--max-candidates", type=int, default=3,
                        help="最多评审几个候选（默认: 3）")

    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key and not args.dry_run:
        print("[ERROR] 请设置 DEEPSEEK_API_KEY 环境变量或通过 --api-key 参数提供")
        sys.exit(1)

    # 加载输入
    print(">> 加载超级智囊输出...")
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERROR] 输入文件不存在: {input_path}")
        sys.exit(1)
    output_content = input_path.read_text(encoding="utf-8")
    # 去掉 YAML front matter（如果有）
    if output_content.startswith("---"):
        parts = output_content.split("---", 2)
        if len(parts) >= 3:
            output_content = parts[2]

    # 解析候选
    candidates = parse_candidates_from_output(output_content)
    print(f"   解析到 {len(candidates)} 个候选方案")
    if args.max_candidates:
        candidates = candidates[:args.max_candidates]

    # 加载知识源
    print(">> 加载知识源...")
    knowledge_dir = Path(args.knowledge_dir)
    knowledge = {}
    for fname in ["competitors", "user_pain", "case_studies"]:
        fpath = knowledge_dir / f"{fname}.md"
        knowledge[fname] = sa.load_markdown_file(str(fpath))
        status = "[OK]" if not knowledge[fname].startswith("[文件不存在") else "[WARN]"
        print(f"   {status} {fname}: {len(knowledge[fname])} 字符")

    # 校验知识源
    source_errors = sa.validate_knowledge_sources(knowledge)
    if source_errors:
        print("\n[ERROR] 知识源校验失败：")
        for err in source_errors:
            print(f"   - {err}")
        sys.exit(1)

    # 加载历史裁决
    decision_log = None
    history_dir = Path(args.history_dir)
    log_path = history_dir / "decision_log.md"
    if log_path.exists():
        decision_log = sa.load_markdown_file(str(log_path))
        print(f"   [OK] decision_log: {len(decision_log)} 字符")

    if args.dry_run:
        print(f"\n[DRY-RUN] 将评审 {len(candidates)} 个候选 × 6 Agent = {len(candidates) * 6} 次 API 调用")
        for i, c in enumerate(candidates, 1):
            print(f"   候选 {i}: {c['name']}")
        return

    # 执行评审
    total_calls = len(candidates) * 6
    print(f"\n>> 开始评审（{len(candidates)} 候选 × 6 Agent = {total_calls} 次并行 API 调用）...")
    results = run_review_matrix(candidates, knowledge, decision_log, api_key)

    for c in results["candidates"]:
        verdict_label = VERDICT_LABELS.get(c["verdict"], c["verdict"])
        # ASCII-safe print for Windows GBK terminals
        safe_label = verdict_label.encode("ascii", errors="replace").decode("ascii")
        print(f"   {c['name']}: {safe_label} "
              f"(支持{c['support_count']}/反对{c['oppose_count']}/中立{c['neutral_count']})")

    # 写入输出
    write_review_output(results, args.output)

    # 追加成本统计
    cost_summary = sa._usage_tracker.format_cost_summary()
    with open(args.output, "a", encoding="utf-8") as f:
        f.write("\n---\n\n")
        f.write(cost_summary)
        f.write("\n")

    print(f"\n{'='*60}")
    print(f"== 评审完成 ==")
    print(f"   API 调用: {total_calls} 次")
    print(f"   Token 总计: {sa._usage_tracker.summary()['total_tokens']:,}")
    print(f"   预估成本: ${sa._usage_tracker.summary()['total_cost']:.4f}")
    print(f"   输出: {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
