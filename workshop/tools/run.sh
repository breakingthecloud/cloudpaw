#!/usr/bin/env bash
# Run CloudPaw on your machine, without deploying anything.
#
#   workshop/tools/run.sh offline [-c "avanza 1 metro"]   robot simulado + planificador por reglas: sin AWS, sin internet
#   workshop/tools/run.sh chat    [-c "avanza 1 metro"]   hablar con el robot en la terminal (el modelo corre en Bedrock)
#   workshop/tools/run.sh dev                              el agente como servicio local (agentcore dev, puerto 8081)
#   workshop/tools/run.sh say "avanza 2 metros"            hablarle al servicio de `dev` (misma sesión: el robot recuerda dónde está)
#   workshop/tools/run.sh test                             los tests (sin AWS ni modelo)
#
# chat y dev necesitan una sesión de AWS válida: AWS_PROFILE=<tu-perfil> workshop/tools/run.sh chat
# Variables: AWS_PROFILE, AWS_REGION (us-east-1 por defecto), PORT (8081), CLOUDPAW_MODEL_ID.

set -u
# With ROS 2 sourced (the ops EC2), PYTHONPATH points at ROS's own Python packages: pytest would load ROS plugins that
# need `lark`, and the agent could import ROS's copies of libraries. The uv environments here are self-contained.
unset PYTHONPATH
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PORT="${PORT:-8081}"
MODE="${1:-}"
[ $# -gt 0 ] && shift

die() { printf "\033[31m✗ %s\033[0m\n" "$1" >&2; [ -n "${2:-}" ] && printf "  → %s\n" "$2" >&2; exit 2; }
usage() { sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; }

need_node() {
  command -v node >/dev/null 2>&1 || die "No encuentro node." "fnm use 22"
  local v; v="$(node -v | sed 's/^v//')"
  [ "$(printf '%s\n%s\n' "22.13.0" "$v" | sort -V | head -n1)" = "22.13.0" ] || die "Node $v es muy antiguo (hace falta 22.13 o más)." "fnm use 22   (el repo trae .node-version)"
}
need_deps() {
  [ -x "$ROOT/app/agent/.venv/bin/python" ] || die "Faltan las dependencias de Python." "(cd app/agent && uv sync)"
}
need_aws() {
  export AWS_REGION="${AWS_REGION:-us-east-1}"
  if ! aws sts get-caller-identity >/dev/null 2>&1; then
    local p="${AWS_PROFILE:-<tu-perfil>}"
    die "No hay una sesión de AWS válida (el modelo corre en Bedrock)." "aws sso login --profile $p ; AWS_PROFILE=$p workshop/tools/run.sh $MODE      — o prueba sin AWS: workshop/tools/run.sh offline"
  fi
}

case "$MODE" in
  offline)
    need_deps
    cd "$ROOT/app/agent" && exec uv run python play.py --offline "$@"
    ;;
  chat)
    need_deps; need_aws
    cd "$ROOT/app/agent" && exec uv run python play.py "$@"
    ;;
  dev)
    need_node; need_deps; need_aws
    command -v agentcore >/dev/null 2>&1 || die "No encuentro agentcore." "pnpm add -g @aws/agentcore   (y workshop/tools/doctor.sh)"
    [ -d "$ROOT/agentcore/cdk/node_modules" ] || die "Faltan las dependencias de CDK." "(cd agentcore/cdk && pnpm install)"
    echo "Servicio local en http://127.0.0.1:$PORT  —  en otra terminal: workshop/tools/run.sh say \"avanza 2 metros\""
    cd "$ROOT" && exec agentcore dev --port "$PORT"
    ;;
  say)
    [ $# -ge 1 ] || die "Falta el mensaje." "workshop/tools/run.sh say \"avanza 2 metros\""
    need_aws
    exec python3 "$ROOT/workshop/tools/say.py" "$1" --local --port "$PORT"
    ;;
  test)
    need_deps
    cd "$ROOT/app/agent" && exec uv run --with pytest pytest -q "$@"
    ;;
  ""|-h|--help|help)
    usage
    ;;
  *)
    die "Modo desconocido: $MODE" "workshop/tools/run.sh --help"
    ;;
esac
