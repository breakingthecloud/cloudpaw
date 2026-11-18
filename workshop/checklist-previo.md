# Checklist previo — CloudPaw (miércoles 18 nov 2026)

Marca cada punto. Lo que ya está verificado en tu máquina está anotado; lo demás es **para hacer el martes**.

## 1. Tu máquina (lo que encontré revisándola)

**Ya hecho en tu máquina (16 nov, noche):**
- CLI de AgentCore **1.0.3** instalada con pnpm bajo Node 22.23.2: `~/Library/pnpm/bin/agentcore`.
- `pnpm setup` añadió a tu `~/.zshrc` el bloque estándar de `PNPM_HOME` (8 líneas). Respaldo: `~/.zshrc.bak-agentcore-20261116`.
- El kit usa pnpm: `agentcore/cdk/pnpm-lock.yaml`, `packageManager` y `engines` fijados, `.node-version` = 22.

**Te toca a ti:**
- [ ] **Abre una terminal nueva** (o `source ~/.zshrc`) y `fnm use 22` (o `fnm default 22` si quieres que sea siempre). Tu predeterminado sigue siendo Node 20.20: con Node 20, `pnpm` 11 no arranca (error de `node:sqlite`).
- [ ] Corre `workshop/tools/doctor.sh` (y `--aws` con credenciales): debe terminar en "Ready".
- [ ] **El `agentcore` viejo (0.11.0, Homebrew) sigue instalado** en `/opt/homebrew/bin`. El nuevo va primero en tu `PATH`, pero un script o una terminal sin tu `.zshrc` (como las de herramientas automáticas) puede usar el viejo. Cuando estés seguro de que no lo usas en otros proyectos: `/opt/homebrew/bin/npm uninstall -g @aws/agentcore`. Ojo: proyectos creados con la CLI 0.x necesitan `agentcore migrate` para la 1.x.
- [ ] Si `agentcore --version` imprime un error, un paquete antiguo de pip lo tapa: `pip uninstall bedrock-agentcore-starter-toolkit`.
- [ ] **Python.** Tu `python3` es 3.9.6 y el proyecto pide 3.10 o más. No hace falta cambiarlo: `uv` descarga y usa 3.12 solo para el proyecto. El ayudante `say.py` sí corre con tu 3.9.

## 2. Instalar el proyecto (una vez)

```bash
cd cloudpaw-workshop
(cd agentcore/cdk && pnpm install)     # dependencias de CDK; sin esto `agentcore build` falla
(cd app/agent && uv sync)              # dependencias de Python
(cd app/agent && uv run --with pytest pytest -q)   # 97 tests, ~3 s, sin AWS
```

## 3. AWS (el martes, con calma)

- [ ] Credenciales válidas en la cuenta de pruebas: `aws sts get-caller-identity --profile <perfil>`. Las sesiones SSO caducan; renuévalas **el miércoles por la mañana**.
- [ ] Región **us-east-1**.
- [ ] Acceso al modelo: `uv run python play.py -c "avanza 1 metro"` responde. El modelo por defecto es `global.anthropic.claude-haiku-4-5-20251001-v1:0`. Si falla por acceso, usa el Plan B1.
- [ ] Permisos para desplegar: tu identidad debe poder llamar a AgentCore y **asumir los roles de bootstrap de CDK** (guía oficial: *Use the AgentCore CLI* → permisos).
- [ ] **Ensayo completo del despliegue (el paso que no pude probar):**
  ```bash
  agentcore build
  agentcore deploy          # el primero incluye el bootstrap de CDK
  agentcore status
  python3 workshop/tools/say.py "avanza 2 metros y gira a la derecha"
  agentcore traces runtime list --since 30m
  ```
  Anota aquí **cuánto tardó** el primer deploy: `______` min, y el segundo: `______` min. Eso decide si lo lanzas en vivo o lo dejas ya desplegado.
- [ ] Deja el agente **ya desplegado** al terminar el ensayo (es tu respaldo si el deploy en vivo se alarga).
- [ ] `agentcore dev --mode browser` abre el Agent Inspector (no lo probé).

## 4. Seguridad y pantalla

- [ ] **No hagas commit de `agentcore/aws-targets.json` después del deploy:** el primer `deploy` crea el destino `default` con el ID de tu cuenta. El repo ya ignora `agentcore/.cli/` y un test falla si aparece un ID real.
- [ ] Las salidas de `agentcore status` y `deploy` muestran ARNs con tu ID de cuenta. Si grabas o transmites, decide si lo tapas.
- [ ] Credenciales: exporta las variables solo en la terminal que las usa (`eval "$(aws configure export-credentials --profile <perfil> --format env)"`) y ciérrala al terminar. Nunca las pegues en un slide.
- [ ] Costos: un mensaje usa tokens de Bedrock; el Runtime cobra por uso. No medí el costo: revisa los precios antes de decir un número.

## 5. Sala

- [ ] Prueba el wifi de la sede o lleva **hotspot** del celular. Sin internet, ve al Plan B (`plan-b.md`).
- [ ] Slides: abre `workshop/slides/index.html` (funciona sin internet: no usa fuentes ni imágenes externas). Flechas ← → para moverte.
- [ ] Letra de la terminal grande; tema oscuro con buen contraste; notificaciones apagadas.
- [ ] Copia de respaldo: el repo y las slides en un USB y en tu celular.
- [ ] **Graba una pantalla** de la demo completa el martes (QuickTime). Es tu mejor respaldo.
- [ ] Pregunta a los organizadores: ¿proyector HDMI o USB-C? ¿hay enchufe? ¿cuántas personas (para el volumen y la letra)?
- [ ] Completa en la slide 17 la URL del repo y un QR cuando lo publiques (hay un comentario HTML en el archivo).

## 6. Después del evento

- [ ] Limpia lo desplegado: `agentcore remove all --yes` y luego `agentcore deploy --yes`. Comprueba con `agentcore status` y en la consola de CloudFormation que el stack ya no está.
- [ ] Revoca o deja caducar las credenciales usadas.
