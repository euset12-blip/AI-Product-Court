# 超级智囊 Agent — 最小可运行验证

> **AI Product Court** 多智能体产品评审系统的核心组件之一
>
> 基于三类知识源（竞品/差评/案例）→ 交叉分析 → 输出有证据支撑的产品候选方案

---

## 这是什么

"超级智囊"是 AI Product Court 系统中负责**提案生成**的 Agent。与传统"AI头脑风暴"不同，它不凭空创造灵感，而是**基于真实用户证据、竞品分析和行业案例的交叉推理**来推导产品机会。

这个目录是超级智囊 Agent 的**最小可运行验证**——一个200行的 Python 脚本 + 三份手写知识源文件，证明"证据驱动的产品候选生成"是可以跑通的。

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 设置 API Key
# 方式A：环境变量（推荐）
export DEEPSEEK_API_KEY=sk-xxxxx

# 方式B：命令行参数
python superbrain_agent.py --api-key sk-xxxxx

# 3. 运行
python superbrain_agent.py

# 4. 查看输出
cat output/output.md
```

## 输入 → 输出

```
knowledge/                    history/
├── competitors.md ───┐       └── decision_log.md (可选)
├── user_pain.md ─────┤                │
└── case_studies.md ──┘                │
       │                               │
       ▼                               ▼
  ┌─────────────────────────────────────────┐
  │         superbrain_agent.py             │
  │  • 全量加载知识源到 Prompt Context      │
  │  • 检查历史裁决记录（避免重复踩坑）      │
  │  • 调用 DeepSeek API                    │
  │  • 输出结构化 Markdown                   │
  └─────────────────────────────────────────┘
                        │
                        ▼
                 output/output.md
            ┌───────────────────────┐
            │ 🔍 机会点识别          │
            │ 💡 3个候选方案         │
            │   • 核心卖点            │
            │   • 证据支撑（引用知识源）│
            │   • 三维评估            │
            │ ⚠️ 历史相似性检查      │
            │ 📋 推荐优先级          │
            └───────────────────────┘
```

## 知识源说明

| 文件 | 内容 | 数据来源 |
|------|------|---------|
| `knowledge/competitors.md` | 8款智能门锁竞品（eufy/Aqara/鹿客/Yale/Schlage/August/德施曼/TCL）的定位、卖点、差评 | 品牌官网 + Amazon + 媒体评测 |
| `knowledge/user_pain.md` | 24条真实用户差评，按4类标签分类（网络/操作/隐私/成本），附正负向统计 | Amazon.com 10款eufy门锁 × 80条真实评论 |
| `knowledge/case_studies.md` | 4个消费电子成功/失败案例，含5条可复用决策模式 | Ring/Apple/Nest/Schlage 公开资料 |
| `history/decision_log.md` | 3条历史裁决记录（掌静脉延迟、UWB否决、电池通过） | AI Product Court 过往评审 |

## 命令行选项

```
python superbrain_agent.py [OPTIONS]

  --knowledge-dir PATH   知识源目录（默认: ./knowledge）
  --history-dir PATH     历史裁决记录目录（默认: ./history）
  --output PATH          输出文件路径（默认: ./output/output.md）
  --api-key KEY          DeepSeek API Key
  --model NAME           模型名称（默认: deepseek-chat）
  --no-history           禁用历史裁决记录检查
  --dry-run              仅统计 prompt 长度，不调用 API
```

## 回归测试（演示"避开历史失败路径"）

1. 正常运行脚本，查看输出中"历史相似性检查"部分
2. 修改 `knowledge/` 中的内容，加入一个与"掌静脉"或"UWB"类似的新技术方向
3. 重新运行，观察输出是否标注 "⚠️ 历史相似警告：该方向与 BIO-001 裁决相似"

这一步演示了 AI Product Court 的核心价值：**不是每次提案都从零开始，而是能检索过去的踩坑记录并主动预警**。

## 设计原则

- **不使用向量数据库/RAG**：知识源总计 < 20KB，全量拼入 Prompt Context 即可
- **知识源与代码分离**：修改知识源文件即可测试不同场景，无需改代码
- **输出侧重"可追溯"**：每个候选必须标注证据来自哪个知识源文件的哪条内容
- **历史裁决是知识源的一部分**：不做复杂的语义检索，直接让 LLM 做相似性判断

## 相关链接

- [AI Product Court 完整方案](../README.md)
- [方法论设计](../02-方法论设计.md)
- [产品案例演示](../04-产品案例演示.md)
- [飞书落地方案](../03-飞书落地方案.md)
