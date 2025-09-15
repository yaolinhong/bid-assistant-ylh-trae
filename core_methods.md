# 核心方法说明

## 1. setup_journeys
**功能**: 设置用户旅程  
**作用**: 定义招投标完整流程：机会发现 → 信息分析 → 投标准备 → 投标文件提交支持  
**核心逻辑**: 通过agent.create_journey()创建用户旅程，映射招投标业务流程

## 2. setup_guidelines  
**功能**: 设置指导原则  
**作用**: 为AI助手定义不同场景下的响应规则和行为准则  
**核心逻辑**: 通过agent.create_guideline()设置条件-动作对，包括搜索、分析、文档准备等场景的处理规则

## 3. web_search_tenders
**功能**: 网络搜索招标信息  
**作用**: 根据关键词、地区、行业搜索招标项目，返回格式化的HTML表格  
**核心逻辑**: 
- 调用WebSearchClient进行搜索
- 缓存结果到data_store

## 4. analyze_project_with_kimi
**功能**: 使用Kimi AI分析项目  
**作用**: 对招标项目进行风险评估、竞争分析、资质要求等多维度分析  
**核心逻辑**:
- 根据analysis_type构建不同的分析提示词
- 调用KimiService的schematic_generator进行AI分析
- 保存分析结果到data_store
- 支持risk/competition/qualification/comprehensive四种分析类型

## 5. setup_tools
**功能**: 注册工具函数  
**作用**: 将工具函数与指导原则关联，让AI助手知道何时使用哪个工具  
**核心逻辑**: 通过agent.create_guideline()将工具绑定到特定条件，实现工具的自动调用机制