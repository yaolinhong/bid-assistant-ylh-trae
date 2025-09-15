#!/bin/bash

# Docker环境测试脚本

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_message() {
    echo -e "${2}${1}${NC}"
}

print_message "=== Docker环境测试 ===" $GREEN

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    print_message "❌ Docker未安装" $RED
    exit 1
else
    print_message "✅ Docker已安装: $(docker --version)" $GREEN
fi

# 检查Docker Compose是否安装
if ! command -v docker-compose &> /dev/null; then
    print_message "❌ Docker Compose未安装" $RED
    exit 1
else
    print_message "✅ Docker Compose已安装: $(docker-compose --version)" $GREEN
fi

# 检查环境变量文件
if [ -f ".env" ]; then
    print_message "✅ .env文件存在" $GREEN
else
    print_message "⚠️  .env文件不存在，将从.env.example复制" $YELLOW
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_message "✅ 已复制.env.example到.env" $GREEN
    else
        print_message "❌ .env.example文件也不存在" $RED
        exit 1
    fi
fi

# 检查Docker配置文件
files=("Dockerfile" "docker-compose.yml" "docker-compose.dev.yml")
for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        print_message "✅ $file 存在" $GREEN
    else
        print_message "❌ $file 不存在" $RED
        exit 1
    fi
done

# 验证Docker配置语法
print_message "验证Docker Compose配置..." $YELLOW
if docker-compose config > /dev/null 2>&1; then
    print_message "✅ docker-compose.yml 语法正确" $GREEN
else
    print_message "❌ docker-compose.yml 语法错误" $RED
    docker-compose config
    exit 1
fi

if docker-compose -f docker-compose.dev.yml config > /dev/null 2>&1; then
    print_message "✅ docker-compose.dev.yml 语法正确" $GREEN
else
    print_message "❌ docker-compose.dev.yml 语法错误" $RED
    docker-compose -f docker-compose.dev.yml config
    exit 1
fi

# 检查项目文件
project_files=("main.py" "requirements.txt" "kimi_client.py" "web_search.py" "data_store.py")
for file in "${project_files[@]}"; do
    if [ -f "$file" ]; then
        print_message "✅ $file 存在" $GREEN
    else
        print_message "❌ $file 不存在" $RED
        exit 1
    fi
done

print_message "=== 所有检查通过！ ===" $GREEN
print_message "可以使用以下命令启动项目：" $YELLOW
print_message "  开发环境: ./start.sh dev" $YELLOW
print_message "  生产环境: ./start.sh prod" $YELLOW