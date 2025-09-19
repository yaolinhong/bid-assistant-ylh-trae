"""
全局共享模块
提供跨模块共享的实例和服务
"""

from web_search import WebSearchClient
import logging

# 全局web_search实例
_web_search_instance = None

# 全局gemini_service实例
_gemini_service_instance = None

def get_web_search_client() -> WebSearchClient:
    """获取全局web_search客户端实例"""
    global _web_search_instance
    if _web_search_instance is None:
        _web_search_instance = WebSearchClient(timeout=15, max_retries=2)
    return _web_search_instance

def set_web_search_client(client: WebSearchClient):
    """设置全局web_search客户端实例"""
    global _web_search_instance
    _web_search_instance = client

def get_gemini_service():
    """获取全局gemini_service实例"""
    global _gemini_service_instance
    return _gemini_service_instance

def set_gemini_service(service):
    """设置全局gemini_service实例"""
    global _gemini_service_instance
    _gemini_service_instance = service