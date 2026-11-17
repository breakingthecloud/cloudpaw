# Plan B — si algo falla en vivo

Regla: **no te disculpes largo, cambia de carril**. Cada nivel baja un escalón y sigue mostrando la idea central: *el modelo propone, el código dispone*.

| Si falla… | Haz esto | Qué sigues mostrando |
|---|---|---|
| **B1 · El modelo no responde o no hay acceso** (error de Bedrock, sesión SSO caducada) | Renueva credenciales si es solo eso. Si no: `export CLOUDPAW_MODEL_ID=us.amazon.nova-lite-v1:0` y repite. | Todo. Nova Lite funcionó en mi prueba, pero **es más débil**: contestó en inglés a mensajes en español y troceó "avanza 10 metros" en llamadas de 2 m. Úsalo para contarlo: el código lo frenó con el presupuesto de distancia (6 m). |
| **B2 · No hay internet** | `uv run python play.py --offline` (planificador por reglas, sin modelo, mismas herramientas y mismos límites). | Herramientas, límites, estados y mapa. Di: "esto es lo que el modelo reemplaza". Prueba `da unos pasos hacia adelante y mira a tu derecha`: no lo entiende. |
| **B3 · El `deploy` se alarga o falla** | Usa el agente desplegado el martes: `agentcore status` y `python3 workshop/tools/say.py "..."` (sin `--local`). | La parte "en la nube" con el agente ya existente. Dilo claro: "este lo dejé desplegado antes". |
| **B4 · Tampoco hay agente desplegado** | Usa `agentcore dev` + `say.py --local` (paso 4) y enseña el video del deploy. | El runtime con la misma interfaz, en local. |
| **B5 · La laptop falla** | Video de la demo completa + slides en el USB o el celular. | La historia completa, sin el vivo. |

## Fallos conocidos y su arreglo (vistos al ensayar)

| Síntoma | Causa | Arreglo |
|---|---|---|
| `agentcore --version` da 0.11.0 o un error | Un `agentcore` antiguo (Homebrew o pip) va antes en el `PATH` | `workshop/tools/doctor.sh` lo detecta. Pon `$PNPM_HOME/bin` primero, y `pip uninstall bedrock-agentcore-starter-toolkit` si aplica |
| `pnpm` falla con `ERR_UNKNOWN_BUILTIN_MODULE: node:sqlite` | pnpm 11 necesita Node 22.13 o más y la terminal está en Node 20 | `fnm use 22` |
| Avisos `EBADENGINE` al instalar con npm | El CLI trae dependencias que piden Node 22 | `fnm use 22` (con Node 22 no salen) |
| `pnpm install` termina con `ERR_PNPM_IGNORED_BUILDS` (esbuild) y código 1 | pnpm 11 bloquea scripts de instalación hasta que decidas | En este repo ya está decidido (`allowBuilds: esbuild: false`). En un proyecto nuevo: `pnpm approve-builds '!esbuild'` |
| `agentcore build` dice "CDK dependencies are missing" | Falta instalar en `agentcore/cdk` | `(cd agentcore/cdk && pnpm install)` |
| El robot "empieza de cero" en cada mensaje | `agentcore invoke` crea una sesión nueva si no le pasas `--session-id` | Usa `workshop/tools/say.py` (sesión fija) |
| `say.py` dice que la sesión es muy corta | AgentCore pide ≥ 33 caracteres | Usa `--session` con un id largo o `--new` |
| Puerto ocupado | Otro `agentcore dev` quedó vivo | `agentcore dev --port 8082` y `--port 8082` en `say.py` |
| El modelo "se salta" un límite | Un modelo débil ignora el prompt | Es el punto de la demo: el límite está en el código; la respuesta del código dice por qué |
| El modelo contesta "ya estoy parado" a `para` | Cree que ya está detenido | No pasa con el reflejo: el código ejecuta `stop` antes de que el modelo lea el mensaje |

## Preguntas que no sabes responder

Di "no lo medí / no lo probé" y anótala. En este kit hay tres cosas que **no se probaron**: el `deploy` contra AWS, el Agent Inspector en el navegador y el costo por mensaje. Es mejor decirlo que adivinar.
