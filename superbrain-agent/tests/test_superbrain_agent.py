"""
超级智囊 Agent — 完整测试套件
==============================

覆盖四个核心风险场景：
  1. 知识源文件缺失/为空时的处理
  2. 候选输出格式校验
  3. 历史相似检索是否正确触发
  4. 无相似历史时不应误报

API 调用全部 mock，仅集成测试标记为 @pytest.mark.integration
"""

import re
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# 被测模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import superbrain_agent as sa


# ================================================================
#  场景 1：知识源文件缺失/为空时的处理
# ================================================================

class TestKnowledgeSourceValidation:
    """知识源校验：文件缺失或为空时必须报错，不能静默失败浪费 API token"""

    def test_missing_file_returns_error_marker(self):
        """不存在的文件应返回 [文件不存在] 标记"""
        content = sa.load_markdown_file("/nonexistent/path/foobar.md")
        assert "[文件不存在" in content

    def test_existing_file_returns_content(self, temp_knowledge_dir):
        """存在的文件应返回实际内容"""
        path = str(Path(temp_knowledge_dir) / "competitors.md")
        content = sa.load_markdown_file(path)
        assert "竞品知识库" in content
        assert not content.startswith("[文件不存在")

    def test_validate_all_sources_present(self, temp_knowledge_dir):
        """三份文件都存在时应返回空错误列表"""
        sources = {
            "competitors": sa.load_markdown_file(str(Path(temp_knowledge_dir) / "competitors.md")),
            "user_pain": sa.load_markdown_file(str(Path(temp_knowledge_dir) / "user_pain.md")),
            "case_studies": sa.load_markdown_file(str(Path(temp_knowledge_dir) / "case_studies.md")),
        }
        errors = sa.validate_knowledge_sources(sources)
        assert len(errors) == 0, f"Expected no errors, got: {errors}"

    def test_validate_missing_file_detected(self, temp_knowledge_dir_missing_file):
        """缺失文件应被检测并报告"""
        sources = {
            "competitors": sa.load_markdown_file(
                str(Path(temp_knowledge_dir_missing_file) / "competitors.md")),
            "user_pain": sa.load_markdown_file(
                str(Path(temp_knowledge_dir_missing_file) / "user_pain.md")),
            "case_studies": sa.load_markdown_file(
                str(Path(temp_knowledge_dir_missing_file) / "case_studies.md")),
        }
        errors = sa.validate_knowledge_sources(sources)

        assert len(errors) >= 1
        # 错误信息应指名哪个文件有问题
        assert any("case_studies" in e.lower() for e in errors), \
            f"Error should mention 'case_studies', got: {errors}"

    def test_validate_empty_file_detected(self, temp_knowledge_dir_empty_file):
        """空文件应被检测并报告"""
        sources = {
            "competitors": sa.load_markdown_file(
                str(Path(temp_knowledge_dir_empty_file) / "competitors.md")),
            "user_pain": sa.load_markdown_file(
                str(Path(temp_knowledge_dir_empty_file) / "user_pain.md")),
            "case_studies": sa.load_markdown_file(
                str(Path(temp_knowledge_dir_empty_file) / "case_studies.md")),
        }
        errors = sa.validate_knowledge_sources(sources)

        assert len(errors) >= 1
        assert any("case_studies" in e.lower() for e in errors), \
            f"Error should mention 'case_studies', got: {errors}"

    def test_validate_multiple_errors_reported(self):
        """多个文件有问题时应报告全部问题"""
        sources = {
            "competitors": "[文件不存在: /x/competitors.md]",
            "user_pain": "",
            "case_studies": "[文件不存在: /x/case_studies.md]",
        }
        errors = sa.validate_knowledge_sources(sources)

        assert len(errors) == 3, \
            f"Expected 3 errors (2 missing + 1 empty), got: {errors}"

    def test_validate_whitespace_only_treated_as_empty(self):
        """仅含空白字符的文件应被视为空"""
        sources = {
            "competitors": "valid content",
            "user_pain": "valid content",
            "case_studies": "   \n\t\n   ",  # 只有空白
        }
        errors = sa.validate_knowledge_sources(sources)
        assert len(errors) >= 1
        assert any("case_studies" in e.lower() for e in errors)


# ================================================================
#  场景 2：候选输出格式校验
# ================================================================

class TestOutputFormatValidation:
    """API 返回内容必须包含必需字段，不完整的结果不能写入 output.md"""

    def test_valid_output_passes(self, valid_api_response):
        """完整格式的输出应通过校验"""
        errors = sa.validate_output(valid_api_response)
        assert len(errors) == 0, f"Expected no errors, got: {errors}"

    def test_output_must_contain_candidate_section(self, api_response_no_candidate):
        """缺少候选方案章节应报错"""
        errors = sa.validate_output(api_response_no_candidate)
        assert len(errors) >= 1
        assert any("候选" in e for e in errors), \
            f"Error should mention missing candidates, got: {errors}"

    def test_output_must_contain_evidence_for_each_candidate(self,
                                                              api_response_missing_evidence):
        """每个候选缺失证据支撑应报错"""
        errors = sa.validate_output(api_response_missing_evidence)
        assert len(errors) >= 1
        assert any("证据" in e for e in errors), \
            f"Error should mention missing evidence, got: {errors}"

    def test_output_must_contain_three_dimensions(self, api_response_missing_dimension):
        """三维评估不完整应报错"""
        errors = sa.validate_output(api_response_missing_dimension)
        assert len(errors) >= 1
        assert any("三维评估" in e or "用户价值" in e or "市场空白" in e or "技术可行性" in e
                   for e in errors), \
            f"Error should mention dimension eval issue, got: {errors}"

    def test_output_must_have_three_candidates(self):
        """少于3个候选应报错"""
        content = """### 💡 候选方案
#### 候选一：唯一的方案
- **核心卖点**：只有这一个
- **证据支撑**：有证据
- **三维评估**：都有
### ⚠️ 历史相似性检查
无
### 📋 推荐优先级
1. 唯一的方案
"""
        errors = sa.validate_output(content)
        assert len(errors) >= 1
        assert any(("候选二" in e or "候选三" in e or "3" in e or "数量" in e)
                   for e in errors), \
            f"Error should mention candidate count, got: {errors}"

    def test_output_must_contain_core_selling_point(self):
        """缺失核心卖点字段应报错"""
        content = """### 💡 候选方案
#### 候选一：某方案
- **证据支撑**：有证据
- **三维评估**：有评估
#### 候选二：方案二
- **核心卖点**：有卖点
- **证据支撑**：有证据
- **三维评估**：有评估
#### 候选三：方案三
- **核心卖点**：有卖点
- **证据支撑**：有证据
- **三维评估**：有评估
### ⚠️ 历史相似性检查
无
### 📋 推荐优先级
1. 方案二
"""
        errors = sa.validate_output(content)
        # 候选一缺少"核心卖点"
        assert len(errors) >= 1

    def test_valid_real_output_from_previous_run(self):
        """真实跑出来的 output.md 应通过格式校验"""
        real_output_path = Path(__file__).resolve().parent.parent / "output" / "output.md"
        if not real_output_path.exists():
            pytest.skip("真实 output.md 不存在，跳过回归验证")

        content = real_output_path.read_text(encoding="utf-8")
        # 去掉脚本添加的 YAML front matter（如果有的话），只保留模型输出
        if content.startswith("---"):
            # 找到第二个 --- 之后的内容
            parts = content.split("---", 2)
            if len(parts) >= 3:
                content = parts[2]

        errors = sa.validate_output(content)
        assert len(errors) == 0, \
            f"Real output.md should pass validation, got errors: {errors}"


# ================================================================
#  场景 3：历史相似检索是否正确触发
# ================================================================

class TestHistoryOverlapDetection:
    """验证历史相似性检查能正确触发"""

    def test_detect_history_warning_in_output(self, api_response_with_bio001_warning):
        """输出中包含 BIO-001 警告时应被检测到"""
        result = sa.check_history_overlap(api_response_with_bio001_warning)
        assert result["has_warning"] is True
        assert len(result["matched_ids"]) >= 1
        assert "BIO-001" in result["matched_ids"], \
            f"Expected BIO-001 in matched IDs, got: {result['matched_ids']}"

    def test_no_warning_when_unrelated(self, valid_api_response):
        """与历史记录无关时不应检测到警告"""
        result = sa.check_history_overlap(valid_api_response)
        assert result["has_warning"] is False
        assert len(result["matched_ids"]) == 0

    def test_warning_includes_correct_record_id(self, api_response_with_bio001_warning):
        """警告内容中应包含正确的历史记录 ID"""
        result = sa.check_history_overlap(api_response_with_bio001_warning)
        assert "BIO-001" in result["matched_ids"]
        # 确认是哪条记录被匹配
        assert result["matched_ids"] == ["BIO-001"] or "BIO-001" in result["matched_ids"]

    def test_real_regression_case_triggers_bio001(self):
        """回归测试：真实跑出来的 regression test output 中应包含 BIO-001 警告"""
        reg_path = Path(__file__).resolve().parent.parent / "output" / "output_regression_test.md"
        if not reg_path.exists():
            pytest.skip("回归测试 output 不存在")

        content = reg_path.read_text(encoding="utf-8")
        # 去掉 YAML front matter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                content = parts[2]

        result = sa.check_history_overlap(content)
        assert result["has_warning"] is True, \
            "Regression test output should contain a history warning"
        assert "BIO-001" in result["matched_ids"], \
            f"Expected BIO-001 warning, matched: {result['matched_ids']}"

    def test_uwb_candidate_triggers_bio002(self):
        """UWB 相关的候选应触发 BIO-002 警告"""
        uwb_output = """### 💡 候选方案
#### 候选一：eufy UWB Pro
- **核心卖点**：超宽带免持解锁
- **证据支撑**：竞品Schlage已有UWB方案
- **三维评估**：用户价值:⭐⭐⭐ 市场空白:⭐⭐ 技术可行性:⭐⭐
#### 候选二：另一个方案
- **核心卖点**：X
- **证据支撑**：Y
- **三维评估**：都有
#### 候选三：再一个方案
- **核心卖点**：Z
- **证据支撑**：W
- **三维评估**：都有
### ⚠️ 历史相似性检查
⚠️ 历史相似警告：该方向与 BIO-002（UWB免持解锁，裁决=否决）相似。
### 📋 推荐优先级
1. 方案二
"""
        result = sa.check_history_overlap(uwb_output)
        assert result["has_warning"] is True
        assert "BIO-002" in result["matched_ids"]

    def test_multiple_history_matches_detected(self):
        """同时匹配多条历史记录时都应被检测到"""
        multi_warning = """### 💡 候选方案
#### 候选一：eufy BioSense
- **核心卖点**：融合掌静脉+UWB
- **证据支撑**：掌静脉参考鹿客，UWB参考Schlage
- **三维评估**：都有
#### 候选二：方案B
- **核心卖点**：X
- **证据支撑**：Y
- **三维评估**：都有
#### 候选三：方案C
- **核心卖点**：Z
- **证据支撑**：W
- **三维评估**：都有
### ⚠️ 历史相似性检查
⚠️ 该方向与 BIO-001（掌静脉识别，裁决=延迟）相似。
⚠️ 该方向与 BIO-002（UWB免持解锁，裁决=否决）相似。
### 📋 推荐优先级
1. 方案B
"""
        result = sa.check_history_overlap(multi_warning)
        assert result["has_warning"] is True
        assert "BIO-001" in result["matched_ids"]
        assert "BIO-002" in result["matched_ids"]

    def test_passed_decision_not_treated_as_warning(self):
        """BIO-003 是通过的裁决，不应被视为历史否决警告"""
        passed_output = """### 💡 候选方案
#### 候选一：电池升级
- **核心卖点**：充电锂电池方案
- **证据支撑**：C30用户每月换电池
- **三维评估**：都有
#### 候选二：方案B
- **核心卖点**：X
- **证据支撑**：Y
- **三维评估**：都有
#### 候选三：方案C
- **核心卖点**：Z
- **证据支撑**：W
- **三维评估**：都有
### ⚠️ 历史相似性检查
该方向与 BIO-003（充电锂电池，裁决=有条件通过）模式相似，属于已通过的增量优化方向。
### 📋 推荐优先级
1. 电池升级
"""
        result = sa.check_history_overlap(passed_output)
        # BIO-003 是通过裁决，不应标记为"警告"
        assert "BIO-003" not in result["matched_ids"] or result["has_warning"] is False


# ================================================================
#  场景 4：无相似历史时不应误报
# ================================================================

class TestNoFalsePositiveWarnings:
    """反向测试：确保与历史记录无关时不会误报"""

    def test_unrelated_content_no_warning(self, valid_api_response):
        """与所有历史记录无关的输出不应产生警告"""
        result = sa.check_history_overlap(valid_api_response)
        assert result["has_warning"] is False
        assert len(result["matched_ids"]) == 0

    def test_mention_of_common_terms_no_false_positive(self):
        """仅包含'识别'等通用词不应触发虚假警告"""
        generic_output = """### 💡 候选方案
#### 候选一：通用优化
- **核心卖点**：提升指纹识别速度和准确率
- **证据支撑**：用户反馈指纹识别慢
- **三维评估**：都有
#### 候选二：方案B
- **核心卖点**：X
- **证据支撑**：Y
- **三维评估**：都有
#### 候选三：方案C
- **核心卖点**：Z
- **证据支撑**：W
- **三维评估**：都有
### ⚠️ 历史相似性检查
未发现历史否决记录与新候选重叠。
### 📋 推荐优先级
1. 通用优化
"""
        result = sa.check_history_overlap(generic_output)
        assert result["has_warning"] is False, \
            f"Common terms should not trigger false positives, got: {result}"

    def test_empty_output_no_crash(self):
        """空输出不应导致崩溃"""
        result = sa.check_history_overlap("")
        assert result["has_warning"] is False
        assert result["matched_ids"] == []


# ================================================================
#  Prompt 构建测试
# ================================================================

class TestPromptBuilding:
    """验证 prompt 构建逻辑正确"""

    def test_prompt_includes_all_sources(self, sample_competitors_content,
                                          sample_user_pain_content,
                                          sample_case_studies_content):
        """prompt 应包含三类知识源"""
        prompt = sa.build_user_prompt(
            sample_competitors_content,
            sample_user_pain_content,
            sample_case_studies_content,
            None
        )
        assert "知识源 1：竞品分析" in prompt
        assert "知识源 2：用户差评证据" in prompt
        assert "知识源 3：产品案例" in prompt
        assert "竞品知识库" in prompt
        assert "Boyd Keller" in prompt
        assert "Ring Video Doorbell" in prompt

    def test_prompt_includes_history_when_provided(self, sample_decision_log_content):
        """提供历史记录时 prompt 应包含第四类知识源"""
        prompt = sa.build_user_prompt("竞品", "差评", "案例", sample_decision_log_content)
        assert "知识源 4：历史裁决记录" in prompt
        assert "BIO-001" in prompt
        assert "必须检查" in prompt

    def test_prompt_no_history_section_when_none(self):
        """不提供历史记录时不应包含知识源 4"""
        prompt = sa.build_user_prompt("竞品", "差评", "案例", None)
        assert "知识源 4" not in prompt

    def test_prompt_includes_task_instructions(self):
        """prompt 应包含明确的任务指令"""
        prompt = sa.build_user_prompt("a", "b", "c", None)
        assert "任务指令" in prompt
        assert "候选" in prompt
        assert "证据" in prompt


# ================================================================
#  输出写入测试
# ================================================================

class TestOutputWriting:
    """验证输出写入逻辑"""

    def test_write_output_creates_file(self, tmp_path):
        """文件应被正确创建"""
        output_path = tmp_path / "sub" / "out.md"
        sa.write_output("# Test", str(output_path), {
            "date": "2026-07-19", "model": "test",
            "sources": ["a"], "history_used": False
        })
        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "# Test" in content
        assert "test" in content

    def test_write_output_includes_metadata(self, tmp_path):
        """输出的 markdown 应包含元数据头部"""
        output_path = tmp_path / "out.md"
        sa.write_output("body", str(output_path), {
            "date": "2026-07-19", "model": "deepseek-chat",
            "sources": ["competitors", "user_pain"], "history_used": True
        })
        content = output_path.read_text(encoding="utf-8")
        assert "deepseek-chat" in content
        assert "history_used: True" in content


# ================================================================
#  集成测试（需要真实 API Key）
# ================================================================

@pytest.mark.integration
class TestIntegration:
    """端到端集成测试，需要 DEEPSEEK_API_KEY 环境变量"""

    def test_real_api_call_produces_valid_output(self, temp_knowledge_dir,
                                                  temp_history_dir, tmp_path):
        """真实 API 调用应产生格式完整的输出"""
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            pytest.skip("未设置 DEEPSEEK_API_KEY，跳过集成测试")

        import os

        # 加载知识源
        sources = {
            "competitors": sa.load_markdown_file(
                str(Path(temp_knowledge_dir) / "competitors.md")),
            "user_pain": sa.load_markdown_file(
                str(Path(temp_knowledge_dir) / "user_pain.md")),
            "case_studies": sa.load_markdown_file(
                str(Path(temp_knowledge_dir) / "case_studies.md")),
        }

        # 校验知识源
        errors = sa.validate_knowledge_sources(sources)
        assert len(errors) == 0, f"Knowledge sources invalid: {errors}"

        # 加载历史记录
        decision_log = sa.load_markdown_file(
            str(Path(temp_history_dir) / "decision_log.md"))

        # 构建 prompt 并调用 API
        user_prompt = sa.build_user_prompt(
            sources["competitors"], sources["user_pain"],
            sources["case_studies"], decision_log
        )

        result = sa.call_deepseek_api(api_key, "deepseek-chat",
                                       sa.SYSTEM_PROMPT, user_prompt)

        # 校验输出格式
        errors = sa.validate_output(result)
        assert len(errors) == 0, \
            f"API output failed validation: {errors}"

        # 写入文件
        output_path = tmp_path / "integration_output.md"
        sa.write_output(result, str(output_path), {
            "date": "test", "model": "deepseek-chat",
            "sources": list(sources.keys()), "history_used": True
        })

        # 验证文件存在且有内容
        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert len(content) > 500  # 不应太短


# ================================================================
#  System Prompt 完整性
# ================================================================

class TestSystemPrompt:
    """System Prompt 的静态检查"""

    def test_prompt_defines_role(self):
        assert "超级智囊" in sa.SYSTEM_PROMPT

    def test_prompt_requires_evidence(self):
        assert "证据" in sa.SYSTEM_PROMPT

    def test_prompt_specifies_output_format(self):
        assert "候选一" in sa.SYSTEM_PROMPT
        assert "核心卖点" in sa.SYSTEM_PROMPT
        assert "三维评估" in sa.SYSTEM_PROMPT
        assert "历史相似性检查" in sa.SYSTEM_PROMPT


# ================================================================
#  常量
# ================================================================

class TestConstants:
    def test_default_model(self):
        assert sa.DEFAULT_MODEL == "deepseek-chat"

    def test_api_endpoint(self):
        assert "api.deepseek.com" in sa.DEEPSEEK_BASE_URL
