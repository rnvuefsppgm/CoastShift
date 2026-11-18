# %% [markdown]
# # 08 — Clima de ondas (ERA5) e setup de Stockdon por setor
# Fonte: ERA5 hourly single levels (Hersbach et al., 2020), Copernicus CDS — requer conta e ~/.cdsapirc
# (https://cds.climate.copernicus.eu/how-to-api). Variáveis: swh (Hs), pp1d (Tp), mwd.
# Setup (Eq. 10): <η> = 0.35 β_f (H0 L0)^0.5, L0 = g T²/2π (Stockdon et al., 2006).
# β_f (declividade da face de praia) vem do config (meça com perfis, CoastSat ou ICESat-2).
# Alternativa sem conta CDS: WAVERYS (Copernicus Marine) com copernicusmarine.

# %%
import json
import os
import sys

import numpy as np
import xarray as xr

if "google.colab" in sys.modules:
    sys.path.insert(0, "/content/CoastShift/scripts")
from _comum import load_config, path

cfg = load_config()
ANOS = range(1995, 2025)
NC = path("ondas", "era5_ondas_{ano}.nc")

# %% 1) Download (1 arquivo por ano; 3-horário; caixa ao largo da Bahia)
import cdsapi
c = cdsapi.Client()
for ano in ANOS:
    if os.path.exists(NC.format(ano=ano)):
        continue
    c.retrieve("reanalysis-era5-single-levels", {
        "product_type": ["reanalysis"], "format": "netcdf",
        "variable": ["significant_height_of_combined_wind_waves_and_swell", "peak_wave_period", "mean_wave_direction"],
        "year": [str(ano)], "month": [f"{m:02d}" for m in range(1, 13)], "day": [f"{d:02d}" for d in range(1, 32)],
        "time": [f"{h:02d}:00" for h in range(0, 24, 3)], "area": [-11.0, -40.0, -19.0, -36.5],
    }, NC.format(ano=ano))

# %% 2) Estatísticas por setor e setup
ds = xr.open_mfdataset(path("ondas", "era5_ondas_*.nc"), combine="by_coords")
tdim = "valid_time" if "valid_time" in ds.dims else "time"
out = {}
for nome, s in cfg["setores"].items():
    lon0, lat0 = s["ponto_mar"]
    p = ds.sel(longitude=lon0, latitude=lat0, method="nearest").load()
    hs, tp = p["swh"].values, p["pp1d"].values
    ok = np.isfinite(hs) & np.isfinite(tp)
    hs99 = float(np.percentile(hs[ok], 99))
    tp99 = float(np.median(tp[ok][hs[ok] >= hs99]))
    beta = s["declividade_praia"]
    L0 = 9.81 * tp99 ** 2 / (2 * np.pi)
    setup = 0.35 * beta * np.sqrt(hs99 * L0)
    out[nome] = {"hs": round(hs99, 2), "tp": round(tp99, 1), "beach_slope": beta, "setup_m": round(float(setup), 3),
                 "hs_mediana": round(float(np.median(hs[ok])), 2), "costa_aberta": s["aberta"],
                 "fonte": "ERA5 1995–2024, Hs p99 e Tp associado; setup Stockdon et al. (2006)"}
    print(nome, out[nome])
for sd, s in cfg["subdominios"].items():
    out[sd] = out[s["setor"]]
with open(path("ondas", "ondas_setores.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1, ensure_ascii=False)
