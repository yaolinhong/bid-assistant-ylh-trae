"""
Dashboard module for bid assistant monitoring and statistics.
Provides Flask routes for search dashboard and API endpoints.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List
from flask import Flask, render_template, jsonify


class SearchLogHandler(logging.Handler):
    """自定义日志处理器，用于收集搜索日志"""

    def __init__(self, logs_list: List[Dict[str, Any]], source_status: Dict[str, Dict[str, Any]]):
        super().__init__()
        self.logs_list = logs_list
        self.source_status = source_status

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
            self.logs_list.append(log_entry)

            # 只保留最近1000条日志
            if len(self.logs_list) > 1000:
                self.logs_list.pop(0)

            # 更新源状态
            message = record.getMessage()
            if '[CCGP' in message:
                if '解析完成' in message:
                    self.source_status['ccgp'] = {'status': 'success', 'last_success': datetime.now().isoformat()}
                elif '搜索失败' in message or '搜索出错' in message:
                    self.source_status['ccgp']['status'] = 'error'
            elif '[中国招标网]' in message:
                if '解析完成' in message:
                    self.source_status['chinabidding'] = {'status': 'success', 'last_success': datetime.now().isoformat()}
                elif '搜索失败' in message or '搜索出错' in message:
                    self.source_status['chinabidding']['status'] = 'error'
            elif '[全国公共资源交易平台]' in message:
                if '解析完成' in message:
                    self.source_status['ggzy'] = {'status': 'success', 'last_success': datetime.now().isoformat()}
                elif '搜索失败' in message or '搜索出错' in message:
                    self.source_status['ggzy']['status'] = 'error'
            elif '[招标网]' in message:
                if '解析完成' in message:
                    self.source_status['bidding'] = {'status': 'success', 'last_success': datetime.now().isoformat()}
                elif '搜索失败' in message or '搜索出错' in message:
                    self.source_status['bidding']['status'] = 'error'

        except Exception:
            pass  # 忽略日志处理错误


class DashboardManager:
    """监控面板管理器"""

    def __init__(self, template_folder: str = 'templates'):
        self.flask_app = Flask(__name__, template_folder=template_folder)
        self.search_logs: List[Dict[str, Any]] = []
        self.source_status: Dict[str, Dict[str, Any]] = {
            'ccgp': {'status': 'unknown', 'last_success': None},
            'chinabidding': {'status': 'unknown', 'last_success': None},
            'ggzy': {'status': 'unknown', 'last_success': None},
            'bidding': {'status': 'unknown', 'last_success': None}
        }

        self._setup_routes()

    def _setup_routes(self):
        """设置路由"""

        @self.flask_app.route('/dashboard')
        def dashboard():
            """监控面板页面"""
            return render_template('search_dashboard.html')

        @self.flask_app.route('/api/search-stats')
        def get_search_stats():
            """获取搜索统计数据API"""
            try:
                # 获取web_search的统计信息（通过全局变量）
                import sys
                main_module = sys.modules.get('main')
                web_search = getattr(main_module, 'web_search', None) if main_module else None

                stats = getattr(web_search, 'stats', {
                    'total_requests': 0,
                    'successful_requests': 0,
                    'failed_requests': 0
                }) if web_search else {
                    'total_requests': 0,
                    'successful_requests': 0,
                    'failed_requests': 0
                }

                # 获取最近的日志
                recent_logs = self.search_logs[-50:] if self.search_logs else []

                return jsonify({
                    'stats': stats,
                    'sources': self.source_status,
                    'logs': recent_logs
                })
            except Exception as e:
                logging.getLogger(__name__).error(f"获取搜索统计数据失败: {e}")
                return jsonify({
                    'stats': {'total_requests': 0, 'successful_requests': 0, 'failed_requests': 0},
                    'sources': self.source_status,
                    'logs': []
                }), 500

    def setup_logging_handler(self, web_search):
        """设置自定义日志处理器到web_search的logger"""
        search_log_handler = SearchLogHandler(self.search_logs, self.source_status)
        web_search.logger.addHandler(search_log_handler)

        # 确保web_search的logger不会重复输出到根logger
        web_search.logger.propagate = False

    def get_app(self) -> Flask:
        """获取Flask应用实例"""
        return self.flask_app

    def get_search_logs(self) -> List[Dict[str, Any]]:
        """获取搜索日志"""
        return self.search_logs

    def get_source_status(self) -> Dict[str, Dict[str, Any]]:
        """获取源状态"""
        return self.source_status