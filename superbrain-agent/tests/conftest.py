"""
pytest 配置 + 共享 fixtures
"""

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# ── 路径设置：确保被测模块可导入 ──
sys_path_root = str(Path(__file__).resolve().parent.parent)
import sys
if sys_path_root not in sys.path:
    sys.path.insert(0, sys_path_root)


# ── pytest markers ──
def pytest_configure(config):
    config.addinivalue_line("markers", "integration: 需要真实 API 调用的集成测试")


# ── 基础 fixtures ──

@pytest.fixture
def sample_competitors_content():
    """一个最小但有效的竞品分析内容"""
    return """# 竞品知识库
## eufy C220
- 定位: 性价比指纹锁
- 差评: 自动锁定基于计时非门状态
## Yale
- 定位: 传统品牌智能转型
- 差评: 无摄像头和生物识别
"""


@pytest.fixture
def sample_user_pain_content():
    """一个最小但有效的用户差评内容"""
    return """# 用户差评证据
## P01 网络
"Setup kept failing." — Boyd Keller (E330)
## P07 操作
"Several family members unable to use at all." — Mark M. Markson (E34)
"""


@pytest.fixture
def sample_case_studies_content():
    """一个最小但有效的案例内容"""
    return """# 产品案例库
## 成功: Ring Video Doorbell
降低安装门槛 > 增加功能
## 失败: 掌静脉识别
高技术感知 ≠ 高用户价值
"""


@pytest.fixture
def sample_decision_log_content():
    """真实的 decision_log.md 内容（用于历史检查测试）"""
    return """## BIO-001 | 掌静脉识别 | 裁决：延迟
核心理由: 营销宣传价值 > 用户可感知价值；BOM增加$35+
决策模式标签: `高技术感知≠高用户价值`

## BIO-002 | UWB 免持解锁 | 裁决：否决
核心理由: 生态就绪度不足；安全信任未建立
决策模式标签: `生态就绪度>技术就绪度`
"""


# ── 临时知识源目录 ──

@pytest.fixture
def temp_knowledge_dir(sample_competitors_content,
                       sample_user_pain_content,
                       sample_case_studies_content):
    """创建包含三份有效知识源的临时目录"""
    tmpdir = tempfile.mkdtemp()
    (Path(tmpdir) / "competitors.md").write_text(sample_competitors_content,
                                                  encoding="utf-8")
    (Path(tmpdir) / "user_pain.md").write_text(sample_user_pain_content,
                                                encoding="utf-8")
    (Path(tmpdir) / "case_studies.md").write_text(sample_case_studies_content,
                                                   encoding="utf-8")
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def temp_knowledge_dir_missing_file(sample_competitors_content,
                                     sample_user_pain_content):
    """创建缺失 case_studies.md 的知识源目录"""
    tmpdir = tempfile.mkdtemp()
    (Path(tmpdir) / "competitors.md").write_text(sample_competitors_content,
                                                  encoding="utf-8")
    (Path(tmpdir) / "user_pain.md").write_text(sample_user_pain_content,
                                                encoding="utf-8")
    # 故意不创建 case_studies.md
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def temp_knowledge_dir_empty_file(sample_competitors_content,
                                   sample_user_pain_content):
    """创建包含空文件的知识源目录"""
    tmpdir = tempfile.mkdtemp()
    (Path(tmpdir) / "competitors.md").write_text(sample_competitors_content,
                                                  encoding="utf-8")
    (Path(tmpdir) / "user_pain.md").write_text(sample_user_pain_content,
                                                encoding="utf-8")
    (Path(tmpdir) / "case_studies.md").write_text("", encoding="utf-8")  # 空文件
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def temp_history_dir(sample_decision_log_content):
    """创建包含历史裁决记录的临时目录"""
    tmpdir = tempfile.mkdtemp()
    (Path(tmpdir) / "decision_log.md").write_text(sample_decision_log_content,
                                                   encoding="utf-8")
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


# ── Mock API 响应 ──

@pytest.fixture
def valid_api_response():
    """一个格式完整的 API 响应（候选人：包含所有必需字段）"""
    return """### 🔍 机会点识别

1. 被忽视的机会: 竞品都在堆开锁方式，没人解决"自动锁定太智障"的问题

### 💡 候选方案

#### 候选一：eufy SenseLock
- **核心卖点**：基于多传感器融合的场景感知自动锁
- **证据支撑**：
  - 用户痛点：P14（冬季气压差无法锁上）、P15（搬东西反复锁）
  - 竞品空白：Yale/Schlage均未提供基于门状态的智能锁定
  - 案例启示：Nest Thermostat M5模式——减少操作>增加控制
- **三维评估**：
  - 用户价值：⭐⭐⭐⭐⭐ 直接解决用户最焦虑的"锁没锁上"问题
  - 市场空白：⭐⭐⭐⭐⭐ 竞品无此功能
  - 技术可行性：⭐⭐⭐⭐ 传感器成本可控
- **风险提示**：算法误判需充分测试

#### 候选二：eufy Access Kit
- **核心卖点**：为老人提供NFC卡+物理钥匙应急方案
- **证据支撑**：
  - 用户痛点：P07/P08（老人无法使用指纹）
  - 竞品空白：竞品NFC非应急定位
  - 案例启示：Ring M1——降低门槛
- **三维评估**：
  - 用户价值：⭐⭐⭐⭐⭐ 解决老人被锁门外
  - 市场空白：⭐⭐⭐⭐ 无人聚焦此场景
  - 技术可行性：⭐⭐⭐⭐⭐ 技术成熟
- **风险提示**：NFC卡丢失风险需远程禁用配合

#### 候选三：eufy Zero-Friction Setup
- **核心卖点**：配网零失败的开箱体验
- **证据支撑**：
  - 用户痛点：P01（配网持续失败）
  - 竞品空白：无人将配网作为核心竞争力
  - 案例启示：Ring M1——降低安装门槛
- **三维评估**：
  - 用户价值：⭐⭐⭐⭐ 消除首因效应
  - 市场空白：⭐⭐⭐⭐ 隐形机会点
  - 技术可行性：⭐⭐⭐ 兼容性测试成本高
- **风险提示**：无法100%覆盖所有网络环境

### ⚠️ 历史相似性检查
未发现历史否决记录与新候选重叠。

### 📋 推荐优先级
1. SenseLock
2. Access Kit
3. Zero-Friction Setup
"""


@pytest.fixture
def api_response_with_bio001_warning():
    """包含 BIO-001 历史警告的 API 响应"""
    return """### 🔍 机会点识别

1. 人脸识别被认为是差异化方向

### 💡 候选方案

#### 候选一：eufy FaceLock
- **核心卖点**：3D结构光人脸识别旗舰门锁
- **证据支撑**：
  - 竞品空白：小米已搭载3D结构光人脸识别
  - 用户痛点：指纹对老人不友好
  - 案例启示：感知价值需验证
- **三维评估**：
  - 用户价值：⭐⭐⭐ 部分用户场景有价值
  - 市场空白：⭐⭐ 竞品已布局
  - 技术可行性：⭐⭐⭐ 模组成本偏高
- **风险提示**：类似于掌静脉的高技术感知≠高用户价值

### ⚠️ 历史相似性检查
⚠️ 历史相似警告：候选一 FaceLock 与 BIO-001（掌静脉识别，裁决=延迟）相似。反对理由是营销宣传价值 > 用户可感知价值；BOM增加$35+ 压缩利润。如仍想推进，需证明重新评估条件已满足。

### 📋 推荐优先级
1. FaceLock（需先解决历史裁决中的问题）
"""


@pytest.fixture
def api_response_missing_evidence():
    """缺失「证据支撑」字段的 API 响应"""
    return """### 💡 候选方案

#### 候选一：某个方案
- **核心卖点**：一个很酷的想法
- **三维评估**：
  - 用户价值：⭐⭐⭐⭐ 不错
  - 市场空白：⭐⭐⭐ 还行
  - 技术可行性：⭐⭐⭐ 能做
- **风险提示**：没太大风险

### ⚠️ 历史相似性检查
未发现历史否决记录。

### 📋 推荐优先级
1. 某个方案
"""


@pytest.fixture
def api_response_missing_dimension():
    """缺失「三维评估」中某一维度的 API 响应"""
    return """### 💡 候选方案

#### 候选一：某个方案
- **核心卖点**：一个想法
- **证据支撑**：
  - 用户痛点：P01
  - 竞品空白：无人做
  - 案例启示：M1
- **三维评估**：
  - 用户价值：⭐⭐⭐⭐ 不错
  - 市场空白：⭐⭐⭐ 还行
- **风险提示**：无

#### 候选二：方案B
- **核心卖点**：另一个想法
- **证据支撑**：都有
- **三维评估**：
  - 用户价值：⭐⭐⭐ 可以
  - 市场空白：⭐⭐ 一般
  - 技术可行性：⭐⭐⭐⭐ 能做
- **风险提示**：无

#### 候选三：方案C
- **核心卖点**：第三个想法
- **证据支撑**：都有
- **三维评估**：
  - 用户价值：⭐⭐⭐ 可以
  - 市场空白：⭐⭐ 一般
  - 技术可行性：⭐⭐⭐⭐ 能做
- **风险提示**：无

### ⚠️ 历史相似性检查
未发现。

### 📋 推荐优先级
1. 方案B
"""


@pytest.fixture
def api_response_no_candidate():
    """完全缺失候选方案的 API 响应"""
    return """### 🔍 机会点识别
没有发现任何机会点。

### ⚠️ 历史相似性检查
无。

### 📋 推荐优先级
无。
"""


# ── Mock OpenAI client ──

@pytest.fixture
def mock_openai_client():
    """创建一个 mock OpenAI client，可配置返回内容"""
    with patch("superbrain_agent.OpenAI") as mock_openai_class:
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        yield mock_client


def make_mock_api_response(mock_client, content: str):
    """配置 mock client 返回指定的内容"""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = content
    mock_client.chat.completions.create.return_value = mock_response
