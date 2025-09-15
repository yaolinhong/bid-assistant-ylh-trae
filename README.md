# 招标助手 (Bid Assistant)

## 📸 Demo 效果展示

<img src="demo%20效果.png" alt="Demo 效果" height="450">

基于 Kimi AI 和 Parlant 框架的智能招标助手，帮助用户高效处理招标相关业务。

### 🚀 Parlant 框架优势

采用 Parlant 对话式AI框架，为招标助手提供了强大的技术支撑：

- **🗣️ 聊天体验好**：能记住前面说了什么，对话很自然
- **🔄 会话不会乱**：可以随时切换话题，之前的内容不会丢
- **🔧 功能好扩展**：想加新功能很容易，代码结构清晰
- **🧠 理解能力强**：知道你想要什么，回答很准确
- **⚡ 开发很简单**：框架帮你搞定复杂的事，专心写业务就行

## 快速启动

```
sh ./start.sh dev # docker启动项目
sh ./start.sh logs # 查看docker日志
sh ./start.sh stop # 停止docker容器
sh ./start.sh restart # 重启docker容器
```

### 1. 环境要求
- Python 3.8+
- pip 或 conda

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 配置环境变量
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，设置你的 Kimi API 密钥
vim .env
```

在 `.env` 文件中设置：
```
KIMI_API_KEY=your_actual_kimi_api_key
```

### 4. 运行项目
```bash
python main.py
```

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

## 功能特性

### 🔍 智能搜索
- 基于博查API进行全网招标信息搜索
- 实时获取最新招标信息
- 智能去重和结果排序

### 📊 智能分析
- **风险分析**：评估技术风险、商务风险、时间风险等
- **竞争分析**：分析竞争对手和市场情况
- **资质匹配**：检查公司资质与招标要求的匹配度
- **关键信息提取**：自动提取项目编号、预算、截止时间等关键信息

### 📝 文档处理
- 招标文件智能总结
- 投标大纲自动生成
- 批量文档处理

### 💾 数据管理
- 会话数据持久化
- 招标项目缓存
- 分析结果存储
- 自动数据清理

## 技术架构

- **AI 模型**：Kimi-k2-0905-preview
- **框架**：Parlant (对话式AI框架)
- **搜索服务**：博查API (全网搜索)
- **网络请求**：aiohttp (异步HTTP客户端)
- **数据存储**：JSON文件存储



## 使用指南

### 基本对话
启动后，你可以通过自然语言与招标助手交互：

```
用户：帮我搜索办公设备采购的招标信息
助手：我来为您搜索办公设备采购相关的招标信息...

用户：分析这个招标文件的风险
助手：我将从技术风险、商务风险、时间风险等方面为您分析...
```

### 主要功能命令

1. **搜索招标信息**
   - "搜索[关键词]招标"
   - "查找[行业]相关项目"
   - "最新的[类型]采购信息"

2. **分析招标文件**
   - "分析这个招标文件"
   - "评估投标风险"
   - "检查资质要求"

3. **生成投标材料**
   - "生成投标大纲"
   - "总结招标要求"
   - "提取关键信息"

## 项目结构

```
bid-assistant/
├── main.py                 # 主程序入口
├── kimi_client.py          # Kimi API 客户端
├── kimi_nlp_service.py     # NLP 分析服务
├── web_search.py           # 网络搜索模块
├── data_store.py           # 数据存储模块
├── requirements.txt        # 依赖包列表
├── .env.example           # 环境变量模板
├── .env                   # 环境变量配置（需要创建）
├── README.md              # 项目说明
└── data/                  # 数据存储目录
    ├── sessions/          # 会话数据
    ├── projects/          # 项目缓存
    └── analysis/          # 分析结果
```

## 核心模块说明

### KimiClient
- 封装 Kimi API 调用
- 支持异步操作
- 提供多种分析方法

### WebSearchClient
- 基于博查API的全网搜索
- 结果去重和排序
- 智能信息提取

### KimiNLPService
- 文档智能分析
- 关键信息提取
- 批量处理支持

### SimpleDataStore
- 会话数据管理
- 项目信息缓存
- 分析结果存储

## 配置说明

### 环境变量
- `KIMI_API_KEY`: Kimi API 密钥（必需）
- `KIMI_MODEL`: 使用的模型名称（默认：kimi-k2-0905-preview）
- `KIMI_BASE_URL`: API 基础URL（默认：https://api.moonshot.cn/v1）
- `DATA_STORE_PATH`: 数据存储路径（默认：./data）
- `SEARCH_TIMEOUT`: 搜索超时时间（默认：30秒）

### Parlant 配置
项目使用 Parlant 框架进行对话管理，支持：
- 用户旅程定义
- 工具函数注册
- 会话状态管理
- 指导原则设置

## 开发指南

### 扩展搜索功能
在 `web_search.py` 中可以扩展搜索参数和过滤条件：

```python
async def search_with_filters(self, query, filters=None):
    # 实现带过滤条件的搜索逻辑
    pass
```

### 添加新的分析类型
在 `kimi_nlp_service.py` 中添加新的分析模板：

```python
self.analysis_templates['new_analysis'] = """
新的分析提示词模板
{content}
"""
```

### 扩展数据存储
在 `data_store.py` 中添加新的存储方法：

```python
def save_new_data_type(self, data):
    # 实现新数据类型的存储逻辑
    pass
```

## 注意事项

1. **API 密钥安全**：请妥善保管 Kimi API 密钥，不要提交到版本控制系统
2. **API调用**：博查API有调用频率限制，建议合理控制请求频率
3. **数据隐私**：处理敏感招标信息时请注意数据安全和隐私保护
4. **模型限制**：AI 分析结果仅供参考，重要决策请结合人工判断

## 故障排除

### 常见问题

1. **API 调用失败**
   - 检查 API 密钥是否正确
   - 确认网络连接正常
   - 查看 API 配额是否充足

2. **搜索结果为空**
   - 检查搜索关键词
   - 确认博查API服务正常
   - 检查API调用参数是否正确

3. **分析结果异常**
   - 检查输入文档格式
   - 确认文档内容完整
   - 查看模型响应日志

### 日志查看
项目使用 Python logging 模块，可以通过设置日志级别查看详细信息：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 许可证

本项目采用 MIT 许可证，详见 LICENSE 文件。

## 贡献

欢迎提交 Issue 和 Pull Request 来改进项目。

## 联系方式

如有问题或建议，请通过以下方式联系：
- 提交 GitHub Issue
- 发送邮件至项目维护者

## Docker 部署

### 快速开始

项目提供了完整的 Docker 容器化部署方案，支持外挂磁盘和文件热更新。

#### 1. 使用启动脚本（推荐）

```bash
# 启动开发环境（支持热更新）
./start.sh dev

# 启动生产环境
./start.sh prod

# 查看日志
./start.sh logs

# 停止服务
./start.sh stop

# 重启服务
./start.sh restart dev  # 重启开发环境
./start.sh restart prod # 重启生产环境

# 清理容器和镜像
./start.sh clean
```

#### 2. 手动使用 Docker Compose

**开发环境**（支持文件热更新）：
```bash
# 启动开发环境
docker-compose -f docker-compose.dev.yml up --build -d

# 查看日志
docker-compose -f docker-compose.dev.yml logs -f

# 停止服务
docker-compose -f docker-compose.dev.yml down
```

**生产环境**：
```bash
# 启动生产环境
docker-compose up --build -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### Docker 特性

#### 外挂磁盘挂载
- **代码目录**：`./:/app` - 项目代码实时同步
- **数据目录**：`./test_data:/app/test_data` - 数据持久化存储
- **环境配置**：`./.env:/app/.env` - 环境变量配置
- **缓存目录**：`./__pycache__:/app/__pycache__` - Python 缓存优化

#### 文件热更新
- **开发环境**：使用 `watchdog` 监听 Python 文件变化，自动重启应用
- **依赖更新**：监听 `requirements.txt` 变化，自动重新安装依赖
- **实时同步**：代码修改后立即生效，无需手动重启容器

#### 网络配置
- **应用端口**：`8800:8800` - Web 服务访问端口
- **调试端口**：`5678:5678` - 开发环境调试端口
- **Redis 端口**：`6379:6379` - 缓存服务端口

#### 环境变量管理
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑环境变量
vim .env
```

必需的环境变量：
```env
KIMI_API_KEY=your_actual_kimi_api_key
```

### 容器服务

#### 主应用服务
- **容器名称**：`bid-assistant-app` (生产) / `bid-assistant-dev` (开发)
- **基础镜像**：`python:3.12-slim`
- **工作目录**：`/app`
- **启动命令**：`python main.py`

#### Redis 缓存服务
- **容器名称**：`bid-assistant-redis` (生产) / `bid-assistant-redis-dev` (开发)
- **基础镜像**：`redis:7-alpine`
- **数据持久化**：支持 AOF 持久化

### 开发工作流

1. **初始化环境**
   ```bash
   # 配置环境变量
   cp .env.example .env
   vim .env
   
   # 启动开发环境
   ./start.sh dev
   ```

2. **开发调试**
   ```bash
   # 查看实时日志
   ./start.sh logs
   
   # 修改代码文件（自动重启）
   vim main.py
   
   # 添加新依赖（自动重新安装）
   echo "new-package==1.0.0" >> requirements.txt
   ```

3. **生产部署**
   ```bash
   # 停止开发环境
   ./start.sh stop
   
   # 启动生产环境
   ./start.sh prod
   ```

### 故障排除

#### Docker 相关问题

1. **容器启动失败**
   ```bash
   # 查看容器日志
   docker-compose logs bid-assistant
   
   # 检查容器状态
   docker-compose ps
   ```

2. **端口冲突**
   ```bash
   # 检查端口占用
   lsof -i :8800
   
   # 修改 docker-compose.yml 中的端口映射
   ports:
     - "8801:8800"  # 改为其他端口
   ```

3. **文件权限问题**
   ```bash
   # 修复文件权限
   sudo chown -R $USER:$USER .
   chmod +x start.sh
   ```

4. **热更新不生效**
   ```bash
   # 重启开发环境
   ./start.sh restart dev
   
   # 检查文件挂载
   docker exec -it bid-assistant-dev ls -la /app
   ```

#### 性能优化

1. **构建缓存优化**
   - 使用 `.dockerignore` 排除不必要文件
   - 分层构建，优先安装依赖

2. **运行时优化**
   - 使用 Redis 缓存提升性能
   - 配置健康检查确保服务稳定

---

**免责声明**：本工具仅用于辅助招标业务处理，所有分析结果仅供参考。用户应当根据实际情况进行判断和决策，开发者不承担因使用本工具而产生的任何责任。