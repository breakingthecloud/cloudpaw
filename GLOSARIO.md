# Glosario de CloudPaw (V1 y V2)

Términos y tecnologías del proyecto, agrupados por área. Cada entrada dice qué es y **cómo se usa en CloudPaw**.
Los nombres de archivos y comandos son los del repositorio.

## 1. El proyecto

| Término | Qué es | En CloudPaw |
|---|---|---|
| **CloudPaw** | Cuadrúpedo controlado por texto, proyecto de IEEE RAS UTEC | Agente en la nube + política en el robot |
| **V1** | Primera versión: agente de lenguaje + robot **simulado sin física** | `app/agent/`, demo del workshop |
| **V2** | Segunda versión: el mismo agente sobre **física real**, más RL, ESP32 y ROS 2 | `v2-strands-robots/`, `ros2_ws/` |
| **Kit del workshop** | Slides, guion, checklist, plan B y herramientas para los 45 min | `workshop/` |
| **Spec inferida** | Especificación supuesta del robot hasta tener el hardware real | `cloudpaw_rl/spec.py`, marcada `ASSUMED` |
| **Sustituto (proxy)** | Robot existente usado en lugar del CloudPaw que aún no tiene modelo | Unitree Go2 con 8 articulaciones activas |

## 2. Agentes de IA

| Término | Qué es | En CloudPaw |
|---|---|---|
| **Agente** | Programa con un modelo que decide qué herramientas llamar, en bucle, hasta cumplir una tarea | Convierte "avanza 1 metro" en `walk(forward, 1)` |
| **LLM** (modelo de lenguaje grande) | Modelo que entiende y genera texto | Claude Haiku 4.5 |
| **Herramienta (tool)** | Función con tipos que el modelo puede llamar; lo único con lo que actúa | 7: `walk`, `turn`, `follow`, `stop`, `stand`, `sit`, `get_status` |
| **System prompt** | Instrucciones fijas que el modelo lee siempre | `cloudpaw/prompt.py`, bilingüe |
| **Docstring** | Texto de una función que el modelo lee para saber cuándo usarla | Describe cada herramienta y sus límites |
| **`Literal`** | Tipo de Python con valores cerrados; el modelo no puede inventar otros | `forward/backward/left/right` |
| **Llamada a herramienta (tool call)** | Petición del modelo de ejecutar una herramienta con argumentos | Se imprimen como `→ walk(...)` |
| **Ejecución secuencial** | Correr las herramientas de una en una | `SequentialToolExecutor`: evita que `walk` empiece antes de terminar `stand` |
| **Hook** | Función que se ejecuta antes o después de cada herramienta | Imprime las llamadas en `play.py` |
| **Temperatura** | Cuánto varía la respuesta del modelo | 0: las órdenes a un robot no deben ser creativas |
| **Sesión** | Conversación con estado propio | En AgentCore, una sesión = un robot con su posición |
| **"El modelo propone, el código dispone"** | Principio: los límites viven en el código, no en el prompt | Base de todo el diseño de seguridad |

## 3. Seguridad del agente

| Término | Qué es | En CloudPaw |
|---|---|---|
| **Límite por llamada** | Rango permitido de cada argumento | 0.1–2 m, 1–180° |
| **Presupuesto de acciones** | Máximo de herramientas por mensaje | 6 |
| **Presupuesto de distancia** | Máximo a recorrer por mensaje, aunque se trocee | 6 m |
| **Reflejo de parada** | `stop` que se ejecuta **antes** de que el modelo lea el mensaje | `cloudpaw/reflex.py` ("alto", "para", "stop"…) |
| **Máquina de estados** | Reglas según el modo del robot | Sentado o siguiendo no puede caminar |
| **Rechazo estructurado** | La herramienta devuelve `ok: false` y la razón, en vez de fallar | El agente explica el rechazo al usuario |
| **E-stop (parada de emergencia)** | Parada que se bloquea y solo libera un operador | `emergency_stop(by=…)`; la física es un botón real |
| **Plan B** | Ruta sin modelo ni internet | `play.py --offline`, planificador por reglas |

## 4. Strands y AWS

| Término | Qué es | En CloudPaw |
|---|---|---|
| **Strands Agents** | SDK de Python de AWS para construir agentes | Define el agente y sus herramientas |
| **Amazon Bedrock** | Servicio de AWS para usar modelos fundacionales por API | Ejecuta Claude Haiku |
| **Perfil de inferencia** | Identificador de modelo enrutado entre regiones (`global.…`, `us.…`) | `global.anthropic.claude-haiku-4-5-…` |
| **Amazon Bedrock AgentCore** | Servicio para desplegar y operar agentes | Runtime del agente V1 (despliegue pendiente) |
| **AgentCore Runtime** | Ejecuta el agente aislado por sesión, sin servidores | El agente como endpoint |
| **CLI de AgentCore** | Herramienta `agentcore` (npm, v1.0.3) | `create`, `dev`, `build`, `deploy`, `invoke`, `traces` |
| **`agentcore dev`** | Corre el Runtime en local con recarga automática | Puerto 8081 en la demo |
| **CodeZip** | Tipo de empaquetado: el código en un zip, sin Docker | El template `agent-python-strands` |
| **AWS CDK** | Infraestructura como código; la CLI la usa para desplegar | `agentcore/cdk/` |
| **Bootstrap de CDK** | Preparación inicial de una cuenta y región para CDK | Hace lento el primer `deploy` |
| **`aws-targets.json`** | Cuenta y región de despliegue | Contiene el ID de cuenta: no se sube |
| **Amazon EC2** | Máquinas virtuales | `cloudpaw-ops`, centro de operaciones |
| **m7i.xlarge** | Tipo de instancia: 4 vCPU, 16 GiB, sin créditos de ráfaga | Para ROS 2, Gazebo y entrenar PPO |
| **AWS Systems Manager (SSM)** | Gestión de instancias sin SSH | Único acceso a la EC2 |
| **Session Manager** | Sesión de terminal por SSM | `aws ssm start-session` |
| **Port forwarding por SSM** | Túnel de un puerto remoto a tu máquina | Foxglove en `localhost:8765` |
| **Security group** | Firewall de la instancia | Sin reglas de entrada |
| **IMDSv2** | Versión segura del servicio de metadatos de EC2 | Obligatoria; v1 devuelve 401 |
| **Rol IAM / instance profile** | Permisos que asume la instancia | `cloudpaw-ops-ec2`: SSM + invocar Bedrock |
| **Alarma de CloudWatch** | Acción automática según una métrica | Apaga la EC2 tras 1 h ociosa |
| **Amazon CloudWatch** | Métricas, logs y trazas | Observabilidad del agente desplegado |
| **SSO (IAM Identity Center)** | Inicio de sesión único con sesiones que caducan | `aws sso login --profile …` |
| **AWS IoT Core / MQTT** | Mensajería para dispositivos | Vía prevista para enviar comandos al ESP32 |

## 5. Herramientas de desarrollo

| Término | Qué es | En CloudPaw |
|---|---|---|
| **uv** | Gestor rápido de Python y entornos | `uv sync`, `uv run` |
| **pnpm** | Gestor de paquetes de Node | Dependencias de CDK y la CLI global |
| **Node 22 / fnm** | Runtime de JavaScript / gestor de versiones | La CLI pide Node ≥ 22.13 (`.node-version`) |
| **pytest** | Framework de tests de Python | ~160 tests entre V1 y V2 |
| **Test de higiene** | Test que falla si el repo expone datos de cuenta | IDs de cuenta, recursos, claves, rutas personales |
| **Test de mutación** | Romper el código a propósito para comprobar que los tests lo detectan | Usado en cada pieza crítica |
| **`run.sh`** | Lanzador único local | `offline`, `chat`, `dev`, `say`, `test` |
| **`doctor.sh`** | Verificador del entorno | Node, pnpm, CLI 1.x, uv, dependencias |
| **`say.py`** | Ayudante para hablarle al Runtime con sesión fija | El robot recuerda su posición |
| **`record_dev.py`** | Graba un ensayo contra `agentcore dev` en Markdown | `workshop/ensayo/` |
| **`.local.env`** | Archivo con valores reales del despliegue, fuera de git | `infra/ec2/ops.local.env` |
| **Apache-2.0** | Licencia de código abierto permisiva | Licencia del repo |

## 6. Robótica

| Término | Qué es | En CloudPaw |
|---|---|---|
| **Cuadrúpedo** | Robot de cuatro patas | CloudPaw |
| **GDL (grados de libertad, DoF)** | Articulaciones que se mueven por separado | 8 (2 por pata) |
| **Cadera (hip) / rodilla (knee)** | Las dos articulaciones de cada pata | `FL_hip`, `FL_knee`… |
| **Abducción** | Movimiento lateral de la cadera | El CloudPaw inferido no la tiene; en el Go2 se bloquea |
| **FL / FR / RL / RR** | Pata delantera izquierda / derecha, trasera izquierda / derecha | Nombres de articulaciones |
| **Pose de pie / sentado** | Ángulos de reposo | De pie 0.6 / −1.2 rad; sentado 1.1 / −2.2 rad |
| **Trote (trot)** | Marcha con pares diagonales a la vez | FL+RR, luego FR+RL |
| **Fase de apoyo / vuelo (stance / swing)** | Pata en el suelo empujando / en el aire volviendo | `gait.py` |
| **Cinemática directa / inversa (FK / IK)** | Ángulos → posición del pie / posición del pie → ángulos | `leg_fk`, `leg_ik` |
| **Lazo abierto** | Mover sin medir el resultado | El trote de ROS 2: resbala |
| **Lazo cerrado** | Mover hasta que la medición diga que se llegó | El adaptador V2: 0.3 m pedidos = 0.30 m |
| **Controlador PD** | Torque = kp·(objetivo − posición) − kd·velocidad | Cómo se sostiene el Go2 simulado |
| **Actuador de torque / de posición** | Recibe fuerza / recibe un ángulo objetivo | El Go2 trae de torque |
| **Servo de hobby (MG90S)** | Motor pequeño con PWM, sin realimentación de posición | 8 en el CloudPaw inferido |
| **PWM** | Señal de pulsos que fija el ángulo del servo | La genera el PCA9685 |
| **IMU** | Acelerómetro + giroscopio | Da gravedad proyectada y velocidad angular |
| **Gravedad proyectada** | Dirección de la gravedad vista desde el cuerpo | Orientación sin brújula |
| **Alabeo / cabeceo / guiñada (roll / pitch / yaw)** | Giros sobre los ejes x, y, z | Rumbo = guiñada |
| **Rumbo (heading)** | Hacia dónde mira el robot | V1: grados en sentido horario desde el inicio |
| **Odometría (`odom`)** | Posición estimada desde el inicio | Marco fijo en Foxglove |
| **Detección de caída** | Inclinación > ~46° o altura < 50% de la de pie | Termina el episodio o el movimiento |

## 7. Simulación

| Término | Qué es | En CloudPaw |
|---|---|---|
| **MuJoCo** | Motor de física para robótica, rápido en CPU | Simulación de la V2 y del entrenamiento |
| **MJCF** | Formato XML de modelos de MuJoCo | Falta el del CloudPaw |
| **MuJoCo Menagerie** | Colección de modelos de robots de DeepMind | De ahí sale el Go2 |
| **strands-robots** | Librería de Strands Labs: el mismo código mueve un robot simulado o real | v0.6.0 |
| **`Robot("nombre")`** | Carga un robot por nombre | `Robot("microduck")`, `Robot("unitree_go2")` |
| **`Policy`** | Convierte una observación en una acción | Política de marcha del microduck |
| **`stop_when`** | Condición que corta un `run` | Base del lazo cerrado |
| **microduck** | Pequeño bípedo con políticas de marcha incluidas | Sustituto visual que sí camina |
| **Unitree Go2** | Cuadrúpedo comercial | Sustituto del CloudPaw |
| **`biastype` AFFINE** | Ajuste de actuador de MuJoCo que activa el término PD | Arreglo del fallo de `set_gains` |
| **`RobotDriver`** | La frontera: 8 métodos iguales para simulación y hardware | V1 simulado, V2 `StrandsRobotsDriver`, mañana el ESP32 |
| **`StrandsRobotsDriver`** | Adaptador del `RobotDriver` sobre strands-robots | El agente V1 sin cambios sobre física |

## 8. Aprendizaje por refuerzo

| Término | Qué es | En CloudPaw |
|---|---|---|
| **RL (aprendizaje por refuerzo)** | Aprender por prueba y error maximizando una recompensa | Cómo aprenderá a caminar |
| **PPO** (Proximal Policy Optimization) | Algoritmo de RL estable y muy usado en locomoción | El elegido |
| **Política** | Función de observación a acción | MLP de 26 → 64 → 64 → 8 |
| **Actor** | La red que produce acciones en PPO | Es la que se exporta al ESP32 |
| **MLP** | Red neuronal de capas densas | 6 408 parámetros, 25 KB |
| **tanh** | Función de activación que acota entre −1 y 1 | Capas ocultas y salida |
| **Observación** | Lo que ve la política en cada paso | 26 valores disponibles en el ESP32 |
| **Acción** | Lo que decide la política | 8 valores en [−1, 1] |
| **Escala de acción** | Cuánto se aleja una acción de la pose de pie | 0.35 rad |
| **Fase de marcha** | Reloj seno/coseno que da ritmo | 1.5 Hz |
| **Recompensa** | Número que premia o castiga cada paso | `cloudpaw_rl/reward.py` |
| **Seguimiento de velocidad** | Premio por igualar la velocidad pedida | Núcleo exponencial, peso 1.5 |
| **Episodio / terminación / truncado** | Un intento / fin por caída / fin por tiempo | 10 s por episodio |
| **Entorno (env)** | Simulación con `reset` y `step` | `cloudpaw_rl/env_mujoco.py` |
| **gymnasium** | Interfaz estándar de entornos de RL | El entorno la sigue sin depender de ella |
| **Stable-Baselines3 / skrl / CleanRL** | Librerías de RL | Opciones para entrenar |
| **Domain randomization** | Variar masas, fricción y retrasos al entrenar | Para que funcione en el robot real |
| **Sim-to-real** | Pasar de simulación a hardware | El reto principal de la V2 |
| **Normalización de la observación** | Restar la media y dividir por la desviación | Se incluye en el header C |

## 9. Electrónica y firmware

| Término | Qué es | En CloudPaw |
|---|---|---|
| **ESP32-S3** | Microcontrolador con Wi-Fi y FPU | Cerebro del robot (inferido) |
| **FPU** | Unidad de punto flotante | Calcula la red en float32 |
| **PCA9685** | Driver de 16 canales PWM por I²C | Mueve los 8 servos |
| **I²C** | Bus de dos cables para sensores y drivers | IMU y PCA9685 |
| **ESP-IDF** | Entorno oficial de desarrollo del ESP32 | Pendiente: compilar la política |
| **FreeRTOS** | Sistema operativo de tiempo real del ESP32 | Tarea de control cada 20 ms |
| **Header C** | Archivo `.h` con la red como constantes | `cloudpaw_policy.h`, sin dependencias |
| **Bucle de control** | Leer IMU → red → recortar → escribir servos | 50 Hz |
| **Timeout de comando** | Si no llega orden en 0.5 s, pasa a (0, 0) | Seguridad ante pérdida de conexión |
| **micro-ROS** | ROS 2 para microcontroladores | Opción futura |

## 10. ROS 2 y visualización

| Término | Qué es | En CloudPaw |
|---|---|---|
| **ROS 2 Jazzy** | Middleware de robótica, versión LTS sobre Ubuntu 24.04 | En la EC2 |
| **Nodo / tópico** | Proceso / canal de mensajes | `cloudpaw_trot`; `/joint_states`, `/cmd_vel` |
| **`/joint_states`** | Ángulos de las articulaciones | 50 Hz |
| **`/cmd_vel` (Twist)** | Velocidad pedida: lineal y angular | Igual que el comando del agente |
| **TF / tf2** | Árbol de marcos de coordenadas | `odom → base_link → patas` |
| **URDF / xacro** | Descripción del robot en XML / con macros y parámetros | `urdf/cloudpaw.urdf.xacro` |
| **`check_urdf`** | Valida un URDF | Pasa |
| **robot_state_publisher** | Calcula la TF desde URDF + `/joint_states` | En `display.launch.py` |
| **colcon** | Compila y prueba espacios de trabajo ROS 2 | `ros2_ws/build.sh` |
| **ament** | Sistema de build de ROS 2 | Necesita el Python del sistema (no el de uv) |
| **Launch file** | Arranca varios nodos a la vez | `display` (sin física) y `gazebo` |
| **Gazebo (Harmonic / gz sim 8)** | Simulador 3D con física integrado con ROS 2 | Trote con física: 0.069 m en 10 s |
| **ros2_control** | Marco de control de hardware y simulación | Controlador de posición de las 8 articulaciones |
| **Controller manager / spawner** | Carga y activa controladores | `joint_state_broadcaster`, `leg_position_controller` |
| **RViz** | Visualizador 3D de ROS | Requiere pantalla |
| **Foxglove** | Visualizador web de datos de robots | Por túnel SSM, `ws://localhost:8765` |
| **foxglove_bridge** | Expone ROS 2 a Foxglove por WebSocket | Escucha solo en `127.0.0.1` |
| **NICE DCV / VNC** | Escritorio remoto | Opción para ver Gazebo o RViz en la EC2 |
