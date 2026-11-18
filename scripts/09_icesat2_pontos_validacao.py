# %% [markdown]
# # 09 — Pontos de referência ICESat-2 ATL08 para validar/calibrar o erro dos DEMs
# Fonte: NASA ICESat-2 ATL08 (Neuenschwander & Pitts, 2019; NSIDC). Requer conta NASA Earthdata (gratuita).
# Lê h_te_best_fit (terreno, altura elipsoidal WGS84) por segmento de 100 m e filtra qualidade.
# A conversão para o datum do pacote (altitude normal SGB − NMM local) é feita no script 11, com a mesma
# cadeia aplicada aos DEMs (Eqs. 1–3), garantindo comparação no mesmo referencial.

# %%
import glob
import os
import sys

import h5py
import numpy as np
import pandas as pd

if "google.colab" in sys.modules:
    sys.path.insert(0, "/content/CoastShift/scripts")
from _comum import load_config, path

cfg = load_config()
import earthaccess
earthaccess.login()  # usuário/senha Earthdata (interativo ou ~/.netrc)

# %% 1) Busca e download por setor
for nome, s in cfg["setores"].items():
    out = path("icesat2", nome)
    os.makedirs(out, exist_ok=True)
    if glob.glob(os.path.join(out, "*.h5")):
        continue
    res = earthaccess.search_data(short_name="ATL08", bounding_box=tuple(s["bbox"]),
                                  temporal=("2019-01-01", "2025-12-31"))
    print(nome, len(res), "granulos")
    earthaccess.download(res, out)

# %% 2) Extração e filtragem
FEIXES = ["gt1l", "gt1r", "gt2l", "gt2r", "gt3l", "gt3r"]
for nome, s in cfg["setores"].items():
    rows = []
    lon0, lat0, lon1, lat1 = s["bbox"]
    for f in glob.glob(path("icesat2", nome, "*.h5")):
        with h5py.File(f, "r") as h:
            for b in FEIXES:
                g = f"{b}/land_segments"
                if g not in h:
                    continue
                lat = h[f"{g}/latitude"][:]
                lon = h[f"{g}/longitude"][:]
                hte = h[f"{g}/terrain/h_te_best_fit"][:]
                unc = h[f"{g}/terrain/h_te_uncertainty"][:]
                can = h[f"{g}/canopy/h_canopy"][:]
                ok = (hte < 1e30) & (unc < 1.0) & (lon >= lon0) & (lon <= lon1) & (lat >= lat0) & (lat <= lat1)
                rows.append(pd.DataFrame({"lon": lon[ok], "lat": lat[ok], "h_elip": hte[ok], "incerteza": unc[ok],
                                          "h_dossel": np.where(can[ok] > 1e30, np.nan, can[ok]),
                                          "granulo": os.path.basename(f), "feixe": b}))
    if rows:
        df = pd.concat(rows, ignore_index=True)
        df = df[df["h_elip"].between(-30, 80)]  # costa baixa; altura elipsoidal inclui ondulação (~ −10 a −20 m na BA)
        df.to_csv(path("icesat2", f"atl08_{nome}.csv"), index=False)
        print(nome, len(df), "pontos")
