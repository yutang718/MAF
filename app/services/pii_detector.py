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

# 本地导入
from core.logging import get_logger
from core.config import settings
from utils.decorators import timed
from utils.helpers import load_json_file, save_json_file

# 初始化日志记录器
logger = get_logger(__name__)

class PIIRule:
    """PII检测规则类"""
    def __init__(
        self, 
        id: str, 
        name: str, 
        type: str, 
        pattern: str = None,
        content: str = None,
        description: str = "",
        enabled: bool = True,
        entity_type: str = None,
        language: str = "en",
        created_at: str = None,
        updated_at: str = None
    ):
        self.id = id
        self.name = name
        self.type = type
        self.pattern = pattern
        self.content = content
        self.description = description
        self.enabled = enabled
        self.entity_type = entity_type or name
        self.language = language
        self.created_at = created_at or datetime.now().isoformat()
        self.updated_at = updated_at
        
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示"""
        result = {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "enabled": self.enabled,
            "entity_type": self.entity_type,
            "language": self.language,
            "created_at": self.created_at
        }
        if self.updated_at:
            result["updated_at"] = self.updated_at
        if self.pattern:
            result["pattern"] = self.pattern
        if self.content:
            result["content"] = self.content
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PIIRule':
        """从字典创建规则对象"""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", ""),
            type=data.get("type", "REGEX"),
            pattern=data.get("pattern"),
            content=data.get("content"),
            description=data.get("description", ""),
            enabled=data.get("enabled", True),
            entity_type=data.get("entity_type"),
            language=data.get("language", "en"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at")
        )

class CustomRuleRecognizer(EntityRecognizer):
    """自定义规则识别器"""
    
    def __init__(
        self,
        rule: Dict[str, Any],
        supported_language: str = "en",
        supported_entity: str = None
    ):
        self.rule = rule
        # 所有规则都当作正则表达式处理
        self.pattern = rule.get('pattern')
        self.expected_confidence_level = rule.get('score', 0.7)
        
        super().__init__(
            supported_entities=[supported_entity or rule['name']],
            supported_language=supported_language
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
        """初始化PII检测器"""
        # 直接使用 settings 中的配置
        self.supported_languages = settings.PII_SUPPORTED_LANGUAGES
        self.rules = []
        self.rules_cache = {}
        self._lock = threading.Lock()
        self._compiled_regex_cache = {}
        self._initialized = False
        
        # 初始化组件为 None
        self.nlp_engine = None
        self.analyzer = None
        self.anonymizer = None

    def initialize(self) -> None:
        """初始化检测器组件"""
        try:
            # 初始化NLP引擎
            import spacy
            try:
                # 直接加载模型
                self.nlp_engine = SpacyNlpEngine(models={"en": "en_core_web_sm"})
                logger.info("Loaded spaCy model successfully")
                
            except OSError:
                # 如果模型未安装，下载并安装
                logger.info("Downloading spaCy model...")
                spacy.cli.download("en_core_web_sm")
                self.nlp_engine = SpacyNlpEngine(models={"en": "en_core_web_sm"})
                logger.info("Downloaded and loaded spaCy model successfully")
            
            # 加载规则
            self.load_rules()
            
            # 初始化分析器和注册表
            registry = RecognizerRegistry()
            registry.load_predefined_recognizers()
            
            # 添加自定义规则识别器
            self._add_custom_recognizers(registry)
            
            # 初始化分析器
            self.analyzer = AnalyzerEngine(
                nlp_engine=self.nlp_engine,
                registry=registry
            )
            
            # 初始化匿名器
            self.anonymizer = AnonymizerEngine()
            
            self._initialized = True
            logger.info("PII detector initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize PII detector: {str(e)}")
            raise

    def detect_pii(self, text: str, language: str = "en") -> Dict[str, Any]:
        """使用 Presidio 和自定义规则检测文本中的 PII"""
        if not self._initialized:
            logger.warning("PII detector not initialized, initializing now...")
            self.initialize()
            
        try:
            logger.info(f"Starting PII detection for language: {language}")
            
            # 获取所有支持的实体类型
            supported_entities = self._get_all_supported_entities()
            
            # 分析文本
            analyzer_results = self.analyzer.analyze(
                text=text,
                language=language,
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
                    "language": language,
                    "entity_types": list(set(e["type"] for e in detected_entities)),
                    "risk_level": self._calculate_risk_level(detected_entities),
                    "custom_entities_found": any(e["is_custom"] for e in detected_entities)
                }
            }
            
        except Exception as e:
            logger.error(f"Error in PII detection: {str(e)}")
            raise

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

    def _add_custom_recognizers(self, registry: RecognizerRegistry) -> None:
        """添加基于规则的自定义识别器"""
        try:
            # 遍历所有规则
            for rule in self.rules:
                if not rule.get('enabled', True):
                    continue
                    
                try:
                    # 创建自定义规则识别器
                    recognizer = CustomRuleRecognizer(
                        rule=rule,
                        supported_language=rule.get('language', 'en'),
                        supported_entity=rule.get('name')
                    )
                    
                    # 添加到注册表
                    registry.add_recognizer(recognizer)
                    logger.info(f"Added custom recognizer for rule: {rule['name']}")
                    
                except Exception as e:
                    logger.warning(f"Failed to create recognizer for rule {rule.get('name', 'unknown')}: {str(e)}")
                    continue
                    
            logger.info(f"Successfully added {len(self.rules)} custom recognizers")
            
        except Exception as e:
            logger.error(f"Error adding custom recognizers: {str(e)}")
            raise

    def _get_masking_operator(self, style: str) -> str:
        """获取匿名化操作符"""
        if style == "asterisk":
            return "mask"
        elif style == "hash":
            return "hash"
        elif style == "redact":
            return "redact"
        return "mask"

    def validate_rule(self, rule: Dict[str, Any]) -> bool:
        """验证规则格式"""
        required_fields = {
            "id": str,
            "name": str,
            "type": str,
            "pattern": str,
            "description": str,
            "category": str,
            "country": str,
            "language": str,
            "enabled": bool,
            "masking_method": str
        }
        
        # 检查所有必需字段
        for field, field_type in required_fields.items():
            if field not in rule:
                logger.warning(f"Rule missing required field '{field}': {rule.get('id', 'unknown')}")
                return False
            if not isinstance(rule[field], field_type):
                logger.warning(f"Rule field '{field}' has wrong type: {rule.get('id', 'unknown')}")
                return False
                
        # 验证类别
        if rule["category"] not in self.supported_categories:
            logger.warning(f"Unsupported category '{rule['category']}' in rule: {rule['id']}")
            return False
            
        # 验证国家代码
        if rule["country"] not in self.country_code_mapping:
            logger.warning(f"Unsupported country code '{rule['country']}' in rule: {rule['id']}")
            return False
            
        # 验证语言
        if rule["language"] not in self.supported_languages:
            logger.warning(f"Unsupported language '{rule['language']}' in rule: {rule['id']}")
            return False
            
        return True

    def initialize_default_rules(self) -> None:
        """初始化默认规则"""
        try:
            # 使用 settings 中定义的路径
            os.makedirs(settings.PII_RULES_FILE.parent, exist_ok=True)
            with open(settings.PII_RULES_FILE, "w", encoding="utf-8") as f:
                json.dump({"rules": []}, f, indent=2, ensure_ascii=False)
            logger.info(f"Created empty rules file at {settings.PII_RULES_FILE}")
        except Exception as e:
            logger.error(f"Error creating rules file: {str(e)}")

    @timed
    def save_rules_to_file(self, rules: List[Dict[str, Any]]) -> bool:
        """将规则保存到文件"""
        try:
            # 使用 settings 中定义的路径
            rules_data = {
                "version": "1.0",
                "last_updated": datetime.now().isoformat(),
                "rules": rules
            }
            
            with open(settings.PII_RULES_FILE, 'w', encoding='utf-8') as f:
                json.dump(rules_data, f, indent=2, ensure_ascii=False)
                
            return True
            
        except Exception as e:
            logger.error(f"Error saving rules to file: {str(e)}")
            return False

    def get_rule_by_id(self, rule_id: str) -> Optional[PIIRule]:
        """根据ID获取规则"""
        for language, rules in self.rules_cache.items():
            for rule in rules:
                if rule.get("id") == rule_id:
                    return rule
        return None
    
    def add_rule(self, rule_id, rule_data):
        """添加新规则"""
        language = rule_data.language
        
        if language not in self.rules_cache:
            self.rules_cache[language] = []
        
        # 创建新规则
        new_rule = {
            "id": rule_id,
            "name": rule_data.name,
            "type": rule_data.type,
            "pattern": rule_data.pattern if rule_data.type == "regex" else None,
            "content": rule_data.content if rule_data.type == "dictionary" else None,
            "description": rule_data.description,
            "enabled": rule_data.enabled,
            "entity_type": rule_data.entity_type,
            "language": language,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        # 添加到缓存
        self.rules_cache[language].append(new_rule)
        
        # 保存到文件
        self._save_rules_to_file()
        
        # 重新初始化recognizers
        self._add_custom_recognizers()
        
        return new_rule
    
    def update_rule(self, rule_id, rule_update):
        """更新规则"""
        # 查找规则
        for language, rules in self.rules_cache.items():
            for i, rule in enumerate(rules):
                if rule.get("id") == rule_id:
                    # 更新规则
                    for field, value in rule_update.dict(exclude_unset=True).items():
                        if value is not None:
                            rule[field] = value
                    
                    rule["updated_at"] = datetime.now().isoformat()
                    
                    # 保存到文件
                    self._save_rules_to_file()
                    
                    # 重新初始化recognizers
                    self._add_custom_recognizers()
                    
                    return rule
        
        return None
    
    def delete_rule(self, rule_id):
        """删除规则"""
        for language, rules in self.rules_cache.items():
            for i, rule in enumerate(rules):
                if rule.get("id") == rule_id:
                    # 从缓存中删除
                    self.rules_cache[language].pop(i)
                    
                    # 保存到文件
                    self._save_rules_to_file()
                    
                    # 重新初始化recognizers
                    self._add_custom_recognizers()
                    
                    return True
        
        return False
    
    def bulk_import_rules(self, rules: List[dict]) -> List[dict]:
        """批量导入规则"""
        try:
            logger.info(f"Processing {len(rules)} rules for bulk import")
            
            # 验证每个规则
            valid_rules = []
            for rule in rules:
                try:
                    # 确保时间戳字段存在
                    if "created_at" not in rule:
                        rule["created_at"] = datetime.utcnow()
                    if "updated_at" not in rule:
                        rule["updated_at"] = datetime.utcnow()
                    
                    # 验证规则
                    if self.validate_rule(rule):
                        valid_rules.append(rule)
                        logger.debug(f"Validated rule: {rule['id']}")
                except Exception as e:
                    logger.warning(f"Invalid rule {rule.get('id', 'unknown')}: {str(e)}")
                    continue
            
            if not valid_rules:
                raise ValueError("No valid rules to import")
            
            # 保存规则到文件 - 注意这里的格式
            with self._lock:
                rules_data = {"rules": valid_rules}  # 确保使用统一的格式
                with open(settings.PII_RULES_FILE, 'w') as f:
                    json.dump(rules_data, f, indent=2, default=str)
            
            # 更新内存中的规则
            self.rules = valid_rules
            self.rules_cache.clear()
            
            # 为每个规则创建缓存
            for rule in valid_rules:
                language = rule.get("language", "en")
                self.rules_cache[language].append(rule)
            
            logger.info(f"Successfully saved {len(valid_rules)} rules to file")
            return valid_rules
            
        except Exception as e:
            logger.error(f"Error in bulk import: {str(e)}")
            raise

    def _save_rules_to_file(self):
        """将规则保存到文件 - 调用标准方法"""
        return self.save_rules_to_file()
    
    def get_supported_entities(self) -> List[Dict[str, Any]]:
        """获取支持的实体类型列表"""
        entity_types = {}
        for rule in self.rules:
            if rule.enabled:
                entity_type = rule.entity_type or rule.name
                if entity_type not in entity_types:
                    entity_types[entity_type] = {
                        "name": entity_type,
                        "description": rule.description,
                        "rules_count": 1
                    }
                else:
                    entity_types[entity_type]["rules_count"] += 1
                    
        return list(entity_types.values())
    
    @lru_cache(maxsize=1000)
    def _get_compiled_regex(self, pattern: str) -> re.Pattern:
        """获取或编译正则表达式"""
        if pattern not in self._compiled_regex_cache:
            try:
                self._compiled_regex_cache[pattern] = re.compile(pattern)
            except Exception as e:
                logger.error(f"Error compiling regex pattern '{pattern}': {str(e)}")
                # 返回一个不会匹配任何内容的模式
                return re.compile(r"(?!)")
        return self._compiled_regex_cache[pattern]
    
    @timed
    def batch_detect_pii(self, text: str, language: str = "en", 
                        sensitivity: float = 0.7) -> Dict[str, Any]:
        """批量处理文本进行PII检测"""
        start_time = time.time()
        
        # 按行分割文本
        lines = text.splitlines()
        total_entities = 0
        processed_lines = []
        all_entities = []
        
        # 处理每一行
        for i, line in enumerate(lines):
            if line.strip():
                result = self.detect_pii(
                    text=line,
                    language=language,
                    masking_style="asterisk"
                )
                line_entities = result["entities"]
                
                # 调整实体的行号信息
                for entity in line_entities:
                    entity["line"] = i
                
                total_entities += len(line_entities)
                all_entities.extend(line_entities)
                processed_lines.append(result["masked_text"])
            else:
                processed_lines.append(line)
        
        # 合并结果
        masked_text = "\n".join(processed_lines)
        
        # 处理时间
        processing_time = time.time() - start_time
        
        # 生成报告
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_lines": len(lines),
            "total_entities_detected": total_entities,
            "processing_summary": {
                "language": language,
                "sensitivity": sensitivity,
                "processing_time": processing_time
            },
            "entity_types": list(set(e["type"] for e in all_entities))
        }
        
        return {
            "timestamp": datetime.now().isoformat(),
            "is_safe": total_entities == 0,
            "masked_text": masked_text,
            "entities": all_entities,
            "report": json.dumps(report, ensure_ascii=False),
            "details": {
                "total_lines": len(lines),
                "total_entities": total_entities,
                "processing_time": processing_time
            }
        }
    
    @timed
    def preview_config(self, text: str, language: str = "en", 
                      sensitivity: float = 0.7, masking_style: str = "Bracketed Labels",
                      custom_rules: Any = None) -> Dict[str, Any]:
        """预览配置效果"""
        # 备份当前规则
        with self._lock:
            original_rules = self.rules.copy()
            
            try:
                # 如果有自定义规则，临时添加
                if custom_rules:
                    self._add_temp_rules(custom_rules)
                
                # 使用当前规则（包括临时规则）进行检测
                result = self.detect_pii(
                    text=text,
                    language=language,
                    masking_style=masking_style
                )
                
                # 添加预览标记
                result["preview_only"] = True
                
                return result
            finally:
                # 恢复原始规则
                self.rules = original_rules
                # 重置正则表达式缓存
                self._compiled_regex_cache = {}
    
    def _add_temp_rules(self, custom_rules: Any) -> None:
        """添加临时规则用于预览"""
        if isinstance(custom_rules, str):
            # 尝试解析JSON字符串
            try:
                custom_rule_data = json.loads(custom_rules)
                # 单个规则
                if isinstance(custom_rule_data, dict):
                    if "id" not in custom_rule_data:
                        custom_rule_data["id"] = f"temp-{str(uuid.uuid4())}"
                    custom_rule = PIIRule.from_dict(custom_rule_data)
                    self.rules.append(custom_rule)
                # 规则列表
                elif isinstance(custom_rule_data, list):
                    for rule_data in custom_rule_data:
                        if "id" not in rule_data:
                            rule_data["id"] = f"temp-{str(uuid.uuid4())}"
                        custom_rule = PIIRule.from_dict(rule_data)
                        self.rules.append(custom_rule)
            except json.JSONDecodeError:
                logger.error("Invalid JSON in custom rules")
        elif isinstance(custom_rules, dict):
            # 直接使用字典对象
            if "id" not in custom_rules:
                custom_rules["id"] = f"temp-{str(uuid.uuid4())}"
            custom_rule = PIIRule.from_dict(custom_rules)
            self.rules.append(custom_rule)
        elif isinstance(custom_rules, list):
            # 直接使用列表对象
            for rule_data in custom_rules:
                if "id" not in rule_data:
                    rule_data["id"] = f"temp-{str(uuid.uuid4())}"
                custom_rule = PIIRule.from_dict(rule_data)
                self.rules.append(custom_rule)

    def get_rules(self) -> List[Dict[str, Any]]:
        """获取所有PII规则"""
        try:
            # 直接返回已加载的规则
            logger.info(f"Returning {len(self.rules)} PII rules")
            return self.rules
        except Exception as e:
            logger.error(f"Error getting PII rules: {str(e)}")
            return []

    def reload(self) -> bool:
        """重新加载PII检测器"""
        try:
            logger.info("Reloading PII detector...")
            self._initialized = False
            self.initialize()
            return True
        except Exception as e:
            logger.error(f"Error reloading PII detector: {str(e)}")
            return False

    def get_processing_time(self):
        """获取最近一次处理的时间（秒）"""
        return self.last_processing_time

    def convert_rules_to_standard_format(self):
        """将规则文件转换为标准格式"""
        try:
            # 读取当前规则
            with open(settings.PII_RULES_FILE, 'r', encoding='utf-8') as f:
                current_rules = json.load(f)
            
            # 转换为标准格式
            if isinstance(current_rules, list):
                standard_format = {
                    "version": "1.0",
                    "last_updated": datetime.now().isoformat(),
                    "categories": [
                        "contact",
                        "identification",
                        "financial",
                        "government_id",
                        "personal",
                        "location",
                        "technical"
                    ],
                    "countries": [
                        "international",
                        "malaysia",
                        "singapore",
                        "brunei",
                        "china"
                    ],
                    "languages": [
                        "en",
                        "ms",
                        "zh"
                    ],
                    "rules": current_rules
                }
                
                # 保存转换后的格式
                with open(settings.PII_RULES_FILE, 'w', encoding='utf-8') as f:
                    json.dump(standard_format, f, indent=2, ensure_ascii=False)
                
                logger.info("Successfully converted rules to standard format")
                return True
                
        except Exception as e:
            logger.error(f"Error converting rules format: {str(e)}")
            return False

    def _get_default_rules(self) -> List[PIIRule]:
        """获取默认规则"""
        return [
            PIIRule(
                id="email",
                name="Email Address",
                pattern=r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                category="contact",
                description="Email address detection"
            ),
            PIIRule(
                id="sg_nric",
                name="Singapore NRIC",
                pattern=r"[STFG]\d{7}[A-Z]",
                category="id",
                country="SG",
                description="Singapore NRIC number"
            ),
            # 添加更多默认规则...
        ]

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
                
                # 按语言分类规则并缓存
                self.rules_cache = defaultdict(list)
                for rule in self.rules:
                    if rule.get('enabled', True):  # 只缓存启用的规则
                        language = rule.get('language', 'en')
                        self.rules_cache[language].append(rule)
                    
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
                rule.setdefault("language", "en")
                rule.setdefault("enabled", True)
                rule.setdefault("masking_method", "mask")
                
                valid_rules.append(rule)
            
            if not valid_rules:
                raise ValueError("No valid rules provided")
            
            # 3. 使用线程锁保护更新操作
            with self._lock:
                # 4. 更新规则列表
                self.rules = valid_rules
                
                # 5. 保存规则到文件
                with open(settings.PII_RULES_FILE, 'w', encoding='utf-8') as f:
                    json.dump({"rules": valid_rules}, f, indent=2, ensure_ascii=False)
                logger.info("Rules saved to file")
                
                # 6. 重新创建识别器注册表
                registry = RecognizerRegistry()
                registry.load_predefined_recognizers()
                logger.info("Loaded predefined recognizers")
                
                # 7. 使用新规则创建自定义识别器
                self._add_custom_recognizers(registry)
                logger.info("Added custom recognizers")
                
                # 8. 更新分析器
                self.analyzer = AnalyzerEngine(
                    nlp_engine=self.nlp_engine,
                    registry=registry
                )
                logger.info("Updated analyzer with new rules")
                
                # 9. 更新规则缓存
                self.rules_cache = {rule['id']: rule for rule in valid_rules}
                
                return True

        except Exception as e:
            logger.error(f"Error updating rules: {str(e)}")
            # 发生错误时回滚到原始状态
            self.rules = original_rules
            self.analyzer = original_analyzer
            self.rules_cache = {rule['id']: rule for rule in original_rules}
            raise RuntimeError(f"Failed to update rules: {str(e)}")

    async def cleanup(self) -> None:
        """清理资源"""
        try:
            logger.info("Cleaning up PII detector resources...")
            
            # 清理 NLP 引擎
            if self.nlp_engine:
                # 如果有需要清理的资源，在这里处理
                self.nlp_engine = None
                
            # 清理分析器
            if self.analyzer:
                self.analyzer = None
                
            # 清理匿名器
            if self.anonymizer:
                self.anonymizer = None
                
            # 清理缓存
            self.rules_cache.clear()
            self._compiled_regex_cache.clear()
            
            # 重置初始化标志
            self._initialized = False
            
            logger.info("PII detector cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during PII detector cleanup: {str(e)}")
            raise