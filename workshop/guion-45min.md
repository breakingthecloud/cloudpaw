# Guion de 45 minutos — CloudPaw (UTEC · IEEE RAS)

**Tu bloque:** 15 min de teoría + 30 min de demo guiada. Los mentores tienen sus propias charlas; este guion no depende de ellas.
**Público:** estudiantes de robótica, ingeniería y mecatrónica del proyecto CloudPaw. Saben de robots, no necesariamente de AWS.
**Regla del bloque:** nadie instala nada hoy. Ellos miran y preguntan; el repositorio es para que lo hagan después.

## Estado del ensayo (léelo antes)

| Paso | ¿Lo probé? |
|---|---|
| `play.py` con el modelo real (Haiku 4.5), ES/EN, límites, estados, reflejo | ✅ varias corridas, ~2.7 s por mensaje |
| `play.py --offline` (Plan B) | ✅ |
| `agentcore build` (valida el proyecto, paquete de 42 MB) | ✅ |
| `agentcore dev` (servidor local) + `say.py --local` con sesión fija | ✅ el robot conserva su posición entre mensajes |
| `agentcore dev --mode browser` (Agent Inspector en el navegador) | ⚠️ **no lo abrí**; solo probé el modo sin navegador |
| `agentcore create ... --skip-install` | ✅ **0.8 s** (sin `--skip-install` ~45 s porque instala con npm y uv) |
| Entorno: Node 22 + pnpm 11 + CLI 1.0.3 | ✅ `workshop/tools/doctor.sh` termina en "Ready"; `agentcore build` pasa sin avisos |
| `agentcore deploy`, `invoke` y `traces` **contra AWS** | ❌ **no los ejecuté**. Es un despliegue real en tu cuenta. Ensáyalo el martes (ver `checklist-previo.md`) y anota cuánto tarda |

La documentación oficial dice que el primer `deploy` "tarda unos minutos" porque hace el bootstrap de CDK. No tengo una medición propia: **no prometas un tiempo en voz alta hasta ensayarlo**.

## Ensayo grabado

`workshop/ensayo/2026-11-17-agentcore-dev.md` es la transcripción de una corrida real de los pasos 2 a 4 contra `agentcore dev`
(comando, salida, tiempo y consola de cada paso, y el log completo; copia en `...-console.log`). Para regrabar:
`AWS_PROFILE=<perfil> python3 workshop/tools/record_dev.py` (necesita sesión de AWS válida). Úsala para saber qué esperar: los
tiempos por mensaje fueron de 2 a 8 s, y con "avanza 10 metros" el modelo a veces camina los 2 m permitidos antes de explicar el límite.

## Cómo está armado el tiempo

| Min | Bloque | Material |
|---|---|---|
| 0:00–0:15 | Teoría (con preámbulo) | Slides 1–13 |
| 0:15–0:17 | Paso 1: el esqueleto | Terminal C (scratch) |
| 0:17–0:23 | Paso 2: hablarle al robot | `play.py` |
| 0:23–0:28 | Paso 3: límites y reflejo | `play.py` + código |
| 0:28–0:32 | Paso 4: el mismo agente, como servicio local | `agentcore dev` + `say.py` |
| 0:32–0:41 | Paso 5: a la nube | `agentcore deploy` + `say.py` |
| 0:41–0:45 | Paso 6: ver qué pensó + cierre | trazas, slides 16–17 |

**Truco de tiempo:** el `deploy` es lo más impredecible. **Lánzalo en una segunda terminal al empezar el paso 2** (o ten el agente ya desplegado desde el martes) y tráelo de vuelta en el paso 5.

---

## Teoría (0:00–0:15)

| Min | Slide | Qué decir (una idea por slide) |
|---|---|---|
| 0:00 | 1 | Presentación breve. "Hoy vamos a escribirle órdenes de texto a un robot." |
| 0:30 | 2 | Muestra lo que se va a ver. "Hoy el robot es simulado; mañana, el cuadrúpedo real." |
| 1:15 | 3 | **Preámbulo:** qué es Strands Agents. SDK abierto: modelo + herramientas + prompt; el modelo decide el bucle. |
| 2:30 | 4 | **Preámbulo:** qué es Strands Robots. El mismo código en simulación o en hardware; hoy no trae marcha de cuadrúpedo (por eso existe la V2). |
| 3:30 | 5 | **Preámbulo:** los servicios de AWS. Bedrock (modelo), AgentCore (despliegue), CloudWatch (trazas), IAM (permisos), CDK, EC2 + SSM. |
| 4:45 | 6 | Agente = modelo + herramientas + bucle. "Un chatbot contesta; un agente actúa." |
| 5:45 | 7 | Una herramienta es una función con tipos. El `Literal` es un menú cerrado. |
| 7:00 | 8 | **La idea central:** el modelo propone, el código dispone. Recorre las 4 capas de la tabla. |
| 9:00 | 9 | Cada capa existe porque algo falló al probar. Cuenta el caso de "ya estoy parado". |
| 10:30 | 10 | La arquitectura de abajo hacia arriba; el driver es lo único que cambia con el robot real. |
| 11:45 | 11 | Los 7 verbos. "Nada más." |
| 12:15 | 12 | AgentCore: Runtime y observabilidad (ya presentado en la 5: pásala rápido). |
| 13:15 | 13 | **Honestidad de ingeniería:** la parada de emergencia es física y los lazos de control son locales. Esto es lo que más valor tiene para ellos. |
| 15:00 | 14 | "Pasemos a la terminal." |

El preámbulo (3–5) suma ~3.5 min. Si vas corto de tiempo, recorta la slide 11 (la tabla se puede leer en el repo) y la 12 (repite la 5).

---

## Demo guiada (0:15–0:45)

Antes de empezar, corre `workshop/tools/doctor.sh --aws` y deja **Node 22 activo en las tres terminales** (`fnm use 22`). Después, tres terminales y **en qué carpeta va cada comando**:

| Terminal | Carpeta | Para qué |
|---|---|---|
| A | `cloudpaw-workshop/app/agent` | `play.py` y los tests |
| B | `cloudpaw-workshop` (la **raíz**) | todos los `agentcore ...` y `say.py` |
| C | una carpeta vacía (scratch) | solo el `agentcore create` del paso 1 |

Proyector con letra grande (Cmd + `+`).

### Paso 1 · El esqueleto (0:15–0:17)

Terminal C (scratch):
```bash
agentcore create --name demo --template agent-python-strands --skip-install
```
Di: "Un comando crea el proyecto: el agente, el modelo, la infraestructura. Lo que vamos a usar ya lo tengo hecho; esto es para que vean que es el mismo esqueleto." Muestra `ls` y `app/agent/main.py` unos segundos. Sale en menos de un segundo (`--skip-install` no instala nada; en tu proyecto real la instalación la haces tú con pnpm y uv). Si algo falla, no esperes: pasa al paso 2.

### Paso 2 · Hablarle al robot (0:17–0:23)

Terminal A (con credenciales del perfil de pruebas ya cargadas):
```bash
uv run python play.py
```
Escribe, en este orden, y comenta cada resultado:

| Escribe | Qué verán | Qué decir |
|---|---|---|
| `avanza 2 metros y gira a la derecha` | dos herramientas (`walk`, `turn`) y el mapa | "El modelo eligió las herramientas. Mira los argumentos." |
| `walk forward half a meter, then turn left 45 degrees` | lo mismo, en inglés | "Mismas herramientas, otro idioma." |
| `da la vuelta` | `turn(right, 180)` | |
| `¿dónde estás?` | `get_status()` | "Solo lectura." |

Resultados vistos en el ensayo: ~2.7 s por mensaje; el modelo responde en el idioma del mensaje.

### Paso 3 · Límites y reflejo (0:23–0:28)

Sigue en `play.py`:

| Escribe | Qué pasa | Qué decir |
|---|---|---|
| `avanza 10 metros` | ✗ `out_of_range`; el modelo explica y ofrece 2 m | "No lo frenó el prompt: lo frenó el código." |
| `walk 2 meters, 20 times` | el modelo pide 20 llamadas; se ejecutan **6** y se rechazan 14 | "Segunda y tercera capa: acciones y distancia por mensaje." |
| `siéntate` y luego `camina 1 metro` | ✗ `sitting`; ofrece levantarse | "Máquina de estados." |
| `sígueme` y luego `para` | ⚡ **reflex: stop executed BEFORE the model** | **El momento clave.** "Esto corre antes de que el modelo lea nada." |
| `salta y haz una voltereta` | lista lo que sí puede hacer | |

Abre `cloudpaw/toolbox.py` (clase `Limits`, ~10 líneas) y `cloudpaw/reflex.py` (~15 líneas) para que vean que no hay magia. Si queda tiempo: `uv run --with pytest pytest -q` (97 tests, ~3 s).

Comparación opcional (30 s): `uv run python play.py --offline` y escribe `da unos pasos hacia adelante y mira a tu derecha` → el planificador por reglas **no lo entiende**; el modelo sí. Es el contraste "reglas vs. modelo".

### Paso 4 · El mismo agente, como servicio (0:28–0:32)

Terminal B (raíz): `agentcore dev --port 8081` (arranca el runtime local con recarga automática). Abre otra pestaña en la raíz y:
```bash
python3 workshop/tools/say.py "avanza 2 metros y gira a la derecha" --local --port 8081
python3 workshop/tools/say.py "camina 1 metro" --local --port 8081
python3 workshop/tools/say.py "alto" --local --port 8081
```
Salida esperada (vista en el ensayo): las herramientas llamadas (`->`) y la respuesta (`PAW:`); el robot **recuerda** dónde está porque `say.py` usa siempre la misma sesión. Di: "Esto es lo que AgentCore llama un Runtime: una sesión por conversación."
Opcional: `agentcore dev --mode browser` abre el Agent Inspector (⚠️ no lo probé).

### Paso 5 · A la nube (0:32–0:41)

```bash
agentcore build        # valida y empaqueta (~42 MB)
agentcore deploy       # crea el stack con CDK y el endpoint del Runtime
agentcore status
python3 workshop/tools/say.py "avanza 2 metros y gira a la derecha"      # sin --local: el Runtime en AWS
python3 workshop/tools/say.py "alto"
```
Notas:
- El primer `deploy` en una cuenta nueva hace el bootstrap de CDK: más lento. El martes ya debe estar hecho.
- El destino `default` se crea solo desde tu cuenta y región actuales. **No hagas `git add` de `agentcore/aws-targets.json` después del deploy** (contiene tu ID de cuenta). El repo ya ignora `agentcore/.cli/`.
- Si el deploy se alarga: pasa al paso 6 con el agente ya desplegado del martes y di la verdad: "esto lo dejé desplegado antes".

### Paso 6 · Ver qué pensó + cierre (0:41–0:45)

```bash
agentcore traces runtime list --since 30m
agentcore logs runtime --since 10m
```
o abre CloudWatch → *GenAI Observability*. Muestra una traza: ven la llamada a `walk`, sus argumentos y la respuesta. Cierra con las slides 16 (qué sigue) y 17.

**Después del evento:** limpia lo desplegado (`agentcore remove all --yes` y luego `agentcore deploy --yes`) para no dejar recursos.

---

## Preguntas que probablemente harán

| Pregunta | Respuesta honesta |
|---|---|
| ¿Funciona con un robot real? | Sí, cuando exista un driver (`RobotDriver`, 8 métodos). Con ROS 2 sería otra clase; el agente y los tests no cambian. |
| ¿Es seguro? | Es una segunda barrera, no la única. La parada de emergencia debe ser física y el firmware debe tener sus propios límites. |
| ¿Y la latencia? | ~3 s por mensaje en el ensayo: sirve para intención ("ve a la puerta"), no para control de motores. |
| ¿Cuánto cuesta? | No lo medí. El modelo es el mayor costo por mensaje; revisa la página de precios de Bedrock y AgentCore antes de dar un número. |
| ¿Se puede con otro modelo? | Sí: variable `CLOUDPAW_MODEL_ID`. Con Amazon Nova Lite funcionó, pero respondió en inglés a mensajes en español y troceó un movimiento largo (el código lo frenó). |
| ¿Por qué no solo reglas (regex)? | Por eso el Plan B existe: entiende lo que le programaste y nada más. |
