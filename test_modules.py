#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模块测试脚本
用于验证各个模块的基本功能
"""

import asyncio
import os
import sys
from datetime import datetime

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """测试模块导入"""
    print("=== 测试模块导入 ===")
    
    try:
        import data_store
        print("✓ data_store 模块导入成功")
    except Exception as e:
        print(f"✗ data_store 模块导入失败: {e}")
        return False
    
    try:
        import kimi_client
        print("✓ kimi_client 模块导入成功")
    except Exception as e:
        print(f"✗ kimi_client 模块导入失败: {e}")
        return False
    
    try:
        import web_search
        print("✓ web_search 模块导入成功")
    except Exception as e:
        print(f"✗ web_search 模块导入失败: {e}")
        return False
    
    try:
        import kimi_nlp_service
        print("✓ kimi_nlp_service 模块导入成功")
    except Exception as e:
        print(f"✗ kimi_nlp_service 模块导入失败: {e}")
        return False
    
    return True

def test_data_store():
    """测试数据存储模块"""
    print("\n=== 测试数据存储模块 ===")
    
    try:
        from data_store import SimpleDataStore
        
        # 创建数据存储实例
        store = SimpleDataStore("./test_data")
        
        # 测试会话保存和加载
        test_session = {
            "session_id": "test_001",
            "user_id": "user_123",
            "messages": [
                {"role": "user", "content": "测试消息"},
                {"role": "assistant", "content": "测试回复"}
            ],
            "timestamp": datetime.now().isoformat()
        }
        
        store.save_session("test_001", test_session)
        loaded_session = store.load_session("test_001")
        
        if loaded_session and loaded_session["session_id"] == "test_001":
            print("✓ 会话保存和加载功能正常")
        else:
            print("✗ 会话保存和加载功能异常")
            return False
        
        # 测试项目缓存
        test_project = {
            "title": "测试招标项目",
            "url": "http://example.com/test",
            "source": "测试来源",
            "publish_date": "2024-01-01"
        }
        
        store.cache_project("test_project_001", test_project)
        cached_projects = store.get_cached_projects()
        
        if "test_project_001" in cached_projects:
            print("✓ 项目缓存功能正常")
        else:
            print("✗ 项目缓存功能异常")
            return False
        
        print("✓ 数据存储模块测试通过")
        return True
        
    except Exception as e:
        print(f"✗ 数据存储模块测试失败: {e}")
        return False

def test_kimi_client_init():
    """测试Kimi客户端初始化"""
    print("\n=== 测试Kimi客户端初始化 ===")
    
    try:
        from kimi_client import KimiClient
        
        # 使用测试API密钥初始化（不会实际调用API）
        client = KimiClient("test_api_key", "kimi-k2-0905-preview")
        
        if client.api_key == "test_api_key" and client.model == "kimi-k2-0905-preview":
            print("✓ Kimi客户端初始化成功")
            return True
        else:
            print("✗ Kimi客户端初始化参数异常")
            return False
            
    except Exception as e:
        print(f"✗ Kimi客户端初始化失败: {e}")
        return False

def test_web_search_init():
    """测试网络搜索客户端初始化"""
    print("\n=== 测试网络搜索客户端初始化 ===")
    
    try:
        from web_search import WebSearchClient
        
        # 初始化搜索客户端
        client = WebSearchClient(timeout=30)
        
        if hasattr(client, 'timeout') and hasattr(client, 'headers'):
            print("✓ 网络搜索客户端初始化成功")
            return True
        else:
            print("✗ 网络搜索客户端初始化异常")
            return False
            
    except Exception as e:
        print(f"✗ 网络搜索客户端初始化失败: {e}")
        return False

def test_nlp_service_init():
    """测试NLP服务初始化"""
    print("\n=== 测试NLP服务初始化 ===")
    
    try:
        from kimi_nlp_service import KimiNLPService
        
        # 使用测试API密钥初始化
        service = KimiNLPService(
            api_key="test_api_key",
            model="kimi-k2-0905-preview"
        )
        
        if hasattr(service, 'kimi_client') and hasattr(service, 'analysis_templates'):
            print("✓ NLP服务初始化成功")
            print(f"  - 可用分析模板: {list(service.analysis_templates.keys())}")
            return True
        else:
            print("✗ NLP服务初始化异常")
            return False
            
    except Exception as e:
        print(f"✗ NLP服务初始化失败: {e}")
        return False

def test_regex_extraction():
    """测试正则表达式信息提取"""
    print("\n=== 测试正则表达式信息提取 ===")
    
    try:
        from kimi_nlp_service import KimiNLPService
        
        service = KimiNLPService(
            api_key="test_api_key"
        )
        
        # 测试文本
        test_content = """
        项目名称：办公设备采购项目
        项目编号：XM2024001
        预算金额：50万元
        投标截止时间：2024年3月15日 14:00
        开标时间：2024年3月15日 14:30
        联系人：张先生
        联系电话：010-12345678
        """
        
        extracted_info = service._regex_extract_info(test_content)
        
        expected_fields = ['project_id', 'budget', 'deadline', 'opening_time']
        found_fields = [field for field in expected_fields if field in extracted_info]
        
        if len(found_fields) >= 3:  # 至少提取到3个字段
            print(f"✓ 正则表达式提取成功，提取到字段: {found_fields}")
            print(f"  提取结果: {extracted_info}")
            return True
        else:
            print(f"✗ 正则表达式提取不完整，仅提取到: {found_fields}")
            return False
            
    except Exception as e:
        print(f"✗ 正则表达式提取测试失败: {e}")
        return False

def test_file_structure():
    """测试文件结构"""
    print("\n=== 测试文件结构 ===")
    
    required_files = [
        'main.py',
        'kimi_client.py',
        'data_store.py',
        'web_search.py',
        'kimi_nlp_service.py',
        'requirements.txt',
        '.env.example',
        'README.md'
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if not missing_files:
        print("✓ 所有必需文件都存在")
        return True
    else:
        print(f"✗ 缺少文件: {missing_files}")
        return False

def main():
    """主测试函数"""
    print("招标助手项目模块测试")
    print("=" * 50)
    
    test_results = []
    
    # 执行各项测试
    test_results.append(test_file_structure())
    test_results.append(test_imports())
    test_results.append(test_data_store())
    test_results.append(test_kimi_client_init())
    test_results.append(test_web_search_init())
    test_results.append(test_nlp_service_init())
    test_results.append(test_regex_extraction())
    
    # 统计结果
    passed = sum(test_results)
    total = len(test_results)
    
    print("\n" + "=" * 50)
    print(f"测试完成: {passed}/{total} 项测试通过")
    
    if passed == total:
        print("🎉 所有测试都通过了！项目基础功能正常。")
        print("\n下一步：")
        print("1. 复制 .env.example 为 .env")
        print("2. 在 .env 文件中设置真实的 KIMI_API_KEY")
        print("3. 运行 python main.py 启动招标助手")
    else:
        print("❌ 部分测试失败，请检查相关模块。")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)