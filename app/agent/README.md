# CloudPaw agent (código de la aplicación)

Es lo que se empaqueta y corre en AgentCore Runtime.

| Archivo | Qué es |
|---|---|
| `main.py` | Entrypoint de AgentCore. Un agente y un robot **por sesión**; antes del modelo ejecuta el reflejo de parada. |
| `model/load.py` | El modelo (Amazon Bedrock). Se cambia con la variable `CLOUDPAW_MODEL_ID`. |
| `parse.py` | Valida el cuerpo de la petición (viene del template de AgentCore). |
| `cloudpaw/robot.py` | El contrato `RobotDriver`, el robot simulado y el mapa ASCII. **Lo único que cambia con un robot real.** |
| `cloudpaw/toolbox.py` | Las 7 herramientas, los límites y los presupuestos por mensaje. |
| `cloudpaw/reflex.py` | La parada que se ejecuta antes del modelo. |
| `cloudpaw/prompt.py` | El prompt del sistema (bilingüe). |
| `cloudpaw/offline.py` | Plan B sin modelo (reglas). |
| `play.py` | Hablar con el robot desde la terminal. |
| `tests/` | 97 tests sin AWS ni modelo. |

## Probar

```bash
uv sync
uv run --with pytest pytest -q                 # tests
uv run python play.py                          # chat (necesita credenciales de AWS con acceso a Bedrock)
uv run python play.py --offline                # sin modelo ni internet
uv run python play.py -c "avanza 2 metros y gira a la derecha" -c "alto"
```

## Payload del Runtime

`{"prompt": "avanza 2 metros"}`. El `session_id` va en el encabezado `X-Amzn-Bedrock-AgentCore-Runtime-Session-Id`:
la misma sesión es el mismo robot. Con la CLI, pasa `--session-id` (al menos 33 caracteres) o usa `workshop/tools/say.py`.

## Variables de entorno

| Variable | Para qué | Por defecto |
|---|---|---|
| `CLOUDPAW_MODEL_ID` | Modelo de Bedrock | `global.anthropic.claude-haiku-4-5-20251001-v1:0` |
| `AWS_REGION` | Región de Bedrock | `us-east-1` |

## Conectar un robot real

Implementa las 8 funciones de `RobotDriver` (`stand`, `sit`, `walk`, `turn`, `follow`, `stop`, `pose`, `mode`) y pásalo
a `build_agent(model, robot=TuRobot())`. `stop` debe funcionar en cualquier estado. **Los límites del código son una segunda
barrera: el firmware del robot debe tener los suyos y la parada de emergencia debe ser física.**
