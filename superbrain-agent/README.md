# 超级智囊 Agent — 最小可运行验证

> **AI Product Court** 多智能体产品评审系统的核心组件
>
> 基于三类知识源（竞品/差评/案例）→ 交叉分析 → 输出有证据支撑的产品候选方案

---

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/euset12-blip/AI-Product-Court.git
cd AI-Product-Court/superbrain-agent

# 2. 安装依赖
pip install -r requirements.txt

# 3. 设置 API Key
export DEEPSEEK_API_KEY=sk-xxxxx

# 4. 运行
python superbrain_agent.py          # 超级智囊：生成候选方案
python review_matrix.py             # 评审矩阵：6方Agent评审

# 5. 查看结果
cat output/output.md                # 候选方案输出
cat output/review_output.md         # 评审矩阵输出
```

> 💡 不想跑 API？直接查看 `output/` 目录下的真实运行结果。

## 项目概览

| 指标 | 数值 |
|------|------|
| 测试通过 | **79** 个（35 superbrain + 44 review_matrix，0 失败） |
| 完成 API 调用 | **21** 次（3 生成 + 18 评审） |
| 方法论验证轮次 | **2** 轮（证据池污染发现 + 对抗性测试） |
| 已识别问题 | **2** 个（证据重叠 67%、传感器方向结构性偏好） |
| Python 依赖 | `openai`（兼容 DeepSeek API） |
| 知识源规模 | 3 个文件，~9KB，覆盖 8 款竞品 + 24 条差评 + 5 个案例模式 |

---

## 我们如何验证 AI 是否真的在思考

本项目不是"搭一个 Demo 跑通就交差"。在开发过程中，我们主动对 AI 推理的真实性做了两轮验证，发现了真实问题并进行了修正。

### 第一轮：发现证据池污染

**问题**：评审矩阵 Agent 和超级智囊 Agent 共享同一批知识源文件。对照实验证实，评审引用的证据中有 **67%** 在生成阶段已被超级智囊引用过——评审 Agent 只是在同一个证据池里换了个角度复述，没有引入真正的外部信息。

**修正**：改造评审 Agent 的 system prompt 为红队对抗模式——要求 Agent 必须指出候选方案中「被选择性使用的证据」「被忽略的反面证据」「证据是否足以支撑结论」，而非简单复述知识源内容。

### 第二轮：对抗性测试

**问题**：怀疑知识源本身可能存在方向性偏好——如果原始 `user_pain.md` 本身就偏向「权限管理是刚需」，那模型只是忠实地复述了这个偏好，还是具备独立推理能力？

**实验设计**：复制一份知识源 `knowledge_adversarial/`，做三处改动：
1. 删除所有支持「权限/授权管理」方向的差评条目（P25-P27 临时密码/远程开门/Airbnb）
2. 新增 5 条反向差评（P31-P35），主题是「用户认为开锁速度/简洁性比授权管理更重要」
3. 竞品格局中将「权限管理=潜在破局点」改为「需求存疑」

**结果**：

| 维度 | 原始输出 | 对抗性输出 |
|------|---------|-----------|
| 权限/授权管理方向 | 出现（Access Kit + NFC） | **完全消失** |
| 速度/简洁性方向 | 次要 | **核心方向**（3 个候选均围绕此主题） |
| 新增证据 P31-P35 被引用 | — | ✅ 全部被引用 |
| 方向转变 | — | 3/3 候选方向全部改变 |

**结论**：模型确实会随知识源变化调整方向，推理具备真实的证据依赖性。完整报告见 `output/adversarial_comparison.md`。

### 已知局限

1. **传感器感知方向的结构性偏好**：即使对抗性知识源大幅改变了差评方向，「传感器+门状态感知」类候选在两个版本中均以不同形态出现（原始版叫 SenseLock，对抗版叫 Shield），说明模型可能对这一技术路径存在结构性偏好，不完全依赖知识源。

2. **单次测试无法排除随机性**：对抗性测试只跑了一轮。同一 prompt 多次运行可能产出不同候选方案，严格验证需要对同一知识源跑 N 次统计方向分布。受限于比赛时间，我们标注此问题但未完全解决。

3. **知识源规模有限**：80 条 Amazon 评论、8 款竞品、5 个案例——对于生产级产品评审系统仍然不够。扩大样本量后结论可能变化。

---

## 这是什么

"超级智囊"是 AI Product Court 系统中负责**提案生成**的 Agent。与传统"AI头脑风暴"不同，它不凭空创造灵感，而是**基于真实用户证据、竞品分析和行业案例的交叉推理**来推导产品机会。

这个目录是超级智囊 Agent 的**最小可运行验证**——一个 200 行的 Python 脚本 + 三份手写知识源文件，证明"证据驱动的产品候选生成"是可以跑通的。配套的 `review_matrix.py`（评审矩阵）实现了 6 方 Agent 对候选方案的独立评审和投票判定。

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

## 测试覆盖

```bash
# 运行全部单元测试（跳过需要 API Key 的集成测试）
python -m pytest tests/ -v -m "not integration"

# 运行集成测试（需要 DEEPSEEK_API_KEY 环境变量）
python -m pytest tests/ -v -m "integration"
```

| 测试场景 | 测试数 | 覆盖率 |
|---------|--------|--------|
| 知识源文件缺失/为空时的处理 | 7 | `validate_knowledge_sources()` 文件不存在、空文件、仅空白字符、多文件同时异常 |
| 候选输出格式校验 | 7 | `validate_output()` 缺失候选、缺失证据、缺失维度、候选数量不足、真实 output.md 回归 |
| 历史相似检索是否触发 | 7 | `check_history_overlap()` BIO-001 警告检测、BIO-002 UWB 检测、多重匹配、通过裁决不误报 |
| 无相似历史不应误报 | 3 | 无关内容零误报、通用词汇不触发、空输入不崩溃 |
| Prompt 构建 | 4 | 三类源完整性、历史裁决注入、任务指令完整性 |
| 输出写入 | 2 | 文件创建、元数据注入 |
| System Prompt / 常量 | 5 | 角色定义、输出格式字段、API 端点 |
| 评审矩阵专项 | 44 | 候选解析、6Agent prompt、响应解析、投票边界(0-6票)、历史联动、Agent调用计数 |
| **集成测试** | 2 | 真实 API 调用 + 完整校验链路 |

### 测试设计原则

- **API 调用全部 mock**：70+ 个单元测试不消耗任何 API token，任意环境秒级跑完
- **真实 case 做 fixture 数据**：回归测试用的 `output_regression_test.md` 直接作为测试输入，验证实际运行效果
- **pytest.mark.integration**：需要真实 API 的端到端测试单独标记，日常跑 `-m "not integration"` 跳过
- **先测试、再实现**：`validate_knowledge_sources` / `validate_output` / `check_history_overlap` 三个函数均为 TDD 方式开发

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
