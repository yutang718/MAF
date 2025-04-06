"""辅助函数模块"""
import json
import os
from typing import Dict, Any, Optional, List, Union
import time
from pathlib import Path
from core.logging import get_logger

# 修正：添加logger名称
logger = get_logger("utils.helpers")

def load_json_file(file_path: str, default_value: Optional[Any] = None) -> Any:
    """
    加载JSON文件
    
    参数:
    - file_path: 文件路径
    - default_value: 如果文件不存在或加载失败时的默认值
    
    返回:
    - 加载的JSON数据或默认值
    """
    try:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found: {file_path}")
            return default_value
            
        with path.open('r', encoding='utf-8') as f:
            data = json.load(f)
            logger.debug(f"Successfully loaded JSON from {file_path}")
            return data
            
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in {file_path}: {str(e)}")
        return default_value
    except Exception as e:
        logger.error(f"Error loading {file_path}: {str(e)}")
        return default_value

def save_json_file(file_path: str, data: Any, ensure_dir: bool = True) -> bool:
    """
    保存数据到JSON文件
    
    参数:
    - file_path: 目标文件路径
    - data: 要保存的数据
    - ensure_dir: 是否确保目录存在
    
    返回:
    - 保存是否成功
    """
    try:
        path = Path(file_path)
        
        # 确保目录存在
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with path.open('w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            logger.debug(f"Successfully saved JSON to {file_path}")
            return True
            
    except Exception as e:
        logger.error(f"Error saving to {file_path}: {str(e)}")
        return False 