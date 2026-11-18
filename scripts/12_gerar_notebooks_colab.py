"""12 — Converte os scripts 01–13 (células '# %%') em notebooks .ipynb para o Google Colab.
Uso: python 12_gerar_notebooks_colab.py   → cria scripts/notebooks/*.ipynb"""
import glob
import json
import os

AQUI = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(AQUI, "notebooks")
os.makedirs(OUT, exist_ok=True)
SETUP = ("import sys, os\nif 'google.colab' in sys.modules and not os.path.isdir('/content/CoastShift'):\n"
         "    os.system('git clone -q https://github.com/rnvuefsppgm/CoastShift /content/CoastShift')\n"
         "sys.path.insert(0, '/content/CoastShift/scripts')")


def celulas(src):
    cells, cur, kind = [], [], "code"
    for line in src.splitlines():
        if line.startswith("# %%"):
            if any(x.strip() for x in cur):
                cells.append((kind, cur))
            kind = "markdown" if "[markdown]" in line else "code"
            cur = []
            rest = line[4:].replace("[markdown]", "").strip()
            if rest and kind == "code":
                cur.append("# " + rest)
            continue
        cur.append(line[2:] if kind == "markdown" and line.startswith("# ") else ("" if kind == "markdown" and line == "#" else line))
    if any(x.strip() for x in cur):
        cells.append((kind, cur))
    return cells


for f in sorted(glob.glob(os.path.join(AQUI, "[01][0-9]_*.py"))):
    if os.path.basename(f).startswith("12_"):
        continue
    cells = [("code", SETUP.splitlines())] + celulas(open(f, encoding="utf-8").read())
    nb = {"nbformat": 4, "nbformat_minor": 5,
          "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"}, "colab": {"provenance": []}},
          "cells": [{"cell_type": k, "metadata": {}, "source": "\n".join(c).strip("\n"),
                     **({"outputs": [], "execution_count": None} if k == "code" else {})} for k, c in cells]}
    dst = os.path.join(OUT, os.path.basename(f).replace(".py", ".ipynb"))
    with open(dst, "w", encoding="utf-8") as g:
        json.dump(nb, g, indent=1, ensure_ascii=False)
    print("notebook:", os.path.basename(dst))
