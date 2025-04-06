"""国际化配置"""

TRANSLATIONS = {
    "pii_detection": {
        # 标题和通用文本
        "page_title": {
            "en": "PII Detection & Filtering",
            "zh": "PII检测与过滤"
        },
        
        # 标签页名称
        "tabs": {
            "introduction": {"en": "Introduction", "zh": "介绍"},
            "configuration": {"en": "Configuration", "zh": "配置"},
            "testing": {"en": "Testing", "zh": "测试"},
            "examples": {"en": "Examples", "zh": "示例"},
            "history": {"en": "History", "zh": "历史记录"}
        },
        
        # 介绍标签页
        "introduction": {
            "title": {
                "en": "PII Detection Technology",
                "zh": "PII检测技术"
            },
            "description": {
                "en": """Our PII detection system is built on **Microsoft Presidio**, an advanced open-source framework
                specifically designed for identifying and protecting personally identifiable information.
                The system has been customized to handle formats specific to Brunei, Malaysia, and Singapore.""",
                "zh": """我们的PII检测系统基于**Microsoft Presidio**构建，这是一个专为识别和保护个人身份信息而设计的先进开源框架。
                该系统已经过自定义，可以处理文莱、马来西亚和新加坡特有的格式。"""
            },
            "tech_architecture": {
                "title": {"en": "Technical Architecture", "zh": "技术架构"},
                "presidio": {
                    "title": {"en": "Microsoft Presidio", "zh": "Microsoft Presidio"},
                    "features": {
                        "en": [
                            "Enterprise-grade PII detection engine",
                            "Highly extensible recognition system",
                            "Built-in anonymization capabilities",
                            "Real-time text analysis"
                        ],
                        "zh": [
                            "企业级PII检测引擎",
                            "高度可扩展的识别系统",
                            "内置匿名化功能",
                            "实时文本分析"
                        ]
                    }
                },
                "nlp": {
                    "title": {"en": "NLP Framework", "zh": "NLP框架"},
                    "features": {
                        "en": [
                            "Industrial-strength NLP processing",
                            "Efficient text analysis algorithms",
                            "Entity recognition capabilities",
                            "Optimized for performance"
                        ],
                        "zh": [
                            "工业级NLP处理",
                            "高效的文本分析算法",
                            "实体识别能力",
                            "性能优化"
                        ]
                    }
                }
            }
        },
        
        # 配置标签页
        "configuration": {
            "title": {"en": "PII Rules Management", "zh": "PII规则管理"},
            "language_select": {"en": "Rules Language", "zh": "规则语言"},
            "category_select": {"en": "Rule Category", "zh": "规则类别"},
            "categories": {
                "all": {"en": "All Rules", "zh": "所有规则"},
                "brunei": {"en": "Brunei", "zh": "文莱"},
                "malaysia": {"en": "Malaysia", "zh": "马来西亚"},
                "singapore": {"en": "Singapore", "zh": "新加坡"},
                "general": {"en": "General", "zh": "通用"}
            },
            "rule_actions": {
                "title": {"en": "Rule Actions", "zh": "规则操作"},
                "add": {"en": "Add New Rule", "zh": "添加规则"},
                "edit": {"en": "Edit Rule", "zh": "编辑规则"},
                "delete": {"en": "Delete Rule", "zh": "删除规则"}
            },
            "rules_loaded": {
                "en": "Successfully loaded {} rules",
                "zh": "已加载 {} 条规则"
            },
            "rules_load_failed": {
                "en": "Failed to load rules: {} - {}",
                "zh": "获取规则失败: {} - {}"
            },
            "api_error": {
                "en": "API Error: {}",
                "zh": "API错误: {}"
            },
            "no_rules_found": {
                "en": "No rules found for selected category",
                "zh": "未找到所选类别的规则"
            },
            "api_endpoint_not_found": {
                "en": "API endpoint not found: {}",
                "zh": "API端点不存在: {}"
            }
        },
        
        # 测试标签页
        "testing": {
            "title": {"en": "Test PII Detection", "zh": "测试PII检测"},
            "options": {
                "title": {"en": "Test Options", "zh": "测试选项"},
                "language": {"en": "Detection Language", "zh": "检测语言"},
                "sensitivity": {"en": "Sensitivity", "zh": "敏感度"},
                "masking_style": {"en": "Masking Style", "zh": "掩码样式"},
                "confidence": {"en": "Confidence Threshold", "zh": "置信度阈值"}
            },
            "input": {
                "label": {"en": "Enter text to test", "zh": "输入要测试的文本"},
                "placeholder": {
                    "en": "Enter text containing potential PII...",
                    "zh": "输入可能包含PII的文本..."
                }
            },
            "results": {
                "title": {"en": "Detection Results", "zh": "检测结果"},
                "entities_found": {"en": "Entities Found", "zh": "发现的实体"},
                "safety_status": {"en": "Safety Status", "zh": "安全状态"},
                "processing_time": {"en": "Processing Time", "zh": "处理时间"}
            }
        },
        
        # 示例标签页
        "examples": {
            "title": {"en": "PII Detection Examples", "zh": "PII检测示例"},
            "region_select": {"en": "Select Region", "zh": "选择地区"},
            "original_text": {"en": "Original Text", "zh": "原始文本"},
            "masked_text": {"en": "Masked Text", "zh": "掩码后的文本"},
            "load_test": {"en": "Load to Test", "zh": "加载到测试"},
            "common_types": {"en": "Common PII Types", "zh": "常见PII类型"},
            "original_text_label": {
                "en": "Original text content",
                "zh": "原始文本内容"
            },
            "masked_text_label": {
                "en": "Masked text content",
                "zh": "掩码后的文本内容"
            }
        },
        
        # 历史记录标签页
        "history": {
            "title": {"en": "Detection History", "zh": "检测历史"},
            "no_history": {"en": "No detection history", "zh": "暂无检测历史"},
            "clear_history": {"en": "Clear History", "zh": "清除历史"},
            "columns": {
                "timestamp": {"en": "Time", "zh": "时间"},
                "text": {"en": "Text", "zh": "文本"},
                "entities": {"en": "Entities Count", "zh": "实体数量"},
                "status": {"en": "Status", "zh": "状态"}
            }
        }
    }
}

def get_text(key_path: str, lang: str = "en") -> str:
    """获取指定语言的文本"""
    try:
        keys = key_path.split(".")
        current = TRANSLATIONS
        for key in keys:
            current = current[key]
        return current.get(lang, current.get("en", key_path))
    except (KeyError, AttributeError):
        return key_path 