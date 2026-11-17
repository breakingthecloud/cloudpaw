# CloudPaw V2 (exploración): las mismas herramientas, un robot con física

**Estado: exploración. No forma parte de la demo de la V1 ni del paquete que se despliega en AgentCore.**
Este directorio tiene su propio entorno (Python 3.12) y no toca `app/agent`.

## Qué es `strands-robots`

Librería de Strands Labs (`strands-labs/robots`, Apache-2.0, versión 0.6.0 del 14-nov-2026, activa). Un `Robot("nombre")` carga un robot por nombre
en una simulación MuJoCo (sin GPU) o en hardware, con el mismo código. Trae manifiesto de límites, cadena de seguridad, e-stop que nada puede
bloquear, aprobación del operador para robots reales y herramientas para agentes (`robot.tool`) generadas desde el manifiesto.

## Lo que verifiqué (16-17 nov)

| Pregunta | Respuesta |
|---|---|
| ¿Se instala fácil? | Sí: `uv sync` en esta carpeta, unos segundos; entorno de 287 MB (MuJoCo 3.17). Python 3.12. |
| ¿Camina en simulación sin pantalla? | Sí. `Robot("microduck")` + `Policy("microduck?vx=0.3")` avanzó 0.63 m en 5 s simulados (7.7 s de reloj, la política baja de Hugging Face). Ver `spike_microduck.py`. |
| ¿Hay cuadrúpedos? | Como **modelo de simulación**, sí: `unitree_go2`, `go1`, `unitree_a1`, `aliengo`, `anymal_b/c/d`, `spot`, `hyq`, `mini_cheetah`, `solo`… |
| ¿Hay política de marcha para ellos? | **No.** Las únicas incluidas son `microduck` (bípedo) y `holosoma` (humanoide G1). Para un cuadrúpedo hay que aportar la propia política (ONNX o LeRobot). |
| ¿Mueve un Unitree real? | **No en 0.6.0.** El driver de Unitree solo lee (`write` lanza `NotImplementedError`; el propio código dice que esta versión no comanda un robot). |
| ¿Cuánto avanza por orden de velocidad? | Menos de lo pedido: `vx=0.3` dio ~0.13 m/s efectivos. Una orden en metros necesita lazo cerrado sobre la pose medida, no "velocidad × tiempo". |

## Cómo encaja con CloudPaw

`strands-robots` opera a nivel de **políticas y articulaciones**; CloudPaw opera a nivel de **órdenes** (`walk`, `turn`, `stop`).
Son capas distintas. El plan de la V2 es un adaptador `StrandsRobotsDriver` que implemente el `RobotDriver` de la V1 (`stand`, `sit`, `walk`,
`turn`, `follow`, `stop`, `pose`, `mode`) sobre `Robot("microduck")`, para que el agente, las herramientas, los límites y el reflejo de parada
**no cambien**, y se vea un robot con física real. El `stop` del adaptador debe llamar al `estop()` de la librería.

Pendiente de decidir antes de construirlo: ¿te sirve el `microduck` (bípedo) como sustituto visual mientras no haya política de cuadrúpedo, o
prefieres esperar a la política propia del Go2/CloudPaw? Ejecutar el adaptador completo en vivo es lento (≈1.5 s de reloj por segundo simulado
a esta velocidad), así que como mucho es un cierre de la charla, no el núcleo.

## Probar el spike

```bash
cd v2-strands-robots && uv sync && uv run python spike_microduck.py
```
