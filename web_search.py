import asyncio
import aiohttp
from typing import Dict, Any, List, Optional
import logging
import re
from datetime import datetime
import time
import json
import os
from collections import defaultdict
from functools import wraps

# 从环境变量读取API密钥
BOCHAAI_API_KEY = os.getenv('BOCHAAI_API_KEY')



class WebSearchClient:
    """网络搜索客户端，支持多个招标网站"""
    
    def __init__(self, timeout: int = 30, max_retries: int = 3):
        """
        初始化WebSearchClient
        
        Args:
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
        """
        # 设置参数
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self.default_sources = ['bochaai']  # 只保留博查AI
        self.concurrent_limit = 5
        self.rate_limit_delay = 1.0
        
        self.logger = logging.getLogger(__name__)
        
        # 设置日志级别为DEBUG
        self.logger.setLevel(logging.DEBUG)
        
        # 统计信息
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'source_stats': defaultdict(lambda: {'success': 0, 'fail': 0, 'total': 0}),
            'error_details': [],
            'last_search_time': None,
            'response_times': [],
            'retry_attempts': 0
        }
        
        # 请求头，模拟浏览器
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        self.logger.info(f"WebSearchClient初始化完成，超时设置: {timeout}秒")
        
    def retry_on_failure(self, max_retries: int = None):
        """重试装饰器"""
        if max_retries is None:
            max_retries = self.max_retries
            
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                last_exception = None
                for attempt in range(max_retries + 1):
                    try:
                        return await func(*args, **kwargs)
                    except (aiohttp.ClientError, asyncio.TimeoutError, Exception) as e:
                        last_exception = e
                        if attempt < max_retries:
                            self.stats['retry_attempts'] += 1
                            wait_time = 2 ** attempt  # 指数退避
                            self.logger.warning(f"请求失败，{wait_time}秒后重试 (第{attempt + 1}次): {str(e)}")
                            await asyncio.sleep(wait_time)
                        else:
                            self.logger.error(f"重试{max_retries}次后仍然失败: {str(e)}")
                            break
                raise last_exception
            return wrapper
        return decorator
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession(
            timeout=self.timeout,
            headers=self.headers
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if hasattr(self, 'session'):
            await self.session.close()
    
    async def search(self, query: str, sources: List[str] = None) -> List[Dict[str, Any]]:
        """
        搜索招标信息
        
        Args:
            query: 搜索关键词
            sources: 指定搜索源，如果不指定则搜索所有源
            
        Returns:
            搜索结果列表
        """
        search_start_time = time.time()
        self.stats['last_search_time'] = datetime.now().isoformat()
        
        if sources is None:
            sources = self.default_sources
        
        self.logger.info(f"开始搜索，关键词: '{query}', 搜索源: {sources}")
        
        all_results = []
        
        # 创建带重试的搜索任务
        async def search_with_retry(search_func, *args):
            for attempt in range(self.max_retries + 1):
                try:
                    return await search_func(*args)
                except Exception as e:
                    if attempt < self.max_retries:
                        self.stats['retry_attempts'] += 1
                        wait_time = 2 ** attempt
                        self.logger.warning(f"搜索失败，{wait_time}秒后重试 (第{attempt + 1}次): {str(e)}")
                        await asyncio.sleep(wait_time)
                    else:
                        raise e
        
        # 创建会话
        async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
            # 使用信号量控制并发数量
            semaphore = asyncio.Semaphore(self.concurrent_limit)
            
            async def execute_with_limit(source, search_func):
                async with semaphore:
                    try:
                        # 添加速率限制
                        if self.rate_limit_delay > 0:
                            await asyncio.sleep(self.rate_limit_delay)
                        
                        self.logger.debug(f"准备搜索源: {source}")
                        result = await search_with_retry(search_func, session, query)
                        return source, result, None
                    except Exception as e:
                        return source, [], e
            
            tasks = []
            for source in sources:
                if source == 'bochaai':
                    tasks.append(execute_with_limit(source, self._search_bochaai))
                else:
                    self.logger.warning(f"不支持的搜索源: {source}，已忽略")
            
            self.logger.debug(f"创建了 {len(tasks)} 个搜索任务，并发限制: {self.concurrent_limit}")
            
            # 并发执行搜索
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 合并结果
            failed_sources = []
            for result in results:
                if isinstance(result, Exception):
                    self.logger.error(f"任务执行异常: {result}")
                    continue
                
                source_name, source_results, error = result
                
                if error is None and source_results:
                    self.logger.info(f"源 {source_name} 返回 {len(source_results)} 个结果")
                    all_results.extend(source_results)
                    self.stats['source_stats'][source_name]['success'] += 1
                else:
                    if error:
                        error_msg = f"源 {source_name} 搜索出错: {str(error)}"
                        self.logger.error(error_msg)
                        self.stats['error_details'].append({
                            'source': source_name,
                            'error': str(error),
                            'timestamp': datetime.now().isoformat(),
                            'query': query
                        })
                    self.stats['source_stats'][source_name]['fail'] += 1
                    failed_sources.append(source_name)
                
                self.stats['source_stats'][source_name]['total'] += 1
            

        
        # 去重和排序
        unique_results = self._deduplicate_results(all_results)
        
        search_duration = time.time() - search_start_time
        self.stats['response_times'].append(search_duration)
        
        self.logger.info(f"搜索完成，耗时: {search_duration:.2f}秒，原始结果: {len(all_results)}，去重后: {len(unique_results)}")
        
        return sorted(unique_results, key=lambda x: x.get('publish_date', ''), reverse=True)
    
    # 已删除_search_ccgp方法，只保留博查AI搜索
    
    # 已删除_search_ggzy方法，只保留博查AI搜索
    
    # 已删除_search_chinabidding方法，只保留博查AI搜索
    
    # 已删除_search_bidding方法，只保留博查AI搜索
    
    # 已删除其他搜索源的解析函数，只保留博查AI搜索
    
    async def _search_bochaai(self, session: aiohttp.ClientSession, query: str) -> List[Dict[str, Any]]:
        """
        使用博查AI搜索
        
        Args:
            session: HTTP会话
            query: 搜索关键词
            
        Returns:
            搜索结果列表
        """
        source_name = "博查AI"
        request_start_time = time.time()
        
        try:
            url = "https://api.bochaai.com/v1/web-search"
            
            payload = {
                "query": query,
                "summary": True,
                "count": 10
            }
            
            headers = {
                'Authorization': f'Bearer {BOCHAAI_API_KEY}',
                'Content-Type': 'application/json'
            }
            
            self.logger.debug(f"[{source_name}] 请求URL: {url}")
            self.logger.debug(f"[{source_name}] 请求参数: {json.dumps(payload, ensure_ascii=False)}")
            self.stats['total_requests'] += 1
            
            async with session.post(url, json=payload, headers=headers) as response:
                request_duration = time.time() - request_start_time
                self.logger.debug(f"[{source_name}] 响应状态: {response.status}, 耗时: {request_duration:.2f}秒")
                
                if response.status == 200:
                    response_data = await response.json()
                    self.logger.debug(f"[{source_name}] 响应数据: {json.dumps(response_data, ensure_ascii=False)[:500]}...")
                    
                    results = self._parse_bochaai_results(response_data)
                    if results:
                        self.logger.info(f"[{source_name}] 解析完成，获得 {len(results)} 个结果")
                        self.stats['successful_requests'] += 1
                        return results
                    else:
                        self.logger.warning(f"[{source_name}] 未获得有效结果")
                        return []
                else:
                    error_msg = f"[{source_name}] 请求失败，状态码: {response.status}"
                    self.logger.error(error_msg)
                    
                    # 尝试读取错误响应内容
                    try:
                        error_content = await response.text()
                        if error_content:
                            self.logger.debug(f"[{source_name}] 错误响应内容: {error_content[:500]}...")
                    except:
                        pass
                    
                    self.stats['failed_requests'] += 1
                    return []
                    
        except asyncio.TimeoutError:
            self.logger.error(f"[{source_name}] 请求超时")
            self.stats['failed_requests'] += 1
            return []
        except Exception as e:
            self.logger.error(f"[{source_name}] 请求出错: {str(e)}")
            self.stats['failed_requests'] += 1
            return []
    
    def _parse_bochaai_results(self, response_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        解析博查AI搜索结果
        
        Args:
            response_data: API响应数据
            
        Returns:
            解析后的结果列表
        """
        results = []
        
        try:
            # 优先检查博查AI实际返回的data.webPages字段
            if 'data' in response_data and isinstance(response_data['data'], dict):
                data = response_data['data']
                if 'webPages' in data and isinstance(data['webPages'], dict):
                    web_pages = data['webPages']
                    if 'value' in web_pages and isinstance(web_pages['value'], list):
                        for item in web_pages['value']:
                            try:
                                title = item.get('name', '').strip()
                                url = item.get('url', '').strip()
                                snippet = item.get('snippet', '').strip()
                                
                                if not title or not url:
                                    continue
                                
                                # 提取发布时间
                                publish_date = item.get('datePublished', '')
                                if not publish_date:
                                    # 尝试从snippet中提取日期
                                    date_patterns = [r'\d{4}-\d{2}-\d{2}', r'\d{4}/\d{2}/\d{2}', r'\d{4}\.\d{2}\.\d{2}']
                                    for pattern in date_patterns:
                                        match = re.search(pattern, snippet)
                                        if match:
                                            publish_date = match.group()
                                            break
                                
                                result = {
                                    'title': title,
                                    'url': url,
                                    'source': '博查AI',
                                    'publish_date': publish_date,
                                    'description': snippet[:200] + '...' if len(snippet) > 200 else snippet
                                }
                                results.append(result)
                                
                            except Exception as e:
                                self.logger.warning(f"解析博查AI单个结果出错: {str(e)}")
                                continue
            
            # 兼容旧格式：直接检查webPages字段
            elif 'webPages' in response_data and isinstance(response_data['webPages'], dict):
                web_pages = response_data['webPages']
                if 'value' in web_pages and isinstance(web_pages['value'], list):
                    for item in web_pages['value']:
                        try:
                            title = item.get('name', '').strip()
                            url = item.get('url', '').strip()
                            snippet = item.get('snippet', '').strip()
                            
                            if not title or not url:
                                continue
                            
                            # 提取发布时间
                            publish_date = item.get('datePublished', '')
                            if not publish_date:
                                # 尝试从snippet中提取日期
                                date_patterns = [r'\d{4}-\d{2}-\d{2}', r'\d{4}/\d{2}/\d{2}', r'\d{4}\.\d{2}\.\d{2}']
                                for pattern in date_patterns:
                                    match = re.search(pattern, snippet)
                                    if match:
                                        publish_date = match.group()
                                        break
                            
                            result = {
                                'title': title,
                                'url': url,
                                'source': '博查AI',
                                'publish_date': publish_date,
                                'description': snippet[:200] + '...' if len(snippet) > 200 else snippet
                            }
                            results.append(result)
                            
                        except Exception as e:
                            self.logger.warning(f"解析博查AI单个结果出错: {str(e)}")
                            continue
            
            # 兼容其他格式：检查data字段
            elif 'data' in response_data and isinstance(response_data['data'], list):
                for item in response_data['data']:
                    try:
                        title = item.get('title', '').strip()
                        url = item.get('url', '').strip()
                        snippet = item.get('snippet', '').strip()
                        
                        if not title or not url:
                            continue
                        
                        # 提取发布时间（如果有的话）
                        publish_date = item.get('date', '')
                        if not publish_date:
                            # 尝试从snippet中提取日期
                            date_patterns = [r'\d{4}-\d{2}-\d{2}', r'\d{4}/\d{2}/\d{2}', r'\d{4}\.\d{2}\.\d{2}']
                            for pattern in date_patterns:
                                match = re.search(pattern, snippet)
                                if match:
                                    publish_date = match.group()
                                    break
                        
                        result = {
                            'title': title,
                            'url': url,
                            'source': '博查AI',
                            'publish_date': publish_date,
                            'description': snippet[:200] + '...' if len(snippet) > 200 else snippet
                        }
                        results.append(result)
                        
                    except Exception as e:
                        self.logger.warning(f"解析博查AI单个结果出错: {str(e)}")
                        continue
            
            # 兼容其他格式：检查results字段
            elif 'results' in response_data and isinstance(response_data['results'], list):
                for item in response_data['results']:
                    try:
                        title = item.get('title', '').strip()
                        url = item.get('link', item.get('url', '')).strip()
                        snippet = item.get('snippet', item.get('description', '')).strip()
                        
                        if not title or not url:
                            continue
                        
                        result = {
                            'title': title,
                            'url': url,
                            'source': '博查AI',
                            'publish_date': '',
                            'description': snippet[:200] + '...' if len(snippet) > 200 else snippet
                        }
                        results.append(result)
                        
                    except Exception as e:
                        self.logger.warning(f"解析博查AI单个结果出错: {str(e)}")
                        continue
            
            else:
                self.logger.warning(f"博查AI响应格式不符合预期，可用字段: {list(response_data.keys())}")
                
        except Exception as e:
            self.logger.error(f"解析博查AI结果出错: {str(e)}")
        
        return results
    
    def _deduplicate_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        去重搜索结果
        
        Args:
            results: 原始结果列表
            
        Returns:
            去重后的结果列表
        """
        seen_titles = set()
        unique_results = []
        
        for result in results:
            title = result.get('title', '').strip()
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique_results.append(result)
        
        return unique_results
    
    async def get_tender_detail(self, url: str) -> Optional[Dict[str, Any]]:
        """
        获取招标详情
        
        Args:
            url: 招标详情页URL
            
        Returns:
            招标详情信息
        """
        try:
            async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        html = await response.text()
                        return self._parse_tender_detail(html, url)
                    else:
                        self.logger.warning(f"获取招标详情失败，状态码: {response.status}")
                        return None
                        
        except Exception as e:
            self.logger.error(f"获取招标详情出错: {str(e)}")
            return None
    
    def _parse_tender_detail(self, html: str, url: str) -> Dict[str, Any]:
        """
        解析招标详情页
        
        Args:
            html: HTML内容
            url: 页面URL
            
        Returns:
            详情信息
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # 提取标题
            title_elem = soup.find('h1') or soup.find('title')
            title = title_elem.get_text(strip=True) if title_elem else ''
            
            # 提取正文内容
            content_selectors = [
                '.content', '.detail-content', '.main-content',
                '#content', '#detail', '.article-content'
            ]
            
            content = ''
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    content = content_elem.get_text(strip=True)
                    break
            
            # 如果没有找到内容区域，使用整个body
            if not content:
                body_elem = soup.find('body')
                if body_elem:
                    content = body_elem.get_text(strip=True)
            
            # 提取关键信息
            detail_info = {
                'title': title,
                'url': url,
                'content': content,
                'extracted_at': datetime.now().isoformat()
            }
            
            # 尝试提取结构化信息
            budget_pattern = r'预算[：:]*\s*([\d,，.]+)\s*[万千百十]*元'
            budget_match = re.search(budget_pattern, content)
            if budget_match:
                detail_info['budget'] = budget_match.group(1)
            
            deadline_pattern = r'截止时间[：:]*\s*(\d{4}[-年]\d{1,2}[-月]\d{1,2}[日]*\s*\d{0,2}[：:]?\d{0,2})'
            deadline_match = re.search(deadline_pattern, content)
            if deadline_match:
                detail_info['deadline'] = deadline_match.group(1)
            
            return detail_info
            
        except Exception as e:
            self.logger.error(f"解析招标详情出错: {str(e)}")
            return {
                'title': '',
                'url': url,
                'content': '',
                'error': str(e),
                'extracted_at': datetime.now().isoformat()
            }
    

    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取搜索统计信息
        
        Returns:
            统计信息字典
        """
        stats = self.stats.copy()
        
        # 计算平均响应时间
        if stats['response_times']:
            stats['avg_response_time'] = sum(stats['response_times']) / len(stats['response_times'])
        else:
            stats['avg_response_time'] = 0
        
        # 计算成功率
        total_requests = stats['total_requests']
        if total_requests > 0:
            stats['success_rate'] = stats['successful_requests'] / total_requests
        else:
            stats['success_rate'] = 0
        
        return stats
    
    def reset_stats(self):
        """
        重置统计信息
        """
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'source_stats': defaultdict(lambda: {'success': 0, 'fail': 0, 'total': 0}),
            'error_details': [],
            'last_search_time': None,
            'response_times': [],
            'retry_attempts': 0
        }

# 使用示例
async def example_usage():
    """
    使用示例
    """
    print("=== WebSearchClient 使用示例 ===")
    
    # 示例1：基本搜索
    print("\n1. 基本搜索")
    async with WebSearchClient() as client:
        results = await client.search("办公设备采购")
        print(f"找到 {len(results)} 个结果")
        
        for i, result in enumerate(results[:3]):
            print(f"\n结果 {i+1}:")
            print(f"标题: {result['title']}")
            print(f"来源: {result['source']}")
            print(f"发布日期: {result['publish_date']}")
            print(f"链接: {result['url']}")
    
    # 示例2：自定义参数搜索
    print("\n2. 自定义参数搜索")
    async with WebSearchClient(timeout=60, max_retries=5) as custom_client:
        custom_results = await custom_client.search("计算机设备采购")
        print(f"自定义参数搜索找到 {len(custom_results)} 个结果")
        
        # 显示统计信息
        stats = custom_client.get_stats()
        print(f"\n统计信息:")
        print(f"总请求: {stats['total_requests']} 次，成功: {stats['successful_requests']} 次")
        print(f"成功率: {stats['success_rate']:.2%}")
        print(f"平均响应时间: {stats['avg_response_time']:.2f} 秒")

if __name__ == "__main__":
    asyncio.run(example_usage())