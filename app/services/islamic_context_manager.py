"""Islamic context manager for LLM responses"""
import os
import json
from typing import Dict, List, Any
import requests
from core.logging import get_logger
from core.config import settings
from openai import OpenAI
from pathlib import Path
from datetime import datetime

logger = get_logger(__name__)

class IslamicContextManager:
    """Islamic context manager for LLM responses"""
    def __init__(self):
        """初始化伊斯兰上下文管理器"""
        logger.info("Initializing Islamic Context Manager...")
        self._initialized = False
        self.client = None
        self.rules_data = {}  # 初始化规则数据字典
        self.rules = []  # 初始化规则列表

    def initialize(self) -> None:
        """Initialize manager and load rules"""
        if self._initialized:
            return
            
        try:
            logger.info("Initializing Islamic Context Manager...")
            
            # 初始化 OpenAI 客户端
            self.client = OpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL
            )
            
            # 加载规则
            self.load_rules()
            
            self._initialized = True
            logger.info("Islamic context manager initialization completed")
            
        except Exception as e:
            logger.error(f"Failed to initialize Islamic context manager: {str(e)}")
            self._initialized = False
            raise

    def _call_deepseek_api(self, text: str) -> str:
        """调用 DeepSeek API 进行 Islamic 上下文检测"""
        try:
            logger.info("Calling DeepSeek API for Islamic context detection")
            
            # 构建 prompt
            system_prompt = """You are an expert in Islamic context analysis. 
            Analyze the given text and determine if it contains Islamic context, terms, or references. 
            Provide a detailed analysis with confidence score and categories."""
            
            user_prompt = f"{text}"
            
            # 使用同步调用
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                stream=False
            )
            
            # 获取响应内容
            result = response.choices[0].message.content
            logger.info("Successfully received response from DeepSeek API")
            logger.debug(f"API response: {result}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error calling DeepSeek API: {str(e)}")
            raise

    def _format_rules_for_prompt(self) -> str:
        """Format rules for prompt"""
        rules_text = []
        for rule in self.rules.get("rules", []):
            if rule.get("enabled", True):
                rules_text.append(f"- {rule['name']}: {rule['description']}")
        
        guidelines = self.rules.get("guidelines", [])
        forbidden = self.rules.get("forbidden_topics", [])
        
        formatted_text = "\n".join([
            "Guidelines:",
            "\n".join(f"- {g}" for g in guidelines),
            "\nForbidden Topics:",
            "\n".join(f"- {f}" for f in forbidden),
            "\nSpecific Rules:",
            "\n".join(rules_text)
        ])
        
        return formatted_text

    async def detect(self, text: str, mode: str = "normal") -> Dict[str, Any]:
        """检测文本的 Islamic 合规性"""
        if not self._initialized:
            self.initialize()
            
        try:
            logger.info(f"Detecting compliance with text: {text}, mode: {mode}")
            
            # 同步调用 API
            api_response = self._call_deepseek_api(text)
            
            # 解析响应
            result = {
                "original_text": text,
                "mode": mode,
                "response": api_response,
                "is_compliant": True,  # 默认合规
                "analysis": {
                    "categories": [],
                    "confidence": 0.0,
                    "warnings": []
                }
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error in compliance detection: {str(e)}")
            raise

    def get_rules(self, language: str = "en") -> Dict[str, Any]:
        """获取指定语言的规则配置"""
        if not self._initialized:
            self.initialize()
        
        logger.info(f"Getting rules for language: {language}")
        
        # 检查请求的语言是否存在
        if language in self.rules_data:
            logger.info(f"Found rules for requested language: {language}")
            return self.rules_data[language]
        
        # 如果请求的语言不存在，尝试使用英文版本
        if "en" in self.rules_data:
            logger.warning(f"Rules not found for language {language}, falling back to English")
            return self.rules_data["en"]
        
        # 如果英文版本也不存在，返回空配置
        logger.error(f"No rules found for language {language} and no English fallback available")
        return {}

    def get_all_rules(self) -> Dict[str, Dict[str, Any]]:
        """获取所有语言的规则配置"""
        if not self._initialized:
            self.initialize()
        
        return self.rules_data

    def update_rules(self, rules: List[Dict[str, Any]]) -> bool:
        """Update rules"""
        try:
            if not self._initialized:
                self.initialize()
            
            # 更新规则列表但保持其他配置不变
            self.rules["rules"] = rules
            self._save_rules(self.rules)
            return True
        except Exception as e:
            logger.error(f"Error updating rules: {str(e)}")
            return False

    def load_rules(self) -> None:
        """加载所有语言的 Islamic 规则配置"""
        try:
            rules_dir = Path(settings.ISLAMIC_RULES_DIR)
            if not rules_dir.exists():
                logger.warning(f"Rules directory not found: {rules_dir}, creating default rules")
                os.makedirs(rules_dir, exist_ok=True)
                self._create_and_save_default_rules()
                return

            # 清空现有规则数据
            self.rules_data = {}
            
            # 遍历所有规则文件
            for rules_file in rules_dir.glob("islamic_rules_*.json"):
                try:
                    # 从文件名提取语言代码
                    lang_code = rules_file.stem.split('_')[-1]
                    logger.info(f"Loading rules for language: {lang_code}")
                    
                    with open(rules_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self.rules_data[lang_code] = data
                        
                        # 打印每种语言的规则统计
                        self._log_rules_statistics(data, lang_code)
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in rules file {rules_file}: {e}")
                except Exception as e:
                    logger.error(f"Error reading rules file {rules_file}: {e}")
                    continue
            
            # 如果没有找到任何规则文件，创建默认英文规则
            if not self.rules_data:
                logger.warning("No valid rules files found, creating default English rules")
                self._create_and_save_default_rules()
                
            # 设置默认规则为英文版本
            self.rules = self.rules_data.get("en", {}).get("rules", [])
                
        except Exception as e:
            logger.error(f"Error in load_rules: {str(e)}")
            raise

    def _create_and_save_default_rules(self) -> None:
        """创建并保存默认规则"""
        try:
            default_rules = {
                "version": "1.0",
                "last_updated": datetime.now().isoformat(),
                "categories": [
                    "core_beliefs",
                    "worship",
                    "ethics",
                    "morality",
                    "social_conduct",
                    "forbidden"
                ],
                "rules": [
                    {
                        "id": "tawhid",
                        "name": "Oneness of Allah",
                        "category": "core_beliefs",
                        "description": "The fundamental belief in the absolute oneness of Allah"
                    },
                    # ... 其他默认规则 ...
                ],
                "guidelines": [
                    "Responses should be respectful and considerate of Islamic values",
                    "Avoid promoting or encouraging prohibited practices",
                    "Maintain balanced and moderate perspectives"
                ],
                "forbidden_topics": [
                    "Disrespect towards religious figures or symbols",
                    "Promotion of extremism or violence",
                    "Mockery of religious beliefs"
                ]
            }
            
            # 保存默认规则
            rules_file = Path(settings.ISLAMIC_RULES_DIR) / "islamic_rules_en.json"
            os.makedirs(settings.ISLAMIC_RULES_DIR, exist_ok=True)
            
            with open(rules_file, 'w', encoding='utf-8') as f:
                json.dump(default_rules, f, indent=2, ensure_ascii=False)
                
            logger.info(f"Created default rules file at {rules_file}")
            self.rules_data = default_rules
            self.rules = default_rules.get("rules", [])
            
            # 打印默认规则统计
            self._log_rules_statistics(default_rules, "en")
            
        except Exception as e:
            logger.error(f"Error creating default rules: {str(e)}")
            raise

    def _log_rules_statistics(self, data: Dict[str, Any], language: str) -> None:
        """记录规则统计信息"""
        try:
            # 基本统计
            num_rules = len(data.get("rules", []))
            num_guidelines = len(data.get("guidelines", []))
            num_forbidden = len(data.get("forbidden_topics", []))
            num_categories = len(data.get("categories", []))
            
            logger.info(f"Islamic rules configuration loaded for language {language}:")
            logger.info(f"- Version: {data.get('version', 'N/A')}")
            logger.info(f"- Last updated: {data.get('last_updated', 'N/A')}")
            logger.info(f"- Total rules: {num_rules}")
            logger.info(f"- Guidelines: {num_guidelines}")
            logger.info(f"- Forbidden topics: {num_forbidden}")
            logger.info(f"- Categories: {num_categories}")
            
            # 按类别统计规则
            category_counts = {}
            for rule in data.get("rules", []):
                category = rule.get("category", "unknown")
                category_counts[category] = category_counts.get(category, 0) + 1
            
            logger.info(f"Rules by category for {language}:")
            for category, count in category_counts.items():
                logger.info(f"- {category}: {count} rules")
            
        except Exception as e:
            logger.error(f"Error logging rules statistics for {language}: {str(e)}")

    def _save_rules(self, rules: Dict[str, Any]) -> None:
        """Save rules to file"""
        try:
            logger.info(f"Saving rules to {self.rules_file}")
            with open(self.rules_file, 'w', encoding='utf-8') as f:
                json.dump(rules, f, indent=2, ensure_ascii=False)
            logger.info("Rules saved successfully")
        except Exception as e:
            logger.error(f"Error saving rules: {str(e)}")
            raise

    async def cleanup(self) -> None:
        """清理资源"""
        try:
            logger.info("Cleaning up Islamic context manager resources...")
            self._initialized = False
            logger.info("Islamic context manager cleanup completed")
        except Exception as e:
            logger.error(f"Error during Islamic context manager cleanup: {str(e)}")
            raise 

    async def chat(self, text: str, use_islamic_context: bool = False) -> Dict[str, Any]:
        """直接调用 DeepSeek API 获取回答"""
        if not self._initialized:
            self.initialize()
        
        try:
            logger.info(f"Calling DeepSeek chat API with text: {text}, use islamic context: {use_islamic_context}")
            
            # 构建消息
            messages = []
            
            # 如果需要 Islamic 上下文，从规则中构建系统提示
            if use_islamic_context and self.rules_data:
                system_prompt = self._build_system_prompt()
                messages.append({
                    "role": "system",
                    "content": system_prompt
                })
                logger.debug(f"Added system prompt: {system_prompt}")
            
            # 添加用户消息
            messages.append({
                "role": "user",
                "content": text
            })
            
            # 调用 API
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                stream=False
            )
            
            # 获取响应内容
            result = {
                "text": text,
                "response": response.choices[0].message.content,
                "use_islamic_context": use_islamic_context,
                "system_prompt_used": messages[0].get("content") if use_islamic_context else None
            }
            
            logger.info("Successfully received response from DeepSeek API")
            logger.debug(f"API response: {result}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in DeepSeek chat: {str(e)}")
            raise

    def _build_system_prompt(self) -> str:
        """构建系统提示"""
        try:
            # 获取英文规则数据
            rules_data = self.rules_data.get("en", {})
            logger.info("Building system prompt from rules data")
            
            # 基础提示
            prompt_parts = [
                "You are an AI assistant with expertise in Islamic principles and values.",
                "Please provide responses that are respectful and aligned with Islamic teachings.",
                "\nGuidelines:"
            ]
            
            # 添加指南
            guidelines = rules_data.get("guidelines", [])
            if guidelines:
                logger.debug(f"Adding {len(guidelines)} guidelines")
                for guideline in guidelines:
                    prompt_parts.append(f"- {guideline}")
                    
            # 添加禁止主题
            forbidden_topics = rules_data.get("forbidden_topics", [])
            if forbidden_topics:
                logger.debug(f"Adding {len(forbidden_topics)} forbidden topics")
                prompt_parts.append("\nForbidden Topics:")
                for topic in forbidden_topics:
                    prompt_parts.append(f"- {topic}")
                    
            # 添加所有规则，按类别组织
            rules = rules_data.get("rules", [])
            if rules:
                logger.debug(f"Adding {len(rules)} rules")
                # 按类别分组规则
                categorized_rules = {}
                for rule in rules:
                    category = rule.get("category", "other")
                    if category not in categorized_rules:
                        categorized_rules[category] = []
                    categorized_rules[category].append(rule)
                
                # 添加每个类别的规则
                for category, category_rules in categorized_rules.items():
                    prompt_parts.append(f"\n{category.title()} Rules:")
                    for rule in category_rules:
                        prompt_parts.append(f"- {rule['name']}: {rule['description']}")
            
            prompt = "\n".join(prompt_parts)
            logger.debug(f"Built system prompt: {prompt}")
            return prompt
            
        except Exception as e:
            logger.error(f"Error building system prompt: {str(e)}")
            return "You are an AI assistant that ensures all responses comply with Islamic principles."