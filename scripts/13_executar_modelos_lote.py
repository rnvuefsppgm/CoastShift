# %% [markdown]
# # 13 — Executar os modelos em lote (sem interface): O1 e O2 para os setores; O3 nos subdomínios
# Gera GeoTIFFs e tabelas em <BASE>/resultados/<pacote>/<modelo>/ e um resumo estadual `resumo_bahia_O2.csv`.
# Para O4/O5 ou ajustes finos, use o aplicativo (app.py / CoastShift.exe).

# %%
import json
import os
import sys

import pandas as pd

if "google.colab" in sys.modules:
    sys.path.insert(0, "/content/CoastShift/scripts")
from _comum import load_config, path, add_repo_to_path

add_repo_to_path()
from coastshift import io as csio, models  # noqa: E402

cfg = load_config()
N_MC = 300
ANOS = [2030, 2050, 2070, 2100, 2150]
SSPS = ["ssp126", "ssp245", "ssp585"]


def salvar(res, pkg, dest):
    os.makedirs(dest, exist_ok=True)
    for k, v in res.layers.items():
        csio.write_raster(os.path.join(dest, f"{k}.tif"), v, pkg.profile)
    pd.DataFrame(res.table).to_csv(os.path.join(dest, "tabela.csv"), index=False, encoding="utf-8-sig")
    json.dump(res.meta, open(os.path.join(dest, "meta.json"), "w", encoding="utf-8"), indent=1, default=str, ensure_ascii=False)


def prog(f, m):
    print(f"\r{f:5.0%} {m:60s}", end="")


resumo = []
for nome in list(cfg["setores"]) + list(cfg["subdominios"]):
    pasta = path("pacotes", nome)
    if not os.path.exists(os.path.join(pasta, "params.json")):
        continue
    pkg = csio.Package(pasta)
    ssps = [s for s in SSPS if s in pkg.params["ar6"].get("scenarios", {})]
    anos = [a for a in ANOS if a <= max(pkg.params["ar6"]["years"])]
    setup = bool(pkg.params["waves"].get("costa_aberta")) and pkg.params["waves"].get("hs", 0) > 0
    base = {"ssps": ssps, "years": anos, "ref": "MHWS", "quantile": 0.5, "setup": setup, "conn": 8}
    rodar = {"O1": base, "O2": {**base, "n": N_MC}} if nome in cfg["setores"] else \
            {"O3": {**base, "years": [2050, 2100], "hours": 13, "coarsen": 1}}
    for m, opt in rodar.items():
        print(f"\n== {nome} {m}")
        r = models.RUNNERS[m](pkg, opt, progress=prog)
        salvar(r, pkg, path("resultados", nome, m))
        if m == "O2":
            resumo += [{"setor": nome, **row} for row in r.table]
pd.DataFrame(resumo).to_csv(path("resultados", "resumo_bahia_O2.csv"), index=False, encoding="utf-8-sig")
print("\nresumo:", path("resultados", "resumo_bahia_O2.csv"))
