"""
Agent setup module for bid assistant.
Handles journey configuration, guidelines, glossary, and canned responses.
"""

import logging
from typing import Any
import parlant.sdk as p
from parlant.sdk import ToolContext, ToolResult


async def setup_journeys(agent: Any):
    """设置用户旅程"""
    try:
        # 暂时跳过旅程设置，专注于核心功能
        print("跳过用户旅程设置以避免框架兼容性问题")
        pass
    except Exception as e:
        print(f"创建用户旅程时出现错误: {e}")
        pass


async def setup_guidelines(agent: Any, web_search_tenders, analyze_project_with_gemini):
    """设置指导原则"""
    try:
        guidelines = [
            {
                "condition": "用户询问招标信息或搜索项目",
                "action": "优先从官方来源获取准确信息，保持回复简洁专业，突出关键信息如截止时间、预算范围、资质要求。只需要询问地区和项目类型，其他参数使用默认值",
                "tools": [web_search_tenders]
            },
            {
                "condition": "用户需要风险评估或项目分析",
                "action": "清晰突出截止时间和风险点，确保合规性，提供具体的改进建议",
                "tools": [analyze_project_with_gemini]
            },
            {
                "condition": "用户询问投标文件准备",
                "action": "确保生成的文档遵循招标合规规则，提供完整的检查清单",
                "tools": [analyze_project_with_gemini]
            },
            {
                "condition": "用户提供的信息不完整",
                "action": "只询问必填信息：地区和项目类型。对于可选参数，询问客户是否使用默认值，不要过度询问"
            }
        ]

        for guideline in guidelines:
            try:
                guideline_params = {
                    "condition": guideline["condition"],
                    "action": guideline["action"]
                }
                if "tools" in guideline:
                    guideline_params["tools"] = guideline["tools"]

                await agent.create_guideline(**guideline_params)
            except Exception as e:
                print(f"创建指导原则失败 ({guideline['condition']}): {e}")
                continue

    except Exception as e:
        print(f"设置指导原则时出现错误: {e}")
        pass


async def setup_glossary(agent: Any):
    """设置术语表"""
    try:
        glossary_terms = {
            "tender": "招标公告或投标机会",
            "bid document": "投标文件，包含公司信息和技术方案",
            "guarantee deposit": "投标保证金",
            "qualification": "资质要求",
            "submission deadline": "投标截止日期",
            "technical proposal": "技术方案",
            "commercial proposal": "商务方案",
            "compliance check": "合规性检查"
        }

        for term, definition in glossary_terms.items():
            if hasattr(agent, 'create_glossary_entry'):
                await agent.create_glossary_entry(
                    term=term,
                    definition=definition
                )
    except Exception as e:
        print(f"设置术语表时出现错误: {e}")


async def setup_canned_responses(agent: Any):
    """设置常用回复模板"""
    try:
        print("跳过常用回复设置以避免API权限问题")
        # 如果需要常用回复，可以在应用运行后手动配置
        pass
    except Exception as e:
        print(f"设置常用回复时出现错误: {e}")


async def setup_tools(agent: Any):
    """注册工具函数"""
    try:
        # 工具注册已移至指导原则中
        print("工具已通过指导原则注册")
        pass
    except Exception as e:
        print(f"注册工具时出现错误: {e}")
        pass