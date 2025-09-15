import asyncio
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List
from flask import Flask, render_template, jsonify
import parlant.sdk as p
from data_store import SimpleDataStore
from kimi_nlp_service import KimiService
from web_search import WebSearchClient

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # 输出到控制台
    ]
)

# 环境变量配置
KIMI_API_KEY = os.getenv('KIMI_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# 初始化数据存储和外部服务
data_store = SimpleDataStore()
logger = logging.getLogger(__name__)
kimi_service = KimiService(logger=logger)
web_search = WebSearchClient()

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
        logger.error(f"获取搜索统计数据失败: {e}")
        return jsonify({
            'stats': {'total_requests': 0, 'successful_requests': 0, 'failed_requests': 0},
            'sources': source_status,
            'logs': []
        }), 500

# 自定义日志处理器，用于收集搜索日志
class SearchLogHandler(logging.Handler):
    def emit(self, record):
        try:
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

async def main():
    """招标助手主程序"""
    async with p.Server(
        port=8800,
        nlp_service=lambda container: kimi_service
    ) as server:
        # 创建招标助手Agent (使用Kimi服务)
        agent = await server.create_agent(
            name="BidAssistant",
            description="专业的招投标助手，帮助用户发现机会、分析项目、准备投标文件。我会根据用户的需求提供准确的招标信息，进行风险评估，并协助准备投标材料。使用Kimi AI模型提供智能分析。"
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
        print("招标助手已启动，使用Kimi AI服务")
        
        # Parlant Server会自动保持运行，不需要手动循环
        # 等待服务器启动完成
        await asyncio.sleep(2)

async def setup_journeys(agent):
    """设置用户旅程"""
    # 根据Parlant框架的API，创建用户旅程
    try:
        # 使用正确的参数：需要title, description, conditions
        await agent.create_journey(
            "招投标流程",  # title
            "完整的招投标流程：机会发现 -> 信息分析 -> 投标准备 -> 提交支持",  # description
            "用户需要招投标相关帮助"  # conditions
        )
    except Exception as e:
        print(f"创建用户旅程时出现错误: {e}")
        # 如果create_journey方法不存在或参数不匹配，跳过这一步
        pass

async def setup_guidelines(agent):
    """设置指导原则"""
    guidelines = [
        {
            "condition": "用户询问招标信息或搜索项目",
            "action": "优先从官方来源获取准确信息，保持回复简洁专业，突出关键信息如截止时间、预算范围、资质要求"
        },
        {
            "condition": "用户需要风险评估或项目分析",
            "action": "清晰突出截止时间和风险点，确保合规性，提供具体的改进建议"
        },
        {
            "condition": "用户询问投标文件准备",
            "action": "确保生成的文档遵循招标合规规则，提供完整的检查清单"
        },
        {
            "condition": "用户提供的信息不完整",
            "action": "礼貌地询问必要的补充信息，如公司类型、目标地区、预算范围等"
        }
    ]
    
    for guideline in guidelines:
        await agent.create_guideline(
            condition=guideline["condition"],
            action=guideline["action"]
        )

# 在文件顶部定义工具函数
@p.tool
async def web_search_tenders(context: p.ToolContext, query: str, region: str = "", industry: str = "") -> p.ToolResult:
    """搜索招标信息
    
    Args:
        context: 工具上下文
        query: 搜索关键词
        region: 地区筛选
        industry: 行业类型
        
    Returns:
        搜索到的招标项目列表
    """
    try:
        # 构建搜索查询
        search_query = f"{query} 招标"
        if region:
            search_query += f" {region}"
        if industry:
            search_query += f" {industry}"
        
        # 调用网络搜索
        results = await web_search.search(search_query)
        
        # 缓存搜索结果
        data_store.cache_tenders(results)
        
        # 格式化为HTML表格
        if not results:
            return p.ToolResult("未找到相关招标信息")
        
        # 构建HTML表格
        table_html = """
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%; font-family: Arial, sans-serif;">
    <thead>
        <tr style="background-color: #f2f2f2; font-weight: bold;">
            <th style="width: 30%;">项目标题</th>
            <th style="width: 15%;">来源</th>
            <th style="width: 15%;">链接</th>
            <th style="width: 40%;">项目摘要</th>
        </tr>
    </thead>
    <tbody>
"""
        
        # 添加搜索结果行
        for i, result in enumerate(results[:5]):  # 限制返回前5个结果
            title = result.get('title', 'N/A')
            source = result.get('source', 'N/A')
            url = result.get('url', 'N/A')
            description = result.get('description', 'N/A')
            
            # 突出显示关键词
            keywords = [query, region, industry]
            for keyword in keywords:
                if keyword and keyword.strip():
                    title = title.replace(keyword, f"<mark style='background-color: yellow;'>{keyword}</mark>")
                    description = description.replace(keyword, f"<mark style='background-color: yellow;'>{keyword}</mark>")
            
            # 处理链接
            link_cell = f'<a href="{url}" target="_blank" style="color: #0066cc; text-decoration: underline;">查看详情</a>' if url != 'N/A' else 'N/A'
            
            # 添加表格行
            row_color = "#f9f9f9" if i % 2 == 0 else "#ffffff"
            table_html += f"""
        <tr style="background-color: {row_color};">
            <td style="padding: 8px; vertical-align: top; word-wrap: break-word;">{title}</td>
            <td style="padding: 8px; vertical-align: top;">{source}</td>
            <td style="padding: 8px; vertical-align: top; text-align: center;">{link_cell}</td>
            <td style="padding: 8px; vertical-align: top; word-wrap: break-word;">{description}</td>
        </tr>
"""
        
        table_html += """
    </tbody>
</table>

<p style="margin-top: 10px; font-size: 12px; color: #666;">共找到 {} 个相关招标项目，显示前5个结果</p>
""".format(len(results))
        
        return p.ToolResult(table_html)
        
    except Exception as e:
        return p.ToolResult(f"搜索过程中出现错误: {str(e)}")

@p.tool
async def analyze_project_with_kimi(context: p.ToolContext, project_info: str, analysis_type: str = "comprehensive") -> p.ToolResult:
    """使用Kimi API分析项目
    
    Args:
        context: 工具上下文
        project_info: 项目信息
        analysis_type: 分析类型 (risk/competition/qualification/comprehensive)
        
    Returns:
        分析结果
    """
    try:
        # 根据分析类型构建提示词
        prompts = {
            "risk": "请分析以下招标项目的风险因素，包括技术风险、商务风险、时间风险等：",
            "competition": "请分析以下招标项目的竞争态势，包括可能的竞争对手、市场情况等：",
            "qualification": "请分析以下招标项目的资质要求，评估参与门槛：",
            "comprehensive": "请对以下招标项目进行综合分析，包括风险评估、竞争分析、资质要求等："
        }
        
        prompt = prompts.get(analysis_type, prompts["comprehensive"])
        full_prompt = f"{prompt}\n\n{project_info}"
        
        # 调用Kimi API
        schematic_generator = kimi_service.get_schematic_generator()
        analysis_result = await schematic_generator.generate(
            prompt=full_prompt,
            schema={"type": "object", "properties": {"analysis": {"type": "string"}}}
        )
        # 提取分析结果
        if isinstance(analysis_result, dict) and 'analysis' in analysis_result:
            analysis_result = analysis_result['analysis']
        else:
            analysis_result = str(analysis_result)
        
        # 保存分析结果
        project_id = f"project_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        data_store.save_analysis(project_id, {
            "analysis_type": analysis_type,
            "result": analysis_result,
            "analyzed_at": datetime.now().isoformat()
        })
        
        return p.ToolResult(analysis_result)
        
    except Exception as e:
        return p.ToolResult(f"分析过程中出现错误: {str(e)}")

@p.tool
async def save_user_session(context: p.ToolContext, session_id: str, user_info: str) -> p.ToolResult:
    """保存用户会话信息
    
    Args:
        context: 工具上下文
        session_id: 会话ID
        user_info: 用户信息
        
    Returns:
        保存状态
    """
    try:
        # 解析用户信息JSON字符串
        import json
        user_data = json.loads(user_info) if isinstance(user_info, str) else user_info
        
        session_data = {
            "user_info": user_data,
            "current_journey_step": "opportunity_discovery",
            "context": {
                "search_history": [],
                "current_projects": [],
                "analysis_results": {}
            },
            "created_at": datetime.now().isoformat()
        }
        
        data_store.save_session(session_id, session_data)
        return p.ToolResult("用户信息已保存")
        
    except Exception as e:
        return p.ToolResult(f"保存用户信息时出现错误: {str(e)}")

@p.tool
async def get_user_session(context: p.ToolContext, session_id: str) -> p.ToolResult:
    """获取用户会话信息
    
    Args:
        context: 工具上下文
        session_id: 会话ID
        
    Returns:
        用户会话信息
    """
    try:
        session_data = data_store.load_session(session_id)
        if session_data:
            return p.ToolResult(json.dumps(session_data, ensure_ascii=False, indent=2))
        else:
            return p.ToolResult("未找到用户会话信息")
            
    except Exception as e:
        return p.ToolResult(f"获取用户信息时出现错误: {str(e)}")

async def setup_tools(agent):
    """注册工具函数"""
    # 通过guidelines关联工具
    await agent.create_guideline(
        condition="用户询问招标信息或搜索项目",
        action="使用网络搜索工具查找相关招标信息，并提供准确的搜索结果",
        tools=[web_search_tenders]
    )
    
    await agent.create_guideline(
        condition="用户需要项目分析或风险评估",
        action="使用Kimi AI分析工具对项目进行深入分析",
        tools=[analyze_project_with_kimi]
    )
    
    await agent.create_guideline(
        condition="需要保存用户会话信息",
        action="保存用户的会话数据以便后续使用",
        tools=[save_user_session]
    )
    
    await agent.create_guideline(
        condition="需要获取用户会话信息",
        action="获取用户的历史会话数据",
        tools=[get_user_session]
    )

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