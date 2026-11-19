"""28 — Comparação estrutural O1 × O2 × O3 no subdomínio de Salvador (Península de Itapagipe – Comércio – Ribeira).

Mesmo DEM, mesma máscara do mar e mesmo nível (MHWS + ΔRSL mediano): O1 bathtub conectado; O2 probabilidade
(p ≥ 0,5, do script 21); O3 hidrodinâmico inercial local (Bates et al., 2010) com hidrograma de maré de 13 h.
Quantifica a superestimação do modelo estático numa área urbana de baía (métodos §4.8, comparação estrutural).
Saídas: <resultados>/validacao/O3_O2_salvador.csv e graficos/Fig_O1_O2_O3_Salvador.png/pdf
"""
import json
import os
import shutil
import sys

import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds

import _v2

sys.path.insert(0, _v2.REPO)
from coastshift import io as csio, models  # noqa: E402

RES = os.environ.get("COASTSHIFT_RESULTADOS", os.path.join(os.path.dirname(_v2.REPO), "resultados_O2_Bahia"))
BBOX_LL = (-38.535, -12.985, -38.455, -12.900)          # Itapagipe, Comércio, Ribeira, Calçada


def recortar(src, dst, bounds):
    os.makedirs(dst, exist_ok=True)
    for f in os.listdir(src):
        if f.endswith(".tif"):
            with rasterio.open(os.path.join(src, f)) as r:
                w = from_bounds(*bounds, transform=r.transform).round_offsets().round_lengths()
                a = r.read(1, window=w)
                prof = dict(r.profile, width=w.width, height=w.height, transform=r.window_transform(w))
            with rasterio.open(os.path.join(dst, f), "w", **prof) as o:
                o.write(a, 1)
    shutil.copy(os.path.join(src, "params.json"), dst)
    return w


def csi(a, b):
    return (a & b).sum() / max((a | b).sum(), 1)


if __name__ == "__main__":
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:4326", _v2.CRS, always_xy=True)
    x0, y0 = tr.transform(BBOX_LL[0], BBOX_LL[1])
    x1, y1 = tr.transform(BBOX_LL[2], BBOX_LL[3])
    src = os.path.join(_v2.BASE, "pacotes", "S2_Salvador_BTS")
    dst = os.path.join(RES, "validacao", "_subdominio_salvador")
    w = recortar(src, dst, (x0, y0, x1, y1))
    pk = csio.Package(dst)
    linhas, mapas = [], {}
    for ssp, ano in [("ssp245", 2014), ("ssp585", 2100)]:
        o1 = models.RUNNERS["O1"](pk, {"ssps": [ssp], "years": [ano], "ref": "MHWS", "quantile": 0.5, "conn": 8},
                                  progress=lambda f, m: None)
        o3 = models.RUNNERS["O3"](pk, {"ssps": [ssp], "years": [ano], "ref": "MHWS", "quantile": 0.5, "hours": 13,
                                       "coarsen": 1, "rain_mmh": 0, "amp": 1.0}, progress=lambda f, m: None)
        tag = "atual_2014" if ano == 2014 else f"{ssp}_{ano}"
        with rasterio.open(os.path.join(RES, "geotiff", f"prob_S2_Salvador_BTS_{tag}.tif")) as r:
            p2 = r.read(1, window=w)
        p2 = np.where(p2 < 0, 0, p2)
        k = f"{ssp}_{ano}"
        a1 = np.nan_to_num(o1.layers[f"inundado_{k}"]) > 0
        a3 = np.nan_to_num(o3.layers[f"prof_max_{k}"]) > 0.05
        a2 = p2 >= 0.5
        terra = np.isfinite(pk.dem)
        a1, a2, a3 = a1 & terra, a2 & terra, a3 & terra
        cel = pk.cell ** 2 / 1e4
        linhas.append({"cenario": "Present day" if ano == 2014 else f"{ssp.upper()} {ano}", "O1_ha": a1.sum() * cel,
                       "O2_p50_ha": a2.sum() * cel, "O2_E_A_ha": p2[terra].sum() * cel, "O3_ha": a3.sum() * cel,
                       "CSI_O3_vs_O1": csi(a3, a1), "CSI_O3_vs_O2": csi(a3, a2),
                       "razao_O1_O3": a1.sum() / max(a3.sum(), 1), "razao_O2_O3": a2.sum() / max(a3.sum(), 1)})
        mapas[k] = (a1, p2, np.nan_to_num(o3.layers[f"prof_max_{k}"]), terra)
    t = pd.DataFrame(linhas).round(3)
    t.to_csv(os.path.join(RES, "validacao", "O3_O2_salvador.csv"), index=False, encoding="utf-8-sig")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    a1, p2, d3, terra = mapas["ssp585_2100"]
    ext = (pk.profile["transform"].c, pk.profile["transform"].c + pk.dem.shape[1] * pk.cell,
           pk.profile["transform"].f - pk.dem.shape[0] * pk.cell, pk.profile["transform"].f)
    fig, axs = plt.subplots(1, 3, figsize=(7.2, 3.2))
    base = np.where(terra, 0.85, np.nan)
    for ax, (arr, cm, vmax, tit) in zip(axs, [(a1.astype(float), "Reds", 1, "(a) O1 bathtub"), (p2, "YlOrRd", 1, "(b) O2 probability"),
                                             (d3, "Blues", 1.5, "(c) O3 max depth (m)")]):
        ax.imshow(base, extent=ext, cmap="gray", vmin=0, vmax=1)
        im = ax.imshow(np.ma.masked_where((arr <= 0.01) | ~terra, arr), extent=ext, cmap=cm, vmin=0, vmax=vmax)
        ax.set_title(tit, fontsize=10.5, fontweight="bold", loc="left")
        ax.set_xticks([])
        ax.set_yticks([])
        if tit.startswith("(b)") or tit.startswith("(c)"):
            cb = fig.colorbar(im, ax=ax, orientation="horizontal", fraction=0.05, pad=0.03)
            cb.ax.tick_params(labelsize=8)
    r = t.iloc[-1]
    fig.suptitle(f"Salvador (Itapagipe–Comércio), SSP5-8.5 2100 at MHWS — O1 {r.O1_ha:,.0f} ha · O2 (p≥0.5) "
                 f"{r.O2_p50_ha:,.0f} ha · O3 {r.O3_ha:,.0f} ha", fontsize=9.5, fontweight="bold", x=0.01, ha="left")
    fig.tight_layout()
    os.makedirs(os.path.join(RES, "graficos"), exist_ok=True)
    for ext_ in ("png", "pdf"):
        fig.savefig(os.path.join(RES, "graficos", f"Fig_O1_O2_O3_Salvador.{ext_}"), dpi=600, bbox_inches="tight")
    _v2.log("O3×O2 Salvador: " + "; ".join(f"{x.cenario}: O1 {x.O1_ha:.0f}, O2 {x.O2_p50_ha:.0f}, O3 {x.O3_ha:.0f} ha"
                                            for x in t.itertuples()))
