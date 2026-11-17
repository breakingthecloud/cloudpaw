#!/usr/bin/env python3
"""Run the CloudPaw demo against `agentcore dev` and save a Markdown transcript + the console log.

    AWS_PROFILE=<perfil> python3 workshop/tools/record_dev.py [--port 8081]

Per step it records the command, its output, the time, and the slice of the `agentcore dev` console produced meanwhile; at the
end, the whole console log. Sanitized: no terminal escapes, home folder as ~, 12-digit numbers replaced. Needs a valid AWS
session (the model runs in Bedrock). Standard library only.
"""
import argparse, datetime, os, re, signal, subprocess, sys, time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SAY = os.path.join(ROOT, "workshop", "tools", "say.py")
ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")
TWELVE = re.compile(r"(?<![0-9])[0-9]{12}(?![0-9])")
SESSION = "cloudpaw-workshop-session-"

BLOCKS = [  # (title, note, session, messages): each block is its own robot
    ("Paso 2 · Hablarle al robot", "Español e inglés, las mismas herramientas.", "block-a-0001",
     ["avanza 2 metros y gira a la derecha", "walk forward half a meter, then turn left 45 degrees", "da la vuelta", "¿dónde estás?"]),
    ("Paso 3 · Límites, estados y reflejo", "El código frena lo que el modelo propone.", "block-b-0001",
     ["avanza 10 metros", "walk 2 meters, 20 times", "siéntate", "camina 1 metro", "sígueme", "para", "salta y haz una voltereta"]),
]


def clean(t):
    t = ANSI.sub("", t).replace("\r", "").replace(os.path.expanduser("~"), "~")
    return TWELVE.sub("<12-digit-number>", t)


def sh(cmd, cwd=ROOT, env=None):
    t0 = time.time()
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120, env=env)
    return (p.stdout + p.stderr).strip(), time.time() - t0, p.returncode


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default="8081")
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "workshop", "ensayo"))
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    day = datetime.date.today().isoformat()
    md_path = os.path.join(a.out_dir, day + "-agentcore-dev.md")
    log_path = os.path.join(a.out_dir, day + "-agentcore-dev-console.log")
    raw = log_path + ".raw"
    env = dict(os.environ, AWS_REGION=os.environ.get("AWS_REGION", "us-east-1"))

    ver = [(k, (clean(sh(c)[0]).splitlines() or ["?"])[0]) for k, c in [("node", ["node", "-v"]), ("pnpm", ["pnpm", "-v"]), ("agentcore", ["agentcore", "--version"])]]
    ver.append(("modelo", env.get("CLOUDPAW_MODEL_ID", "global.anthropic.claude-haiku-4-5-20251001-v1:0 (por defecto)")))

    steps = []  # (title, note, command, output, seconds, console slice)
    t0 = time.time()
    with open(raw, "wb") as lf:
        dev = subprocess.Popen(["agentcore", "dev", "--port", a.port], cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT, env=env, start_new_session=True)
    ready = False
    while time.time() - t0 < 90 and dev.poll() is None:
        if "is running on port" in open(raw, errors="ignore").read():
            ready = True
            break
        time.sleep(1)
    steps.append(("Paso 4 · `agentcore dev` (arranque)", "El agente como servicio local, con recarga automática y trazas locales.", "agentcore dev --port " + a.port,
                  "Listo en %.0f s." % (time.time() - t0) if ready else "NO arrancó (ver consola).", time.time() - t0, clean(open(raw, errors="ignore").read())))
    try:
        offset = len(open(raw, "rb").read())
        for title, note, sess, msgs in (BLOCKS if ready else []):
            for m in msgs:
                out, secs, rc = sh([sys.executable, SAY, m, "--local", "--port", a.port, "--session", SESSION + sess], env=env)
                data = open(raw, "rb").read()
                steps.append((title, note, 'python3 workshop/tools/say.py "%s" --local --port %s' % (m, a.port),
                              clean(out) + ("\n(exit code %d)" % rc if rc else ""), secs, clean(data[offset:].decode("utf-8", "ignore"))))
                offset = len(data)
        if ready:
            out, secs, _ = sh([sys.executable, SAY, "alto", "--local", "--port", a.port, "--session", SESSION + "block-c-0001", "--raw"], env=env)
            ev = [l for l in clean(out).splitlines() if l.startswith("data:")]
            steps.append(("Paso 4 · El flujo crudo del Runtime", "Lo que `say.py` resume: eventos SSE del servicio.", 'python3 workshop/tools/say.py "alto" --local --port %s --raw' % a.port,
                          "\n".join(ev[:14]) + "\n... (%d eventos)" % len(ev), secs, ""))
    finally:
        time.sleep(1)
        os.killpg(dev.pid, signal.SIGTERM)
        try:
            dev.wait(timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(dev.pid, signal.SIGKILL)

    full = clean(open(raw, errors="ignore").read())
    os.remove(raw)
    open(log_path, "w").write(full)

    L = ["# Ensayo de CloudPaw con `agentcore dev` — " + day, "",
         "Grabado con `workshop/tools/record_dev.py`. Cada paso corre contra el servicio local de `agentcore dev`; el modelo es real (Amazon Bedrock).",
         "Sanitizado: sin secuencias de terminal, tu carpeta personal como `~` y los números de 12 dígitos reemplazados.", "", "## Entorno", ""]
    L += ["- **%s:** `%s`" % kv for kv in ver] + ["", "## Resumen", "", "| # | Paso | Comando | Tiempo |", "|---|---|---|---|"]
    L += ["| %d | %s | `%s` | %.1f s |" % (i, s[0], s[2].replace("|", "\\|"), s[4]) for i, s in enumerate(steps, 1)] + [""]
    last = None
    for i, (title, note, cmd, out, secs, sl) in enumerate(steps, 1):
        if title != last:
            L += ["## " + title, "", note, ""]
            last = title
        L += ["### %d. `%s`" % (i, cmd[:90]), "", "```bash", cmd, "```", "", "Salida (%.1f s):" % secs, "", "```text", out or "(sin salida)", "```", ""]
        if sl.strip():
            L += ["<details><summary>Consola de <code>agentcore dev</code> durante este paso</summary>", "", "```text", sl.strip(), "```", "", "</details>", ""]
    L += ["## Log completo de la consola de `agentcore dev`", "", "Copia en `%s`." % os.path.basename(log_path), "",
          "<details><summary>Ver el log completo (%d líneas)</summary>" % len(full.splitlines()), "", "```text", full.strip(), "```", "", "</details>", ""]
    open(md_path, "w").write("\n".join(L))
    print("Transcripción:", os.path.relpath(md_path, ROOT))
    print("Log de consola:", os.path.relpath(log_path, ROOT))
    print("Pasos grabados:", len(steps))
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
