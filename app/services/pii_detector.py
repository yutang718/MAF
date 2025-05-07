"""PII检测服务"""
# 标准库导入
import json
import os
import re
import time
import uuid
from typing import Dict, List, Optional, Any, Tuple, Set, TYPE_CHECKING
from datetime import datetime
from pathlib import Path
from functools import lru_cache
import threading
from collections import defaultdict

# 第三方库导入
from presidio_analyzer import (
    AnalyzerEngine,
    RecognizerRegistry,
    EntityRecognizer,
    Pattern,
    PatternRecognizer,
    RecognizerResult
)
from presidio_analyzer.nlp_engine import (
    NlpEngineProvider,
    SpacyNlpEngine,
    NlpEngine,
    NlpArtifacts
)
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from pydantic import BaseModel
import spacy

# 本地导入
from core.logging import get_logger
from core.config import settings
from utils.decorators import timed
from utils.helpers import load_json_file, save_json_file

# 初始化日志记录器
logger = get_logger(__name__)

# class PIIRule:
#     """PII检测规则类"""
#     def __init__(
#         self, 
#         id: str, 
#         name: str, 
#         type: str, 
#         pattern: str = None,
#         content: str = None,
#         description: str = "",
#         enabled: bool = True,
#         entity_type: str = None,
#         created_at: str = None,
#         updated_at: str = None
#     ):
#         self.id = id
#         self.name = name
#         self.type = type
#         self.pattern = pattern
#         self.content = content
#         self.description = description
#         self.enabled = enabled
#         self.entity_type = entity_type or name
#         self.created_at = created_at or datetime.now().isoformat()
#         self.updated_at = updated_at
        
#     def to_dict(self) -> Dict[str, Any]:
#         """转换为字典表示"""
#         result = {
#             "id": self.id,
#             "name": self.name,
#             "type": self.type,
#             "description": self.description,
#             "enabled": self.enabled,
#             "entity_type": self.entity_type,
#             "created_at": self.created_at
#         }
#         if self.updated_at:
#             result["updated_at"] = self.updated_at
#         if self.pattern:
#             result["pattern"] = self.pattern
#         if self.content:
#             result["content"] = self.content
#         return result
    
#     @classmethod
#     def from_dict(cls, data: Dict[str, Any]) -> 'PIIRule':
#         """从字典创建规则对象"""
#         return cls(
#             id=data.get("id", str(uuid.uuid4())),
#             name=data.get("name", ""),
#             type=data.get("type", "REGEX"),
#             pattern=data.get("pattern"),
#             content=data.get("content"),
#             description=data.get("description", ""),
#             enabled=data.get("enabled", True),
#             entity_type=data.get("entity_type"),
#             created_at=data.get("created_at"),
#             updated_at=data.get("updated_at")
#         )
#         # End of Selection

class CustomRuleRecognizer(EntityRecognizer):
    """自定义规则识别器"""
    
    def __init__(
        self,
        rule: Dict[str, Any],
        supported_entity: str = None
    ):
        self.rule = rule
        # 所有规则都当作正则表达式处理
        self.pattern = rule.get('pattern')
        self.expected_confidence_level = rule.get('score', 0.7)
        
        super().__init__(
            supported_entities=[supported_entity or rule['name']],
            supported_language="en"
        )

    def analyze(
        self, text: str, entities: List[str], nlp_artifacts: NlpArtifacts
    ) -> List[RecognizerResult]:
        """分析文本"""
        results = []
        
        try:
            logger.info(f"Starting analysis with rule: {self.supported_entities[0]}")
            logger.debug(f"Pattern: {self.pattern}")
            logger.debug(f"Analyzing text: {text[:100]}...")  # 只记录前100个字符
            
            if self.pattern:
                # 使用正则表达式匹配
                matches = re.finditer(self.pattern, text)
                for match in matches:
                    matched_text = text[match.start():match.end()]

                    result = RecognizerResult(
                        entity_type=self.supported_entities[0],
                        start=match.start(),
                        end=match.end(),
                        score=self.expected_confidence_level,
                    )
                    results.append(result)
                    
            logger.info(f"Analysis complete. Found {len(results)} matches for rule {self.supported_entities[0]}")
            
        except Exception as e:
            logger.error(f"Error in custom recognizer analysis: {str(e)}", exc_info=True)
            
        return results

class PIIDetector:
    """PII检测器类"""
    
    def __init__(self):
        self._initialized = False
        self.analyzer = None
        self.anonymizer = None
        self.rules = []
        self.rules_cache = []
        self.last_processing_time = 0.0
        self.initialize()

    def initialize(self) -> None:
        """初始化检测器组件"""
        try:
            # 加载规则
            self.load_rules()
            
            # 初始化分析器
            try:
                spacy.load('en_core_web_lg')    
                
                # 创建分析器引擎
                self.analyzer = AnalyzerEngine()
                
                # 初始化匿名化器
                self.anonymizer = AnonymizerEngine()
                
                # 注册自定义规则
                self._register_custom_rules()
                
                self._initialized = True
                logger.info("PII detector initialized successfully")
                
            except Exception as e:
                logger.error(f"Failed to initialize NLP engine: {str(e)}")
                raise
            
        except Exception as e:
            logger.error(f"Failed to initialize PII detector: {str(e)}")
            raise

    def detect_pii(self, text: str) -> Dict[str, Any]:
        """使用 Presidio 和自定义规则检测文本中的 PII"""
        if not self._initialized:
            logger.warning("PII detector not initialized, initializing now...")
            self.initialize()
            
        try:
            logger.info("Starting PII detection")
            
            # 获取所有支持的实体类型
            supported_entities = self._get_all_supported_entities()
            
            # 分析文本
            analyzer_results = self.analyzer.analyze(
                text=text,
                language="en",
                entities=supported_entities,
                score_threshold=0.3
            )
            
            # 匿名化文本
            anonymized_text = self.anonymizer.anonymize(
                text=text,
                analyzer_results=analyzer_results
            ).text
            
            # 转换检测结果为标准格式
            detected_entities = []
            for result in analyzer_results:
                entity = {
                    "type": result.entity_type,
                    "text": text[result.start:result.end],
                    "start": result.start,
                    "end": result.end,
                    "score": result.score,
                    "category": self._get_entity_category(result.entity_type),
                    "is_custom": self._is_custom_entity(result.entity_type)
                }
                detected_entities.append(entity)
            
            logger.info(f"Found {len(detected_entities)} PII entities")
            
            return {
                "is_safe": len(detected_entities) == 0,
                "masked_text": anonymized_text,
                "entities": detected_entities,
                "analysis": {
                    "entity_types": list(set(e["type"] for e in detected_entities)),
                    "risk_level": self._calculate_risk_level(detected_entities),
                    "custom_entities_found": any(e["is_custom"] for e in detected_entities)
                }
            }
            
        except Exception as e:
            logger.error(f"Error in PII detection: {str(e)}")
            raise

    def load_rules(self) -> None:
        """从文件加载PII规则"""
        try:
            # 使用 settings 中定义的规则文件路径
            rules_file = settings.PII_RULES_FILE
            if not rules_file.exists():
                logger.warning(f"Rules file not found at {rules_file}, using default rules")
                self.rules = []
                return

            try:
                with open(rules_file, 'r', encoding='utf-8') as f:
                    file_rules = json.load(f)
                    # 支持单个规则或规则列表
                    if isinstance(file_rules, dict) and "rules" in file_rules:
                        self.rules = file_rules["rules"]
                    elif isinstance(file_rules, list):
                        self.rules = file_rules
                    else:
                        logger.warning("Invalid rules format, using empty rules list")
                        self.rules = []
                    
                logger.info(f"Loaded {len(self.rules)} rules from {rules_file}")
                
                # 缓存启用的规则
                self.rules_cache = [rule for rule in self.rules if rule.get('enabled', True)]
                    
            except Exception as e:
                logger.error(f"Error loading rules from {rules_file}: {str(e)}")
                self.rules = []
            
        except Exception as e:
            logger.error(f"Error loading PII rules: {str(e)}")
            self.rules = []

    def update_rules(self, rules: List[Dict[str, Any]]) -> bool:
        """更新所有规则并重新初始化检测器"""
        # 保存原始规则，用于出错时回滚
        original_rules = self.rules.copy()
        original_analyzer = self.analyzer
        
        try:
            logger.info(f"Updating {len(rules)} PII rules")
            
            # 1. 确保规则格式正确
            if not isinstance(rules, list):
                raise ValueError("Rules must be a list")
            
            # 2. 验证所有规则
            valid_rules = []
            for rule in rules:
                if not isinstance(rule, dict):
                    logger.warning(f"Skipping invalid rule format: {rule}")
                    continue
                    
                # 确保规则包含必要字段
                required_fields = ["id", "name", "type", "pattern"]
                if not all(field in rule for field in required_fields):
                    logger.warning(f"Rule missing required fields: {rule}")
                    continue
                
                # 添加默认值
                rule.setdefault("description", "")
                rule.setdefault("category", "general")
                rule.setdefault("country", "international")
                rule.setdefault("enabled", True)
                rule.setdefault("masking_method", "mask")
                
                valid_rules.append(rule)
            
            if not valid_rules:
                raise ValueError("No valid rules provided")
            
            # 3. 更新规则
            self.rules = valid_rules
            
            # 4. 重新初始化检测器
            self.initialize()
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating rules: {str(e)}")
            # 回滚到原始状态
            self.rules = original_rules
            self.analyzer = original_analyzer
            return False

    def _get_all_supported_entities(self) -> List[str]:
        """获取所有支持的实体类型（预定义 + 自定义）"""
        # 预定义的实体类型
        predefined_entities = {
            "PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", 
            "CREDIT_CARD", "IBAN_CODE", "LOCATION", 
            "PASSPORT", "DRIVER_LICENSE", "TAX_ID",
            "BANK_ACCOUNT", "ID_CARD", "MAC_ADDRESS",
            "IP_ADDRESS", "NRP", "MEDICAL_LICENSE"
        }
        
        # 从自定义规则中获取实体类型
        custom_entities = {rule.get('name') for rule in self.rules if rule.get('enabled', True)}
        
        # 合并并返回所有实体类型
        return list(predefined_entities | custom_entities)

    def _is_custom_entity(self, entity_type: str) -> bool:
        """检查是否为自定义实体类型"""
        return any(rule.get('name') == entity_type for rule in self.rules)

    def _get_entity_category(self, entity_type: str) -> str:
        """获取实体类别"""
        categories = {
            "PERSON": "personal",
            "EMAIL_ADDRESS": "contact",
            "PHONE_NUMBER": "contact",
            "CREDIT_CARD": "financial",
            "IBAN_CODE": "financial",
            "BANK_ACCOUNT": "financial",
            "LOCATION": "location",
            "PASSPORT": "id",
            "DRIVER_LICENSE": "id",
            "ID_CARD": "id",
            "TAX_ID": "financial",
            "MAC_ADDRESS": "technical",
            "IP_ADDRESS": "technical",
            "NRP": "medical",
            "MEDICAL_LICENSE": "medical"
        }
        return categories.get(entity_type, "other")

    def _calculate_risk_level(self, entities: List[Dict[str, Any]]) -> str:
        """计算风险等级"""
        if not entities:
            return "low"
            
        # 计算平均置信度得分
        avg_score = sum(e["score"] for e in entities) / len(entities)
        # 考虑实体数量和类型
        unique_categories = len(set(e["category"] for e in entities))
        
        if avg_score > 0.8 and unique_categories > 2:
            return "high"
        elif avg_score > 0.6 or unique_categories > 1:
            return "medium"
        else:
            return "low"

    def _get_category(self, entity_type: str) -> str:
        """根据实体类型返回分类"""
        for rule in self.rules:
            if rule["id"] == entity_type:
                return rule.get("category", "general")
        return "general"

    def _get_country(self, entity_type: str) -> str:
        """根据实体类型返回相关国家"""
        for rule in self.rules:
            if rule["id"] == entity_type:
                return rule.get("country", "international")
        return "international"

    def get_processing_time(self) -> float:
        """获取最近一次处理的时间（秒）"""
        return self.last_processing_time

    def _register_custom_rules(self) -> None:
        """注册自定义规则"""
        try:
            registry = RecognizerRegistry()
            
            # 遍历所有规则
            for rule in self.rules:
                if not rule.get('enabled', True):
                    continue
                    
                try:
                    # 创建自定义规则识别器
                    recognizer = CustomRuleRecognizer(
                        rule=rule,
                        supported_entity=rule.get('name')
                    )
                    
                    # 添加到注册表
                    registry.add_recognizer(recognizer)
                    logger.info(f"Added custom recognizer for rule: {rule['name']}")
                    
                except Exception as e:
                    logger.warning(f"Failed to create recognizer for rule {rule.get('name', 'unknown')}: {str(e)}")
                    continue
            
            # 更新分析器的注册表
            self.analyzer.registry = registry
            logger.info(f"Successfully registered {len(self.rules)} custom recognizers")
            
        except Exception as e:
            logger.error(f"Error registering custom rules: {str(e)}")
            raise

    async def cleanup(self) -> None:
        """清理资源"""
        try:
            logger.info("Cleaning up PII detector resources...")
            
            # 清理分析器
            if self.analyzer:
                self.analyzer = None
                
            # 清理匿名器
            if self.anonymizer:
                self.anonymizer = None
                
            # 清理缓存
            self.rules_cache.clear()
            
            # 重置初始化标志
            self._initialized = False
            
            logger.info("PII detector cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during PII detector cleanup: {str(e)}")
            raise