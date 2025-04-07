"""API 调用工具"""
import aiohttp
import json
from typing import Dict, Any, Optional, List
import streamlit as st
from core.logging import get_logger
import httpx
from config.settings import get_api_url

logger = get_logger("utils.api")

# API 基础配置
BASE_URL = "http://localhost:8000/api/v1"  # 添加 /api/v1 前缀

async def handle_response(response: aiohttp.ClientResponse) -> Dict[str, Any]:
    """处理API响应"""
    try:
        if response.status == 200:
            return await response.json()
        else:
            error_text = await response.text()
            # 只在这里记录一次错误
            logger.error(f"API error: {response.status} - {error_text}")
            raise Exception(f"API returned {response.status}: {error_text}")
    except Exception as e:
        # 不要在这里重复记录错误
        raise

async def call_api(endpoint: str, method: str = "GET", data: Optional[Dict] = None) -> Dict[str, Any]:
    """调用后端API"""
    url = f"{BASE_URL}{endpoint}"
    logger.info(f"Making {method} request to {url}")
    
    try:
        async with aiohttp.ClientSession() as session:
            if method == "GET":
                async with session.get(url) as response:
                    return await handle_response(response)
            elif method == "POST":
                async with session.post(url, json=data) as response:
                    return await handle_response(response)
            elif method == "PUT":
                logger.debug("Sending PUT request")
                async with session.put(url, json=data) as response:
                    logger.debug(f"Response status: {response.status}")
                    response_text = await response.text()
                    logger.debug(f"Response body: {response_text}")
                    return await handle_response(response)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
    except Exception as e:
        # 这里只记录未被捕获的异常
        if not isinstance(e, Exception) or "API returned" not in str(e):
            logger.error(f"API call failed for {url}: {str(e)}")
        raise

# Prompt Detection APIs
async def get_available_models() -> Dict[str, Any]:
    """获取可用的模型列表"""
    return await call_api('/prompt/models')

async def get_current_model() -> Dict[str, Any]:
    """获取当前使用的模型"""
    return await call_api('/prompt/current-model')

async def set_current_model(model_id: str) -> Dict[str, Any]:
    """设置当前模型"""
    return await call_api('/prompt/set-model', 'POST', {
        'model_id': model_id
    })

async def detect_prompt(text: str, mode: str = "normal") -> Dict[str, Any]:
    """检测提示词注入"""
    return await call_api('/prompt/detect', 'POST', {
        'text': text,
        'mode': mode
    })

async def update_prompt_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """更新提示词检测配置"""
    return await call_api('/prompt/config/update', 'POST', config)

# PII Detection APIs
async def get_pii_rules() -> List[Dict[str, Any]]:
    """获取所有PII规则"""
    try:
        logger.info("Fetching PII rules")
        response = await call_api('/pii/rules')
        
        # 添加详细的日志
        logger.debug(f"Response type: {type(response)}")
        logger.debug(f"Response content: {json.dumps(response, indent=2)}")
        
        # 确保返回的是字典类型且包含 rules 字段
        if not isinstance(response, dict):
            logger.error(f"Expected dict response, got {type(response)}")
            return []
            
        rules = response.get("rules", [])
        if not isinstance(rules, list):
            logger.error(f"Expected list of rules, got {type(rules)}")
            return []
            
        logger.info(f"Successfully fetched {len(rules)} rules")
        return rules
        
    except Exception as e:
        logger.error(f"Error getting PII rules: {repr(e)}")
        return []  # 返回空列表而不是抛出异常

async def update_pii_rule(rule_id: str, rule_data: Dict[str, Any]) -> Dict[str, Any]:
    """更新PII规则"""
    try:
        return await call_api(f'/pii/rules/{rule_id}', method='PUT', data=rule_data)
    except Exception as e:
        logger.error(f"Error updating PII rule: {str(e)}")
        raise

async def detect_pii(text: str) -> Dict[str, Any]:
    """检测文本中的PII信息"""
    try:
        response = await call_api(
            method='POST',
            endpoint='/pii/detect',
            data={"text": text}
        )
        return response
    except Exception as e:
        logger.error(f"Error detecting PII: {str(e)}")
        raise

async def update_pii_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """更新PII检测配置"""
    return await call_api('/pii/config/update', 'POST', config)

async def update_pii_rules(rules: List[Dict[str, Any]]) -> Dict[str, Any]:
    """批量更新PII规则"""
    try:
        logger.info("Starting batch update of PII rules")
        
        # 验证并转换规则数据
        validated_rules = []
        for rule in rules:
            validated_rule = {
                "id": str(rule["id"]),
                "name": str(rule["name"]),
                "type": str(rule["type"]),
                "pattern": str(rule["pattern"]),
                "description": str(rule.get("description", "")),
                "category": str(rule.get("category", "general")),
                "country": str(rule.get("country", "international")),
                "language": str(rule.get("language", "en")),
                "enabled": bool(rule.get("enabled", True)),
                "masking_method": str(rule.get("masking_method", "mask"))
            }
            validated_rules.append(validated_rule)
        
        # 构建正确的请求格式 - 只需要包装在 rules 字段中
        request_data = {
            "rules": validated_rules
        }
        
        logger.debug(f"Sending request data: {json.dumps(request_data, indent=2)}")
        
        response = await call_api(
            "/pii/rules/bulk",
            method="PUT",
            data=request_data
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error updating PII rules: {str(e)}")
        raise

# Islamic Rules APIs
async def get_islamic_rules(language: str = "en") -> Dict[str, Any]:
    """获取 Islamic 规则配置"""
    try:
        logger.info(f"Calling Islamic rules API with language: {language}")
        response = await call_api(f'/islamic/rules?language={language}')
        logger.debug(f"Received API response: {response}")
        return response
    except Exception as e:
        logger.error(f"Error fetching Islamic rules: {str(e)}", exc_info=True)
        raise

async def get_all_islamic_rules() -> Dict[str, Dict[str, Any]]:
    """获取所有语言的 Islamic 规则配置"""
    try:
        return await call_api('/islamic/rules/all')
    except Exception as e:
        logger.error(f"Error fetching all Islamic rules: {str(e)}")
        raise

async def update_islamic_rules(rules: Dict[str, Any]) -> Dict[str, Any]:
    """更新 Islamic 规则"""
    try:
        return await call_api('/islamic/rules', 'POST', rules)
    except Exception as e:
        logger.error(f"Error updating Islamic rules: {str(e)}")
        raise

async def detect_islamic_compliance(text: str, mode: str = "normal") -> Dict[str, Any]:
    """检测文本的 Islamic 合规性"""
    try:
        return await call_api(
            '/islamic/detect',
            'POST',
            {"text": text, "mode": mode}
        )
    except Exception as e:
        logger.error(f"Error detecting Islamic compliance: {str(e)}")
        raise

# System APIs
async def get_system_health() -> Dict[str, Any]:
    """获取系统健康状态"""
    return await call_api('/system/health')

async def analyze_prompt(text: str) -> Dict[str, Any]:
    """分析提示词"""
    return await call_api('/prompt/analyze', 'POST', {'text': text})

async def update_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """更新检测配置"""
    return await call_api('/prompt/config/update', 'POST', config)

async def islamic_chat(text: str, use_islamic_context: bool = False) -> Dict[str, Any]:
    """调用 Islamic chat API"""
    try:
        return await call_api(
            '/islamic/chat',
            'POST',
            {
                "text": text,
                "use_islamic_context": use_islamic_context
            }
        )
    except Exception as e:
        logger.error(f"Error in Islamic chat: {str(e)}")
        raise 