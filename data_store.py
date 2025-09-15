import os
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
import logging
from pathlib import Path

class SimpleDataStore:
    """简单的JSON文件数据存储"""
    
    def __init__(self, data_dir: str = "data"):
        """
        初始化数据存储
        
        Args:
            data_dir: 数据存储目录
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # 创建子目录
        self.sessions_dir = self.data_dir / "sessions"
        self.tenders_dir = self.data_dir / "tenders"
        self.analysis_dir = self.data_dir / "analysis"
        
        for dir_path in [self.sessions_dir, self.tenders_dir, self.analysis_dir]:
            dir_path.mkdir(exist_ok=True)
        
        # 设置日志
        self.logger = logging.getLogger(__name__)
    
    def _save_json(self, file_path: Path, data: Dict[str, Any]) -> bool:
        """
        保存JSON数据到文件
        
        Args:
            file_path: 文件路径
            data: 要保存的数据
            
        Returns:
            是否保存成功
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            self.logger.error(f"保存文件失败 {file_path}: {str(e)}")
            return False
    
    def _load_json(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        从文件加载JSON数据
        
        Args:
            file_path: 文件路径
            
        Returns:
            加载的数据，如果失败返回None
        """
        try:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return None
        except Exception as e:
            self.logger.error(f"加载文件失败 {file_path}: {str(e)}")
            return None
    
    def save_session(self, session_id: str, session_data: Dict[str, Any]) -> bool:
        """
        保存用户会话数据
        
        Args:
            session_id: 会话ID
            session_data: 会话数据
            
        Returns:
            是否保存成功
        """
        session_data['updated_at'] = datetime.now().isoformat()
        file_path = self.sessions_dir / f"{session_id}.json"
        return self._save_json(file_path, session_data)
    
    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        加载用户会话数据
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话数据
        """
        file_path = self.sessions_dir / f"{session_id}.json"
        return self._load_json(file_path)
    
    def update_session_context(self, session_id: str, context_key: str, context_value: Any) -> bool:
        """
        更新会话上下文
        
        Args:
            session_id: 会话ID
            context_key: 上下文键
            context_value: 上下文值
            
        Returns:
            是否更新成功
        """
        session_data = self.load_session(session_id)
        if session_data is None:
            session_data = {
                "context": {},
                "created_at": datetime.now().isoformat()
            }
        
        if "context" not in session_data:
            session_data["context"] = {}
        
        session_data["context"][context_key] = context_value
        return self.save_session(session_id, session_data)
    
    def cache_tenders(self, tenders: List[Dict[str, Any]], cache_key: str = None) -> bool:
        """
        缓存招标项目数据
        
        Args:
            tenders: 招标项目列表
            cache_key: 缓存键，如果不提供则使用时间戳
            
        Returns:
            是否缓存成功
        """
        if cache_key is None:
            cache_key = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        cache_data = {
            "tenders": tenders,
            "cached_at": datetime.now().isoformat(),
            "count": len(tenders)
        }
        
        file_path = self.tenders_dir / f"cache_{cache_key}.json"
        return self._save_json(file_path, cache_data)
    
    def get_cached_tenders(self, cache_key: str) -> Optional[List[Dict[str, Any]]]:
        """
        获取缓存的招标项目
        
        Args:
            cache_key: 缓存键
            
        Returns:
            招标项目列表
        """
        file_path = self.tenders_dir / f"cache_{cache_key}.json"
        cache_data = self._load_json(file_path)
        
        if cache_data and "tenders" in cache_data:
            return cache_data["tenders"]
        return None
    
    def list_tender_caches(self) -> List[Dict[str, Any]]:
        """
        列出所有招标缓存
        
        Returns:
            缓存信息列表
        """
        caches = []
        for file_path in self.tenders_dir.glob("cache_*.json"):
            cache_data = self._load_json(file_path)
            if cache_data:
                cache_info = {
                    "cache_key": file_path.stem.replace("cache_", ""),
                    "cached_at": cache_data.get("cached_at"),
                    "count": cache_data.get("count", 0)
                }
                caches.append(cache_info)
        
        # 按时间排序
        caches.sort(key=lambda x: x["cached_at"], reverse=True)
        return caches
    
    def save_analysis(self, analysis_id: str, analysis_data: Dict[str, Any]) -> bool:
        """
        保存分析结果
        
        Args:
            analysis_id: 分析ID
            analysis_data: 分析数据
            
        Returns:
            是否保存成功
        """
        analysis_data['saved_at'] = datetime.now().isoformat()
        file_path = self.analysis_dir / f"{analysis_id}.json"
        return self._save_json(file_path, analysis_data)
    
    def load_analysis(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """
        加载分析结果
        
        Args:
            analysis_id: 分析ID
            
        Returns:
            分析数据
        """
        file_path = self.analysis_dir / f"{analysis_id}.json"
        return self._load_json(file_path)
    
    def list_analyses(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        列出分析结果
        
        Args:
            limit: 返回数量限制
            
        Returns:
            分析结果列表
        """
        analyses = []
        for file_path in self.analysis_dir.glob("*.json"):
            analysis_data = self._load_json(file_path)
            if analysis_data:
                analysis_info = {
                    "analysis_id": file_path.stem,
                    "analysis_type": analysis_data.get("analysis_type"),
                    "saved_at": analysis_data.get("saved_at"),
                    "summary": analysis_data.get("result", "")[:100] + "..." if len(analysis_data.get("result", "")) > 100 else analysis_data.get("result", "")
                }
                analyses.append(analysis_info)
        
        # 按时间排序并限制数量
        analyses.sort(key=lambda x: x["saved_at"], reverse=True)
        return analyses[:limit]
    
    def save_project(self, project_id: str, project_data: Dict[str, Any]) -> bool:
        """
        保存项目信息
        
        Args:
            project_id: 项目ID
            project_data: 项目数据
            
        Returns:
            是否保存成功
        """
        project_data['saved_at'] = datetime.now().isoformat()
        file_path = self.tenders_dir / f"project_{project_id}.json"
        return self._save_json(file_path, project_data)
    
    def load_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        加载项目信息
        
        Args:
            project_id: 项目ID
            
        Returns:
            项目数据
        """
        file_path = self.tenders_dir / f"project_{project_id}.json"
        return self._load_json(file_path)
    
    def cache_project(self, project_id, project_data):
        """缓存招标项目"""
        projects_file = os.path.join(self.data_dir, "cached_projects.json")
        
        # 加载现有缓存
        cached_projects = {}
        if os.path.exists(projects_file):
            try:
                with open(projects_file, 'r', encoding='utf-8') as f:
                    cached_projects = json.load(f)
            except Exception as e:
                print(f"加载缓存项目失败: {e}")
        
        # 添加新项目
        cached_projects[project_id] = {
            **project_data,
            "cached_at": datetime.now().isoformat()
        }
        
        # 保存缓存
        try:
            with open(projects_file, 'w', encoding='utf-8') as f:
                json.dump(cached_projects, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存缓存项目失败: {e}")
    
    def get_cached_projects(self, limit=100):
        """获取缓存的招标项目"""
        projects_file = os.path.join(self.data_dir, "cached_projects.json")
        if not os.path.exists(projects_file):
            return {}
        
        try:
            with open(projects_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载缓存项目失败: {e}")
            return {}
    
    def search_projects(self, keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        搜索项目
        
        Args:
            keyword: 搜索关键词
            limit: 返回数量限制
            
        Returns:
            匹配的项目列表
        """
        projects = []
        keyword_lower = keyword.lower()
        
        for file_path in self.tenders_dir.glob("project_*.json"):
            project_data = self._load_json(file_path)
            if project_data:
                # 在项目标题、描述等字段中搜索关键词
                searchable_text = (
                    project_data.get("title", "") + " " +
                    project_data.get("description", "") + " " +
                    project_data.get("content", "")
                ).lower()
                
                if keyword_lower in searchable_text:
                    project_info = {
                        "project_id": file_path.stem.replace("project_", ""),
                        "title": project_data.get("title", "未知项目"),
                        "saved_at": project_data.get("saved_at"),
                        "summary": project_data.get("description", "")[:100] + "..." if len(project_data.get("description", "")) > 100 else project_data.get("description", "")
                    }
                    projects.append(project_info)
        
        # 按时间排序并限制数量
        projects.sort(key=lambda x: x["saved_at"], reverse=True)
        return projects[:limit]
    
    def cleanup_old_data(self, days: int = 30) -> Dict[str, int]:
        """
        清理旧数据
        
        Args:
            days: 保留天数
            
        Returns:
            清理统计信息
        """
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days)
        cleanup_stats = {
            "sessions_cleaned": 0,
            "caches_cleaned": 0,
            "analyses_cleaned": 0
        }
        
        # 清理会话数据
        for file_path in self.sessions_dir.glob("*.json"):
            data = self._load_json(file_path)
            if data and "updated_at" in data:
                try:
                    updated_at = datetime.fromisoformat(data["updated_at"])
                    if updated_at < cutoff_date:
                        file_path.unlink()
                        cleanup_stats["sessions_cleaned"] += 1
                except Exception as e:
                    self.logger.warning(f"清理会话文件时出错 {file_path}: {str(e)}")
        
        # 清理缓存数据
        for file_path in self.tenders_dir.glob("cache_*.json"):
            data = self._load_json(file_path)
            if data and "cached_at" in data:
                try:
                    cached_at = datetime.fromisoformat(data["cached_at"])
                    if cached_at < cutoff_date:
                        file_path.unlink()
                        cleanup_stats["caches_cleaned"] += 1
                except Exception as e:
                    self.logger.warning(f"清理缓存文件时出错 {file_path}: {str(e)}")
        
        # 清理分析数据
        for file_path in self.analysis_dir.glob("*.json"):
            data = self._load_json(file_path)
            if data and "saved_at" in data:
                try:
                    saved_at = datetime.fromisoformat(data["saved_at"])
                    if saved_at < cutoff_date:
                        file_path.unlink()
                        cleanup_stats["analyses_cleaned"] += 1
                except Exception as e:
                    self.logger.warning(f"清理分析文件时出错 {file_path}: {str(e)}")
        
        return cleanup_stats
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """
        获取存储统计信息
        
        Returns:
            存储统计信息
        """
        stats = {
            "sessions_count": len(list(self.sessions_dir.glob("*.json"))),
            "tenders_cache_count": len(list(self.tenders_dir.glob("cache_*.json"))),
            "projects_count": len(list(self.tenders_dir.glob("project_*.json"))),
            "analyses_count": len(list(self.analysis_dir.glob("*.json"))),
            "total_files": 0,
            "storage_size_mb": 0
        }
        
        # 计算总文件数和存储大小
        total_size = 0
        total_files = 0
        
        for dir_path in [self.sessions_dir, self.tenders_dir, self.analysis_dir]:
            for file_path in dir_path.glob("*.json"):
                total_files += 1
                total_size += file_path.stat().st_size
        
        stats["total_files"] = total_files
        stats["storage_size_mb"] = round(total_size / (1024 * 1024), 2)
        
        return stats

# 使用示例
if __name__ == "__main__":
    # 创建数据存储实例
    store = SimpleDataStore()
    
    # 测试会话保存
    session_data = {
        "user_info": {"name": "测试用户", "company": "测试公司"},
        "current_journey_step": "opportunity_discovery",
        "context": {"search_history": [], "current_projects": []}
    }
    
    store.save_session("test_session_001", session_data)
    print("会话数据已保存")
    
    # 测试会话加载
    loaded_session = store.load_session("test_session_001")
    print(f"加载的会话数据: {loaded_session}")
    
    # 测试招标缓存
    tenders = [
        {"title": "测试项目1", "budget": "100万", "deadline": "2024-02-01"},
        {"title": "测试项目2", "budget": "200万", "deadline": "2024-02-15"}
    ]
    
    store.cache_tenders(tenders, "test_cache")
    print("招标数据已缓存")
    
    # 获取存储统计
    stats = store.get_storage_stats()
    print(f"存储统计: {stats}")