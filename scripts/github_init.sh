#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# ============================================================
# 自动化 GitHub 初始化脚本
# 执行前请先填写下方 [必填] 信息
# ============================================================

# --------------- [必填] 修改以下内容 ---------------

# 1. GitHub 仓库归属：你的用户名或组织名
#    例如: GITHUB_OWNER="wengyuho" 或 GITHUB_OWNER="my-org"
GITHUB_OWNER="hooootk"

# 2. 仓库可见性：public 或 private
REPO_VISIBILITY="public"

# 3. 仓库描述（可选）
REPO_DESCRIPTION="零风险纸面交易模拟平台 — LLM 多智能体 + 24 因子回测引擎"

# ---------------------------------------------------

REPO_NAME="paper-trading-project"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ---- 前置检查 ----
command -v git >/dev/null 2>&1 || err "请先安装 Git: https://git-scm.com"
command -v gh  >/dev/null 2>&1 || err "请先安装 GitHub CLI: https://cli.github.com"

gh auth status >/dev/null 2>&1 || err "请先登录 gh: 运行 gh auth login"

if [ "$GITHUB_OWNER" = "YOUR_GITHUB_USERNAME_OR_ORG" ]; then
  err "请编辑此脚本，将 GITHUB_OWNER 改为你的 GitHub 用户名或组织名"
fi

log "检查通过：Git / gh CLI / 认证 均已就绪"

# ---- 1. 初始化 Git 仓库 ----
if [ -d .git ]; then
  warn "已有 .git 目录，跳过 git init"
else
  log "初始化 Git 仓库..."
  git init
fi

# ---- 2. 创建 .env 检查占位文件（确保 .env 不被提交） ----
# .gitignore 已包含 .env，这里做个二次确认
if [ -f .env ]; then
  warn "检测到 .env 文件存在，确保其已被 .gitignore 排除..."
  git check-ignore .env >/dev/null 2>&1 || {
    warn ".env 未被 .gitignore 忽略，自动追加..."
    echo ".env" >> .gitignore
  }
fi

# ---- 3. 添加所有文件并创建初始 commit ----
log "添加所有文件到暂存区..."
git add .

if git diff --cached --quiet; then
  log "没有变更需要提交，跳过 commit"
else
  log "创建初始 commit..."
  git commit -m "$(cat <<'COMMIT_MSG'
chore: 初始化项目 — 纸面交易系统

双引擎架构：LLM 多智能体流水线 + 24 因子规则回测引擎。
基于 Alpaca Paper Trading API，Python 3.12+。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
COMMIT_MSG
  )"
fi

# ---- 4. 在 GitHub 创建远程仓库 ----
log "在 GitHub 上创建远程仓库 (${REPO_VISIBILITY}): ${GITHUB_OWNER}/${REPO_NAME}..."

if gh repo view "${GITHUB_OWNER}/${REPO_NAME}" >/dev/null 2>&1; then
  warn "远程仓库 ${GITHUB_OWNER}/${REPO_NAME} 已存在，跳过创建"
else
  gh repo create "${GITHUB_OWNER}/${REPO_NAME}" \
    --"${REPO_VISIBILITY}" \
    --description "${REPO_DESCRIPTION}" \
    --source . \
    --remote origin \
    --push
  log "仓库创建成功: https://github.com/${GITHUB_OWNER}/${REPO_NAME}"
  exit 0
fi

# ---- 5. 若仓库已存在，设置 remote 并推送 ----
if ! git remote get-url origin >/dev/null 2>&1; then
  git remote add origin "https://github.com/${GITHUB_OWNER}/${REPO_NAME}.git"
fi

log "推送到远程仓库..."
git push -u origin main 2>/dev/null || git push -u origin master

log "完成: https://github.com/${GITHUB_OWNER}/${REPO_NAME}"
