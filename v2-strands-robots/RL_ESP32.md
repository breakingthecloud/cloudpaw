# CloudPaw RL: PPO, recompensa y despliegue en el ESP32

Estado (17-nov-2026): **especificación, recompensa, entorno y exportador a C hechos y probados. La política todavía NO está entrenada.**
Las specs del robot son **inferidas** (no hay hardware definido); todas están en `cloudpaw_rl/spec.py`, marcadas `ASSUMED`.

## 1. El reparto de responsabilidades

| Capa | Dónde corre | Frecuencia | Qué decide |
|---|---|---|---|
| Agente de lenguaje (V1: Strands + Bedrock) | Nube / AgentCore | segundos | *Qué* hacer: "avanza 1 m", "gira", "alto" → comando `(vx, wz)` |
| Política PPO (MLP) | **ESP32** | 50 Hz | *Cómo* mover las patas para cumplir el comando |
| Servos + límites | ESP32 + PCA9685 | 50 Hz | Recorta a límites y velocidad del servo; e-stop físico aparte |

El agente nunca manda ángulos de articulación: manda un comando de velocidad acotado. La política, que vive en el robot, lo
traduce en movimiento. Si se pierde la conexión, el robot sigue estable con el último comando o `(0, 0)`.

## 2. Specs inferidas (cámbialas en `spec.py`)

| | Supuesto | Por qué |
|---|---|---|
| Microcontrolador | ESP32-S3, 240 MHz, FPU | barato, con FPU de float32; un MLP de este tamaño cabe de sobra |
| Servos | 8 × MG90S (2 por pata: cadera y rodilla), sin realimentación | lo típico en cuadrúpedos DIY; 12 si se añade abducción |
| Driver | PCA9685 por I²C | 16 canales PWM, libera al ESP32 |
| IMU | MPU-6050 / ICM-42688 | da gravedad proyectada y velocidad angular |
| Control | 50 Hz | 20 ms por ciclo; la inferencia toma mucho menos (no medido en el ESP32) |
| Velocidad del servo | 10 rad/s | MG90S ≈ 0.1 s / 60° a 4.8 V |

## 3. Observación (26 valores) y acción (8)

`projected_gravity` (3, IMU) · `angular_velocity` (3, IMU) · `command` (2: vx, wz) · `gait_phase` (2: sin/cos de un reloj de 1.5 Hz) ·
`joint_commanded` (8: **posición ordenada** menos la de pie, porque los servos no informan su posición) · `last_action` (8).

Acción en [-1, 1] → desfase desde la pose de pie × 0.35 rad → **recortado** a ±límite y a lo que el servo puede recorrer en 20 ms
(`policy_io.action_to_targets`). El mismo recorte corre en el ESP32: la política nunca aprende a pedir algo que no obtendrá.

## 4. Recompensa (`cloudpaw_rl/reward.py`)

Recompensa por paso = Σ peso × término × dt.

| Término | Peso | Qué premia o castiga |
|---|---|---|
| `track_vx` | +1.5 | seguir la velocidad pedida: exp(−error²/0.25) |
| `track_wz` | +0.8 | seguir el giro pedido |
| `lin_vel_z` | −2.0 | rebotar |
| `ang_vel_xy` | −0.05 | balancearse (roll/pitch) |
| `orientation` | −1.0 | inclinar el cuerpo |
| `base_height` | −20 | alejarse de la altura de pie |
| `action_rate` | −0.02 | movimientos bruscos (engranajes plásticos) |
| `servo_speed` | −0.01 | pedir más velocidad que la del servo |
| `joint_limits` | −1.0 | acercarse al tope mecánico |
| `alive` | +0.5 | no caerse |

**Fin de episodio:** inclinación > 0.8 rad (~46°) o altura < 50% de la de pie. Los pesos son un **punto de partida**; se ajustan
mirando cada término por separado (el entorno los devuelve en `info["terms"]`).

## 5. Entrenamiento (siguiente paso, en la EC2)

`cloudpaw_rl/env_mujoco.py` es un entorno con la interfaz de gymnasium, sobre el **Go2 como proxy de 8 grados de libertad**
(abducción bloqueada) hasta tener el modelo propio de CloudPaw. Medido en una Mac M-series: ~1 100 pasos/s por proceso.
Plan propuesto (no ejecutado):
1. Modelo propio del CloudPaw (MJCF/URDF con masas y medidas reales) → sustituye al proxy.
2. PPO con Stable-Baselines3 (`MlpPolicy`, actor 26→64→64→8 tanh), 8–16 entornos en paralelo en la EC2 (4 vCPU), comandos aleatorios.
3. **Domain randomization** para pasar a lo real: masa ±20%, fricción 0.5–1.25, retraso de servo 0–20 ms, ruido de IMU,
   ganancias de servo ±30%, empujones.
4. Exportar el actor (`W0, b0, W1, b1, W2, b2` + `obs_mean/std` a un `.npz`) y generar el header:
   `uv run python -m cloudpaw_rl.export_c policy.npz cloudpaw_policy.h`.

No hay estimación de tiempo de entrenamiento: depende del modelo real y no se ha medido.

## 6. En el ESP32

`export_c.py` genera **un header sin dependencias**: pesos `static const float` (6 408 parámetros, 25 KB en flash como float32) y
`cloudpaw_policy_forward(obs, act)`. **Probado:** compilado con `cc -std=c99 -Wall -Werror` y comparado con numpy (error < 1e-5).
**No probado:** compilado con ESP-IDF ni medido en una placa.

Bucle de control (diseño, no compilado):
```c
// cada 20 ms (timer de hardware o tarea FreeRTOS con vTaskDelayUntil)
imu_read(&gravity, &gyro);                         // MPU-6050 por I2C
build_obs(obs, gravity, gyro, cmd_vx, cmd_wz, t, commanded_offset, last_action);   // mismo orden que policy_io.build_obs
cloudpaw_policy_forward(obs, act);                 // < 1 ms esperado (no medido)
action_to_targets(act, targets);                   // mismo recorte: límites + velocidad del servo
if (!estop_pressed && !tilt_exceeded) pca9685_write(targets);   // e-stop físico y caída: servos sueltos o en pose segura
```
El comando `(cmd_vx, cmd_wz)` llega por Wi-Fi o MQTT (AWS IoT) desde el agente; si no llega en 0.5 s, pasa a `(0, 0)`.

## 7. Qué está verificado

| Pieza | Estado |
|---|---|
| Spec, observación, mapeo de acción | ✅ tests (`tests/test_rl.py`) |
| Recompensa: cada mal comportamiento la baja; términos aislados | ✅ tests + 2 mutaciones detectadas |
| Detección de caída | ✅ test y simulación (colapso detectado en 0.46 s) |
| Entorno MuJoCo (proxy Go2) | ✅ 6 tests de integración: de pie con acción 0, finito con acciones aleatorias, reproducible |
| Exportador C | ✅ compilado y comparado con numpy (con y sin normalización) |
| Política PPO entrenada | ❌ no entrenada |
| Firmware ESP32 | ❌ diseño; no compilado ni probado en placa |
| Modelo físico propio de CloudPaw | ❌ falta (se usa el Go2 como proxy) |
