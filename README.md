# CloudPaw · un cerebro de texto para un cuadrúpedo

Un agente hecho con **Strands Agents**, desplegable en **Amazon Bedrock AgentCore**, que convierte órdenes de texto en español o inglés
("avanza 2 metros y gira a la derecha", "turn left 45 degrees") en llamadas a **herramientas acotadas** de un robot cuadrúpedo.
Hoy el robot es simulado; el día que exista el hardware solo cambia el *driver*.

Workshop del proyecto CloudPaw (UTEC · IEEE RAS), 18 de noviembre de 2026.

> **EN:** a Strands agent (tools only) that turns Spanish/English text into bounded commands for a quadruped robot, deployable to
> Amazon Bedrock AgentCore. The robot is simulated; a real driver only needs to implement `RobotDriver`.
> Safety limits live in code, not in the prompt, and a stop word stops the robot before any model reads the message.

## La idea en una línea

**El modelo propone, el código dispone.** El agente solo tiene 7 herramientas; cada una valida sus argumentos y el estado del robot.

| Capa | Qué hace | Valor |
|---|---|---|
| Rango por llamada | Rechaza lo que se sale de rango | 0.1–2 m · 1–180° |
| Acciones por mensaje | Corta cadenas y bucles | 6 |
| Distancia por mensaje | Evita trocear un movimiento largo | 6 m |
| Reflejo de parada | `stop` antes de que el modelo lea el mensaje | siempre |
| Estados | Sentado no camina; siguiendo no camina | máquina de estados |

## Herramientas

`walk(direction, meters)` · `turn(side, degrees)` · `follow(target)` · `stop()` · `stand()` · `sit()` · `get_status()`

## Empezar

Necesitas: **Node 22.13 o más** (el repo lo fija en `.node-version`), **pnpm 11**, [`uv`](https://docs.astral.sh/uv/) (descarga Python 3.12 para el proyecto), la CLI de AgentCore 1.x y credenciales de AWS con acceso a Bedrock.
Con Node 20 `pnpm` 11 no arranca; `workshop/tools/doctor.sh` revisa todo esto y dice cómo arreglarlo.

```bash
fnm use 22                             # o: fnm install 22
pnpm setup                             # una vez: define PNPM_HOME (abre una terminal nueva)
pnpm add -g @aws/agentcore             # CLI 1.x
cd cloudpaw-workshop
workshop/tools/doctor.sh               # ¿todo listo?
(cd agentcore/cdk && pnpm install)
(cd app/agent && uv sync)

cd app/agent
uv run --with pytest pytest -q         # 97 tests, sin AWS
uv run python play.py --offline        # sin modelo ni internet
uv run python play.py                  # con el modelo (Bedrock)
```

Ejemplo:
```
> avanza 2 metros y luego gira a la derecha
  → walk(direction='forward', meters=2)
  → turn(side='right', degrees=90)
🐾 Listo. Avancé 2 metros y giré 90 grados a la derecha. Ahora estoy en (0, 2) metros.
```

## Como servicio (AgentCore)

Desde la raíz del proyecto:
```bash
agentcore dev --port 8081                                       # runtime local
python3 workshop/tools/say.py "avanza 2 metros" --local --port 8081
agentcore build && agentcore deploy                             # a AWS
python3 workshop/tools/say.py "avanza 2 metros"                 # el Runtime desplegado
agentcore traces runtime list --since 30m                       # qué pensó
agentcore remove all --yes && agentcore deploy --yes            # limpiar
```
`say.py` usa una sesión fija para que el robot recuerde dónde está; sin ella, `agentcore invoke` crea una sesión nueva en cada mensaje.

## Estructura

```
app/agent/            código del agente (main.py, cloudpaw/, tests/, play.py)
agentcore/            configuración del proyecto AgentCore (agentcore.json, CDK)
workshop/slides/      las slides (abrir index.html; funcionan sin internet)
workshop/guion-45min.md · checklist-previo.md · plan-b.md
workshop/tools/say.py ayudante para hablarle al Runtime con sesión fija
```

## Seguridad

- Los límites son una **segunda barrera**. La parada de emergencia debe ser **física** y el firmware debe tener sus propios límites.
- Un mensaje al agente tarda segundos: sirve para **intención**, no para control de motores.
- **No subas** `agentcore/aws-targets.json` después de desplegar: el destino `default` incluye el ID de tu cuenta. El repo ignora `agentcore/.cli/` y un test falla si aparece un ID de cuenta real.

## Estado

V1: probado en local con Claude Haiku 4.5 en Bedrock (español e inglés) y con el runtime local de AgentCore. **No** verificado todavía: el despliegue contra AWS de este proyecto, el Agent Inspector en el navegador y el costo por mensaje. Licencia: Apache-2.0 (ver `LICENSE`).
