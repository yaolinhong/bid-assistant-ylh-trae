#!/bin/bash

# 招标助手Docker启动脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_message() {
    echo -e "${2}${1}${NC}"
}

# 检查Docker是否安装
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_message "错误: Docker未安装，请先安装Docker" $RED
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_message "错误: Docker Compose未安装，请先安装Docker Compose" $RED
        exit 1
    fi
}

# 检查环境变量文件
check_env_file() {
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            print_message "复制.env.example到.env..." $YELLOW
            cp .env.example .env
            print_message "请编辑.env文件，配置必要的API密钥" $YELLOW
        else
            print_message "警告: 未找到.env文件，请确保配置了必要的环境变量" $YELLOW
        fi
    fi
}

# 显示帮助信息
show_help() {
    echo "招标助手Docker启动脚本"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  dev     启动开发环境（支持热更新）"
    echo "  prod    启动生产环境"
    echo "  stop    停止所有服务"
    echo "  restart 重启服务"
    echo "  logs    查看日志"
    echo "  clean   清理容器和镜像"
    echo "  help    显示此帮助信息"
    echo ""
}

# 启动开发环境
start_dev() {
    print_message "启动开发环境..." $GREEN
    docker-compose -f docker-compose.dev.yml up --build -d
    print_message "开发环境已启动!" $GREEN
    print_message "应用地址: http://localhost:8800" $BLUE
    print_message "Redis地址: localhost:6379" $BLUE
    print_message "查看日志: ./start.sh logs" $YELLOW
}

# 启动生产环境
start_prod() {
    print_message "启动生产环境..." $GREEN
    docker-compose up --build -d
    print_message "生产环境已启动!" $GREEN
    print_message "应用地址: http://localhost:8800" $BLUE
    print_message "查看日志: ./start.sh logs" $YELLOW
}

# 停止服务
stop_services() {
    print_message "停止所有服务..." $YELLOW
    docker-compose down
    docker-compose -f docker-compose.dev.yml down
    print_message "所有服务已停止" $GREEN
}

# 重启服务
restart_services() {
    print_message "重启服务..." $YELLOW
    stop_services
    sleep 2
    if [ "$1" = "dev" ]; then
        start_dev
    else
        start_prod
    fi
}

# 查看日志
show_logs() {
    if docker-compose ps | grep -q "bid-assistant-dev"; then
        docker-compose -f docker-compose.dev.yml logs -f
    else
        docker-compose logs -f
    fi
}

# 清理容器和镜像
clean_docker() {
    print_message "清理Docker资源..." $YELLOW
    docker-compose down --rmi all --volumes --remove-orphans
    docker-compose -f docker-compose.dev.yml down --rmi all --volumes --remove-orphans
    print_message "清理完成" $GREEN
}

# 主逻辑
main() {
    check_docker
    check_env_file
    
    case "${1:-help}" in
        "dev")
            start_dev
            ;;
        "prod")
            start_prod
            ;;
        "stop")
            stop_services
            ;;
        "restart")
            restart_services "$2"
            ;;
        "logs")
            show_logs
            ;;
        "clean")
            clean_docker
            ;;
        "help")
            show_help
            ;;
        *)
            print_message "未知选项: $1" $RED
            show_help
            exit 1
            ;;
    esac
}

main "$@"