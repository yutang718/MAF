import streamlit as st
import asyncio
from typing import Dict, Any
from utils.api import (
    get_islamic_rules,
    update_islamic_rules,
    detect_islamic_compliance,
    islamic_chat
)
from core.logging import get_logger
import uuid
import pandas as pd

logger = get_logger("frontend.pages.islamic_rules")

def render_intro_tab():
    """Render introduction tab"""
    st.header("Islamic Content Compliance System")
    
    st.markdown("""
    ### Overview
    This system helps ensure that LLM responses comply with Islamic principles, Brunei regulations, 
    and data security requirements through customized prompts and rules.
    
    ### Core Capabilities
    1. **Islamic Compliance**
       - Ensures responses align with Islamic values and principles
       - Filters inappropriate or prohibited content
       - Maintains cultural sensitivity
       - **Halal Certification Check**
         - Validates Halal certification status
         - Verifies product and service compliance
         - Monitors Halal supply chain integrity
    
    2. **Data Security**
       - PII (Personal Identifiable Information) protection
       - Data privacy compliance
       - Secure information handling
    
    3. **Legal & Ethical Compliance**
       - Adherence to Brunei's legal requirements
       - Ethical content generation
       - Moral and cultural considerations
    
    ### Benefits
    - Culturally appropriate responses
    - Enhanced data protection
    - Legal compliance
    - Ethical content generation
    - **Halal compliance verification**
    """)

def render_config_tab():
    """渲染规则配置标签页"""
    try:
        st.subheader("Islamic Rules Configuration")
        
        # 获取规则配置
        logger.info("Fetching Islamic rules from API...")
        rules_data = asyncio.run(get_islamic_rules())
        logger.debug(f"Received rules data: {rules_data}")
        
        if not rules_data:
            logger.warning("No rules data received from API")
            st.warning("No rules configuration found")
            return
            
        # 显示版本信息
        version = rules_data.get('version')
        last_updated = rules_data.get('last_updated')
        logger.info(f"Version: {version}, Last Updated: {last_updated}")
        
        st.text(f"Version: {version or 'N/A'}")
        st.text(f"Last Updated: {last_updated or 'N/A'}")
        
        # 显示分类
        categories = rules_data.get("categories", [])
        logger.info(f"Found {len(categories)} categories: {categories}")
        
        st.subheader("Categories")
        if categories:
            st.write(", ".join(categories))
        else:
            st.info("No categories defined")
        
        # 显示规则表格
        st.subheader("Rules")
        rules = rules_data.get("rules", [])
        logger.info(f"Found {len(rules)} rules")
        
        if rules:
            logger.debug(f"Rules data: {rules}")
            rules_df = pd.DataFrame(rules)
            logger.info(f"Created DataFrame with columns: {rules_df.columns.tolist()}")
            st.dataframe(
                rules_df,
                use_container_width=True
            )
        else:
            st.info("No rules defined")
            
        # 显示指南
        st.subheader("Guidelines")
        guidelines = rules_data.get("guidelines", [])
        logger.info(f"Found {len(guidelines)} guidelines")
        
        if guidelines:
            for guideline in guidelines:
                st.markdown(f"- {guideline}")
        else:
            st.info("No guidelines defined")
            
        # 显示禁止主题
        st.subheader("Forbidden Topics")
        forbidden = rules_data.get("forbidden_topics", [])
        logger.info(f"Found {len(forbidden)} forbidden topics")
        
        if forbidden:
            for topic in forbidden:
                st.markdown(f"- {topic}")
        else:
            st.info("No forbidden topics defined")
            
    except Exception as e:
        logger.error(f"Error loading rules configuration: {str(e)}", exc_info=True)
        st.error(f"Error loading rules configuration: {str(e)}")

def render_compliance_tab():
    """渲染合规性测试标签页"""
    try:
        st.subheader("Islamic Compliance Testing")
        
        # 用户输入区域
        test_text = st.text_area(
            "Enter text to test for compliance",
            height=100,
            placeholder="Enter your text here to check Islamic compliance..."
        )
        
        if st.button("Check Compliance"):
            if not test_text:
                st.warning("Please enter some text to test")
                return
                
            with st.spinner("Analyzing text..."):
                try:
                    # 获取两种响应
                    col1, col2 = st.columns(2)
                    
                    # 调用 chat API 获取两种响应
                    standard_response = asyncio.run(islamic_chat(
                        text=test_text,
                        use_islamic_context=False
                    ))
                    
                    islamic_response = asyncio.run(islamic_chat(
                        text=test_text,
                        use_islamic_context=True
                    ))
                    
                    # 显示标准响应
                    with col1:
                        st.markdown("### Standard Response")
                        st.markdown("*Without Islamic context:*")
                        st.markdown(standard_response.get("response", ""))
                    
                    # 显示 Islamic 响应
                    with col2:
                        st.markdown("### Islamic-Guided Response")
                        st.markdown("*With Islamic context:*")
                        st.markdown(islamic_response.get("response", ""))
                    
                    # 显示分析结果
                    with st.expander("View Compliance Analysis"):
                        st.markdown("### Response Analysis")
                        
                        # 显示系统提示（如果使用了）
                        if islamic_response.get("system_prompt_used"):
                            st.markdown("#### Applied Islamic Guidelines")
                            st.markdown(islamic_response["system_prompt_used"])
                        
                        # 显示差异分析
                        st.markdown("#### Key Differences")
                        st.markdown("""
                        - **Perspective**: Compare how each response approaches the topic
                        - **Terminology**: Note the use of Islamic terms and concepts
                        - **Values**: Observe alignment with Islamic principles
                        - **Guidance**: Compare the nature of advice given
                        """)
                        
                except Exception as e:
                    st.error(f"Error analyzing text: {str(e)}")
                    logger.error(f"Error in compliance testing: {str(e)}", exc_info=True)
        
            
    except Exception as e:
        st.error(f"Error in compliance testing tab: {str(e)}")
        logger.error(f"Error in render_compliance_tab: {str(e)}", exc_info=True)

def render_examples_tab():
    """渲染案例标签页"""
    try:
        st.subheader("Islamic Context Examples")
        
        # 预设示例分类
        examples = {
            "Religious Questions": [
                {
                    "question": "What happens after death?",
                    "description": "Understanding afterlife concepts"
                },
                {
                    "question": "How should we interpret religious texts?",
                    "description": "Approach to religious interpretation"
                },
                {
                    "question": "What is the purpose of fasting?",
                    "description": "Understanding religious practices"
                }
            ],
            "Ethical Dilemmas": [
                {
                    "question": "Is it okay to lie to protect someone's feelings?",
                    "description": "Moral perspective on truthfulness"
                },
                {
                    "question": "How should we handle interest in financial transactions?",
                    "description": "Islamic finance principles"
                },
                {
                    "question": "What should we do when we find lost money?",
                    "description": "Ethical handling of found property"
                }
            ],
            "Social Relations": [
                {
                    "question": "How should we treat our parents in their old age?",
                    "description": "Family values and obligations"
                },
                {
                    "question": "What are the guidelines for business partnerships?",
                    "description": "Business ethics and relationships"
                },
                {
                    "question": "How should we respond to someone who wrongs us?",
                    "description": "Conflict resolution and forgiveness"
                }
            ],
            "Modern Challenges": [
                {
                    "question": "What is the proper use of social media?",
                    "description": "Digital ethics and behavior"
                },
                {
                    "question": "How should we approach environmental conservation?",
                    "description": "Environmental stewardship"
                },
                {
                    "question": "What are the guidelines for entertainment choices?",
                    "description": "Modern lifestyle choices"
                }
            ]
        }

        # 选择示例类别
        category = st.selectbox(
            "Select a category:",
            list(examples.keys())
        )

        # 选择具体示例
        selected_example = st.selectbox(
            "Select an example:",
            [ex["question"] for ex in examples[category]],
            format_func=lambda x: f"{x} - {next((ex['description'] for ex in examples[category] if ex['question'] == x), '')}"
        )

        if st.button("Compare Responses"):
            with st.spinner("Generating responses..."):
                # 获取两种模式的响应
                normal_response = asyncio.run(islamic_chat(
                    text=selected_example,
                    use_islamic_context=False
                ))
                islamic_response = asyncio.run(islamic_chat(
                    text=selected_example,
                    use_islamic_context=True
                ))
                
                # 显示响应比较
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("### Standard Response")
                    st.markdown("*Without Islamic context:*")
                    st.markdown(normal_response.get("response", ""))
                
                with col2:
                    st.markdown("### Islamic-Guided Response")
                    st.markdown("*With Islamic context:*")
                    st.markdown(islamic_response.get("response", ""))
                
                # 显示分析
                with st.expander("View Response Analysis"):
                    st.markdown("### Key Differences Analysis")
                    st.markdown("#### Perspective")
                    st.markdown("- Standard response provides a general viewpoint")
                    st.markdown("- Islamic response incorporates religious principles and values")
                    
                    st.markdown("#### References")
                    st.markdown("- Standard response may use secular or diverse sources")
                    st.markdown("- Islamic response includes religious teachings and guidelines")
                    
                    st.markdown("#### Guidance")
                    st.markdown("- Standard response focuses on practical or common approaches")
                    st.markdown("- Islamic response aligns with Islamic ethical framework")
                    
                    # 显示使用的系统提示
                    if islamic_response.get("system_prompt_used"):
                        st.markdown("### System Prompt Used")
                        st.markdown(islamic_response["system_prompt_used"])
                    
    except Exception as e:
        st.error(f"Error in examples tab: {str(e)}")
        logger.error(f"Error in render_examples_tab: {str(e)}", exc_info=True)

def render_islamic_rules_page():
    """Render Islamic rules main page"""
    st.title("Islamic Content Compliance System")

    # Create tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "Introduction",
        "Rules Configuration",
        "Compliance Testing",
        "Examples"
    ])
    
    with tab1:
        render_intro_tab()
    with tab2:
        render_config_tab()
    with tab3:
        render_compliance_tab()
    with tab4:
        render_examples_tab()

if __name__ == "__main__":
    render_islamic_rules_page() 