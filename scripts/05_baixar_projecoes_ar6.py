# %% [markdown]
# # 05 — Projeções regionais do IPCC AR6 por setor (Python/Colab)
# Fonte: Garner et al. (2021) IPCC AR6 Sea Level Projections, Zenodo doi:10.5281/zenodo.6382554
# (Fox-Kemper et al., 2021, AR6 WGI cap. 9). Arquivo: pacote "regional confidence"; variável `sea_level_change`
# (mm, rel. 1995–2014) com dimensões (quantiles, years, locations). **Confira nomes no pacote baixado.**
# Saída: `ar6/ar6_setores.json` no formato lido pelo CoastShift (m).

# %%
import glob
import json
import os
import sys
import zipfile

import numpy as np
import requests
import xarray as xr

if "google.colab" in sys.modules:
    sys.path.insert(0, "/content/CoastShift/scripts")
from _comum import load_config, path

cfg = load_config()
QUANTIS = [0.01, 0.05, 0.17, 0.5, 0.83, 0.95, 0.99]
dest = path("ar6")

# %% 1) Localizar e baixar o zip regional (vários GB; feito uma vez)
rec = requests.get("https://zenodo.org/api/records/6382554", timeout=60).json()
arquivos = {f["key"]: f["links"]["self"] for f in rec["files"]}
print("\n".join(arquivos))
alvo = next(k for k in arquivos if "regional" in k and "confidence" in k)
zpath = os.path.join(dest, alvo)
if not os.path.exists(zpath):
    with requests.get(arquivos[alvo], stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(zpath, "wb") as f:
            for chunk in r.iter_content(1 << 22):
                f.write(chunk)
print("zip:", zpath)

# %% 2) Extrair apenas os arquivos "total_<ssp>_medium_confidence_values.nc" (+ low confidence SSP5-8.5)
with zipfile.ZipFile(zpath) as z:
    membros = [m for m in z.namelist() if m.endswith("_values.nc") and "/total_" in m
               and ("medium_confidence" in m or ("low_confidence" in m and "ssp585" in m))]
    for m in membros:
        if not os.path.exists(os.path.join(dest, os.path.basename(m))):
            with z.open(m) as src, open(os.path.join(dest, os.path.basename(m)), "wb") as out:
                out.write(src.read())
print("\n".join(os.path.basename(m) for m in membros))

# %% 3) Ponto da grade mais próximo do 'ponto_mar' de cada setor
saida = {}
for nome, s in cfg["setores"].items():
    lon0, lat0 = s["ponto_mar"]
    setor = {"quantiles": QUANTIS, "scenarios": {}, "fonte": "IPCC AR6 (Garner et al., 2021) medium confidence"}
    for nc in sorted(glob.glob(os.path.join(dest, "total_*_values.nc"))):
        conf = "low" if "low_confidence" in nc else "medium"
        ssp = os.path.basename(nc).split("_")[1] + ("_lowconf" if conf == "low" else "")
        ds = xr.open_dataset(nc)
        lat, lon = ds["lat"].values, ds["lon"].values
        lon = np.where(lon > 180, lon - 360, lon)
        grid = ds["locations"].values > 1000  # IDs de grade (marégrafos PSMSL têm IDs pequenos) — confira no arquivo
        d2 = (lat - lat0) ** 2 + (lon - lon0) ** 2
        d2[~grid] = np.inf
        i = int(np.argmin(d2))
        v = ds["sea_level_change"].isel(locations=i).sel(quantiles=QUANTIS, method="nearest")
        v = v.transpose("years", "quantiles")
        setor["years"] = [int(y) for y in ds["years"].values]
        setor["scenarios"][ssp] = (v.values / 1000.0).round(4).tolist()
        setor["ponto_ar6"] = {"lat": float(lat[i]), "lon": float(lon[i]), "location_id": int(ds["locations"].values[i])}
    saida[nome] = setor
    print(nome, setor["ponto_ar6"], {k: v[setor['years'].index(2100)][3] for k, v in setor["scenarios"].items()})

for sd, s in cfg["subdominios"].items():
    saida[sd] = saida[s["setor"]]
with open(os.path.join(dest, "ar6_setores.json"), "w", encoding="utf-8") as f:
    json.dump(saida, f, indent=1)
print("salvo ar6_setores.json (valores em m, rel. 1995–2014; anos:", saida[next(iter(saida))]["years"], ")")
