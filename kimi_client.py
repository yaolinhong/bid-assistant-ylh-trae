import asyncio
import os
from typing import Dict, Any, List, Optional
from openai import AsyncOpenAI
import json
import logging

class KimiClient:
    """Kimi API客户端，使用OpenAI Python包调用Kimi API"""
    
    def __init__(self, api_key: str, model: str = "kimi-k2-0905-preview", base_url: str = "https://api.moonshot.cn/v1"):
        """
        初始化Kimi客户端
        
        Args:
            api_key: Kimi API密钥
            model: 使用的模型名称，默认为kimi-k2-0905-preview
            base_url: API基础URL
        """
        self.api_key = api_key
        self.model = model
        self.default_model = model
        self.base_url = base_url
        
        # 初始化OpenAI客户端，指向Kimi API
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )
        
        # 设置日志
        self.logger = logging.getLogger(__name__)
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.client.close()
    
    async def chat_completion(self, messages: List[Dict[str, str]], model: Optional[str] = None, **kwargs) -> str:
        """
        调用Kimi聊天完成API
        
        Args:
            messages: 消息列表
            model: 模型名称，如果不指定则使用默认模型
            **kwargs: 其他参数
            
        Returns:
            API响应内容
        """
        try:
            response = await self.client.chat.completions.create(
                model=model or self.default_model,
                messages=messages,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"Kimi API调用失败: {str(e)}")
            raise
    
    async def analyze(self, content: str, analysis_type: str = "comprehensive") -> str:
        """
        使用Kimi进行内容分析
        
        Args:
            content: 要分析的内容
            analysis_type: 分析类型
            
        Returns:
            分析结果
        """
        system_prompts = {
            "risk": "你是一个专业的招投标风险分析师。请分析项目的技术风险、商务风险、时间风险和合规风险，并提供具体的风险缓解建议。",
            "competition": "你是一个市场竞争分析专家。请分析招标项目的竞争态势，包括可能的竞争对手、市场准入门槛、竞争优势等。",
            "qualification": "你是一个资质评估专家。请分析招标项目的资质要求，评估参与门槛，并提供资质准备建议。",
            "comprehensive": "你是一个专业的招投标顾问。请对项目进行全面分析，包括机会评估、风险分析、竞争态势、资质要求等，并提供投标建议。"
        }
        
        system_prompt = system_prompts.get(analysis_type, system_prompts["comprehensive"])
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content}
        ]
        
        return await self.chat_completion(messages)
    
    async def risk_analysis(self, project_info: str) -> str:
        """
        项目风险分析
        
        Args:
            project_info: 项目信息
            
        Returns:
            风险分析结果
        """
        prompt = f"""
        请对以下招标项目进行风险分析，重点关注：
        1. 技术实现风险
        2. 时间进度风险
        3. 成本控制风险
        4. 合规性风险
        5. 市场竞争风险
        
        项目信息：
        {project_info}
        
        请提供具体的风险点和相应的缓解措施建议。
        """
        
        messages = [
            {"role": "system", "content": "你是一个专业的项目风险评估专家，擅长识别和分析招投标项目中的各种风险因素。"},
            {"role": "user", "content": prompt}
        ]
        
        return await self.chat_completion(messages)
    
    async def competition_analysis(self, project_info: str, company_info: str = "") -> str:
        """
        竞争分析
        
        Args:
            project_info: 项目信息
            company_info: 公司信息
            
        Returns:
            竞争分析结果
        """
        prompt = f"""
        请分析以下招标项目的竞争态势：
        
        项目信息：
        {project_info}
        
        {f'我方公司信息：{company_info}' if company_info else ''}
        
        请分析：
        1. 可能的竞争对手类型
        2. 市场准入门槛
        3. 竞争优势要素
        4. 差异化策略建议
        5. 胜率评估
        """
        
        messages = [
            {"role": "system", "content": "你是一个市场竞争分析专家，擅长分析招投标项目的竞争环境和制定竞争策略。"},
            {"role": "user", "content": prompt}
        ]
        
        return await self.chat_completion(messages)
    
    async def qualification_check(self, project_requirements: str, company_profile: str) -> str:
        """
        资质匹配检查
        
        Args:
            project_requirements: 项目资质要求
            company_profile: 公司资质情况
            
        Returns:
            资质匹配分析结果
        """
        prompt = f"""
        请检查公司资质与项目要求的匹配情况：
        
        项目资质要求：
        {project_requirements}
        
        公司资质情况：
        {company_profile}
        
        请分析：
        1. 已满足的资质要求
        2. 缺失的资质要求
        3. 资质获取的难度和时间
        4. 是否建议参与投标
        5. 资质提升建议
        """
        
        messages = [
            {"role": "system", "content": "你是一个资质评估专家，擅长分析企业资质与项目要求的匹配度。"},
            {"role": "user", "content": prompt}
        ]
        
        return await self.chat_completion(messages)
    
    async def summarize(self, content: str, max_length: int = 500) -> str:
        """
        内容总结
        
        Args:
            content: 要总结的内容
            max_length: 最大长度
            
        Returns:
            总结结果
        """
        prompt = f"""
        请对以下内容进行总结，要求：
        1. 突出关键信息
        2. 保持逻辑清晰
        3. 控制在{max_length}字以内
        
        内容：
        {content}
        """
        
        messages = [
            {"role": "system", "content": "你是一个专业的内容总结专家，擅长提取关键信息并进行简洁表达。"},
            {"role": "user", "content": prompt}
        ]
        
        return await self.chat_completion(messages)
    
    async def extract_key_info(self, tender_document: str) -> Dict[str, Any]:
        """
        从招标文件中提取关键信息
        
        Args:
            tender_document: 招标文件内容
            
        Returns:
            提取的关键信息字典
        """
        prompt = f"""
        请从以下招标文件中提取关键信息，并以JSON格式返回：
        
        {tender_document}
        
        请提取以下信息：
        - project_name: 项目名称
        - budget: 预算金额
        - deadline: 投标截止时间
        - requirements: 主要技术要求
        - qualifications: 资质要求
        - contact_info: 联系方式
        - evaluation_criteria: 评标标准
        - key_dates: 重要时间节点
        
        请确保返回有效的JSON格式。
        """
        
        messages = [
            {"role": "system", "content": "你是一个专业的招标文件分析师，擅长从复杂文档中提取结构化信息。请始终返回有效的JSON格式。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = await self.chat_completion(messages)
            # 尝试解析JSON响应
            return json.loads(response)
        except json.JSONDecodeError:
            # 如果JSON解析失败，返回原始文本
            self.logger.warning("无法解析JSON响应，返回原始文本")
            return {"raw_response": response}
    
    async def generate_bid_outline(self, project_info: str, company_info: str) -> str:
        """
        生成投标文件大纲
        
        Args:
            project_info: 项目信息
            company_info: 公司信息
            
        Returns:
            投标文件大纲
        """
        prompt = f"""
        基于以下信息生成投标文件大纲：
        
        项目信息：
        {project_info}
        
        公司信息：
        {company_info}
        
        请生成包含以下部分的详细大纲：
        1. 商务部分
        2. 技术部分
        3. 项目管理部分
        4. 售后服务部分
        5. 附件清单
        
        每个部分请提供具体的章节结构和要点。
        """
        
        messages = [
            {"role": "system", "content": "你是一个专业的投标文件编写专家，擅长根据项目要求制定完整的投标方案结构。"},
            {"role": "user", "content": prompt}
        ]
        
        return await self.chat_completion(messages)

# 使用示例
async def example_usage():
    """使用示例"""
    api_key = os.getenv('KIMI_API_KEY')
    if not api_key:
        print("请设置KIMI_API_KEY环境变量")
        return
    
    async with KimiClient(api_key) as client:
        # 测试基本聊天功能
        messages = [
            {"role": "user", "content": "你好，请介绍一下招投标的基本流程"}
        ]
        response = await client.chat_completion(messages)
        print(f"聊天响应: {response}")
        
        # 测试项目分析功能
        project_info = "某市政府采购办公设备项目，预算100万元，要求提供电脑、打印机等设备及安装服务"
        analysis = await client.analyze(project_info, "comprehensive")
        print(f"项目分析: {analysis}")

if __name__ == "__main__":
    asyncio.run(example_usage())