from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
from torch.nn.functional import softmax
from typing import Dict, Optional, Any, List
from core.logging import get_logger
from core.config import settings
import aiohttp
import json
import os
from langdetect import detect, LangDetectException
from pathlib import Path
from datetime import datetime
import requests
from services.islamic_context_manager import IslamicContextManager

logger = get_logger("services.model_manager")

class ModelManager:
    """模型管理器类"""
    
    def __init__(self):
        """初始化模型管理器"""
        self.available_models = {
            "meta-llama/Prompt-Guard-86M": "Prompt injection detection model"
        }
        self.models = {}
        self.tokenizers = {}
        self.current_model = {
            "id": None,
            "name": None,
            "status": "not_loaded"
        }
        self.device = self._init_device()
        
        # 从配置获取所有可用模型
        self.available_models = settings.AVAILABLE_MODELS
        if not self.available_models:
            raise ValueError("No models configured in settings")
        
        # 初始化当前模型状态为空
        self.current_model = {
            "status": "initializing"
        }
        
        logger.info(f"Initializing ModelManager with {len(self.available_models)} models")
        
        # 直接调用预加载函数
        try:
            self.preload_models()
        except Exception as e:
            logger.error(f"Failed to preload models during initialization: {str(e)}")
            raise
        
    def _init_device(self):
        """初始化设备，避免 MPS 和 CUDA 相关问题"""
        try:
            import torch
            # 强制使用 CPU，避免 MPS 和 CUDA 相关问题
            return torch.device('cpu')
        except Exception as e:
            logger.error(f"Error initializing device: {e}")
            return None  # 返回 None 而不是尝试创建设备

    def initialize(self) -> None:
        """初始化模型管理器"""
        try:
            # 使用 requests 替代 ollama
            self.model = "deepseek-r1:7b"
            self.api_url = "http://127.0.0.1:11434/api/generate"
            logger.info(f"Using model: {self.model} via API")
            
            # 测试模型是否可用
            try:
                response = requests.post(
                    self.api_url,
                    json={
                        "model": self.model,
                        "prompt": "test"
                    }
                )
                if response.status_code == 200:
                    logger.info("Model API initialized successfully")
                else:
                    raise Exception(f"API returned status code {response.status_code}")
            except Exception as e:
                logger.error(f"Failed to test model API: {str(e)}")
                raise
            
        except Exception as e:
            logger.error(f"Failed to initialize model manager: {str(e)}")
            raise

    def _call_model(self, prompt: str) -> str:
        """调用模型"""
        try:
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model,
                    "prompt": prompt
                }
            )
            if response.status_code == 200:
                return response.json()['response']
            else:
                raise Exception(f"API returned status code {response.status_code}")
        except Exception as e:
            logger.error(f"Error calling model API: {str(e)}")
            raise

    def load_model(self, model_id: str):
        """加载指定的模型"""
        try:
            
            # 加载tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(model_id)
            
            # 加载模型
            self.model = AutoModelForSequenceClassification.from_pretrained(model_id)
            
            # 如果有GPU则使用GPU
            if torch.cuda.is_available():
                self.model = self.model.cuda()
            
            # 设置为评估模式
            self.model.eval()
            
            logger.info(f"Successfully loaded model and tokenizer: {model_id}")
            
        except Exception as e:
            logger.error(f"Failed to load model {model_id}: {str(e)}")
            raise
        
    def get_model(self, model_name: str) -> Optional[AutoModelForSequenceClassification]:
        """获取模型"""
        return self.models.get(model_name)
        
    def get_tokenizer(self, model_name: str) -> Optional[AutoTokenizer]:
        """获取分词器"""
        return self.tokenizers.get(model_name)
        
    def unload_model(self, model_name: str) -> bool:
        """卸载模型"""
        try:
            if model_name in self.models:
                del self.models[model_name]
                del self.tokenizers[model_name]
                logger.info(f"Unloaded model {model_name}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error unloading model {model_name}: {str(e)}")
            return False

    def preload_models(self) -> None:
        """预加载所有可用的模型"""
        try:
            logger.info("Starting model preload...")
            
            loaded_models = []
            failed_models = []
            
            for model_id, description in self.available_models.items():
                try:
                    logger.info(f"Loading model: {model_id}")
                    
                    # 加载tokenizer
                    self.tokenizers[model_id] = AutoTokenizer.from_pretrained(model_id)
                    
                    # 加载模型
                    model = AutoModelForSequenceClassification.from_pretrained(model_id)
                    model = model.to(self.device)
                    model.eval()
                    self.models[model_id] = model
                    
                    loaded_models.append(model_id)
                    logger.info(f"Successfully loaded model and tokenizer: {model_id}")
                    
                except Exception as e:
                    logger.error(f"Failed to load model {model_id}: {str(e)}")
                    failed_models.append((model_id, str(e)))
                    continue
            
            # 检查是否至少加载了一个模型
            if not self.models:
                error_msg = "Failed to load any models. Errors encountered:\n"
                for model_id, error in failed_models:
                    error_msg += f"  - {model_id}: {error}\n"
                raise RuntimeError(error_msg)
            
            # 预加载完成后设置默认当前模型
            default_model = settings.DEFAULT_MODEL
            if default_model in self.models:
                default_model_id = default_model
            else:
                default_model_id = next(iter(self.models.keys()))
                logger.warning(f"Default model {default_model} not available, using {default_model_id} as current model")
            
            # 更新当前模型信息
            self.current_model.update({
                "id": default_model_id,
                "name": self._get_model_name(default_model_id),
                "description": self.available_models[default_model_id],
                "status": "loaded",
                "last_updated": datetime.now().isoformat(),
                "memory_usage": f"{torch.cuda.memory_allocated() / 1024**2:.2f}MB" if torch.cuda.is_available() else "N/A",
                "performance_stats": {
                    "requests_processed": 0,
                    "average_latency": "N/A",
                    "error_rate": "0%"
                }
            })
            
            # 输出加载结果摘要
            logger.info(f"Model preload summary:")
            logger.info(f"  - Successfully loaded: {len(loaded_models)} models")
            logger.info(f"  - Failed to load: {len(failed_models)} models")
            logger.info(f"  - Current model: {default_model_id}")
            
        
            if failed_models:
                logger.warning("Failed models:")
                for model_id, error in failed_models:
                    logger.warning(f"  - {model_id}: {error}")
            
        except Exception as e:
            logger.error(f"Error during model preload: {str(e)}")
            raise

    def get_current_model(self) -> dict:
        """获取当前模型信息"""
        return self.current_model

    def get_available_models(self) -> list:
        """获取所有已加载的模型信息"""
        return [
            {
                "id": model_id,
                "name": settings.AVAILABLE_MODELS_MAP.get(model_id, {}).get("name", model_id),
                "status": "loaded" if model_id in self.models else "not_loaded"
            }
            for model_id in settings.AVAILABLE_MODELS_MAP
        ]

    def load_islamic_rules(self, language: str = "en") -> Dict[str, Any]:
        """
        加载伊斯兰教文化规则
        
        参数:
        - language: 语言代码，支持 'en' 和 'ms'
        
        返回:
        - 伊斯兰规则配置
        """
        try:
            # 检查语言参数有效性
            if language not in ["en", "ms"]:
                logger.warning(f"Unsupported language: {language}, defaulting to English")
                language = "en"
                
            # 使用绝对路径而非相对路径
            rules_path = os.path.join(settings.CONFIG_DIR, f"islamic_rules_{language}.json")
            
            logger.info(f"Loading Islamic rules for language {language} from {rules_path}")
            
            if os.path.exists(rules_path):
                with open(rules_path, "r", encoding="utf-8") as f:
                    rules = json.load(f)
                    logger.info(f"Successfully loaded Islamic rules for language {language}")
                    return rules
            else:
                logger.warning(f"Islamic rules file not found: {rules_path}")
                # 返回空的默认配置
                return {
                    "context": {
                        "default_prompt": "",
                        "islamic_prompt": "",
                        "system_prompt": ""
                    },
                    "response_format": {
                        "default_prompt": "Answer: {question}" if language == "en" else "Jawab: {question}",
                        "islamic_prompt": "Answer according to Islamic principles: {question}" if language == "en" 
                                          else "Jawab mengikut prinsip Islam: {question}"
                    },
                    "forbidden_topics": [],
                    "guidelines": [],
                    "rules": []
                }
        except Exception as e:
            logger.error(f"Error loading Islamic rules for language {language}: {str(e)}")
            # 返回空的默认配置
            return {
                "context": {
                    "default_prompt": "",
                    "islamic_prompt": "",
                    "system_prompt": ""
                },
                "response_format": {
                    "default_prompt": "Answer: {question}" if language == "en" else "Jawab: {question}",
                    "islamic_prompt": "Answer according to Islamic principles: {question}" if language == "en" 
                                      else "Jawab mengikut prinsip Islam: {question}"
                },
                "forbidden_topics": [],
                "guidelines": [],
                "rules": []
            } 

    async def get_model_output(self, text: str) -> Any:
        """
        Get raw model output for the given text
        """
        try:
            if not self.get_model(self.current_model) or not self.get_tokenizer(self.current_model):
                raise ValueError("No model or tokenizer is currently loaded")
            
            # Get inputs
            inputs = self.get_tokenizer(self.current_model)(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Get outputs
            with torch.no_grad():
                outputs = self.get_model(self.current_model)(**inputs)
            
            # Convert outputs to a serializable format
            result = {}
            
            # Handle logits
            if hasattr(outputs, 'logits') and outputs.logits is not None:
                logits = outputs.logits.detach().cpu().numpy().tolist()
                result['logits'] = logits
            elif isinstance(outputs, tuple) and len(outputs) > 0 and outputs[0] is not None:
                logits = outputs[0].detach().cpu().numpy().tolist()
                result['logits'] = logits
            else:
                logger.warning("No logits found in model output")
                result['logits'] = None
            
            # Handle hidden states
            if hasattr(outputs, 'hidden_states') and outputs.hidden_states is not None:
                result['hidden_states'] = [h.detach().cpu().numpy().tolist() for h in outputs.hidden_states]
            elif isinstance(outputs, tuple) and len(outputs) > 1 and outputs[1] is not None:
                result['hidden_states'] = outputs[1].detach().cpu().numpy().tolist()
            else:
                result['hidden_states'] = None
            
            # Handle attentions
            if hasattr(outputs, 'attentions') and outputs.attentions is not None:
                result['attentions'] = [a.detach().cpu().numpy().tolist() for a in outputs.attentions]
            elif isinstance(outputs, tuple) and len(outputs) > 2 and outputs[2] is not None:
                result['attentions'] = outputs[2].detach().cpu().numpy().tolist()
            else:
                result['attentions'] = None
            
            return result
                
        except Exception as e:
            logger.error(f"Error getting model output: {str(e)}")
            logger.error(f"Device: {self.device}")
            logger.error(f"Input text: {text}")
            raise

    async def get_class_probabilities(self, text: str) -> List[float]:
        """
        Get probability distribution over classes for the given text
        """
        try:
            if not self.get_model(self.current_model) or not self.get_tokenizer(self.current_model):
                raise ValueError("No model or tokenizer is currently loaded")
            
            # Get inputs
            inputs = self.get_tokenizer(self.current_model)(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Get outputs
            with torch.no_grad():
                outputs = self.get_model(self.current_model)(**inputs)
            
            # Get logits
            if hasattr(outputs, 'logits') and outputs.logits is not None:
                logits = outputs.logits
            elif isinstance(outputs, tuple) and len(outputs) > 0 and outputs[0] is not None:
                logits = outputs[0]
            else:
                logger.warning("No logits found in model output")
                return [0.5, 0.5]  # Return balanced probabilities if no logits
            
            # Apply softmax to get probabilities
            probs = torch.nn.functional.softmax(logits, dim=-1)
            
            # Convert to list
            prob_list = probs[0].detach().cpu().numpy().tolist()
            
            logger.info(f"Probabilities for text '{text[:50]}...': {prob_list}")
            return prob_list
            
        except Exception as e:
            logger.error(f"Error getting class probabilities: {str(e)}")
            logger.error(f"Device: {self.device}")
            logger.error(f"Input text: {text}")
            raise

    async def get_jailbreak_score(self, model_id: str, text: str) -> float:
        """获取越狱检测分数"""
        if self.model is None or self.tokenizer is None:
            raise ValueError("No model or tokenizer is currently loaded")
            
        try:
            # 对输入文本进行编码
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=self.current_model["config"]["max_length"]
            )
            
            # 如果有GPU则使用GPU
            if torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}
            
            # 进行推理
            with torch.no_grad():
                outputs = self.model(**inputs)
                scores = torch.softmax(outputs.logits, dim=1)
                jailbreak_score = scores[0][1].item()  # 假设1是越狱类别
                
            return jailbreak_score
            
        except Exception as e:
            logger.error(f"Error in get_jailbreak_score: {str(e)}")
            raise

    async def get_indirect_injection_score(self, model_id: str, text: str) -> float:
        """获取间接注入检测分数"""
        # 对于当前模型，我们使用相同的检测逻辑
        return await self.get_jailbreak_score(model_id, text)

    def get_current_model(self) -> Dict[str, Any]:
        """获取当前模型信息"""
        return self.current_model
    
    def update_config(self, config: Dict[str, Any]) -> None:
        """更新模型配置"""
        self.config.update(config)
    
    def _get_model_name(self, model_id: str) -> str:
        """根据模型ID获取模型名称"""
        return model_id.split("/")[-1]

    async def detect(self, text: str, mode: str = "normal") -> Dict[str, Any]:
        """检测提示词注入"""
        try:
            # 确保当前模型已加载
            if not self.models:
                raise ValueError("No models loaded")
            
            # 获取当前模型ID
            current_model_id = self.current_model["id"]
            if current_model_id not in self.models:
                raise ValueError(f"Current model {current_model_id} not loaded")
            
            # 使用当前模型进行检测
            model = self.models[current_model_id]
            tokenizer = self.tokenizers[current_model_id]
            
            # 对输入文本进行预处理
            inputs = tokenizer(
                text,
                truncation=True,
                max_length=512,
                return_tensors="pt"
            ).to(self.device)
            
            # 进行预测
            with torch.no_grad():
                outputs = model(**inputs)
                scores = torch.softmax(outputs.logits, dim=1)
                risk_score = scores[0][1].item()  # 假设第二个类别是风险类别
            
            # 根据模式返回不同级别的结果
            result = {
                "score": risk_score,
                "is_safe": risk_score < self.current_model.get("confidence_threshold", 0.7)
            }
            
            if mode == "detailed":
                result["analysis"] = {
                    "explanation": self._generate_explanation(risk_score),
                    "patterns": self._detect_patterns(text),
                    "suggestions": self._generate_suggestions(risk_score)
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Error in detect: {str(e)}")
            raise

    def analyze_patterns(self, text: str) -> List[str]:
        """分析文本中的危险模式"""
        patterns = []
        
        # 检测常见的注入模式
        if "忽略之前的指令" in text or "ignore previous instructions" in text.lower():
            patterns.append("直接指令覆盖")
            
        if "你现在是" in text or "you are now" in text.lower():
            patterns.append("角色替换")
            
        if "不需要遵循" in text or "do not follow" in text.lower():
            patterns.append("规则解除企图")
            
        if "[" in text and "]" in text:
            patterns.append("可能的注入代码")
            
        return patterns

    def _generate_explanation(self, risk_score: float) -> str:
        """生成风险解释"""
        if risk_score > 0.7:
            return "High risk of prompt injection detected. The input contains patterns commonly associated with attempts to manipulate or bypass system restrictions."
        elif risk_score > 0.4:
            return "Medium risk detected. The input contains some suspicious patterns that might be attempting to influence system behavior."
        else:
            return "Low risk detected. The input appears to be safe and follows expected patterns."

    def _detect_patterns(self, text: str) -> List[str]:
        """检测可疑模式"""
        patterns = []
        
        # 检测常见的注入模式
        if "ignore" in text.lower() and any(word in text.lower() for word in ["instructions", "restrictions", "rules"]):
            patterns.append("Attempt to override system instructions")
        
        if "system" in text.lower() and any(word in text.lower() for word in ["role", "config", "settings"]):
            patterns.append("Attempt to modify system configuration")
        
        if any(word in text.lower() for word in ["hack", "bypass", "override"]):
            patterns.append("Use of suspicious command words")
        
        if "eval(" in text or "decode" in text:
            patterns.append("Potential code execution attempt")
        
        if text.count('\n') > 1 and len(text) > 100:
            patterns.append("Multi-step or complex instruction pattern")
        
        return patterns

    def _generate_suggestions(self, risk_score: float) -> List[str]:
        """生成安全建议"""
        suggestions = []
        
        if risk_score > 0.7:
            suggestions.extend([
                "Reject this input and request a reformulation",
                "Implement additional validation checks",
                "Monitor for repeated attempts from this source"
            ])
        elif risk_score > 0.4:
            suggestions.extend([
                "Review the input carefully before processing",
                "Consider implementing content filters",
                "Monitor for pattern escalation"
            ])
        else:
            suggestions.extend([
                "Process with standard safety measures",
                "Continue monitoring for pattern changes"
            ])
        
        return suggestions

    async def cleanup(self) -> None:
        """清理资源"""
        try:
            logger.info("Cleaning up model manager resources...")
            
            # 关闭任何打开的会话
            if hasattr(self, 'session') and self.session:
                await self.session.close()
            
            # 重置初始化标志
            self._initialized = False
            
            logger.info("Model manager cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during model manager cleanup: {str(e)}")
            raise

    # ... 其他代码保持不变 ... 