"""
Tool functions module for bid assistant.
Contains search and analysis tools for the Parlant agent.
"""

import logging
import parlant.sdk as p
from parlant.sdk import ToolContext, ToolResult


@p.tool
async def web_search_tenders(context: ToolContext, query: str, region: str = "全国", industry: str = "不限") -> ToolResult:
    """
    搜索招标信息

    Args:
        context: 工具上下文
        query: 搜索关键词（必填）
        region: 搜索地区（可选，默认"全国"）
        industry: 行业分类（可选，默认"不限"）

    Returns:
        搜索结果字符串
    """
    try:
        # 从共享模块获取web_search实例
        from shared import get_web_search_client
        web_search = get_web_search_client()

        if not web_search:
            return ToolResult("❌ 搜索服务暂时不可用。")

        # 构建搜索查询
        search_query = query
        if region and region != "全国":
            search_query += f" {region}"
        if industry and industry != "不限":
            search_query += f" {industry}"

        # 执行搜索
        results = await web_search.search(search_query)

        if not results:
            return ToolResult("❌ 未找到相关招标信息，请尝试调整搜索关键词。")

        # 格式化结果
        formatted_results = []
        for i, result in enumerate(results[:8]):  # 限制返回结果数量为8条
            formatted_result = f"""
📋 **结果 {i+1}**
🏷️ **标题**：{result['title']}
🌐 **来源**：{result['source']}
📅 **发布时间**：{result['publish_date'] or '未知'}
📝 **描述**：{result['description'][:200]}{'...' if len(result['description']) > 200 else ''}
🔗 **链接**：{result['url']}
                """
            formatted_results.append(formatted_result)

        # 最终结果
        final_result = f"""
🎯 **搜索完成！**
关键词：'{search_query}'
找到 {len(results)} 条相关招标信息，以下是最相关的 {len(formatted_results)} 条：

{'='*60}
{''.join(formatted_results)}
{'='*60}

💡 **提示**：如果需要更多结果或特定条件的筛选，请告诉我。
        """

        return ToolResult(final_result)

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"搜索招标信息时出错: {e}")
        return ToolResult(f"❌ 搜索过程中出现错误：{str(e)}")


@p.tool
async def analyze_project_with_gemini(context: ToolContext, project_info: str, analysis_type: str = "comprehensive") -> ToolResult:
    """
    分析项目风险和机会

    Args:
        context: 工具上下文
        project_info: 项目信息（必填）
        analysis_type: 分析类型（可选，默认comprehensive，可选值：comprehensive/technical/commercial/time/compliance）

    Returns:
        分析结果字符串
    """
    try:
        # 从共享模块获取gemini_service实例
        from shared import get_gemini_service
        gemini_service = get_gemini_service()

        # 使用Gemini服务进行分析
        if gemini_service:
            result = await gemini_service.generate_structured_output(
                prompt=f"请分析以下招标项目：\n\n{project_info}\n\n分析类型：{analysis_type}",
                schema={
                    "type": "object",
                    "properties": {
                        "risk_assessment": {"type": "string"},
                        "opportunities": {"type": "string"},
                        "recommendations": {"type": "string"}
                    }
                }
            )

            # 格式化分析结果
            analysis_result = f"""
🎯 **项目分析完成！**
📋 **分析类型**：{analysis_type}

{'='*60}
🚨 **风险评估**
{result.get('risk_assessment', 'N/A')}

💰 **机会分析**
{result.get('opportunities', 'N/A')}

💡 **建议**
{result.get('recommendations', 'N/A')}
{'='*60}

⚠️ **注意**：以上分析仅供参考，请结合实际情况进行决策。
            """

            return ToolResult(analysis_result)
        else:
            return ToolResult("❌ 分析服务暂时不可用，请直接提供项目分析建议。")

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"分析项目时出错: {e}")
        return ToolResult(f"❌ 分析过程中出现错误：{str(e)}")