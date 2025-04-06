"""测试配置"""
import pytest
from fastapi.testclient import TestClient
import os
import json
from typing import Dict, Any, Generator
import tempfile

from main import app
from core.dependencies import get_services, Services
from services.pii_detector import PIIDetector

@pytest.fixture
def test_client() -> TestClient:
    """创建测试客户端"""
    return TestClient(app)

@pytest.fixture
def temp_config_file() -> Generator[str, None, None]:
    """创建临时配置文件"""
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    
    yield path
    
    # 测试完成后清理
    if os.path.exists(path):
        os.unlink(path)

@pytest.fixture
def test_pii_rules() -> Dict[str, Any]:
    """测试用PII规则数据"""
    return [
        {
            "id": "test-rule-1",
            "name": "Test Email",
            "type": "REGEX",
            "pattern": r"[a-z]+@example\.com",
            "description": "Test email rule",
            "enabled": True,
            "entity_type": "EMAIL",
            "language": "en"
        },
        {
            "id": "test-rule-2",
            "name": "Test Phone",
            "type": "REGEX",
            "pattern": r"\d{3}-\d{4}",
            "description": "Test phone rule",
            "enabled": True,
            "entity_type": "PHONE",
            "language": "en"
        }
    ]

@pytest.fixture
def mock_pii_detector(temp_config_file, test_pii_rules) -> PIIDetector:
    """创建带有测试规则的PII检测器"""
    # 写入测试规则到临时文件
    with open(temp_config_file, "w") as f:
        json.dump(test_pii_rules, f)
    
    # 创建检测器并配置使用临时文件
    detector = PIIDetector()
    detector.rules_file = temp_config_file
    detector.load_rules_from_file()
    
    return detector 