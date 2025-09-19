import asyncio
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List
from flask import Flask, render_template, jsonify
import parlant.sdk as p
from parlant.sdk import ToolContext, ToolResult
from parlant.core.loggers import Logger
from data_store import SimpleDataStore
from gemini_nlp_service import GeminiService
from web_search import WebSearchClient

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not found, using existing environment variables")

# 移除未使用的Kimi导入，优化启动速度

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # 输出到控制台
    ]
)

# 环境变量配置
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# 初始化数据存储和外部服务 - 性能优化
data_store = SimpleDataStore()
web_search = WebSearchClient(timeout=15, max_retries=2)

# 初始化Gemini服务（需要logger参数，稍后在main函数中初始化）
gemini_service = None
print("Google Gemini AI服务将在main函数中初始化")

# 初始化Flask应用用于监控面板
flask_app = Flask(__name__, template_folder='templates')

# 存储搜索日志的全局变量
search_logs = []
source_status = {
    'ccgp': {'status': 'unknown', 'last_success': None},
    'chinabidding': {'status': 'unknown', 'last_success': None},
    'ggzy': {'status': 'unknown', 'last_success': None},
    'bidding': {'status': 'unknown', 'last_success': None}
}

@flask_app.route('/dashboard')
def dashboard():
    """监控面板页面"""
    return render_template('search_dashboard.html')

@flask_app.route('/api/search-stats')
def get_search_stats():
    """获取搜索统计数据API"""
    try:
        # 获取web_search的统计信息
        stats = getattr(web_search, 'stats', {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0
        })
        
        # 获取最近的日志
        recent_logs = search_logs[-50:] if search_logs else []
        
        return jsonify({
            'stats': stats,
            'sources': source_status,
            'logs': recent_logs
        })
    except Exception as e:
        logging.getLogger(__name__).error(f"获取搜索统计数据失败: {e}")
        return jsonify({
            'stats': {'total_requests': 0, 'successful_requests': 0, 'failed_requests': 0},
            'sources': source_status,
            'logs': []
        }), 500

# 自定义日志处理器，用于收集搜索日志
class SearchLogHandler(logging.Handler):
    def emit(self, record):
        try:
            # 首先输出到控制台
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            console_handler.emit(record)
            
            log_entry = {
                'timestamp': datetime.fromtimestamp(record.created).isoformat(),
                'level': record.levelname.lower(),
                'message': record.getMessage()
            }
            search_logs.append(log_entry)
            
            # 只保留最近1000条日志
            if len(search_logs) > 1000:
                search_logs.pop(0)
                
            # 更新源状态
            message = record.getMessage()
            if '[CCGP' in message:
                if '解析完成' in message:
                    source_status['ccgp'] = {'status': 'success', 'last_success': datetime.now().isoformat()}
                elif '搜索失败' in message or '搜索出错' in message:
                    source_status['ccgp']['status'] = 'error'
            elif '[中国招标网]' in message:
                if '解析完成' in message:
                    source_status['chinabidding'] = {'status': 'success', 'last_success': datetime.now().isoformat()}
                elif '搜索失败' in message or '搜索出错' in message:
                    source_status['chinabidding']['status'] = 'error'
            elif '[全国公共资源交易平台]' in message:
                if '解析完成' in message:
                    source_status['ggzy'] = {'status': 'success', 'last_success': datetime.now().isoformat()}
                elif '搜索失败' in message or '搜索出错' in message:
                    source_status['ggzy']['status'] = 'error'
            elif '[招标网]' in message:
                if '解析完成' in message:
                    source_status['bidding'] = {'status': 'success', 'last_success': datetime.now().isoformat()}
                elif '搜索失败' in message or '搜索出错' in message:
                    source_status['bidding']['status'] = 'error'
                    
        except Exception:
            pass  # 忽略日志处理错误

# 添加自定义日志处理器到web_search的logger
search_log_handler = SearchLogHandler()
web_search.logger.addHandler(search_log_handler)

# 确保web_search的logger不会重复输出到根logger
web_search.logger.propagate = False

async def main():
    """招标助手主程序"""
    async with p.Server(
        port=8800,
        nlp_service=lambda container: GeminiService(container[Logger])
    ) as server:
        # 获取logger并初始化gemini_service
        logger = logging.getLogger(__name__)
        global gemini_service
        gemini_service = GeminiService(logger)

        # 创建招标助手Agent (使用Gemini服务)
        agent = await server.create_agent(
            name="BidAssistant",
            description="专业的招投标助手，帮助用户发现机会、分析项目、准备投标文件。我会根据用户的需求提供准确的招标信息，进行风险评估，并协助准备投标材料。使用Google Gemini AI模型提供智能分析。"
        )

        # 定义用户旅程
        await setup_journeys(agent)

        # 设置指导原则
        await setup_guidelines(agent)

        # 注册工具
        await setup_tools(agent)

        # 设置术语表
        await setup_glossary(agent)

        # 设置常用回复
        await setup_canned_responses(agent)

        print("招标助手已启动，访问 http://localhost:8800 开始使用")
        print("招标助手已启动，使用Google Gemini AI服务")

        # Parlant Server会自动保持运行，不需要手动循环
        # 等待服务器启动完成
        await asyncio.sleep(2)

async def setup_journeys(agent):
    """设置用户旅程"""
    # 简化旅程设置，避免复杂的节点配置导致的错误
    try:
        # 暂时跳过旅程设置，专注于核心功能
        print("跳过用户旅程设置以避免框架兼容性问题")
        pass
    except Exception as e:
        print(f"创建用户旅程时出现错误: {e}")
        pass

async def setup_guidelines(agent):
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

# Web搜索工具函数
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
{"".join(formatted_results)}
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

async def setup_tools(agent):
    """注册工具函数"""
    try:
        # 工具注册已移至指导原则中
        print("工具已通过指导原则注册")
        pass
    except Exception as e:
        print(f"注册工具时出现错误: {e}")
        pass

async def setup_glossary(agent):
    """设置术语表"""
    # 如果Agent没有create_glossary_entry方法，跳过术语表设置
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

async def setup_canned_responses(agent):
    """设置常用回复模板"""
    # 暂时跳过常用回复设置，避免API权限问题
    try:
        print("跳过常用回复设置以避免API权限问题")
        # 如果需要常用回复，可以在应用运行后手动配置
        pass
    except Exception as e:
        print(f"设置常用回复时出现错误: {e}")

if __name__ == "__main__":
    asyncio.run(main())