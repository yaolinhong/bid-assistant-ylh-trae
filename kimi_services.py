"""Kimi相关的辅助服务类"""

import hashlib
import logging
from typing import Dict, Any, List
from parlant.core.nlp.embedding import Embedder

class KimiTokenizer:
    """Kimi分词器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def count_tokens(self, text: str) -> int:
        """估算token数量（简化实现）"""
        # 简化的token计算：中文字符按1个token，英文单词按平均4个字符1个token
        chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        english_chars = len([c for c in text if c.isalpha() and not ('\u4e00' <= c <= '\u9fff')])
        other_chars = len(text) - chinese_chars - english_chars
        
        # 估算：中文1:1，英文4:1，其他2:1
        estimated_tokens = chinese_chars + (english_chars // 4) + (other_chars // 2)
        return max(1, estimated_tokens)
    
    def encode(self, text: str) -> List[int]:
        """编码文本为token ID列表（简化实现）"""
        # 简化实现：使用字符的ASCII/Unicode值作为token ID
        return [ord(c) for c in text[:1000]]  # 限制长度
    
    def decode(self, token_ids: List[int]) -> str:
        """解码token ID列表为文本"""
        try:
            return ''.join([chr(token_id) for token_id in token_ids if 0 <= token_id <= 1114111])
        except ValueError:
            return ""
    
    @property
    def max_tokens(self) -> int:
        """返回最大token数"""
        return 127000  # Kimi模型的上下文长度

# KimiEmbedder已移除，使用SimpleEmbedder替代

# KimiModerationService已移除，使用SimpleModerationService替代

class SimpleEmbedder(Embedder):
    """简化的嵌入模型实现"""
    
    def __init__(self):
        self._tokenizer = KimiTokenizer()
    
    @property
    def tokenizer(self):
        """分词器"""
        return self._tokenizer
    
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """生成简化的嵌入向量（基于文本哈希）"""
        embeddings = []
        for text in texts:
            # 使用简单的哈希方法生成固定维度的向量
            hash_obj = hashlib.md5(text.encode('utf-8'))
            hash_bytes = hash_obj.digest()
            
            # 将哈希值转换为1536维的浮点向量
            embedding = []
            for i in range(1536):
                byte_idx = i % len(hash_bytes)
                embedding.append((hash_bytes[byte_idx] - 128) / 128.0)
            
            embeddings.append(embedding)
        
        return embeddings
    
    async def embed_single(self, text: str) -> List[float]:
        """生成单个文本的嵌入向量"""
        embeddings = await self.embed([text])
        return embeddings[0] if embeddings else [0.0] * 1536
    
    @property
    def dimensions(self) -> int:
        """返回嵌入向量维度"""
        return 1536
    
    @property
    def max_tokens(self) -> int:
        """返回最大token数"""
        return 8191
    
    @property
    def id(self) -> str:
        """嵌入器ID"""
        return "simple-embedder"

class SimpleModerationService:
    """简化的内容审核服务"""
    
    def __init__(self):
        pass
    
    async def moderate(self, text: str) -> Dict[str, Any]:
        """简化的内容审核（基于关键词检测）"""
        # 简单的关键词过滤
        sensitive_keywords = [
            "暴力", "色情", "赌博", "毒品", "恐怖", "政治敏感",
            "violence", "porn", "gambling", "drugs", "terror"
        ]
        
        text_lower = text.lower()
        flagged = any(keyword in text_lower for keyword in sensitive_keywords)
        
        return {
            "flagged": flagged,
            "categories": {
                "hate": flagged,
                "hate/threatening": False,
                "harassment": False,
                "harassment/threatening": False,
                "self-harm": False,
                "self-harm/intent": False,
                "self-harm/instructions": False,
                "sexual": flagged,
                "sexual/minors": False,
                "violence": flagged,
                "violence/graphic": False
            },
            "category_scores": {
                "hate": 0.1 if flagged else 0.01,
                "hate/threatening": 0.01,
                "harassment": 0.01,
                "harassment/threatening": 0.01,
                "self-harm": 0.01,
                "self-harm/intent": 0.01,
                "self-harm/instructions": 0.01,
                "sexual": 0.1 if flagged else 0.01,
                "sexual/minors": 0.01,
                "violence": 0.1 if flagged else 0.01,
                "violence/graphic": 0.01
            }
        }