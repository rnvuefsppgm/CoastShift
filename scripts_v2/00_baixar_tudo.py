"""00 — Executa todos os downloads V2 (01–14). Cada script é independente: uma falha não interrompe os demais.
Uso: python 00_baixar_tudo.py [--paralelo 4] [--so 02,04,09]
Resumo em <BASE>/logs/status_downloads.json e log detalhado em <BASE>/logs/<script>.log
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import _v2

AQUI = os.path.dirname(os.path.abspath(__file__))


def rodar(script):
    t0 = time.time()
    logf = _v2.p("logs", os.path.basename(script).replace(".py", ".log"))
    with open(logf, "w", encoding="utf-8") as fh:
        r = subprocess.run([sys.executable, script], cwd=AQUI, stdout=fh, stderr=subprocess.STDOUT,
                           env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    st = {"script": os.path.basename(script), "ok": r.returncode == 0, "minutos": round((time.time() - t0) / 60, 1),
          "log": logf}
    print(("OK   " if st["ok"] else "FALHA"), st["script"], f"{st['minutos']} min", flush=True)
    return st


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--paralelo", type=int, default=4)
    ap.add_argument("--so", default="")
    a = ap.parse_args()
    scripts = sorted(glob.glob(os.path.join(AQUI, "[01][0-9]_*.py")))
    scripts = [s for s in scripts if not os.path.basename(s).startswith("00_")]
    if a.so:
        scripts = [s for s in scripts if os.path.basename(s)[:2] in a.so.split(",")]
    print("BASE:", _v2.BASE)
    res = []
    primeiro = [s for s in scripts if os.path.basename(s).startswith("01_")]
    for s in primeiro:                              # a zona costeira primeiro (evita corrida na criação)
        res.append(rodar(s))
    with ThreadPoolExecutor(a.paralelo) as ex:
        res += list(ex.map(rodar, [s for s in scripts if s not in primeiro]))
    _v2.salvar_json(res, "logs", "status_downloads.json")
    falhas = [r["script"] for r in res if not r["ok"]]
    print("Falhas:", falhas or "nenhuma")
