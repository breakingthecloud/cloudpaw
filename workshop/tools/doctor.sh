#!/usr/bin/env bash
# Checks that this machine is ready to run the CloudPaw kit: Node 22, pnpm, AgentCore CLI 1.x, uv, installed dependencies.
#
#   workshop/tools/doctor.sh           # local checks only
#   workshop/tools/doctor.sh --aws     # also checks that AWS credentials are valid (never prints the account id)
#
# Exit code 0 = ready, 1 = something to fix (each failure says how).

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FAILS=0
ok()   { printf "  \033[32m✓\033[0m %s\n" "$1"; }
bad()  { printf "  \033[31m✗\033[0m %s\n      → %s\n" "$1" "$2"; FAILS=$((FAILS + 1)); }
warn() { printf "  \033[33m!\033[0m %s\n      → %s\n" "$1" "$2"; }
# version_ge A B  → true when A >= B (dotted versions)
version_ge() { [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -n1)" = "$2" ]; }

echo "CloudPaw doctor ($ROOT)"

echo "Node"
if command -v node >/dev/null 2>&1; then
  NODE_V="$(node -v | sed 's/^v//')"
  if version_ge "$NODE_V" "22.13.0"; then ok "node $NODE_V"; else bad "node $NODE_V is too old (need >= 22.13)" "fnm use 22   (this folder has a .node-version; or: fnm install 22 && fnm default 22)"; fi
else
  bad "node not found" "install it with fnm: fnm install 22 && fnm use 22"
fi

echo "pnpm"
if command -v pnpm >/dev/null 2>&1 && PNPM_V="$(pnpm -v 2>/dev/null | tail -n1)" && [ -n "$PNPM_V" ] && [[ "$PNPM_V" =~ ^[0-9]+\. ]]; then
  ok "pnpm $PNPM_V"
else
  bad "pnpm does not run (pnpm 11 needs Node >= 22.13)" "fnm use 22, then: corepack enable   (or: npm i -g pnpm)"
fi
if [ -z "${PNPM_HOME:-}" ]; then
  warn "PNPM_HOME is not set (global pnpm installs have nowhere to go)" "run: pnpm setup   and open a new terminal"
fi

echo "AgentCore CLI"
if command -v agentcore >/dev/null 2>&1; then
  AC_FIRST="$(command -v agentcore)"
  # the old 0.x CLI prints a terminal escape after the version: strip escapes and keep the first version-looking line
  AC_V="$(agentcore --version 2>/dev/null | sed 's/\x1b\[[0-9;?]*[a-zA-Z]//g' | grep -E '^[0-9]+\.[0-9]+' | head -n1)"
  if [[ "$AC_V" =~ ^[0-9]+\.[0-9]+ ]] && version_ge "$AC_V" "1.0.0"; then
    ok "agentcore $AC_V  ($AC_FIRST)"
  else
    bad "agentcore resolves to ${AC_V:-an unreadable version} ($AC_FIRST); need 1.x" "pnpm add -g @aws/agentcore ; make sure \$PNPM_HOME/bin comes first in PATH. An old pip package can also shadow it: pip uninstall bedrock-agentcore-starter-toolkit"
  fi
  COUNT="$(which -a agentcore 2>/dev/null | sort -u | wc -l | tr -d ' ')"
  if [ "$COUNT" -gt 1 ]; then warn "$COUNT 'agentcore' executables on PATH (the first one wins)" "which -a agentcore   — remove the old ones when you are sure nothing uses them"; fi
else
  bad "agentcore not found" "pnpm add -g @aws/agentcore"
fi
if command -v pip >/dev/null 2>&1 && pip show bedrock-agentcore-starter-toolkit >/dev/null 2>&1; then
  warn "the old pip package bedrock-agentcore-starter-toolkit is installed (it can shadow the new CLI)" "pip uninstall bedrock-agentcore-starter-toolkit"
fi

echo "Python"
if command -v uv >/dev/null 2>&1; then ok "uv $(uv --version | awk '{print $2}') (it provides Python 3.10+ for the project)"; else bad "uv not found" "brew install uv   or see https://docs.astral.sh/uv/"; fi

echo "Project dependencies"
if [ -x "$ROOT/agentcore/cdk/node_modules/.bin/cdk" ]; then ok "agentcore/cdk dependencies installed"; else bad "agentcore/cdk dependencies missing (agentcore build would fail)" "(cd agentcore/cdk && pnpm install)"; fi
if [ -x "$ROOT/app/agent/.venv/bin/python" ]; then ok "app/agent virtual environment present"; else bad "app/agent virtual environment missing" "(cd app/agent && uv sync)"; fi

echo "Repository hygiene"
if [ -f "$ROOT/agentcore/aws-targets.json" ] && [ "$(tr -d '[:space:]' < "$ROOT/agentcore/aws-targets.json")" != "[]" ]; then
  warn "agentcore/aws-targets.json contains a deployment target (it has your AWS account id)" "do not commit it: git update-index --skip-worktree agentcore/aws-targets.json"
else
  ok "agentcore/aws-targets.json is empty"
fi

if [ "${1:-}" = "--aws" ]; then
  echo "AWS"
  if aws sts get-caller-identity >/dev/null 2>&1; then ok "AWS credentials are valid (region: ${AWS_REGION:-${AWS_DEFAULT_REGION:-$(aws configure get region 2>/dev/null || echo unset)}})"; else bad "AWS credentials are not valid" "aws sso login --profile <profile>   or export credentials for this shell"; fi
fi

echo
if [ "$FAILS" -eq 0 ]; then echo "Ready."; else echo "$FAILS problem(s) to fix."; fi
exit $([ "$FAILS" -eq 0 ] && echo 0 || echo 1)
