#!/bin/bash

# 飞机电磁环境效应仿真支持平台 - Linux安装脚本
# 适用于局域网环境安装

set -e  # 遇到错误立即退出

echo "================================================"
echo "飞机电磁环境效应仿真支持平台 - 安装程序"
echo "================================================"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否以root权限运行
check_root() {
    if [[ $EUID -eq 0 ]]; then
        log_warn "正在以root用户运行，建议使用普通用户安装"
    fi
}

# 检查系统架构
check_architecture() {
    ARCH=$(uname -m)
    if [[ "$ARCH" != "x86_64" ]]; then
        log_warn "检测到系统架构: $ARCH，建议使用x86_64架构"
    fi
}

# 安装系统依赖
install_system_deps() {
    log_info "安装系统依赖包..."
    
    if command -v apt > /dev/null 2>&1; then
        # Ubuntu/Debian
        sudo apt update
        sudo apt install -y build-essential zlib1g-dev libncurses5-dev \
            libgdbm-dev libnss3-dev libssl-dev libreadline-dev \
            libffi-dev libsqlite3-dev libbz2-dev liblzma-dev \
            wget curl
    elif command -v yum > /dev/null 2>&1; then
        # CentOS/RHEL/Rocky
        sudo yum groupinstall -y "Development Tools"
        sudo yum install -y zlib-devel bzip2-devel openssl-devel \
            ncurses-devel sqlite-devel readline-devel tk-devel \
            gdbm-devel libffi-devel xz-devel wget curl
    elif command -v dnf > /dev/null 2>&1; then
        # Fedora
        sudo dnf groupinstall -y "Development Tools"
        sudo dnf install -y zlib-devel bzip2-devel openssl-devel \
            ncurses-devel sqlite-devel readline-devel tk-devel \
            gdbm-devel libffi-devel xz-devel wget curl
    else
        log_error "不支持的包管理器，请手动安装编译工具"
        exit 1
    fi
}

# 检查Python是否已安装
check_python() {
    log_info "检查Python环境..."
    
    if command -v python3.10 > /dev/null 2>&1; then
        PYTHON_VERSION=$(python3.10 --version 2>&1 | awk '{print $2}')
        log_info "检测到已安装Python: $PYTHON_VERSION"
        return 0
    else
        log_warn "未找到Python 3.10，将进行安装..."
        return 1
    fi
}

# 安装Python 3.10.4
install_python() {
    log_info "开始安装Python 3.10.4..."
    
    # 检查是否已有Python安装包
    if [[ -f "python_installer/Python-3.10.4.tar.xz" ]]; then
        log_info "使用本地Python源码包安装..."
        tar -xf python_installer/Python-3.10.4.tar.xz -C /tmp/
    else
        log_info "下载Python 3.10.4源码包..."
        wget -O /tmp/Python-3.10.4.tar.xz https://www.python.org/ftp/python/3.10.4/Python-3.10.4.tar.xz
        tar -xf /tmp/Python-3.10.4.tar.xz -C /tmp/
    fi
    
    cd /tmp/Python-3.10.4
    
    log_info "配置Python编译选项..."
    ./configure --enable-optimizations --prefix=/usr/local/python3.10.4 \
                --enable-shared --with-system-ffi --with-ensurepip=install
    
    log_info "编译Python（此过程可能需要较长时间）..."
    make -j$(nproc)
    
    log_info "安装Python..."
    sudo make altinstall
    
    # 创建软链接
    sudo ln -sf /usr/local/python3.10.4/bin/python3.10 /usr/local/bin/python3.10 2>/dev/null || true
    sudo ln -sf /usr/local/python3.10.4/bin/pip3.10 /usr/local/bin/pip3.10 2>/dev/null || true
    
    # 配置共享库路径
    echo '/usr/local/python3.10.4/lib' | sudo tee /etc/ld.so.conf.d/python3.10.conf > /dev/null
    sudo ldconfig
    
    cd -
}

# 安装Python依赖包
install_python_deps() {
    log_info "安装Python依赖包..."
    
    # 使用本地包目录安装（局域网环境）
    if [[ -d "packages" ]]; then
        log_info "使用本地依赖包安装..."
        python3.10 -m pip install --no-index --find-links=./packages -r requirements.txt
    else
        log_info "使用PyPI安装依赖（可配置国内镜像）..."
        # 可选：使用国内镜像源
        python3.10 -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
    fi
}

# 创建运行脚本
create_run_script() {
    log_info "创建运行脚本..."
    
    cat > run.sh << 'EOF'
#!/bin/bash
# 飞机电磁环境效应仿真支持平台 - 运行脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查Python环境
if ! command -v python3.10 > /dev/null 2>&1; then
    echo "错误: 未找到Python 3.10，请先运行install.sh安装"
    exit 1
fi

# 检查依赖
if ! python3.10 -c "import streamlit" > /dev/null 2>&1; then
    echo "错误: 依赖未安装，请先运行install.sh安装"
    exit 1
fi

echo "启动飞机电磁环境效应仿真支持平台..."
echo "访问地址: http://localhost:8501"
echo "按Ctrl+C停止服务"

# 运行应用
python3.10 -m streamlit run app.py --server.port=8501 --server.address=0.0.0.0
EOF
    
    chmod +x run.sh
    log_info "运行脚本已创建: ./run.sh"
}

# 设置环境变量（可选）
setup_environment() {
    log_info "配置环境变量..."
    
    # 检测当前shell类型
    if [[ -n "$BASH_VERSION" ]]; then
        SHELL_RC="$HOME/.bashrc"
    elif [[ -n "$ZSH_VERSION" ]]; then
        SHELL_RC="$HOME/.zshrc"
    else
        SHELL_RC="$HOME/.bashrc"
    fi
    
    # 添加Python路径到PATH
    if ! grep -q "python3.10.4/bin" "$SHELL_RC" 2>/dev/null; then
        echo 'export PATH="/usr/local/python3.10.4/bin:$PATH"' >> "$SHELL_RC"
        log_info "已添加Python路径到 $SHELL_RC"
        log_info "请执行 'source $SHELL_RC' 或重新登录使配置生效"
    fi
}

# 验证安装
verify_installation() {
    log_info "验证安装..."
    
    if command -v python3.10 > /dev/null 2>&1; then
        log_info "✓ Python 3.10.4 安装成功"
    else
        log_error "✗ Python 安装失败"
        exit 1
    fi
    
    if python3.10 -c "import streamlit, numpy" > /dev/null 2>&1; then
        log_info "✓ Python依赖包安装成功"
    else
        log_error "✗ 依赖包安装失败"
        exit 1
    fi
    
    if [[ -f "run.sh" ]]; then
        log_info "✓ 运行脚本创建成功"
    fi
}

# 显示安装完成信息
show_completion() {
    echo ""
    echo "================================================"
    echo "安装完成！"
    echo "================================================"
    echo ""
    echo "下一步操作："
    echo "1. 运行应用程序: ./run.sh"
    echo "2. 在浏览器中访问: http://localhost:8501"
    echo "3. 局域网访问: http://$(hostname -I | awk '{print $1}'):8501"
    echo ""
    echo "如需配置数据库，请编辑 config.ini 文件"
    echo "更多信息请参考安装配置手册"
    echo ""
}

# 主安装流程
main() {
    log_info "开始安装飞机电磁环境效应仿真支持平台..."
    
    check_root
    check_architecture
    install_system_deps
    if ! check_python; then
        install_python
    fi
    install_python_deps
    create_run_script
    setup_environment
    verify_installation
    show_completion
}

# 执行主函数
main "$@"