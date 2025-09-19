import asyncio
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List
import parlant.sdk as p
from parlant.core.loggers import Logger
from data_store import SimpleDataStore
from gemini_nlp_service import GeminiService
from web_search import WebSearchClient
from dashboard import DashboardManager
from agent_setup import setup_journeys, setup_guidelines, setup_glossary, setup_canned_responses, setup_tools
from bid_tools import web_search_tenders, analyze_project_with_gemini

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not found, using existing environment variables")

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

# 设置全局共享实例
from shared import set_web_search_client, set_gemini_service
set_web_search_client(web_search)

# 初始化Gemini服务（需要logger参数，稍后在main函数中初始化）
gemini_service = None
print("Google Gemini AI服务将在main函数中初始化")

# 初始化监控面板管理器
dashboard_manager = DashboardManager()
flask_app = dashboard_manager.get_app()

# 设置搜索日志处理器
dashboard_manager.setup_logging_handler(web_search)

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

        # 设置全局共享的gemini_service
        set_gemini_service(gemini_service)

        # 创建招标助手Agent (使用Gemini服务)
        agent = await server.create_agent(
            name="BidAssistant",
            description="专业的招投标助手，帮助用户发现机会、分析项目、准备投标文件。我会根据用户的需求提供准确的招标信息，进行风险评估，并协助准备投标材料。使用Google Gemini AI模型提供智能分析。"
        )

        # 定义用户旅程
        await setup_journeys(agent)

        # 设置指导原则（传入工具函数）
        await setup_guidelines(agent, web_search_tenders, analyze_project_with_gemini)

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


if __name__ == "__main__":
    asyncio.run(main())