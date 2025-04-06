"""伊斯兰内容相关API端点"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any, List, TYPE_CHECKING
from core.logging import get_logger
from core.dependencies import get_services,Services

router = APIRouter()
logger = get_logger(__name__)

@router.get("/rules")
async def get_islamic_rules(
    language: str = Query("en", description="Language code"),
    services: Services = Depends(get_services)
) -> Dict[str, Any]:
    """获取 Islamic 规则配置"""
    try:
        logger.info(f"Getting Islamic rules for language: {language}")
        rules = services.islamic_context_manager.get_rules(language)
        logger.debug(f"Retrieved rules: {rules}")
        
        if not rules:
            logger.warning("No rules found")
            return {}
            
        return rules
        
    except Exception as e:
        logger.error(f"Error getting Islamic rules: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get Islamic rules: {str(e)}"
        )

@router.get("/rules/all")
async def get_all_islamic_rules(
    services: Services = Depends(get_services)
) -> Dict[str, Dict[str, Any]]:
    """获取所有语言的 Islamic 规则配置"""
    try:
        return services.islamic_context_manager.get_all_rules()
    except Exception as e:
        logger.error(f"Error getting all Islamic rules: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get all Islamic rules: {str(e)}"
        )

@router.put("/rules/bulk")
def update_rules_bulk(rules_data: dict):
    """批量更新Islamic规则"""
    try:
        manager = get_services.get_islamic_manager()
        success = manager.update_rules(rules_data.get("rules", []))
        if success:
            return {
                "status": "success",
                "message": f"Successfully updated rules"
            }
        raise HTTPException(
            status_code=500,
            detail="Failed to update rules"
        )
    except Exception as e:
        logger.error(f"Error updating Islamic rules: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update rules: {str(e)}"
        )

@router.post("/detect")
async def detect_islamic_context(
    request: Dict[str, Any],
    services: Services = Depends(get_services)
) -> Dict[str, Any]:
    """检测文本中的 Islamic 上下文"""
    try:
        text = request.get("text", "")
        if not text:
            raise HTTPException(
                status_code=400,
                detail="Text field is required"
            )
            
        # 等待异步结果
        manager = get_services.get_islamic_manager()
        result = await manager.detect(text)
        return result
        
    except Exception as e:
        logger.error(f"Error in Islamic context detection: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to detect Islamic context: {str(e)}"
        )

@router.post("/chat")
async def chat_with_deepseek(
    request: Dict[str, Any],
    services: Services = Depends(get_services)
) -> Dict[str, Any]:
    """直接调用 DeepSeek API 获取回答"""
    try:
        text = request.get("text", "")
        use_islamic_context = request.get("use_islamic_context", False)
        
        if not text:
            raise HTTPException(
                status_code=400,
                detail="Text field is required"
            )
            
        result = await services.islamic_context_manager.chat(
            text=text,
            use_islamic_context=use_islamic_context
        )
        return result
        
    except Exception as e:
        logger.error(f"Error in DeepSeek chat: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get response: {str(e)}"
        ) 