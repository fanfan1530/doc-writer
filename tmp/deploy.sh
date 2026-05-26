#!/usr/bin/env bash
set -e

echo "============================================"
echo "  智慧警务智能工作台 v2.0 — 离线部署脚本"
echo "============================================"
echo ""

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"

# 查找 Python
PYTHON=""
for cmd in python3 python python3.12 python3.11 python3.10; do
    if command -v "$cmd" &>/dev/null; then
        VER=$("$cmd" --version 2>&1 | grep -oP '\d+\.\d+')
        MAJ=$(echo "$VER" | cut -d. -f1)
        MIN=$(echo "$VER" | cut -d. -f2)
        if [ "$MAJ" -gt 3 ] || ([ "$MAJ" -eq 3 ] && [ "$MIN" -ge 10 ]); then
            PYTHON="$cmd"
            echo "[✓] 找到 Python: $VER"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "[✗] 未找到 Python 3.10+，请先安装"
    echo "     Ubuntu/Debian: apt install python3 python3-venv python3-pip"
    echo "     CentOS/RHEL:   yum install python3 python3-pip"
    exit 1
fi

echo ""

# 合并 wheels 分卷
echo "[1/5] 合并 Python wheels 分卷..."
WHEELS_TAR="${BASE_DIR}/wheels.tar.gz"
cat "${BASE_DIR}"/wheels.tar.gz.part-* > "$WHEELS_TAR"
echo "[✓] 合并完成"

# 解压 wheels
echo "[2/5] 解压 wheels..."
WHEELS_DIR="${BASE_DIR}/wheels"
rm -rf "$WHEELS_DIR"
mkdir -p "$WHEELS_DIR"
$PYTHON -c "import tarfile; tarfile.open(r'$WHEELS_TAR', 'r').extractall(r'$WHEELS_DIR')"
rm -f "$WHEELS_TAR"
echo "[✓] 解压完成"

# 创建虚拟环境
echo "[3/5] 创建 Python 虚拟环境..."
VENV_DIR="${BASE_DIR}/venv"
rm -rf "$VENV_DIR"
$PYTHON -m venv "$VENV_DIR"
echo "[✓] 虚拟环境创建完成"

# 安装依赖
echo "[4/5] 安装 Python 依赖（离线安装）..."
source "${VENV_DIR}/bin/activate"
pip install --no-index --find-links="$WHEELS_DIR" -r "${BASE_DIR}/app-source/requirements.txt" 2>&1 || {
    echo "[!] 部分包安装失败，尝试逐个安装..."
    for whl in "$WHEELS_DIR"/*.whl; do
        pip install --no-deps "$whl" 2>/dev/null || true
    done
}
echo "[✓] 依赖安装完成"

# 准备应用
echo "[5/5] 初始化应用..."
APP_DIR="${BASE_DIR}/app"
rm -rf "$APP_DIR"
cp -r "${BASE_DIR}/app-source" "$APP_DIR"
mkdir -p "$APP_DIR/app/knowledge/chroma_db"

# 创建 .env（如果不存在）
if [ ! -f "$APP_DIR/.env" ]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    # 生成随机密钥
    RANDOM_KEY=$($PYTHON -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/change-me-to-a-random-string/$RANDOM_KEY/" "$APP_DIR/.env"
    echo "[✓] 已生成随机 SECRET_KEY"
fi

echo ""
echo "============================================"
echo "  部署完成！"
echo "============================================"
echo ""
echo "  启动后端:"
echo "    cd ${APP_DIR}"
echo "    source ${VENV_DIR}/bin/activate"
echo "    uvicorn app.main:app --host 0.0.0.0 --port 8091"
echo ""
echo "  前端静态文件: ${BASE_DIR}/frontend-dist/"
echo "  Nginx 配置示例:"
echo "    location / {"
echo "      root ${BASE_DIR}/frontend-dist;"
echo "      try_files \$uri /index.html;"
echo "    }"
echo "    location /api {"
echo "      proxy_pass http://127.0.0.1:8091;"
echo "    }"
echo ""
echo "  首次启动会自动初始化 ChromaDB 向量库（约30秒）"
echo ""
