#!/bin/bash

# ============================================
# 版本迭代脚本
# ============================================
# 功能：自动备份项目为 tar 包，并将版本号加 1
# 使用方法：从任意目录运行此脚本
# ============================================

set -e  # 遇到错误立即退出

# 获取项目根目录（脚本所在目录的父目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 配置（使用绝对路径）
VERSION_FILE="${PROJECT_ROOT}/VERSION"
BACKUP_DIR="${PROJECT_ROOT}/backups"
PROJECT_DIR="${PROJECT_ROOT}"

# ============================================
# 辅助函数
# ============================================

log_info() {
    echo "[INFO] $1"
}

log_error() {
    echo "[ERROR] $1" >&2
}

ensure_directory() {
    local dir="$1"
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir" || {
            log_error "无法创建目录：$dir"
            exit 1
        }
        log_info "创建目录：$dir"
    fi
}

ensure_writable() {
    local target="$1"
    if [ -e "$target" ] && [ ! -w "$target" ]; then
        log_error "无法写入：$target"
        log_error "请检查文件权限或手动运行：chmod +w $target"
        exit 1
    fi
}

write_file() {
    local file="$1"
    local content="$2"
    echo "$content" > "$file" || {
        log_error "无法写入文件：$file"
        exit 1
    }
}

# ============================================
# 主程序
# ============================================

echo "========================================"
echo "版本迭代脚本"
echo "========================================"
echo "项目根目录：${PROJECT_ROOT}"
echo ""

# 1. 确保备份目录存在且可写
ensure_directory "${BACKUP_DIR}"
ensure_writable "${BACKUP_DIR}"

# 2. 检查版本文件
if [ ! -f "${VERSION_FILE}" ]; then
    log_info "版本文件不存在，创建初始版本"
    CURRENT_VERSION="1.0.0"
    write_file "${VERSION_FILE}" "${CURRENT_VERSION}"
else
    ensure_writable "${VERSION_FILE}"
    CURRENT_VERSION=$(cat "${VERSION_FILE}" | tr -d '[:space:]')
fi

log_info "当前版本：${CURRENT_VERSION}"

# 3. 解析版本号
IFS="." read -r MAJOR MINOR PATCH <<< "${CURRENT_VERSION}"

# 验证版本号格式
if [ -z "$MAJOR" ] || [ -z "$MINOR" ] || [ -z "$PATCH" ]; then
    log_error "无效的版本号格式：${CURRENT_VERSION}"
    log_error "期望格式：MAJOR.MINOR.PATCH（如 1.0.0）"
    exit 1
fi

# 4. 增加补丁版本号
NEW_PATCH=$((PATCH + 1))
NEW_VERSION="${MAJOR}.${MINOR}.${NEW_PATCH}"

log_info "新版本：${NEW_VERSION}"

# 5. 备份项目
backup_file="${BACKUP_DIR}/chaos-${NEW_VERSION}.tar.gz"
log_info "创建备份：${backup_file}"

cd "${PROJECT_ROOT}"
tar -czf "${backup_file}" \
    --exclude="backups" \
    --exclude=".git" \
    --exclude=".pytest_cache" \
    --exclude="__pycache__" \
    --exclude="*.pyc" \
    . 2>/dev/null || {
    log_error "创建备份失败"
    exit 1
}

log_info "备份创建成功"

# 6. 更新版本号
write_file "${VERSION_FILE}" "${NEW_VERSION}"

echo ""
echo "========================================"
echo "版本迭代完成"
echo "  新版本：${NEW_VERSION}"
echo "  备份文件：${backup_file}"
echo "========================================"
