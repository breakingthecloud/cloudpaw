# CloudPaw en ROS 2 (Jazzy): cómo se va a mover

Paquete `cloudpaw_description`: modelo URDF del CloudPaw **inferido** (8 servos: cadera y rodilla por pata), una marcha de
trote para **ver** cómo se moverá, y lanzamientos para Foxglove/RViz (sin física) y Gazebo (con física).
La marcha de aquí es una demo visual en lazo abierto; la marcha real saldrá de la política PPO (`v2-strands-robots/cloudpaw_rl`).

## Verificado el 17-nov-2026 en la EC2 de operaciones (Ubuntu 24.04, ROS 2 Jazzy, Gazebo Harmonic 8)

| Prueba | Resultado |
|---|---|
| `xacro` + `check_urdf` | ✅ URDF válido: `base_link` con 4 patas y la IMU |
| `colcon build` + `colcon test` | ✅ 18 tests, 0 fallos (17 de la marcha: cinemática inversa, pares diagonales del trote, límites) |
| `display.launch.py` sin pantalla | ✅ nodos `cloudpaw_trot`, `robot_state_publisher`, `foxglove_bridge`; `/joint_states` a **50.0 Hz** con las 8 articulaciones; el cuerpo recorre el cuadrado de la demo en `/tf`; modo `sit` → cadera 1.1, rodilla −2.2 |
| `gazebo.launch.py` sin pantalla | ✅ robot creado en `empty.sdf`; `joint_state_broadcaster` y `leg_position_controller` activos; las articulaciones siguen las órdenes de pie (0.6/−1.2) y sentado (1.1/−2.2); cuerpo a 0.080 m sentado |
| Caminar con física en Gazebo (`gz_trot.py`, 10 s a 0.15 m/s pedidos) | ✅ camina y **no se cae**: avanzó **0.069 m** (deriva lateral 0.016 m), terminó a 0.134 m de altura con ~7° de alabeo y ~5° de cabeceo. Es **~5% de lo pedido**: la marcha en lazo abierto resbala sobre un modelo con masas y fricción supuestas. Para eso está la política PPO |
| Verlo en Foxglove desde tu navegador | ❌ no probado por mí (necesita tu navegador); pasos abajo |

## Ejecutar (en la EC2)

```bash
aws ssm start-session --target $CLOUDPAW_INSTANCE_ID --profile $CLOUDPAW_PROFILE --region us-east-1
sudo -iu ubuntu
cd ~/cloudpaw && git pull && ros2_ws/build.sh          # compila y corre los tests (usa el Python del sistema)
source ros2_ws/install/setup.bash
ros2 launch cloudpaw_description display.launch.py      # camina en cuadrado; demo:=false para mandarlo tú
```

Mandarle órdenes (otra sesión SSM):
```bash
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.15}, angular: {z: 0.0}}"   # avanzar
ros2 topic pub --once /cloudpaw/mode std_msgs/msg/String "{data: sit}"                           # sentarse
```
Sin `/cmd_vel` durante 0.5 s se detiene, igual que el firmware del ESP32 previsto.

## Verlo en Foxglove (desde tu Mac, sin abrir puertos)

1. Túnel SSM al puerto 8765 (el bridge escucha solo en `127.0.0.1` de la EC2):
   ```bash
   aws ssm start-session --target $CLOUDPAW_INSTANCE_ID --profile $CLOUDPAW_PROFILE --region us-east-1 \
     --document-name AWS-StartPortForwardingSession --parameters '{"portNumber":["8765"],"localPortNumber":["8765"]}'
   ```
2. Foxglove (app o https://app.foxglove.dev) → *Open connection* → *Foxglove WebSocket* → `ws://localhost:8765`.
3. Panel **3D**: marco fijo `odom`, activa *robot_description*. Verás el cuadrúpedo trotando.

## Gazebo (física)

```bash
ros2 launch cloudpaw_description gazebo.launch.py        # servidor sin ventana (EC2)
ros2 topic pub --once /leg_position_controller/commands std_msgs/msg/Float64MultiArray "{data: [0.6,-1.2,0.6,-1.2,0.6,-1.2,0.6,-1.2]}"
```
Con pantalla: `gui:=true`. En la EC2 no hay escritorio; para ver Gazebo hay que añadir un escritorio remoto (abajo).

## Lo que se necesita (requisitos)

| Para | Necesitas | En la EC2 |
|---|---|---|
| Compilar y la demo sin física | ROS 2 Jazzy (`ros-jazzy-desktop`), `xacro`, `robot_state_publisher`, `colcon` | ✅ instalado |
| Ver en el navegador | `ros-jazzy-foxglove-bridge` + túnel SSM + Foxglove | ✅ bridge; túnel y navegador en tu Mac |
| Física | `ros-jazzy-ros-gz`, `ros-jazzy-gz-ros2-control`, `ros2_controllers` | ✅ instalado |
| Ver la ventana de Gazebo o RViz | un escritorio remoto: NICE DCV (gratis en EC2) o VNC por túnel SSM, o una máquina Linux con pantalla | ❌ no instalado |
| En tu Mac (opcional) | Docker Desktop con `osrf/ros:jazzy-desktop`, o RoboStack con `pixi` | ❌ |
| El robot real | ROS 2 en una Raspberry Pi o micro-ROS en el ESP32; o sin ROS: el firmware de `RL_ESP32.md` | — |

**Ojo:** en la EC2 `uv` instala su propio `python3.12` en `~/.local/bin`. Si CMake lo elige, `colcon` falla con
`No module named 'catkin_pkg'`. `ros2_ws/build.sh` fija el Python del sistema.

## Siguiente paso

Sustituir la marcha abierta por la política PPO entrenada (misma interfaz: 8 ángulos a 50 Hz) y medir cuánto se acerca a la
velocidad pedida. Antes, cargar las masas, medidas y fricción reales del CloudPaw en el URDF.

```bash
ros2 launch cloudpaw_description gazebo.launch.py &
ros2 run cloudpaw_description gz_trot.py --ros-args -p speed:=0.15 -p seconds:=10   # trote con física
```
