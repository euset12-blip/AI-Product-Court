"""
评审矩阵模块 — 完整测试套件
============================

覆盖：
  1. 候选方案解析（从 output.md 提取）
  2. Prompt 构建（6 个 Agent 独立 prompt）
  3. 评审响应解析（立场/理由/依据）
  4. 综合判定边界（0/1/2/3/4/6 反对票）
  5. 历史相似联动
  6. 输出写入

API 调用全部 mock，仅集成测试标记 @pytest.mark.integration
"""

import re
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import review_matrix as rm
import superbrain_agent as sa


# ================================================================
#  场景 1：候选方案解析
# ================================================================

class TestParseCandidates:
    """从 output.md 中解析候选方案列表"""

    @pytest.fixture
    def sample_output_content(self):
        return """### 💡 候选方案

#### 候选一：eufy SenseLock
- **核心卖点**：基于多传感器融合的场景感知自动锁
- **证据支撑**：
  - 用户痛点：P14（冬季气压差无法锁上）
  - 竞品空白：Yale/Schlage均未提供
  - 案例启示：Nest Thermostat M5模式
- **三维评估**：
  - 用户价值：⭐⭐⭐⭐⭐
  - 市场空白：⭐⭐⭐⭐⭐
  - 技术可行性：⭐⭐⭐⭐
- **风险提示**：算法误判需充分测试

#### 候选二：eufy Access Kit
- **核心卖点**：为老人提供NFC卡+物理钥匙应急方案
- **证据支撑**：
  - 用户痛点：P07/P08（老人无法使用指纹）
  - 竞品空白：竞品NFC非应急定位
  - 案例启示：Ring M1——降低门槛
- **三维评估**：
  - 用户价值：⭐⭐⭐⭐⭐
  - 市场空白：⭐⭐⭐⭐
  - 技术可行性：⭐⭐⭐⭐⭐
- **风险提示**：NFC卡丢失风险

#### 候选三：eufy Zero-Friction Setup
- **核心卖点**：配网零失败的开箱体验
- **证据支撑**：
  - 用户痛点：P01（配网持续失败）
  - 竞品空白：无人将配网作为核心竞争力
  - 案例启示：Ring M1——降低安装门槛
- **三维评估**：
  - 用户价值：⭐⭐⭐⭐
  - 市场空白：⭐⭐⭐⭐
  - 技术可行性：⭐⭐⭐
- **风险提示**：无法100%覆盖网络环境

### ⚠️ 历史相似性检查
未发现。

### 📋 推荐优先级
1. SenseLock 2. Access Kit 3. Zero-Friction
"""

    def test_parse_three_candidates(self, sample_output_content):
        """应解析出 3 个候选方案"""
        candidates = rm.parse_candidates_from_output(sample_output_content)
        assert len(candidates) == 3

    def test_parse_candidate_name(self, sample_output_content):
        """每个候选应有名称"""
        candidates = rm.parse_candidates_from_output(sample_output_content)
        names = [c["name"] for c in candidates]
        assert "eufy SenseLock" in names[0]
        assert "eufy Access Kit" in names[1]
        assert "eufy Zero-Friction Setup" in names[2]

    def test_parse_candidate_selling_point(self, sample_output_content):
        """每个候选应保留核心卖点"""
        candidates = rm.parse_candidates_from_output(sample_output_content)
        assert "多传感器融合" in candidates[0]["content"]
        assert "NFC卡" in candidates[1]["content"]
        assert "配网零失败" in candidates[2]["content"]

    def test_parse_candidate_has_evidence(self, sample_output_content):
        """每个候选应保留证据支撑"""
        candidates = rm.parse_candidates_from_output(sample_output_content)
        for c in candidates:
            assert "证据支撑" in c["content"] or "用户痛点" in c["content"]

    def test_parse_empty_input(self):
        """空输入应返回空列表而不是崩溃"""
        candidates = rm.parse_candidates_from_output("")
        assert candidates == []

    def test_parse_no_candidates(self):
        """无候选方案的内容应返回空列表"""
        content = "### 🔍 机会点识别\n一些分析。\n### 📋 推荐优先级\n无。"
        candidates = rm.parse_candidates_from_output(content)
        assert candidates == []

    def test_parse_single_candidate(self):
        """只有 1 个候选时应只解析出 1 个"""
        content = """#### 候选一：唯一方案
- **核心卖点**：只有一个
- **证据支撑**：有证据
- **三维评估**：有评估
"""
        candidates = rm.parse_candidates_from_output(content)
        assert len(candidates) == 1


# ================================================================
#  场景 2：Prompt 构建
# ================================================================

class TestBuildReviewPrompt:
    """每个 Agent 的评审 prompt 构建"""

    @pytest.fixture
    def candidate(self):
        return {"name": "eufy SenseLock", "content": "核心卖点：场景感知自动锁\n证据：P14/P15"}

    @pytest.fixture
    def knowledge_sources(self):
        return {
            "competitors": "# 竞品\nYale: 无场景感知",
            "user_pain": "# 差评\nP14: 冬季锁不上",
            "case_studies": "# 案例\nNest M5: 减少操作",
        }

    def test_all_six_agents_have_prompts(self, candidate, knowledge_sources):
        """6 个 Agent 都应该有定义的 system prompt"""
        agents = rm.get_all_agents()
        assert len(agents) == 6
        for agent in agents:
            assert "system_prompt" in agent
            assert "name" in agent
            assert len(agent["system_prompt"]) > 20

    def test_expert_agents_count(self):
        """应有 3 个行业专家"""
        experts = rm.get_expert_agents()
        assert len(experts) == 3

    def test_user_persona_agents_count(self):
        """应有 3 个用户替身"""
        personas = rm.get_user_persona_agents()
        assert len(personas) == 3

    def test_build_prompt_includes_candidate_info(self, candidate, knowledge_sources):
        """评审 prompt 应包含候选方案信息"""
        agent = rm.get_all_agents()[0]
        system_prompt, user_prompt = rm.build_review_prompt(
            agent, candidate, knowledge_sources
        )
        assert "eufy SenseLock" in user_prompt
        assert "场景感知" in user_prompt

    def test_build_prompt_includes_knowledge_sources(self, candidate, knowledge_sources):
        """评审 prompt 应包含相关知识源"""
        agent = rm.get_all_agents()[0]
        _, user_prompt = rm.build_review_prompt(agent, candidate, knowledge_sources)
        # 至少应包含竞品或差评或案例
        assert any(src in user_prompt for src in ["P14", "Yale", "Nest"])

    def test_cost_expert_gets_competitor_context(self, candidate, knowledge_sources):
        """成本专家应看到竞品和案例中的成本数据"""
        cost_agent = [a for a in rm.get_expert_agents() if "成本" in a["name"]][0]
        _, user_prompt = rm.build_review_prompt(cost_agent, candidate, knowledge_sources)
        assert "竞品" in user_prompt or "competitors" in user_prompt

    def test_security_expert_checks_compliance(self, candidate, knowledge_sources):
        """安全专家的 system prompt 应涉及合规"""
        sec_agent = [a for a in rm.get_expert_agents() if "安全" in a["name"]][0]
        assert "安全" in sec_agent["system_prompt"] or "合规" in sec_agent["system_prompt"] or "隐私" in sec_agent["system_prompt"] or "风险" in sec_agent["system_prompt"]

    def test_market_expert_gets_competitor_data(self, candidate, knowledge_sources):
        """市场专家应看到竞品数据"""
        market_agent = [a for a in rm.get_expert_agents() if "市场" in a["name"]][0]
        _, user_prompt = rm.build_review_prompt(market_agent, candidate, knowledge_sources)
        assert "竞品" in user_prompt or "competitors" in user_prompt

    def test_user_persona_prompts_include_pain_points(self, candidate, knowledge_sources):
        """用户替身的 prompt 应包含差评数据"""
        persona = rm.get_user_persona_agents()[0]
        _, user_prompt = rm.build_review_prompt(persona, candidate, knowledge_sources)
        assert "差评" in user_prompt or "user_pain" in user_prompt

    def test_landlord_persona_focuses_on_remote_auth(self, candidate, knowledge_sources):
        """短租房东的 prompt 应关注远程授权"""
        landlord = [a for a in rm.get_user_persona_agents() if "短租" in a["name"] or "房东" in a["name"]][0]
        sp = landlord["system_prompt"]
        assert any(kw in sp for kw in ["远程", "授权", "权限", "管理", "租客"]), \
            f"Landlord prompt should mention remote/authorization: {sp[:100]}"


# ================================================================
#  场景 3：评审响应解析
# ================================================================

class TestParseReviewResponse:
    """解析 Agent 返回的评审结果"""

    def test_parse_support_response(self):
        """支持立场的响应"""
        response = """**立场**：支持
**理由**：该方案成本可控，复用现有硬件
**依据**：competitors.md — Yale 同类功能 BOM 增加 $3-5"""
        result = rm.parse_review_response(response)
        assert result["stance"] == "support"
        assert "成本可控" in result["reason"]
        assert result["evidence_source"] is not None

    def test_parse_oppose_response(self):
        """反对立场的响应"""
        response = """**立场**：反对
**理由**：涉及生物特征数据，GDPR合规成本未消化
**依据**：user_pain.md P17 — 掌静脉数据本地存储但用户不知情"""
        result = rm.parse_review_response(response)
        assert result["stance"] == "oppose"
        assert "GDPR" in result["reason"]

    def test_parse_neutral_response(self):
        """中立立场的响应"""
        response = """**立场**：中立
**理由**：方案有价值但市场窗口不确定
**依据**：competitors.md — 竞品尚未布局但可能跟进"""
        result = rm.parse_review_response(response)
        assert result["stance"] == "neutral"

    def test_parse_response_without_explicit_stance_defaults_neutral(self):
        """无明确立场标记时应默认中立"""
        response = "这个方案看起来不错但有些问题需要进一步研究"
        result = rm.parse_review_response(response)
        assert result["stance"] == "neutral"

    def test_parse_response_extracts_reason(self):
        """应提取理由文本"""
        response = """**立场**：支持
**理由**：基于现有硬件，BOM增加不到$5，在目标ASP区间内利润可控。
**依据**：competitors.md"""
        result = rm.parse_review_response(response)
        assert len(result["reason"]) > 10

    def test_parse_response_strips_whitespace(self):
        """应清理首尾空白"""
        response = """

        **立场**：支持

        **理由**：好方案

        """
        result = rm.parse_review_response(response)
        assert result["stance"] == "support"


# ================================================================
#  场景 4：综合判定边界
# ================================================================

class TestAggregateResults:
    """投票规则和综合判定"""

    def _make_reviews(self, oppose_count, neutral_count=0):
        """构造指定数量的评审结果"""
        total = oppose_count + neutral_count
        support_count = 6 - total
        reviews = []
        # 反对
        for i in range(oppose_count):
            reviews.append({
                "agent": f"agent_{i}",
                "candidate": "test_candidate",
                "stance": "oppose",
                "reason": "test reason",
                "evidence_source": "test source"
            })
        # 中立
        for i in range(neutral_count):
            reviews.append({
                "agent": f"agent_{oppose_count + i}",
                "candidate": "test_candidate",
                "stance": "neutral",
                "reason": "test",
                "evidence_source": "test"
            })
        # 支持
        for i in range(support_count):
            reviews.append({
                "agent": f"agent_{oppose_count + neutral_count + i}",
                "candidate": "test_candidate",
                "stance": "support",
                "reason": "test",
                "evidence_source": "test"
            })
        return reviews

    def test_zero_oppose_pass(self):
        """0 反对 → 建议通过"""
        reviews = self._make_reviews(0)
        result = rm.aggregate_results(reviews, None)
        assert result["verdict"] == "pass"

    def test_one_oppose_pass(self):
        """1 反对 → 建议通过"""
        reviews = self._make_reviews(1)
        result = rm.aggregate_results(reviews, None)
        assert result["verdict"] == "pass"

    def test_two_oppose_discuss(self):
        """2 反对 → 建议进一步讨论"""
        reviews = self._make_reviews(2)
        result = rm.aggregate_results(reviews, None)
        assert result["verdict"] == "discuss"

    def test_three_oppose_discuss(self):
        """3 反对 → 建议进一步讨论（边界）"""
        reviews = self._make_reviews(3)
        result = rm.aggregate_results(reviews, None)
        assert result["verdict"] == "discuss"

    def test_four_oppose_block(self):
        """4 反对 → 建议搁置（边界）"""
        reviews = self._make_reviews(4)
        result = rm.aggregate_results(reviews, None)
        assert result["verdict"] == "block"

    def test_five_oppose_block(self):
        """5 反对 → 建议搁置"""
        reviews = self._make_reviews(5)
        result = rm.aggregate_results(reviews, None)
        assert result["verdict"] == "block"

    def test_six_oppose_block(self):
        """6 反对（全票反对）→ 建议搁置"""
        reviews = self._make_reviews(6)
        result = rm.aggregate_results(reviews, None)
        assert result["verdict"] == "block"

    def test_neutral_not_counted_as_oppose(self):
        """中立票不应被算作反对票"""
        reviews = self._make_reviews(1, neutral_count=2)  # 1 oppose, 2 neutral, 3 support
        result = rm.aggregate_results(reviews, None)
        # 只有 1 票反对 → 通过
        assert result["verdict"] == "pass"

    def test_aggregate_counts_correctly(self):
        """统计数字应正确"""
        reviews = self._make_reviews(2, neutral_count=1)
        result = rm.aggregate_results(reviews, None)
        assert result["support_count"] == 3
        assert result["oppose_count"] == 2
        assert result["neutral_count"] == 1
        assert result["total_agents"] == 6

    def test_empty_reviews(self):
        """空评审列表不应崩溃"""
        result = rm.aggregate_results([], None)
        assert result["verdict"] == "discuss"  # 默认需讨论
        assert result["total_agents"] == 0


# ================================================================
#  场景 5：历史相似联动
# ================================================================

class TestHistoryIntegration:
    """评审结果中应包含历史相似性检查"""

    def test_aggregate_with_history_overlap(self):
        """有历史相似时应标注"""
        reviews = [
            {"agent": f"agent_{i}", "candidate": "FaceLock",
             "stance": "support", "reason": "test", "evidence_source": "test"}
            for i in range(6)
        ]
        # 模拟有历史警告的输出文本（需匹配 check_history_overlap 的解析格式）
        history_context = """### ⚠️ 历史相似性检查
⚠️ 历史相似警告：该方向与 BIO-001（掌静脉识别，裁决=延迟）相似。反对理由是营销宣传价值 > 用户可感知价值。"""
        result = rm.aggregate_results(reviews, history_context)
        assert result["history_warning"] is True
        assert "BIO-001" in result.get("history_detail", "")

    def test_aggregate_without_history_overlap(self):
        """无历史相似时不应标注"""
        reviews = [
            {"agent": f"agent_{i}", "candidate": "SafeLock",
             "stance": "support", "reason": "test", "evidence_source": "test"}
            for i in range(6)
        ]
        result = rm.aggregate_results(reviews, None)
        assert result["history_warning"] is False

    def test_aggregate_preserves_oppose_reasons(self):
        """应保留反对意见的摘要"""
        reviews = [
            {"agent": "成本专家", "candidate": "X",
             "stance": "oppose", "reason": "BOM过高", "evidence_source": "case"},
            {"agent": "安全专家", "candidate": "X",
             "stance": "support", "reason": "无合规风险", "evidence_source": "case"},
            {"agent": "市场专家", "candidate": "X",
             "stance": "support", "reason": "有窗口", "evidence_source": "case"},
            {"agent": "独居女性", "candidate": "X",
             "stance": "support", "reason": "安全", "evidence_source": "case"},
            {"agent": "多代家庭", "candidate": "X",
             "stance": "support", "reason": "简单", "evidence_source": "case"},
            {"agent": "短租房东", "candidate": "X",
             "stance": "support", "reason": "高效", "evidence_source": "case"},
        ]
        result = rm.aggregate_results(reviews, None)
        assert result["verdict"] == "pass"
        assert len(result["oppose_reasons"]) == 1
        assert "BOM过高" in result["oppose_reasons"][0]


# ================================================================
#  场景 6：输出写入
# ================================================================

class TestWriteReviewOutput:
    """评审输出文件的写入"""

    def test_write_review_output_creates_file(self, tmp_path):
        """应创建文件"""
        output_path = tmp_path / "review_output.md"
        results = {
            "candidates": [
                {
                    "name": "TestLock",
                    "content": "test content",
                    "reviews": [
                        {"agent": "成本专家", "stance": "support",
                         "reason": "成本可控", "evidence_source": "case"},
                        {"agent": "安全专家", "stance": "neutral",
                         "reason": "需进一步评估", "evidence_source": "pain"},
                        {"agent": "市场专家", "stance": "support",
                         "reason": "有差异化", "evidence_source": "comp"},
                        {"agent": "独居女性", "stance": "support",
                         "reason": "安全可靠", "evidence_source": "pain"},
                        {"agent": "多代家庭", "stance": "support",
                         "reason": "操作简单", "evidence_source": "pain"},
                        {"agent": "短租房东", "stance": "support",
                         "reason": "远程管理好", "evidence_source": "pain"},
                    ],
                    "verdict": "pass",
                    "oppose_count": 0,
                    "support_count": 5,
                    "neutral_count": 1,
                    "history_warning": False,
                    "history_detail": "",
                }
            ],
            "meta": {"date": "2026-07-19", "model": "deepseek-chat"},
        }
        rm.write_review_output(results, str(output_path))

        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "TestLock" in content
        assert "成本专家" in content
        assert "pass" in content or "通过" in content

    def test_write_review_output_with_history_warning(self, tmp_path):
        """有历史警告的输出应包含警告标记"""
        output_path = tmp_path / "review_output.md"
        results = {
            "candidates": [
                {
                    "name": "BioLock",
                    "content": "test",
                    "reviews": [],
                    "verdict": "block",
                    "oppose_count": 4,
                    "support_count": 1,
                    "neutral_count": 1,
                    "history_warning": True,
                    "history_detail": "BIO-001: 掌静脉已被延迟",
                }
            ],
            "meta": {"date": "2026-07-19", "model": "deepseek-chat"},
        }
        rm.write_review_output(results, str(output_path))

        content = output_path.read_text(encoding="utf-8")
        assert "BIO-001" in content
        assert "历史" in content


# ================================================================
#  场景 7：6 Agent 全部被调用（集成检查）
# ================================================================

class TestAllAgentsCalled:
    """验证所有 6 个 Agent 都被正确调用"""

    @patch("review_matrix.call_deepseek_api")
    def test_all_six_agents_called_per_candidate(self, mock_api):
        """每个候选应调用 6 个 Agent"""
        mock_api.return_value = """**立场**：支持
**理由**：测试理由
**依据**：测试来源"""

        candidates = [
            {"name": "Candidate A", "content": "test content A"},
        ]
        knowledge = {"competitors": "data", "user_pain": "data", "case_studies": "data"}

        results = rm.run_review_matrix(candidates, knowledge, None, "sk-test")

        # 每个候选 × 6 个 Agent = 6 次调用
        assert mock_api.call_count == 6
        # 验证返回结构
        assert len(results["candidates"]) == 1
        assert len(results["candidates"][0]["reviews"]) == 6

    @patch("review_matrix.call_deepseek_api")
    def test_three_candidates_call_eighteen_times(self, mock_api):
        """3 个候选 × 6 Agent = 18 次调用"""
        mock_api.return_value = """**立场**：支持
**理由**：测试
**依据**：测试"""

        candidates = [
            {"name": "A", "content": "a"},
            {"name": "B", "content": "b"},
            {"name": "C", "content": "c"},
        ]
        knowledge = {"competitors": "d", "user_pain": "d", "case_studies": "d"}

        rm.run_review_matrix(candidates, knowledge, None, "sk-test")
        assert mock_api.call_count == 18

    @patch("review_matrix.call_deepseek_api")
    def test_agent_names_in_results(self, mock_api):
        """返回结果中应包含 Agent 名称"""
        mock_api.return_value = """**立场**：支持
**理由**：测试
**依据**：测试"""

        candidates = [{"name": "Test", "content": "test"}]
        knowledge = {"competitors": "d", "user_pain": "d", "case_studies": "d"}

        results = rm.run_review_matrix(candidates, knowledge, None, "sk-test")

        agent_names = [r["agent"] for r in results["candidates"][0]["reviews"]]
        assert "成本专家" in agent_names
        assert "安全专家" in agent_names
        assert "市场专家" in agent_names
        # 用户替身
        assert any("独居" in n for n in agent_names)
        assert any("多代" in n or "家庭" in n for n in agent_names)
        assert any("短租" in n or "房东" in n for n in agent_names)


# ================================================================
#  Agent 定义完整性
# ================================================================

class TestAgentDefinitions:
    """Agent 定义的静态检查"""

    def test_expert_agents_have_required_fields(self):
        for agent in rm.get_expert_agents():
            assert "name" in agent
            assert "role" in agent
            assert "system_prompt" in agent
            assert "evidence_tags" in agent

    def test_persona_agents_have_required_fields(self):
        for agent in rm.get_user_persona_agents():
            assert "name" in agent
            assert "persona" in agent
            assert "system_prompt" in agent
            assert "concerns" in agent

    def test_no_duplicate_agent_names(self):
        agents = rm.get_all_agents()
        names = [a["name"] for a in agents]
        assert len(names) == len(set(names)), f"Duplicate names: {names}"


# ================================================================
#  集成测试
# ================================================================

@pytest.mark.integration
class TestIntegration:
    """需要真实 API Key 的端到端测试"""

    def test_real_review_on_one_candidate(self, tmp_path):
        """真实 API 评审单个候选"""
        import os
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            pytest.skip("未设置 DEEPSEEK_API_KEY")

        candidate = {
            "name": "eufy SenseLock",
            "content": "核心卖点：基于多传感器融合的场景感知自动锁。证据：P14冬季锁不上。",
        }
        knowledge = {
            "competitors": "Yale无场景感知 | Schlage仅计时",
            "user_pain": "P14: 冬季因气压差无法锁上 | P15: 搬东西反复锁定",
            "case_studies": "Nest M5: 减少操作>增加控制",
        }

        # 只测试成本专家（1 次 API 调用）
        cost_agent = [a for a in rm.get_expert_agents() if "成本" in a["name"]][0]
        system_prompt, user_prompt = rm.build_review_prompt(
            cost_agent, candidate, knowledge
        )
        result = sa.call_deepseek_api(api_key, "deepseek-chat", system_prompt, user_prompt)
        parsed = rm.parse_review_response(result)

        assert parsed["stance"] in ("support", "oppose", "neutral")
        assert len(parsed["reason"]) > 5
