#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试博查AI集成功能
"""

import asyncio
import logging
from web_search import WebSearchClient

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_bochaai_search():
    """
    测试博查AI搜索功能
    """
    print("\n=== 测试博查AI搜索功能 ===")
    
    # 创建搜索客户端
    client = WebSearchClient()
    
    # 测试查询
    query = "政府采购"
    sources = ['bochaai']  # 只测试博查AI
    
    try:
        print(f"搜索关键词: {query}")
        print(f"搜索源: {sources}")
        print("开始搜索...")
        
        # 执行搜索
        results = await client.search(query, sources=sources)
        
        print(f"\n搜索完成！")
        print(f"总结果数: {len(results)}")
        
        # 显示前几个结果
        if results:
            print("\n前5个搜索结果:")
            for i, result in enumerate(results[:5], 1):
                print(f"\n{i}. {result.get('title', 'N/A')}")
                print(f"   来源: {result.get('source', 'N/A')}")
                print(f"   链接: {result.get('url', 'N/A')}")
                print(f"   描述: {result.get('description', 'N/A')[:100]}...")
                if result.get('publish_date'):
                    print(f"   发布时间: {result.get('publish_date')}")
        else:
            print("\n未获得搜索结果")
        
        # 显示统计信息
        stats = client.get_stats()
        print(f"\n搜索统计:")
        print(f"  总请求数: {stats.get('total_requests', 0)}")
        print(f"  成功请求数: {stats.get('successful_requests', 0)}")
        print(f"  失败请求数: {stats.get('failed_requests', 0)}")
        
        return len(results) > 0
        
    except Exception as e:
        print(f"搜索出错: {str(e)}")
        return False

async def test_mixed_sources():
    """
    测试混合搜索源（包含博查AI）
    """
    print("\n=== 测试混合搜索源 ===")
    
    # 创建搜索客户端
    client = WebSearchClient()
    
    # 测试查询
    query = "招标公告"
    sources = ['bochaai', 'ccgp']  # 博查AI + 中国政府采购网
    
    try:
        print(f"搜索关键词: {query}")
        print(f"搜索源: {sources}")
        print("开始搜索...")
        
        # 执行搜索
        results = await client.search(query, sources=sources)
        
        print(f"\n搜索完成！")
        print(f"总结果数: {len(results)}")
        
        # 按来源统计结果
        source_stats = {}
        for result in results:
            source = result.get('source', 'Unknown')
            source_stats[source] = source_stats.get(source, 0) + 1
        
        print("\n各来源结果统计:")
        for source, count in source_stats.items():
            print(f"  {source}: {count} 个结果")
        
        # 显示统计信息
        stats = client.get_stats()
        print(f"\n搜索统计:")
        print(f"  总请求数: {stats.get('total_requests', 0)}")
        print(f"  成功请求数: {stats.get('successful_requests', 0)}")
        print(f"  失败请求数: {stats.get('failed_requests', 0)}")
        
        return len(results) > 0
        
    except Exception as e:
        print(f"搜索出错: {str(e)}")
        return False

async def test_error_handling():
    """
    测试错误处理
    """
    print("\n=== 测试错误处理 ===")
    
    # 创建搜索客户端
    client = WebSearchClient()
    
    # 测试空查询
    try:
        print("测试空查询...")
        results = await client.search("", sources=['bochaai'])
        print(f"空查询结果数: {len(results)}")
    except Exception as e:
        print(f"空查询错误: {str(e)}")
    
    # 测试无效源
    try:
        print("\n测试无效源...")
        results = await client.search("测试", sources=['invalid_source'])
        print(f"无效源结果数: {len(results)}")
    except Exception as e:
        print(f"无效源错误: {str(e)}")
    
    return True

async def main():
    """
    主测试函数
    """
    print("博查AI集成测试开始")
    print("=" * 50)
    
    # 运行测试
    test_results = []
    
    # 测试1: 博查AI搜索
    result1 = await test_bochaai_search()
    test_results.append(("博查AI搜索", result1))
    
    # 测试2: 混合搜索源
    result2 = await test_mixed_sources()
    test_results.append(("混合搜索源", result2))
    
    # 测试3: 错误处理
    result3 = await test_error_handling()
    test_results.append(("错误处理", result3))
    
    # 显示测试结果
    print("\n" + "=" * 50)
    print("测试结果汇总:")
    for test_name, success in test_results:
        status = "✓ 通过" if success else "✗ 失败"
        print(f"  {test_name}: {status}")
    
    # 总结
    passed_tests = sum(1 for _, success in test_results if success)
    total_tests = len(test_results)
    print(f"\n总计: {passed_tests}/{total_tests} 个测试通过")
    
    if passed_tests == total_tests:
        print("\n🎉 所有测试通过！博查AI集成成功！")
    else:
        print(f"\n⚠️  有 {total_tests - passed_tests} 个测试失败，请检查配置")

if __name__ == "__main__":
    asyncio.run(main())