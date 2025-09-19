import asyncio
import aiohttp
from typing import Dict, Any, List, Optional, Union
import logging
import re
from datetime import datetime
import time
import json
import os
from collections import defaultdict
from functools import wraps
from bs4 import BeautifulSoup
import traceback
import uuid

from parlant.core.loggers import Logger

# 从环境变量读取API密钥
BOCHAAI_API_KEY = os.getenv('BOCHAAI_API_KEY')


class RequestTracker:
    """基于Logger的请求追踪器，支持Parlant Logger和标准Python logging"""

    def __init__(self, logger: Union[Logger, logging.Logger]):
        self.logger = logger
        self.request_start_time = {}
        self.request_stats = defaultdict(lambda: {
            'count': 0,
            'total_duration': 0,
            'avg_duration': 0,
            'min_duration': float('inf'),
            'max_duration': 0
        })

    def start_request(self, request_id: str, operation: str, **kwargs):
        """开始追踪请求"""
        self.request_start_time[request_id] = time.time()

        # 根据Logger类型选择不同的日志方法
        if hasattr(self.logger, 'info') and callable(getattr(self.logger, 'info')):
            # Parlant Logger或标准Logger
            self.logger.info(f"[{request_id}] Starting {operation}", extra={
                'operation': operation,
                'request_id': request_id,
                'event_type': 'request_start',
                **kwargs
            })
        else:
            # 回退到print或其他方式
            print(f"[{request_id}] Starting {operation}")

    def end_request(self, request_id: str, operation: str, success: bool = True, **kwargs):
        """结束追踪请求"""
        if request_id in self.request_start_time:
            duration = time.time() - self.request_start_time[request_id]
            del self.request_start_time[request_id]

            # 更新统计信息
            stats = self.request_stats[operation]
            stats['count'] += 1
            stats['total_duration'] += duration
            stats['avg_duration'] = stats['total_duration'] / stats['count']
            stats['min_duration'] = min(stats['min_duration'], duration)
            stats['max_duration'] = max(stats['max_duration'], duration)

            # 记录性能日志
            log_data = {
                'operation': operation,
                'request_id': request_id,
                'duration_ms': round(duration * 1000, 2),
                'success': success,
                'event_type': 'request_end',
                **kwargs
            }

            # 根据Logger类型选择不同的日志方法
            if hasattr(self.logger, 'info') and callable(getattr(self.logger, 'info')):
                if success:
                    self.logger.info(f"[{request_id}] Completed {operation} in {duration:.3f}s", extra=log_data)
                else:
                    self.logger.error(f"[{request_id}] Failed {operation} after {duration:.3f}s", extra=log_data)
            else:
                # 回退到print
                status = "Completed" if success else "Failed"
                print(f"[{request_id}] {status} {operation} in {duration:.3f}s")

            return duration
        return None

    def get_stats(self) -> Dict[str, Any]:
        """获取请求统计信息"""
        return dict(self.request_stats)



class WebSearchClient:
    """网络搜索客户端，支持多个招标网站"""
    
    def __init__(self, timeout: int = 30, max_retries: int = 3, logger: Union[Logger, logging.Logger] = None):
        """
        初始化WebSearchClient

        Args:
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
            logger: Logger实例（Parlant Logger或标准Python logging.Logger）
        """
        # 设置参数 - 性能优化
        self.timeout = aiohttp.ClientTimeout(total=timeout, connect=10)
        self.max_retries = max_retries
        self.default_sources = ['bochaai']  # 只保留博查AI
        self.concurrent_limit = 10  # 提高并发数
        self.rate_limit_delay = 0.2  # 减少延迟

        # 初始化Logger，支持Parlant Logger和标准Python logging
        if logger is None:
            # 尝试使用Parlant Logger，如果失败则回退到标准Python logging
            try:
                self.logger = Logger()
            except (TypeError, ImportError, TypeError):
                # 回退到标准Python logging
                self.logger = logging.getLogger(__name__)
                if not self.logger.handlers:
                    handler = logging.StreamHandler()
                    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                    handler.setFormatter(formatter)
                    self.logger.addHandler(handler)
                    self.logger.setLevel(logging.INFO)
        else:
            self.logger = logger

        # Logger兼容性方法
        def _log_info(message: str, extra: Dict[str, Any] = None):
            """兼容性日志方法 - info级别"""
            if hasattr(self.logger, 'info') and callable(getattr(self.logger, 'info')):
                if extra:
                    self.logger.info(message, extra=extra)
                else:
                    self.logger.info(message)
            else:
                print(f"INFO: {message}")

        def _log_debug(message: str, extra: Dict[str, Any] = None):
            """兼容性日志方法 - debug级别"""
            if hasattr(self.logger, 'debug') and callable(getattr(self.logger, 'debug')):
                if extra:
                    self.logger.debug(message, extra=extra)
                else:
                    self.logger.debug(message)
            else:
                print(f"DEBUG: {message}")

        def _log_warning(message: str, extra: Dict[str, Any] = None):
            """兼容性日志方法 - warning级别"""
            if hasattr(self.logger, 'warning') and callable(getattr(self.logger, 'warning')):
                if extra:
                    self.logger.warning(message, extra=extra)
                else:
                    self.logger.warning(message)
            elif hasattr(self.logger, 'warn') and callable(getattr(self.logger, 'warn')):
                if extra:
                    self.logger.warn(message, extra=extra)
                else:
                    self.logger.warn(message)
            else:
                print(f"WARNING: {message}")

        def _log_error(message: str, extra: Dict[str, Any] = None):
            """兼容性日志方法 - error级别"""
            if hasattr(self.logger, 'error') and callable(getattr(self.logger, 'error')):
                if extra:
                    self.logger.error(message, extra=extra)
                else:
                    self.logger.error(message)
            else:
                print(f"ERROR: {message}")

        # 绑定方法到实例
        self._log_info = _log_info
        self._log_debug = _log_debug
        self._log_warning = _log_warning
        self._log_error = _log_error

        self.request_tracker = RequestTracker(self.logger)

        # 生成客户端实例ID
        self.client_id = str(uuid.uuid4())[:8]

        # 记录初始化日志
        self._log_info(f"Initializing WebSearchClient [{self.client_id}]", extra={
            'event_type': 'client_init',
            'client_id': self.client_id,
            'timeout': timeout,
            'max_retries': max_retries,
            'concurrent_limit': self.concurrent_limit
        })

        # 添加搜索缓存
        self._search_cache = {}
        self._cache_ttl = 300  # 5分钟缓存

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
        
        self._log_info(f"WebSearchClient初始化完成，超时设置: {timeout}秒")

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
    
    async def search(self, query: str, sources: List[str] = None,
                 freshness: str = None, include_sites: List[str] = None,
                 exclude_sites: List[str] = None, count: int = 15,
                 summary: bool = True, page: int = 1,
                 search_type: str = "web") -> List[Dict[str, Any]]:
        """
        搜索招标信息

        Args:
            query: 搜索关键词
            sources: 指定搜索源，如果不指定则搜索所有源
            freshness: 时间范围过滤 (day, week, month, year)
            include_sites: 包含的网站域名列表
            exclude_sites: 排除的网站域名列表
            count: 返回结果数量
            summary: 是否生成摘要
            page: 分页页码
            search_type: 搜索类型 ("web", "image", "mixed")

        Returns:
            搜索结果列表
        """
        search_start_time = time.time()
        self.stats['last_search_time'] = datetime.now().isoformat()

        if sources is None:
            sources = self.default_sources

        # 生成请求ID
        request_id = str(uuid.uuid4())[:8]

        # 记录搜索开始
        search_params = {
            'query': query,
            'sources': sources,
            'freshness': freshness,
            'include_sites': include_sites,
            'exclude_sites': exclude_sites,
            'count': count,
            'summary': summary,
            'page': page,
            'search_type': search_type,
            'event_type': 'search_start'
        }

        self.logger.info(f"[{request_id}] Starting search for: {query}", extra=search_params)
        self.request_tracker.start_request(request_id, 'search', **search_params)

        # 检查缓存
        cache_key = f"{query}:{':'.join(sorted(sources))}:{freshness or 'all'}:{page}"
        if include_sites:
            cache_key += f":include_{':'.join(sorted(include_sites))}"
        if exclude_sites:
            cache_key += f":exclude_{':'.join(sorted(exclude_sites))}"
        current_time = time.time()

        if cache_key in self._search_cache:
            cached_data = self._search_cache[cache_key]
            if current_time - cached_data['timestamp'] < self._cache_ttl:
                self.logger.info(f"[{request_id}] Cache hit for: {query}", extra={
                    'event_type': 'cache_hit',
                    'query': query,
                    'cache_key': cache_key,
                    'cache_age': current_time - cached_data['timestamp'],
                    'result_count': len(cached_data['results'])
                })
                self.stats['cache_hits'] = self.stats.get('cache_hits', 0) + 1

                # 记录缓存性能
                self.request_tracker.end_request(request_id, 'search_cache', success=True, extra={
                    'result_count': len(cached_data['results']),
                    'from_cache': True
                })
                return cached_data['results']

        self.logger.debug(f"[{request_id}] Search parameters", extra={
            'event_type': 'search_params',
            'query': query,
            'sources': sources,
            'freshness': freshness,
            'include_sites_count': len(include_sites) if include_sites else 0,
            'exclude_sites_count': len(exclude_sites) if exclude_sites else 0,
            'count': count,
            'search_type': search_type
        })

        all_results = []

        # 创建带重试的搜索任务 - 优化重试策略
        async def search_with_retry(search_func, *args, **kwargs):
            source_name = kwargs.get('source_name', 'unknown')
            for attempt in range(self.max_retries + 1):
                try:
                    return await search_func(*args, **kwargs)
                except Exception as e:
                    if attempt < self.max_retries:
                        self.stats['retry_attempts'] += 1
                        wait_time = min(1.0, 0.5 * (attempt + 1))  # 快速重试，最多等待1秒

                        # 记录重试日志
                        self.logger.warning(f"[{request_id}] Retry {attempt + 1}/{self.max_retries} for {source_name}: {str(e)}", extra={
                            'event_type': 'search_retry',
                            'source': source_name,
                            'attempt': attempt + 1,
                            'max_retries': self.max_retries,
                            'wait_time': wait_time,
                            'error': str(e),
                            'error_type': type(e).__name__,
                            'query': query
                        })

                        await asyncio.sleep(wait_time)
                    else:
                        # 记录最终失败
                        self.logger.error(f"[{request_id}] Max retries reached for {source_name}: {str(e)}", extra={
                            'event_type': 'search_failed',
                            'source': source_name,
                            'max_attempts_reached': True,
                            'error': str(e),
                            'error_type': type(e).__name__,
                            'query': query
                        })
                        raise e
        
        # 创建会话
        async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
            # 使用信号量控制并发数量
            semaphore = asyncio.Semaphore(self.concurrent_limit)

            async def execute_with_limit(source, search_func, search_params=None):
                source_request_id = str(uuid.uuid4())[:8]

                async with semaphore:
                    try:
                        # 记录搜索任务开始
                        self.logger.info(f"[{source_request_id}] Starting {source} search task", extra={
                            'event_type': 'search_task_start',
                            'source': source,
                            'search_params': search_params,
                            'concurrent_tasks': len(tasks) + 1,
                            'parent_request_id': request_id
                        })

                        # 添加速率限制
                        if self.rate_limit_delay > 0:
                            await asyncio.sleep(self.rate_limit_delay)

                        self.logger.debug(f"[{source_request_id}] Executing {source} search", extra={
                            'event_type': 'search_task_execute',
                            'source': source,
                            'query': query,
                            'parent_request_id': request_id
                        })

                        if search_params:
                            result = await search_with_retry(
                                search_func, session, query, **search_params
                            )
                        else:
                            result = await search_with_retry(
                                search_func, session, query
                            )

                        # 记录搜索任务成功
                        self.logger.info(f"[{source_request_id}] {source} search completed with {len(result) if result else 0} results", extra={
                            'event_type': 'search_task_success',
                            'source': source,
                            'result_count': len(result) if result else 0,
                            'duration': time.time() - search_start_time,
                            'parent_request_id': request_id
                        })

                        return source, result, None
                    except Exception as e:
                        # 记录搜索任务失败
                        self.logger.error(f"[{source_request_id}] {source} search failed: {str(e)}", extra={
                            'event_type': 'search_task_error',
                            'source': source,
                            'error': str(e),
                            'error_type': type(e).__name__,
                            'query': query,
                            'duration': time.time() - search_start_time,
                            'parent_request_id': request_id
                        })
                        return source, [], e

            tasks = []
            for source in sources:
                if source == 'bochaai':
                    tasks.append(execute_with_limit(source, self._search_bochaai, {
                        'freshness': freshness,
                        'include_sites': include_sites,
                        'exclude_sites': exclude_sites,
                        'count': count,
                        'summary': summary,
                        'page': page,
                        'search_type': search_type
                    }))
                else:
                    self.logger.warning(f"Unsupported search source: {source}", extra={
                        'event_type': 'unsupported_source',
                        'source': source,
                        'query': query,
                        'request_id': request_id
                    })

            self.logger.info(f"[{request_id}] Created {len(tasks)} search tasks", extra={
                'event_type': 'search_tasks_created',
                'task_count': len(tasks),
                'concurrent_limit': self.concurrent_limit,
                'sources': sources
            })

            # 并发执行搜索
            gather_start = time.time()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            gather_duration = time.time() - gather_start

            self.logger.info(f"[{request_id}] Gathered {len(tasks)} tasks in {gather_duration:.3f}s", extra={
                'event_type': 'search_gather',
                'task_count': len(tasks),
                'gather_duration_ms': round(gather_duration * 1000, 2),
                'request_id': request_id
            })

            # 合并结果
            failed_sources = []
            successful_results = 0
            for result in results:
                if isinstance(result, Exception):
                    self.logger.error(f"[{request_id}] Task execution exception: {str(result)}", extra={
                        'event_type': 'task_execution_exception',
                        'exception': str(result),
                        'exception_type': type(result).__name__,
                        'request_id': request_id
                    })
                    continue

                source_name, source_results, error = result

                if error is None and source_results:
                    self.logger.info(f"[{request_id}] {source_name} returned {len(source_results)} results", extra={
                        'event_type': 'source_success',
                        'source': source_name,
                        'result_count': len(source_results),
                        'total_results_so_far': len(all_results) + len(source_results),
                        'request_id': request_id
                    })
                    all_results.extend(source_results)
                    self.stats['source_stats'][source_name]['success'] += 1
                    successful_results += len(source_results)
                else:
                    if error:
                        error_details = {
                            'source': source_name,
                            'error': str(error),
                            'timestamp': datetime.now().isoformat(),
                            'query': query,
                            'error_type': type(error).__name__ if error else 'Unknown',
                            'request_id': request_id
                        }

                        self.stats['error_details'].append(error_details)
                        self.logger.error(f"[{request_id}] {source_name} search error: {str(error)}", extra={
                            'event_type': 'source_error',
                            **error_details
                        })

                    self.stats['source_stats'][source_name]['fail'] += 1
                    failed_sources.append(source_name)

                self.stats['source_stats'][source_name]['total'] += 1
            

        
        # 去重和排序
        unique_results = self._deduplicate_results(all_results)

        search_duration = time.time() - search_start_time
        self.stats['response_times'].append(search_duration)

        # 缓存结果
        if unique_results:
            self._search_cache[cache_key] = {
                'results': unique_results,
                'timestamp': current_time
            }

            # 清理过期缓存
            if len(self._search_cache) > 100:  # 限制缓存大小
                expired_keys = [
                    key for key, data in self._search_cache.items()
                    if current_time - data['timestamp'] > self._cache_ttl
                ]
                for key in expired_keys:
                    del self._search_cache[key]

        self.logger.info(f"[{request_id}] Search completed in {search_duration:.2f}s", extra={
            'event_type': 'search_completed',
            'search_duration': round(search_duration, 3),
            'raw_results': len(all_results),
            'unique_results': len(unique_results),
            'cache_hit': False,
            'failed_sources': failed_sources,
            'successful_sources': len(sources) - len(failed_sources),
            'request_id': request_id,
            'query': query
        })

        # 记录搜索性能
        self.request_tracker.end_request(request_id, 'search', success=True, extra={
            'result_count': len(unique_results),
            'raw_result_count': len(all_results),
            'failed_sources': len(failed_sources),
            'successful_sources': len(sources) - len(failed_sources),
            'from_cache': False
        })

        return sorted(unique_results, key=lambda x: x.get('publish_date', ''), reverse=True)
    
    # 已删除_search_ccgp方法，只保留博查AI搜索
    
    # 已删除_search_ggzy方法，只保留博查AI搜索
    
    # 已删除_search_chinabidding方法，只保留博查AI搜索
    
    # 已删除_search_bidding方法，只保留博查AI搜索
    
    # 已删除其他搜索源的解析函数，只保留博查AI搜索
    
    async def _search_bochaai(self, session: aiohttp.ClientSession, query: str,
                              freshness: str = None, include_sites: List[str] = None,
                              exclude_sites: List[str] = None, count: int = 15,
                              summary: bool = True, page: int = 1,
                              search_type: str = "web") -> List[Dict[str, Any]]:
        """
        使用博查AI搜索

        Args:
            session: HTTP会话
            query: 搜索关键词
            freshness: 时间范围过滤
            include_sites: 包含的网站域名列表
            exclude_sites: 排除的网站域名列表
            count: 返回结果数量
            summary: 是否生成摘要
            page: 分页页码
            search_type: 搜索类型 ("web", "image", "mixed")

        Returns:
            搜索结果列表
        """
        source_name = "博查AI"
        request_start_time = time.time()
        operation_id = str(uuid.uuid4())[:8]

        try:
            # 根据搜索类型选择不同的API端点
            if search_type == "image":
                url = "https://api.bochaai.com/v1/image-search"
                self.logger.debug(f"[{operation_id}] Using image search API for {source_name}", extra={
                    'event_type': 'api_endpoint',
                    'source': source_name,
                    'url': url,
                    'search_type': search_type,
                    'query': query
                })
            else:
                url = "https://api.bochaai.com/v1/web-search"
                self.logger.debug(f"[{operation_id}] Using web search API for {source_name}", extra={
                    'event_type': 'api_endpoint',
                    'source': source_name,
                    'url': url,
                    'search_type': search_type,
                    'query': query
                })
            
            payload = {
                "query": query,
                "count": count
            }

            # 图片搜索特定参数
            if search_type == "image":
                payload["image_search"] = True
                payload["safe_search"] = True  # 启用安全搜索
                # 图片搜索默认启用摘要
                payload["summary"] = True
            else:
                payload["summary"] = summary

            # 添加时间范围过滤（仅网页搜索支持）
            if search_type != "image" and freshness:
                if freshness in ['day', 'week', 'month', 'year']:
                    payload["freshness"] = freshness
                    self.logger.debug(f"[{source_name}] 启用时间过滤: {freshness}")
                else:
                    self.logger.warning(f"[{source_name}] 无效的freshness参数: {freshness}")

            # 添加网站范围过滤（仅网页搜索支持）
            if search_type != "image":
                if include_sites:
                    payload["include"] = ",".join(include_sites)
                    self.logger.debug(f"[{source_name}] 包含网站: {include_sites}")

                if exclude_sites:
                    payload["exclude"] = ",".join(exclude_sites)
                    self.logger.debug(f"[{source_name}] 排除网站: {exclude_sites}")

            # 添加分页支持
            if page > 1:
                payload["offset"] = (page - 1) * count
                self.logger.debug(f"[{source_name}] 分页: 第{page}页")
            
            headers = {
                'Authorization': f'Bearer {BOCHAAI_API_KEY}',
                'Content-Type': 'application/json'
            }

            self.logger.debug(f"[{operation_id}] API request to {url}", extra={
                'event_type': 'api_request',
                'source': source_name,
                'url': url,
                'payload_size': len(json.dumps(payload)),
                'query': query
            })
            self.stats['total_requests'] += 1

            async with session.post(url, json=payload, headers=headers) as response:
                request_duration = time.time() - request_start_time

                self.logger.debug(f"[{operation_id}] API response: {response.status} in {request_duration:.3f}s", extra={
                    'event_type': 'api_response',
                    'source': source_name,
                    'status_code': response.status,
                    'request_duration_ms': round(request_duration * 1000, 2),
                    'query': query
                })
                
                if response.status == 200:
                    response_data = await response.json()
                    self.logger.debug(f"[{operation_id}] API response data received", extra={
                        'event_type': 'api_data_received',
                        'source': source_name,
                        'data_size': len(json.dumps(response_data)),
                        'query': query
                    })

                    # 根据搜索类型解析结果
                    if search_type == "image":
                        results = self._parse_bochaai_image_results(response_data)
                    else:
                        results = self._parse_bochaai_results(response_data)

                    if results:
                        self.logger.info(f"[{operation_id}] {source_name} parsed {len(results)} results", extra={
                            'event_type': 'api_parse_success',
                            'source': source_name,
                            'result_count': len(results),
                            'total_duration': round(request_duration, 3),
                            'query': query
                        })
                        self.stats['successful_requests'] += 1
                        return results
                    else:
                        self.logger.warning(f"[{operation_id}] {source_name} no valid results parsed", extra={
                            'event_type': 'api_parse_empty',
                            'source': source_name,
                            'total_duration': round(request_duration, 3),
                            'query': query
                        })
                        return []
                else:
                    error_msg = f"[{source_name}] 请求失败，状态码: {response.status}"
                    self.logger.error(error_msg, extra={
                        'event_type': 'api_error',
                        'source': source_name,
                        'status_code': response.status,
                        'query': query
                    })

                    # 详细的错误码处理
                    error_info = await self._handle_bochaai_error(response, source_name, operation_id)
                    self.stats['error_details'].append({
                        'source': source_name,
                        'error': error_info,
                        'status_code': response.status,
                        'timestamp': datetime.now().isoformat(),
                        'query': query
                    })

                    self.stats['failed_requests'] += 1
                    return []
                    
        except asyncio.TimeoutError:
            self.logger.error(f"[{operation_id}] {source_name} request timeout", extra={
                'event_type': 'api_timeout',
                'source': source_name,
                'duration': round(time.time() - request_start_time, 3),
                'query': query
            })
            self.stats['failed_requests'] += 1
            return []
        except Exception as e:
            self.logger.error(f"[{operation_id}] {source_name} request error: {str(e)}", extra={
                'event_type': 'api_exception',
                'source': source_name,
                'error': str(e),
                'error_type': type(e).__name__,
                'duration': round(time.time() - request_start_time, 3),
                'query': query
            })
            self.stats['failed_requests'] += 1
            return []

    async def _handle_bochaai_error(self, response, source_name: str, operation_id: str = None) -> str:
        """
        处理博查AI API 错误响应

        Args:
            response: HTTP响应对象
            source_name: 搜索源名称
            operation_id: 操作ID

        Returns:
            错误信息描述
        """
        try:
            error_content = await response.text()
            error_info = f"状态码: {response.status}"

            # 根据状态码提供具体错误信息
            if response.status == 400:
                error_info += " - 请求参数错误"
            elif response.status == 401:
                error_info += " - API密钥无效或过期"
            elif response.status == 403:
                error_info += " - 访问被拒绝，可能超出配额"
            elif response.status == 404:
                error_info += " - 接口不存在"
            elif response.status == 429:
                error_info += " - 请求频率过高，被限流"
            elif response.status == 500:
                error_info += " - 服务器内部错误"
            elif response.status == 502:
                error_info += " - 网关错误"
            elif response.status == 503:
                error_info += " - 服务不可用"
            elif response.status == 504:
                error_info += " - 网关超时"
            else:
                error_info += f" - 未知错误"

            if error_content:
                error_info += f", 响应内容: {error_content[:200]}"
                self.logger.debug(f"[{operation_id or 'unknown'}] {source_name} error details: {error_content[:500]}...", extra={
                    'event_type': 'error_details',
                    'source': source_name,
                    'error_content_size': len(error_content),
                    'status_code': response.status
                })

            return error_info

        except Exception as e:
            return f"处理错误响应时异常: {str(e)}"
    
    def _parse_bochaai_image_results(self, response_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        解析博查AI图片搜索结果

        Args:
            response_data: API响应数据

        Returns:
            解析后的结果列表
        """
        results = []

        try:
            # 解析图片搜索结果
            if 'data' in response_data and isinstance(response_data['data'], dict):
                data = response_data['data']
                if 'images' in data and isinstance(data['images'], list):
                    for item in data['images']:
                        try:
                            title = item.get('title', item.get('name', '')).strip()
                            url = item.get('url', item.get('contentUrl', '')).strip()
                            thumbnail_url = item.get('thumbnailUrl', '').strip()
                            image_url = item.get('contentUrl', url).strip()

                            if not title or not url:
                                continue

                            # 提取图片尺寸信息
                            width = item.get('width', 0)
                            height = item.get('height', 0)

                            result = {
                                'title': title,
                                'url': url,
                                'thumbnail_url': thumbnail_url,
                                'image_url': image_url,
                                'source': '博查AI图片',
                                'width': width,
                                'height': height,
                                'publish_date': '',
                                'description': f'图片搜索结果: {title} ({width}x{height})'
                            }
                            results.append(result)

                        except Exception as e:
                            self.logger.warning(f"解析博查AI图片单个结果出错: {str(e)}")
                            continue

            # 兼容其他格式
            elif 'images' in response_data and isinstance(response_data['images'], list):
                for item in response_data['images']:
                    try:
                        title = item.get('title', item.get('name', '')).strip()
                        url = item.get('url', item.get('contentUrl', '')).strip()

                        if not title or not url:
                            continue

                        result = {
                            'title': title,
                            'url': url,
                            'thumbnail_url': item.get('thumbnailUrl', ''),
                            'image_url': item.get('contentUrl', url),
                            'source': '博查AI图片',
                            'width': item.get('width', 0),
                            'height': item.get('height', 0),
                            'publish_date': '',
                            'description': f'图片搜索结果: {title}'
                        }
                        results.append(result)

                    except Exception as e:
                        self.logger.warning(f"解析博查AI图片单个结果出错: {str(e)}")
                        continue

            if not results:
                self.logger.warning(f"博查AI图片搜索响应格式不符合预期，可用字段: {list(response_data.keys())}")

        except Exception as e:
            self.logger.error(f"解析博查AI图片结果出错: {str(e)}")

        return results

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
                                
                                # 提取发布时间 - 优化时间解析
                                publish_date = item.get('datePublished', '')
                                if not publish_date:
                                    publish_date = item.get('dateLastCrawled', '')

                                if not publish_date:
                                    # 尝试从snippet中提取日期
                                    date_patterns = [
                                        r'\d{4}-\d{2}-\d{2}',
                                        r'\d{4}/\d{2}/\d{2}',
                                        r'\d{4}\.\d{2}\.\d{2}',
                                        r'\d{4}年\d{1,2}月\d{1,2}日',
                                        r'\d{4}-\d{1,2}-\d{1,2}'
                                    ]
                                    for pattern in date_patterns:
                                        match = re.search(pattern, snippet)
                                        if match:
                                            publish_date = match.group()
                                            # 标准化日期格式
                                            publish_date = re.sub(r'[年/\.]', '-', publish_date)
                                            publish_date = re.sub(r'[月日]', '', publish_date)
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
    logger = Logger()
    async with WebSearchClient(logger=logger) as client:
        results = await client.search("办公设备采购")
        print(f"找到 {len(results)} 个结果")

        for i, result in enumerate(results[:3]):
            print(f"\n结果 {i+1}:")
            print(f"标题: {result['title']}")
            print(f"来源: {result['source']}")
            print(f"发布日期: {result['publish_date']}")
            print(f"链接: {result['url']}")

    # 示例2：优化参数搜索
    print("\n2. 优化参数搜索")
    logger = Logger()
    async with WebSearchClient(logger=logger) as client:
        # 使用时间过滤、网站过滤和更多结果
        optimized_results = await client.search(
            "计算机设备采购",
            freshness="month",  # 最近一个月
            include_sites=["ccgp.gov.cn", "ggzy.gov.cn"],  # 政府采购网
            count=20,  # 更多结果
            summary=True  # 生成摘要
        )
        print(f"优化参数搜索找到 {len(optimized_results)} 个结果")

        # 显示统计信息
        stats = client.get_stats()
        print(f"\n统计信息:")
        print(f"总请求: {stats['total_requests']} 次，成功: {stats['successful_requests']} 次")
        print(f"成功率: {stats['success_rate']:.2%}")
        print(f"平均响应时间: {stats['avg_response_time']:.2f} 秒")

        # 显示请求追踪统计
        request_stats = client.request_tracker.get_stats()
        print(f"\n请求追踪统计:")
        for operation, op_stats in request_stats.items():
            print(f"操作 {operation}: {op_stats['count']} 次，平均耗时: {op_stats['avg_duration']:.3f}s")

    # 示例3：分页搜索
    print("\n3. 分页搜索示例")
    logger = Logger()
    async with WebSearchClient(logger=logger) as client:
        page1_results = await client.search("工程招标", page=1, count=10)
        page2_results = await client.search("工程招标", page=2, count=10)

        print(f"第1页: {len(page1_results)} 个结果")
        print(f"第2页: {len(page2_results)} 个结果")

        # 检查去重效果
        all_titles = [r['title'] for r in page1_results + page2_results]
        unique_titles = set(all_titles)
        print(f"总结果: {len(all_titles)}, 去重后: {len(unique_titles)}")

    # 示例4：网站排除过滤
    print("\n4. 网站排除过滤")
    logger = Logger()
    async with WebSearchClient(logger=logger) as client:
        exclude_results = await client.search(
            "软件开发招标",
            exclude_sites=["baidu.com", "sogou.com"],  # 排除搜索引擎
            freshness="week"  # 最近一周
        )
        print(f"排除搜索引擎后找到 {len(exclude_results)} 个结果")

    # 示例5：图片搜索
    print("\n5. 图片搜索")
    logger = Logger()
    async with WebSearchClient(logger=logger) as client:
        image_results = await client.search(
            "招标公告 截图",
            search_type="image",
            count=10
        )
        print(f"图片搜索找到 {len(image_results)} 个结果")

        for i, result in enumerate(image_results[:3]):
            print(f"\n图片 {i+1}:")
            print(f"标题: {result['title']}")
            print(f"尺寸: {result['width']}x{result['height']}")
            print(f"缩略图: {result['thumbnail_url']}")
            print(f"原图: {result['image_url']}")

    print("\n=== 日志功能演示完成 ===")
    print("日志将输出到控制台和日志文件中")
    print("支持的日志级别: DEBUG, INFO, WARNING, ERROR")
    print("结构化数据通过 extra 参数记录")

if __name__ == "__main__":
    asyncio.run(example_usage())