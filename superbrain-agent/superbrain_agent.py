#!/usr/bin/env python3
"""
超级智囊 Agent — AI Product Court 的最小可运行验证
====================================================

职责：基于三类知识源（竞品分析、用户差评、产品案例）生成有证据支撑的产品候选方案，
      而非凭空头脑风暴。

用法：
    # 基本运行
    python superbrain_agent.py

    # 指定自定义路径
    python superbrain_agent.py --knowledge-dir ./my_knowledge --output ./my_output.md

    # 指定 API Key（也可用环境变量 DEEPSEEK_API_KEY）
    python superbrain_agent.py --api-key sk-xxxxx

    # 使用历史裁决记录进行相似性检查（默认启用）
    python superbrain_agent.py --history-dir ./history

依赖：
    pip install openai

设计原则：
    - 不使用向量数据库/RAG框架，知识源全量拼入 prompt context
    - 内容量不大（总计 < 20KB），单次 API 调用即可
    - 知识源独立于脚本，方便替换内容测试不同场景
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# ── 常量 ──────────────────────────────────────────────
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_KNOWLEDGE_DIR = "./knowledge"
DEFAULT_HISTORY_DIR = "./history"
DEFAULT_OUTPUT = "./output/output.md"

# ── Prompt 模板 ───────────────────────────────────────

SYSTEM_PROMPT = """你是一个叫"超级智囊"的产品策略 Agent，属于"AI Product Court"多智能体产品评审系统。

你的核心职责：基于用户证据、竞品知识、产品案例三类知识源，交叉分析生成有依据的产品候选方案。

你不是在"头脑风暴创意"，而是在"基于证据推导机会"。

## 输出规则

1. 每个判断必须有证据来源——引用具体的竞品数据、用户评论或案例模式
2. 优先识别"被忽视的机会点"——竞品没做、用户抱怨但没人解决、案例模式提示可行的方向
3. 如果提供的知识源不足以支撑某个判断，标注"[证据不足]"而非凭空编造
4. 如果有历史裁决记录，必须检查新候选是否与已否决方向相似

## 输出格式

严格按以下 Markdown 结构输出，不要添加额外章节：

### 🔍 机会点识别
[1-2个被忽视的机会点，每个附证据引用]

### 💡 候选方案

#### 候选一：[名称]
- **核心卖点**：[一句话描述]
- **证据支撑**：
  - 用户痛点：[引用 user_pain.md 中的具体条目]
  - 竞品空白：[引用 competitors.md 中的具体数据]
  - 案例启示：[引用 case_studies.md 中的具体模式]
- **三维评估**：
  - 用户价值：⭐×N [说明]
  - 市场空白：⭐×N [说明]
  - 技术可行性：⭐×N [说明]
- **风险提示**：[主要风险]

#### 候选二：[名称]
[同上结构]

#### 候选三：[名称]
[同上结构]

### ⚠️ 历史相似性检查
[如果 history 包含否决记录且新候选与之相似，在此标注。如果无历史记录或不相似，写"未发现历史否决记录与新候选重叠。"]

### 📋 推荐优先级
[1-3 排序，简要说明理由]
"""


def load_markdown_file(filepath: str) -> str:
    """读取 markdown 文件，文件不存在时返回提示而非崩溃"""
    path = Path(filepath)
    if path.exists():
        return path.read_text(encoding="utf-8")
    else:
        return f"[文件不存在: {filepath}]"


def build_user_prompt(competitors: str, user_pain: str, case_studies: str,
                      decision_log: str | None) -> str:
    """将所有知识源和用户指令拼接为一个 user prompt"""

    prompt_parts = [
        "## 知识源 1：竞品分析",
        competitors,
        "---",
        "## 知识源 2：用户差评证据",
        user_pain,
        "---",
        "## 知识源 3：产品案例",
        case_studies,
    ]

    if decision_log:
        prompt_parts += [
            "---",
            "## 知识源 4：历史裁决记录（必须检查！）",
            decision_log,
        ]

    prompt_parts += [
        "---",
        "## 任务指令",
        "请基于以上三类（或四类）知识源，按照 System Prompt 中定义的输出格式，生成分析结果。",
        "",
        "关键要求：",
        "1. 识别 1-2 个被竞品忽视、被用户差评印证、且案例模式支持的机会点",
        "2. 生成 3 个候选产品概念，每个候选必须引用具体知识源作为证据",
        "3. 如果有历史裁决记录，检查新候选是否与已否决方向相似，并在输出中标注",
        "4. 不要生成与知识源无关的「灵感创意」——所有候选必须有据可查",
    ]

    return "\n\n".join(prompt_parts)


def call_deepseek_api(api_key: str, model: str, system_prompt: str,
                      user_prompt: str) -> str:
    """调用 DeepSeek API，返回模型生成的文本"""
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,      # 需要一定发散性，但不至于胡编
        max_tokens=4096,
    )

    return response.choices[0].message.content


def write_output(content: str, output_path: str, metadata: dict):
    """将模型输出写入 markdown 文件，附带元数据头部"""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    header = f"""---
title: 超级智囊 Agent 输出
date: {metadata.get("date", datetime.now().isoformat())}
model: {metadata.get("model", "unknown")}
knowledge_sources: {metadata.get("sources", [])}
history_used: {metadata.get("history_used", False)}
---

> 🤖 本文件由超级智囊 Agent 自动生成 | AI Product Court v1.0
> 所有候选方案的证据均引用自输入的知识源文件，非凭空生成

---

"""

    path.write_text(header + content, encoding="utf-8")
    print(f"[OK] 输出已写入: {path.resolve()}")


def main():
    parser = argparse.ArgumentParser(
        description="超级智囊 Agent — AI Product Court 最小可运行验证",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--knowledge-dir", default=DEFAULT_KNOWLEDGE_DIR,
        help=f"知识源目录，包含 competitors.md/user_pain.md/case_studies.md（默认: {DEFAULT_KNOWLEDGE_DIR}）"
    )
    parser.add_argument(
        "--history-dir", default=DEFAULT_HISTORY_DIR,
        help=f"历史裁决记录目录，包含 decision_log.md（默认: {DEFAULT_HISTORY_DIR}）"
    )
    parser.add_argument(
        "--output", default=DEFAULT_OUTPUT,
        help=f"输出文件路径（默认: {DEFAULT_OUTPUT}）"
    )
    parser.add_argument(
        "--api-key", default=None,
        help="DeepSeek API Key（也可用环境变量 DEEPSEEK_API_KEY）"
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        help=f"模型名称（默认: {DEFAULT_MODEL}）"
    )
    parser.add_argument(
        "--no-history", action="store_true",
        help="禁用历史裁决记录检索"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="仅打印 prompt 长度统计，不实际调用 API"
    )

    args = parser.parse_args()

    # ── 1. 获取 API Key ──
    api_key = args.api_key or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key and not args.dry_run:
        print("[ERROR] 请设置 DEEPSEEK_API_KEY 环境变量或通过 --api-key 参数提供")
        print("   export DEEPSEEK_API_KEY=sk-xxxxx")
        print("   或: python superbrain_agent.py --api-key sk-xxxxx")
        sys.exit(1)

    # ── 2. 加载知识源 ──
    print(">> 加载知识源文件...")
    knowledge_dir = Path(args.knowledge_dir)
    sources = {
        "competitors": load_markdown_file(str(knowledge_dir / "competitors.md")),
        "user_pain": load_markdown_file(str(knowledge_dir / "user_pain.md")),
        "case_studies": load_markdown_file(str(knowledge_dir / "case_studies.md")),
    }

    for name, content in sources.items():
        status = "[OK]" if not content.startswith("[文件不存在") else "[WARN]"
        print(f"   {status} {name}: {len(content)} 字符")

    # ── 3. 加载历史裁决记录（可选） ──
    decision_log = None
    history_used = False
    if not args.no_history:
        history_dir = Path(args.history_dir)
        log_path = history_dir / "decision_log.md"
        if log_path.exists():
            decision_log = load_markdown_file(str(log_path))
            history_used = True
            print(f"   [OK] decision_log: {len(decision_log)} 字符（将用于相似性检查）")
        else:
            print(f"   [INFO] decision_log.md 不存在，跳过历史检查")

    # ── 4. 构建 Prompt ──
    print("\n>> 构建 Prompt...")
    user_prompt = build_user_prompt(
        sources["competitors"],
        sources["user_pain"],
        sources["case_studies"],
        decision_log,
    )

    total_chars = len(SYSTEM_PROMPT) + len(user_prompt)
    print(f"   System Prompt: {len(SYSTEM_PROMPT)} 字符")
    print(f"   User Prompt: {len(user_prompt)} 字符")
    print(f"   总计: {total_chars} 字符 (~{total_chars // 4} tokens)")

    if args.dry_run:
        print("\n[DRY-RUN] Dry-run 模式，跳过 API 调用。")
        # 保存拼接后的完整 prompt 供调试
        debug_path = Path(args.output).parent / "debug_prompt.md"
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        debug_path.write_text(
            f"# System Prompt\n\n{SYSTEM_PROMPT}\n\n---\n\n# User Prompt\n\n{user_prompt}",
            encoding="utf-8"
        )
        print(f"   完整 prompt 已保存至: {debug_path.resolve()}")
        return

    # ── 5. 调用 API ──
    print(f"\n>> 调用 DeepSeek API (model={args.model})...")
    try:
        result = call_deepseek_api(api_key, args.model, SYSTEM_PROMPT, user_prompt)
        print(f"   返回: {len(result)} 字符")
    except Exception as e:
        print(f"[ERROR] API 调用失败: {e}")
        sys.exit(1)

    # ── 6. 写入输出 ──
    metadata = {
        "date": datetime.now().isoformat(),
        "model": args.model,
        "sources": list(sources.keys()),
        "history_used": history_used,
    }
    write_output(result, args.output, metadata)

    # ── 7. 摘要 ──
    print(f"\n{'='*60}")
    print(f"== 运行摘要 ==")
    print(f"   知识源: {len(sources)} 个文件")
    print(f"   历史检查: {'启用' if history_used else '未启用'}")
    print(f"   Prompt: ~{total_chars // 4} tokens")
    print(f"   模型: {args.model}")
    print(f"   输出: {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
