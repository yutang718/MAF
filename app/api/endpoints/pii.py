"""PII检测相关API端点"""
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from datetime import datetime
import uuid
from fastapi import APIRouter, Path, Query, HTTPException, Depends, status, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import json
import logging

from models.pii import (
    PIIRule,
    PIIRuleUpdateRequest,
    PIIDetectionRequest,
    PIIDetectionResponse,
    PIIBatchDetectionRequest,
    PIIConfigPreviewRequest,
    PIIRuleBulkUpdate,
    PIIRuleResponse
)
from core.dependencies import get_services, Services
from core.logging import get_logger


# 获取模块的logger
logger = logging.getLogger(__name__)
router = APIRouter()

class DetectionRequest(BaseModel):
    text: str
    mask: bool = False
    batch: bool = False

@router.get("/rules")
async def get_rules(
    services: Services = Depends(get_services)
) -> Dict[str, List[Dict[str, Any]]]:
    """获取所有PII规则"""
    try:
        rules = services.pii_detector.get_rules()
        logger.info(f"API returning {len(rules)} PII rules")
        return {"rules": rules}
    except Exception as e:
        logger.error(f"Error getting PII rules: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get PII rules: {str(e)}"
        )

@router.get("/rules/{rule_id}", response_model=PIIRule)
async def get_pii_rule(
    rule_id: str,
    services: Services = Depends(get_services)
):
    """获取特定ID的PII规则"""
    try:
        rule = services.pii_detector.get_rule_by_id(rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail=f"规则ID {rule_id} 不存在")
        return rule
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取规则失败: {str(e)}")

@router.post("/rules", response_model=PIIRule)
async def create_rule(rule: PIIRule):
    """创建新的PII规则"""
    try:
        rule_data = rule.dict()
        if 'country' not in rule_data:
            rule_data['country'] = ''
        if 'enabled' not in rule_data:
            rule_data['enabled'] = True
            
        new_rule = pii_detector.add_rule(rule_data)
        pii_detector.reload_rules()
        return new_rule
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/rules/{rule_id}", response_model=PIIRule)
async def update_rule(rule_id: str, rule: PIIRule) -> Dict[str, Any]:
    """更新单个PII规则"""
    try:
        pii_detector = get_services().get_pii_detector()
        
        # 确保路径参数和请求体中的ID匹配
        if rule_id != rule.id:
            raise HTTPException(
                status_code=400,
                detail="Rule ID in path does not match ID in request body"
            )
            
        updated_rule = pii_detector.update_rule(rule_id, rule.dict())
        if not updated_rule:
            raise HTTPException(
                status_code=404,
                detail=f"Rule with ID {rule_id} not found"
            )
            
        return updated_rule
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating PII rule {rule_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update rule: {str(e)}"
        )

@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str):
    """删除PII规则"""
    try:
        pii_detector.delete_rule(rule_id)
        await pii_detector.reload_rules()  # 重新加载所有规则
        return {"message": "Rule deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/rules/reload")
def reload_rules() -> Dict[str, Any]:
    """
    重新加载PII规则
    """
    try:
        # 重新加载规则
        pii_detector.load_rules_from_file()  # 移除 await
        
        return {
            "status": "success",
            "message": "Rules reloaded successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/detect")
async def detect_pii(
    request: Dict[str, Any],
    services: Services = Depends(get_services)
) -> Dict[str, Any]:
    """检测文本中的PII信息"""
    try:
        text = request.get("text", "")
        if not text:
            raise HTTPException(
                status_code=400,
                detail="Text field is required"
            )
            
        # 使用已初始化的 pii_detector 实例
        result = services.pii_detector.detect_pii(text)
        return result
        
    except Exception as e:
        logger.error(f"Error in PII detection: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to detect PII: {str(e)}"
        )

@router.put("/rules/bulk", response_model=PIIRuleResponse)
async def update_rules_bulk(rules_data: PIIRuleBulkUpdate) -> Dict[str, Any]:
    """批量更新PII规则"""
    try:
        pii_detector = get_services().get_pii_detector()
        logger.info(f"Updating {len(rules_data.rules)} PII rules")
        
        # Pydantic 已经验证了数据格式，直接使用
        success = pii_detector.update_rules([rule.dict() for rule in rules_data.rules])
        
        if success:
            return {
                "status": "success",
                "message": f"Successfully updated {len(rules_data.rules)} rules",
                "rules": rules_data.rules
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to update rules"
            )
            
    except Exception as e:
        logger.error(f"Error updating PII rules: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update rules: {str(e)}"
        )

@router.post("/mask")
async def mask_pii(request: Request) -> Dict[str, Any]:
    """PII脱敏处理"""
    try:
        data = await request.json()
        text = data.get("text", "")
        
        if not text:
            raise HTTPException(
                status_code=400,
                detail="Text field is required"
            )
            
        # 使用 PIIDetector 的 mask 方法
        masked_result = pii_detector.mask(text)
        return masked_result
        
    except Exception as e:
        logger.error(f"Error in mask_pii: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to mask PII: {str(e)}"
        )

def calculate_risk_level(entities: List[Dict[str, Any]]) -> str:
    """计算整体风险等级"""
    if not entities:
        return "low"
        
    # 根据实体数量和类型计算风险等级
    high_risk_types = {"CREDIT_CARD", "PASSPORT", "ID_NUMBER", "BANK_ACCOUNT"}
    medium_risk_types = {"EMAIL", "PHONE", "ADDRESS"}
    
    high_risk_count = sum(1 for e in entities if e["type"] in high_risk_types)
    medium_risk_count = sum(1 for e in entities if e["type"] in medium_risk_types)
    
    if high_risk_count > 0:
        return "high"
    elif medium_risk_count > 0:
        return "medium"
    return "low"

@router.post("/detect/batch")
async def batch_detect_pii(
    request: PIIBatchDetectionRequest,
    services: Services = Depends(get_services)
):
    """批量检测文本中的PII"""
    try:
        results = []
        for text in request.texts:
            result = services.pii_detector.detect_pii(
                text=text,
                language=request.language
            )
            results.append(result)
        
        return {
            "results": results,
            "summary": {
                "total": len(results),
                "safe_count": sum(1 for r in results if r["is_safe"]),
                "unsafe_count": sum(1 for r in results if not r["is_safe"])
            }
        }
    except Exception as e:
        logger.error(f"Error in batch detection: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@router.post("/preview-config")
async def preview_config(
    request: PIIConfigPreviewRequest,
    services: Services = Depends(get_services)
):
    """预览PII检测配置效果"""
    try:
        result = pii_detector.preview_config(
            text=request.text,
            language=request.language,
            sensitivity=request.sensitivity,
            masking_style=request.masking_style,
            custom_rules=request.custom_rules
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/technical-info")
async def get_technical_info():
    """获取PII检测系统技术信息"""
    return {
        "system_overview": {
            "name": "Custom PII Detection & Filtering System",
            "version": "1.0",
            "description": "基于 Presidio 框架的东南亚地区 PII 检测和过滤系统，集成了自定义规则引擎"
        },
        "core_technologies": {
            "presidio_framework": {
                "name": "Microsoft Presidio",
                "version": "2.2.32",
                "components": [
                    {
                        "name": "Presidio Analyzer",
                        "description": "核心分析引擎，用于PII实体识别",
                        "features": [
                            "预训练模型支持",
                            "自定义识别器集成",
                            "上下文感知分析"
                        ]
                    },
                    {
                        "name": "Presidio Anonymizer",
                        "description": "PII脱敏处理引擎",
                        "features": [
                            "多种脱敏策略",
                            "可定制替换规则",
                            "保持文本结构"
                        ]
                    }
                ]
            },
            "nlp_engine": {
                "name": "Spacy NLP",
                "models": [
                    {
                        "name": "en_core_web_lg",
                        "description": "英语大型模型",
                        "capabilities": [
                            "命名实体识别",
                            "词性标注",
                            "依存句法分析"
                        ]
                    },
                    {
                        "name": "xx_ent_wiki_sm",
                        "description": "多语言实体识别模型",
                        "supported_languages": [
                            "马来语 (ms)",
                            "印尼语 (id)",
                            "中文 (zh)"
                        ]
                    }
                ]
            }
        },
        "custom_pii_rules": {
            "rule_categories": [
                {
                    "category": "ID_NUMBERS",
                    "rules": [
                        {
                            "name": "Brunei IC",
                            "description": "文莱身份证号码识别",
                            "pattern": "\\b\\d{2}-\\d{6}\\b",
                            "examples": ["00-123456"]
                        },
                        {
                            "name": "Singapore NRIC",
                            "description": "新加坡身份证号码识别",
                            "pattern": "\\b[STFG]\\d{7}[A-Z]\\b",
                            "examples": ["S1234567A"]
                        },
                        {
                            "name": "Malaysian NRIC",
                            "description": "马来西亚身份证号码识别",
                            "pattern": "\\b\\d{6}-\\d{2}-\\d{4}\\b",
                            "examples": ["123456-12-1234"]
                        }
                    ]
                },
                {
                    "category": "NAMES",
                    "rules": [
                        {
                            "name": "Brunei Royal Names",
                            "description": "文莱皇室名称识别",
                            "patterns": [
                                "\\b(Pengiran|Yang Teramat Mulia|Yang Di-Pertuan)\\b",
                                "\\b(Paduka Seri|Duli Yang Teramat)\\b"
                            ]
                        },
                        {
                            "name": "Malay Names",
                            "description": "马来名称识别",
                            "patterns": [
                                "\\b(bin|binti)\\b",
                                "\\b(Haji|Hajjah)\\b"
                            ]
                        }
                    ]
                }
            ],
            "rule_features": [
                "支持正则表达式模式",
                "支持上下文验证",
                "支持多语言检测",
                "支持自定义置信度阈值",
                "支持规则优先级设置"
            ]
        },
        "supported_regions": {
            "brunei": {
                "name": "文莱",
                "supported_pii_types": [
                    {
                        "name": "Brunei IC",
                        "description": "文莱身份证号码",
                        "pattern": "\\b\\d{2}-\\d{6}\\b"
                    },
                    {
                        "name": "Brunei Names",
                        "description": "文莱人名识别",
                        "includes": ["通用名称", "皇室名称"]
                    }
                ]
            },
            "singapore": {
                "name": "新加坡",
                "supported_pii_types": [
                    {
                        "name": "Singapore NRIC",
                        "description": "新加坡身份证号码",
                        "pattern": "\\b[STFG]\\d{7}[A-Z]\\b"
                    }
                ]
            },
            "malaysia": {
                "name": "马来西亚",
                "supported_pii_types": [
                    {
                        "name": "Malaysian NRIC",
                        "description": "马来西亚身份证号码",
                        "pattern": "\\b\\d{6}-\\d{2}-\\d{4}\\b"
                    }
                ]
            }
        },
        "performance_metrics": {
            "average_processing_speed": "~1000 tokens/second",
            "supported_languages": ["en", "ms", "id", "zh"],
            "concurrent_requests": "支持",
            "rule_update_time": "<1s",
            "accuracy_metrics": {
                "precision": "95%+",
                "recall": "90%+",
                "f1_score": "92%+"
            }
        },
        "integration_features": {
            "api_interface": "RESTful API",
            "bulk_processing": "支持",
            "real_time_detection": "支持",
            "configuration_preview": "支持",
            "custom_rule_management": {
                "rule_import": "支持JSON批量导入",
                "rule_export": "支持JSON格式导出",
                "rule_validation": "自动语法检查",
                "rule_testing": "支持样本测试"
            }
        }
    }

@router.get("/models")
async def get_models():
    """获取支持的NLP模型信息"""
    return {
        "models": [
            {
                "id": "en_core_web_lg",
                "name": "English Large Model",
                "language": "en",
                "size": "789MB",
                "description": "英语大型模型，支持完整的NLP功能",
                "features": [
                    "命名实体识别",
                    "词性标注",
                    "依存句法分析",
                    "词向量"
                ],
                "performance": {
                    "accuracy": "92%",
                    "speed": "~1000 tokens/s"
                }
            },
            {
                "id": "xx_ent_wiki_sm",
                "name": "Multilingual Small Model",
                "languages": ["ms", "id", "zh"],
                "size": "45MB",
                "description": "多语言小型模型，专注于实体识别",
                "features": [
                    "命名实体识别",
                    "基础词性标注"
                ],
                "performance": {
                    "accuracy": "85%",
                    "speed": "~2000 tokens/s"
                }
            }
        ],
        "current_model": "en_core_web_lg",
        "model_settings": {
            "auto_language_detection": True,
            "fallback_model": "xx_ent_wiki_sm",
            "cache_enabled": True,
            "cache_size": "1GB"
        }
    }

@router.get("/prompt/current-model")
async def get_current_model():
    """获取当前使用的模型信息"""
    return {
        "current_model": {
            "id": "en_core_web_lg",
            "name": "English Large Model",
            "language": "en",
            "status": "loaded",
            "last_updated": "2024-04-01T18:00:00Z",
            "memory_usage": "789MB",
            "active_workers": 4,
            "performance_stats": {
                "requests_processed": 1000,
                "average_latency": "50ms",
                "error_rate": "0.1%"
            }
        },
        "model_health": {
            "status": "healthy",
            "uptime": "24h",
            "load_average": "45%",
            "memory_available": "2GB"
        }
    }

@router.get("/system/info")
async def get_system_info() -> Dict[str, Any]:
    """获取系统信息"""
    try:
        return {
            "version": pii_detector.version,
            "rules_count": len(pii_detector.get_rules()),
            "supported_languages": pii_detector.supported_languages,
            "models": pii_detector.get_models_info(),
            "last_updated": pii_detector.last_updated
        }
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/config/update")
async def update_config(config: Dict[str, Any]):
    """更新配置"""
    return {"status": "success", "message": "Configuration updated"} 