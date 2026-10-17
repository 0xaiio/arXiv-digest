#!/bin/sh
# 安装 arXiv-digest 的 git hooks（post-commit 自动 push）。
# 用法： sh tools/git-hooks/install.sh        （在仓库根或任意目录均可）
# 说明：hooks 不被 git 跟踪，clone 之后需要跑一次本脚本；重复执行是幂等的。
set -e
root=$(git rev-parse --show-toplevel)
hooks="$root/.git/hooks"
mkdir -p "$hooks"
for f in post-commit; do
  cp "$root/tools/git-hooks/$f" "$hooks/$f"
  chmod +x "$hooks/$f"
  echo "installed: $hooks/$f"
done
echo "远程 origin: $(git config --get remote.origin.url)"
echo "验证： sh .git/hooks/post-commit   （应打印 [auto-push] 已推送…）"
