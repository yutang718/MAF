import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from config.settings import API_BASE_URL
from core.logging import get_logger
from utils.api import (
    get_pii_rules,
    update_pii_rule,
    update_pii_rules,
    detect_pii,
    update_pii_config
)
import os
import uuid
from typing import List, Dict, Any
import json
import httpx
import asyncio
import plotly.graph_objects as go

# 获取当前模块的logger
logger = get_logger("frontend.pages.pii_filtering")

# 更新 TEXTS 字典，确保所有文本都是英文
TEXTS = {
    "page_title": "PII Detection & Filtering",
    "tabs": ["Introduction", "Configuration", "Testing", "Examples"],
    "introduction": {
        "title": "PII Detection Introduction",
        "sections": {
            "technical_overview": "Technical Overview",
            "supported_types": "Supported PII Types",
            "how_it_works": "How It Works",
            "advantages": "Advantages & Limitations",
            "performance": "Performance Metrics",
            "best_practices": "Best Practices",
            "updates": "Recent Updates"
        },
        "pii_types": {
            "general": "General PII",
            "sea_specific": "Southeast Asia Specific",
            "extended": "Extended Recognition"
        }
    },
    "testing": {
        "title": "PII Detection Testing",
        "options": {
            "title": "Test Options",
            "sensitivity": "Detection Sensitivity",
            "confidence": "Confidence Threshold",
            "masking_style": "Masking Style"
        },
        "input_label": "Enter text to analyze",
        "run_test": "Run Test",
        "show_details": "Show Analysis Details",
        "results": {
            "safe": "No sensitive information detected",
            "unsafe": "Sensitive information detected",
            "masked_text": "Masked Text",
            "detected_entities": "Detected Entities"
        }
    },
    "configuration": {
        "title": "Rule Configuration",
        "add_rule": "Add New Rule",
        "delete_rule": "Delete Selected",
        "rule_columns": {
            "name": "Name",
            "type": "Type",
            "pattern": "Pattern/Content",
            "description": "Description",
            "enabled": "Enabled"
        },
        "messages": {
            "load_error": "Failed to load rules",
            "save_success": "Rules saved successfully",
            "save_error": "Failed to save rules"
        }
    },
    "examples": {
        "title": "Usage Examples",
        "region_select": "Select Region",
        "original_text": "Original Text",
        "masked_text": "Masked Text",
        "load_test": "Load to Test",
        "common_types": "Common PII Types",
        "regions": {
            "brunei": "Brunei"
        }
    }
}

def get_text(key_path):
    """获取英文文本"""
    keys = key_path.split('.')
    current = TEXTS
    for key in keys:
        current = current[key]
    return current

def render_pii_filtering_page():
    """渲染PII过滤页面"""
    initialize_session_state()
    
    st.title(get_text("page_title"))
    
    # 创建标签页
    tabs = st.tabs(["Introduction", "Configuration", "Testing", "Examples"])
    
    # 渲染各个标签页
    with tabs[0]:
        render_intro_tab()
    with tabs[1]:
        render_config_tab()
    with tabs[2]:
        render_test_tab()
    with tabs[3]:
        render_examples_tab()

def render_intro_tab():
    st.header("PII Detection and Filtering")
    
    st.markdown("""
    ### Microsoft Presidio and Spacy NLP Engine
    
    Our PII detection system leverages Microsoft Presidio with Spacy NLP engine to provide 
    robust and accurate personally identifiable information (PII) detection and anonymization.
    """)
    
    # Presidio Introduction
    st.subheader("Microsoft Presidio")
    st.markdown("""
    #### Key Features
    - 🌐 Multi-language support
    - 🔧 Customizable recognition patterns
    - 🚀 High performance and scalability
    - 🔄 Multiple anonymization methods
    
    #### Advantages
    - Built on modern NLP technologies
    - Extensible architecture
    - Production-ready performance
    - Strong community support
    - Regular updates and improvements
    
    #### Limitations
    - Resource intensive for large-scale processing
    - Requires fine-tuning for specific use cases
    - Limited support for some Asian languages
    """)
    
    # Spacy NLP Engine
    st.subheader("Spacy NLP Engine")
    
    # Create comparison table
    nlp_comparison = {
        "Features": [
            "Processing Speed",
            "Memory Usage",
            "Accuracy",
            "Multi-language Support",
            "Community Support",
            "Ease of Integration",
            "Custom Entity Support",
            "Pipeline Customization"
        ],
        "Spacy": [
            "Fast ⚡",
            "Efficient 🎯",
            "High ✨",
            "Excellent 🌍",
            "Strong 💪",
            "Easy ✅",
            "Yes ✓",
            "Flexible 🔧"
        ],
        "NLTK": [
            "Moderate",
            "High",
            "Good",
            "Limited",
            "Strong",
            "Moderate",
            "Limited",
            "Complex"
        ],
        "Stanford NLP": [
            "Slow",
            "High",
            "Very High",
            "Good",
            "Limited",
            "Complex",
            "Yes",
            "Limited"
        ]
    }
    
    df = pd.DataFrame(nlp_comparison)
    st.table(df)
    
    # Performance Comparison Chart
    st.subheader("Performance Comparison")
    
    metrics = ['Speed', 'Accuracy', 'Memory Efficiency', 'Ease of Use']
    spacy_scores = [90, 85, 80, 95]
    nltk_scores = [70, 75, 65, 70]
    stanford_scores = [60, 95, 55, 60]
    
    fig = go.Figure(data=[
        go.Scatterpolar(
            r=spacy_scores,
            theta=metrics,
            fill='toself',
            name='Spacy'
        ),
        go.Scatterpolar(
            r=nltk_scores,
            theta=metrics,
            fill='toself',
            name='NLTK'
        ),
        go.Scatterpolar(
            r=stanford_scores,
            theta=metrics,
            fill='toself',
            name='Stanford NLP'
        )
    ])
        
    fig.update_layout(
        title="PII Detection Results",
        xaxis_title="Category",
        yaxis_title="Count",
        showlegend=True
    )
        
    st.plotly_chart(fig)
    
def render_config_tab():
    """渲染配置标签页"""
    st.header("PII Rules Configuration")
    
    try:
        # 获取所有PII规则
        rules = asyncio.run(get_pii_rules())
        
        if rules:
            # 显示规则统计
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Rules", len(rules))
            with col2:
                enabled_rules = sum(1 for rule in rules if rule.get("enabled", True))
                st.metric("Enabled Rules", enabled_rules)
            with col3:
                categories = len(set(rule.get("category", "") for rule in rules))
                st.metric("Categories", categories)
            
            # 显示规则表格
            st.subheader("PII Detection Rules")
            
            # 修改 dataframe 调用，移除不支持的参数
            st.dataframe(
                data=rules,
                use_container_width=True
            )
            
            # 添加新规则表单
            with st.expander("Add New Rule"):
                col1, col2 = st.columns(2)
                
                with col1:
                    rule_id = st.text_input("Rule ID", key="rule_id")
                    rule_name = st.text_input("Rule Name", key="rule_name")
                    rule_type = st.text_input("Rule Type", key="rule_type")
                    pattern = st.text_input("Pattern", key="rule_pattern")
                    description = st.text_area("Description", key="rule_description")
                    
                with col2:
                    category = st.selectbox(
                        "Category",
                        options=["general", "financial", "medical", "contact", "id"],
                        key="rule_category"
                    )
                    country = st.selectbox(
                        "Country",
                        options=["BN"],
                        key="rule_country"
                    )
                    masking_method = st.selectbox(
                        "Masking Method",
                        options=["mask", "hash", "redact"],
                        key="rule_masking"
                    )
                    enabled = st.checkbox("Enabled", value=True, key="rule_enabled")
                
                if st.button("Add Rule"):
                    new_rule = {
                        "id": rule_id,
                        "name": rule_name,
                        "type": rule_type,
                        "pattern": pattern,
                        "description": description,
                        "category": category,
                        "country": country,
                        "enabled": enabled,
                        "masking_method": masking_method
                    }
                    
                    try:
                        response = asyncio.run(update_pii_rule(new_rule))
                        if response:
                            st.success("Rule added successfully")
                            st.experimental_rerun()
                        else:
                            st.error("Failed to add rule")
                    except Exception as e:
                        st.error(f"Error adding rule: {str(e)}")
            
            # 刷新按钮
            col1, col2 = st.columns([3, 1])
            
            with col2:
                if st.button("🔄 Refresh"):
                    st.experimental_rerun()
                    
        else:
            st.warning("No PII rules found. Add some rules to get started.")
            
    except Exception as e:
        logger.error(f"Error in render_config_tab: {str(e)}")
        st.error(f"Error loading PII rules: {str(e)}")

def render_test_tab():
    st.header("PII Detection Test")
    
    # Text input
    input_text = st.text_area(
        "Enter text for PII detection",
        height=150,
        placeholder="Enter the text you want to analyze..."
    )
    
    if st.button("Detect PII"):
        if not input_text:
            st.warning("Please enter text for detection")
            return
            
        try:
            result = asyncio.run(detect_pii(input_text))
            
            if result:
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Detection Results")
                    if not result.get("is_safe", True):
                        st.warning("⚠️ PII Detected")
                        
                        # 显示检测到的实体
                        st.markdown("### Detected Items")
                        for entity in result.get("entities", []):
                            st.markdown(f"""
                            - **Type**: {entity.get('type')}
                            - **Text**: {entity.get('text')}
                            - **Score**: {entity.get('score', 0):.2%}
                            - **Rule**: {entity.get('rule_name', 'Unknown')}
                            - **Position**: {entity.get('start')} - {entity.get('end')}
                            """)
                    else:
                        st.success("✅ No PII Detected")
                
                with col2:
                    st.subheader("Masked Text")
                    st.code(result.get("masked_text", input_text))
                    
                # 如果是详细模式，显示额外信息
                if result.get("analysis"):
                    st.subheader("Detailed Analysis")
                    st.json(result["analysis"])
                    
        except Exception as e:
            st.error(f"Detection error: {str(e)}")

def render_examples_tab():
    st.header("PII Detection Examples")
    
    # 创建国家/地区选择
    region = st.selectbox(
        "Select Region",
        ["Brunei"]
    )
    
    examples = {
        "Brunei": {
            "title": "Brunei PII Examples",
            "text": """
=== Brunei Personal Information ===
Name: Mohammad Bin Abdullah
IC: 00-123456 (yellow)
Date of Birth: 15/01/1980
Race: Malay
Religion: Islam
Place of Birth: RIPAS Hospital, Bandar Seri Begawan
Nationality: Bruneian
Passport: BN1234567
Expiry Date: 31/12/2025

=== Contact Information ===
Phone (Mobile): +673 711 2345
Phone (Home): +673 2 234567
Email: mohammad.abdullah@gmail.com
Address: No. 12, Simpang 13
Kampong Mata-Mata
Gadong BE1518, Brunei Darussalam

=== Employment & Financial ===
Occupation: Senior Officer
Employer: Ministry of Finance
Staff ID: MOF/2010/1234
Bank: BIBD
Account: 01-001-01-123456
Branch: Gadong Branch
TAP Number: T123456789
            """
        }
    }
    
    if region in examples:
        example = examples[region]
        st.subheader(example["title"])
        
        # 显示示例文本
        st.text_area(
            "Example Text",
            value=example["text"],
            height=400,
            disabled=True
        )
        
        # 添加测试按钮
        if st.button("Test This Example"):
            try:
                result = asyncio.run(detect_pii(example["text"]))
                
                if result:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader("Detection Results")
                        if not result.get("is_safe", True):
                            st.warning("⚠️ PII Detected")
                            
                            # 显示检测到的实体
                            if not result.get("is_safe", True):
                                st.markdown("#### Detected PII Entities")
                                entities_df = pd.DataFrame(result.get("entities", []))
                                if not entities_df.empty:
                                    # 按类型分组统计
                                    st.markdown("##### PII Types Summary")
                                    type_counts = entities_df['type'].value_counts()
                                    st.bar_chart(type_counts)
                                    
                                    # 显示详细实体表格
                                    st.markdown("##### Detailed Entities")
                                    columns_order = {
                                        'type': 'PII Type',
                                        'text': 'Original Text',
                                        'score': 'Confidence',
                                        'start': 'Start',
                                        'end': 'End'
                                    }
                                    entities_df = entities_df.rename(columns=columns_order)
                                    entities_df = entities_df[[col for col in columns_order.values() if col in entities_df.columns]]
                                    
                                    if 'Confidence' in entities_df.columns:
                                        entities_df['Confidence'] = entities_df['Confidence'].apply(lambda x: f"{x:.2%}")
                                    
                                    st.dataframe(entities_df)
                        else:
                            st.success("✅ No PII Detected")
                            
                    with col2:
                        st.subheader("Masked Text")
                        st.code(result.get("masked_text", example["text"]))
                        
            except Exception as e:
                st.error(f"Detection error: {str(e)}")

def get_profile_example(region):
    """获取完整个人资料示例"""
    profiles = {
        "brunei": {
            "original": """
            Personal Information:
            Name: Mohammad Bin Abdullah
            IC Number: 00-123456 (yellow)
            Date of Birth: January 15, 1980
            Passport: 12345678
            Phone: +673 711 2345
            Email: mohammad.abdullah@gmail.com
            Address: No. 12, Simpang 13, Kg. Mata-Mata, Gadong, BE1518, Brunei Darussalam
            Employment: Senior Officer at Ministry of Finance
            Bank Account: 1234567890 (BIBD)
            """,
            "masked": """
            Personal Information:
            Name: Mohammad Bin Abdullah
            IC Number: XX-XXXX56 (yellow)
            Date of Birth: January 15, 1980
            Passport: XXXXX678
            Phone: +673 XXX 2345
            Email: mXXXXXXX.abdullah@gXXXX.com
            Address: No. XX, Simpang XX, Kg. Mata-Mata, Gadong, XXXXX, Brunei Darussalam
            Employment: Senior Officer at Ministry of Finance
            Bank Account: XXXXXX7890 (BIBD)
            """
        },
        "malaysia": {
            "original": """
            Personal Information:
            Name: Lim Mei Ling
            IC Number: 800115-14-5678
            Date of Birth: January 15, 1980
            Passport: A1234567
            Phone: +60 12-345 6789
            Email: meiling.lim@hotmail.com
            Address: 42, Jalan Merdeka, Taman Selayang Baru, 68100 Batu Caves, Selangor
            Employment: Marketing Manager at Petronas
            Bank Account: 1234567890 (Maybank)
            Credit Card: 5105 1051 0510 5100
            """,
            "masked": """
            Personal Information:
            Name: Lim Mei Ling
            IC Number: XXXXXX-14-5678
            Date of Birth: January 15, 1980
            Passport: AXXXX567
            Phone: +60 12-XXX 6789
            Email: mXXXXXX.lim@hXXXXX.com
            Address: XX, Jalan Merdeka, Taman Selayang Baru, XXXXX Batu Caves, Selangor
            Employment: Marketing Manager at Petronas
            Bank Account: XXXXXX7890 (Maybank)
            Credit Card: XXXX XXXX XXXX 5100
            """
        },
        "singapore": {
            "original": """
            Personal Information:
            Name: Tan Wei Ming
            NRIC: S1234567D
            Date of Birth: January 15, 1980
            Passport: K1234567
            Phone: +65 8123 4567
            Email: weimingt@gmail.com
            Address: Block 123, Ang Mo Kio Avenue 6, #12-34, Singapore 560123
            Employment: Senior Software Engineer at DBS Bank
            Bank Account: 012-34567-8 (POSB)
            Credit Card: 4111 1111 1111 1111
            """,
            "masked": """
            Personal Information:
            Name: Tan Wei Ming
            NRIC: SXXXX567D
            Date of Birth: January 15, 1980
            Passport: KXXXX567
            Phone: +65 8XXX 4567
            Email: wXXXXXt@gXXXX.com
            Address: Block XXX, Ang Mo Kio Avenue 6, #XX-XX, Singapore XXXXXX
            Employment: Senior Software Engineer at DBS Bank
            Bank Account: XXX-XXXXX-8 (POSB)
            Credit Card: XXXX XXXX XXXX 1111
                    """
                }
            }
    
    return profiles.get(region, {"original": "", "masked": ""})

def display_test_results(result):
    """显示测试结果"""
    if result["is_safe"]:
        st.success(get_text("testing.results.safe"))
    else:
        st.warning(get_text("testing.results.unsafe"))
    
    st.markdown("### Masked Text")
    st.code(result["masked_text"])
    
    if result["entities"]:
        st.markdown("### Detected Entities")
        for entity in result["entities"]:
            st.markdown(f"- **{entity['type']}**: {entity['text']} (Confidence: {entity['confidence']:.2f})")

async def save_rule_changes(rules_data):
    """保存规则更改"""
    try:
        # 修改 URL 路径，添加 _v2 后缀以区分
        url = "http://localhost:8000/api/v1/pii/rules/bulk_v2"  
        async with httpx.AsyncClient() as client:
            response = await client.put(url, json=rules_data)
            response.raise_for_status()
            return True
    except Exception as e:
        logger.error(f"Failed to save rules: {str(e)}")
        return False

def handle_rule_changes(edited_df):
    """处理规则更改"""
    if st.session_state.previous_df is not None:
        changes = edited_df.compare(st.session_state.previous_df)
        if not changes.empty:
            response = call_pii_api("rules", method="PUT", data=edited_df.to_dict('records'))
            if response and response.status_code == 200:
                st.success(get_text("configuration.messages.save_success"))
            else:
                handle_api_error(response, get_text("configuration.messages.save_error"))

def handle_api_error(response, error_message="API Error"):
    """统一处理API错误"""
    if response.status_code == 404:
        st.error(f"API endpoint not found: {response.url}")
    elif response.status_code == 500:
        st.error("Internal server error. Please try again later.")
    else:
        st.error(f"{error_message}: {response.status_code}")
        if response.text:
            st.code(response.text)

def initialize_session_state():
    """初始化会话状态"""
    if "pii_history" not in st.session_state:
        st.session_state.pii_history = []
    if "example_test_text" not in st.session_state:
        st.session_state.example_test_text = ""
    if "previous_df" not in st.session_state:
        st.session_state.previous_df = None
    if "show_add_form" not in st.session_state:
        st.session_state.show_add_form = False
    if "show_delete_confirm" not in st.session_state:
        st.session_state.show_delete_confirm = False

def call_pii_api(endpoint, method="GET", data=None):
    """统一的API调用函数"""
    try:
        url = f"{API_BASE_URL}/pii/{endpoint}"
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url, json=data)
        elif method == "PUT":
            response = requests.put(url, json=data)
        elif method == "DELETE":
            response = requests.delete(url)
        
        return response
    except requests.exceptions.RequestException as e:
        st.error(f"API call failed: {str(e)}")
        return None

def render_system_info_tab():
    st.header("System Information")
    
    try:
        # 获取系统信息
        response = requests.get(f"{API_BASE_URL}/api/v1/pii/system/info")
        
        if response.status_code == 200:
            info = response.json()
            
            # 显示基本信息
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Version", info["version"])
            with col2:
                st.metric("Rules Count", info["rules_count"])
            with col3:
                st.metric("Languages", len(info["supported_languages"]))
            
            # 显示模型信息
            st.subheader("Models")
            for model in info["models"]:
                with st.expander(model["name"]):
                    st.write(f"Language: {model['language']}")
                    st.write(f"Size: {model['size']}")
                    st.write(f"Features: {', '.join(model['features'])}")
            
            # 显示最后更新时间
            st.info(f"Last Updated: {info['last_updated']}")
        else:
            st.error(f"Failed to fetch system info: {response.text}")
    except Exception as e:
        st.error(f"Error fetching system info: {str(e)}")

def prepare_rule_for_update(rule_data: Dict[str, Any]) -> Dict[str, Any]:
    """准备用于更新的规则数据"""
    return {
        "id": str(rule_data["id"]),
        "name": str(rule_data["name"]),
        "type": str(rule_data["type"]),
        "pattern": str(rule_data["pattern"]),
        "description": str(rule_data.get("description", "")),
        "category": str(rule_data.get("category", "general")),
        "country": str(rule_data.get("country", "BN")),
        "enabled": bool(rule_data.get("enabled", True)),
        "masking_method": str(rule_data.get("masking_method", "mask"))
    }

if __name__ == "__main__":
    render_pii_filtering_page() 