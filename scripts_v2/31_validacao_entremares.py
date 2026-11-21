"""31 — Validação pela zona entremarés (consistência ecológica), para cada rodada de ℓ.

Mangue e apicum ocupam, por definição, a faixa alagada pelas preamares de sizígia; portanto, na linha de base atual e
na MHWS, essas áreas devem aparecer inundadas. Referências independentes do DEM: MapBiomas (mangue = 5, apicum = 32,
campo alagado = 11) e Global Mangrove Watch v3 2020 (script 15). Métricas por habitat, setor e ℓ: área, fração com
p ≥ 0,5 (taxa de acerto entremarés), p médio e fração com p ≥ 0,9; e a fração da área prevista com p ≥ 0,5 que cai em
habitat entremarés/úmido (coerência). Apicum fica entre a MHWS e a preamar máxima: espera-se acerto parcial.

Saídas: resultados_O2_Bahia/validacao_entremares/{entremares_por_ell.csv, Fig_validacao_entremares.png|pdf}
"""
import glob
import os

import matplotlib
import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT

import _v2

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

R = os.path.join(os.path.dirname(_v2.REPO), "resultados_O2_Bahia")
OUT = os.path.join(R, "validacao_entremares")
HAB = {"Mangue (MapBiomas)": ("mb", [5]), "Apicum (MapBiomas)": ("mb", [32]), "Campo alagado (MapBiomas)": ("mb", [11]),
       "Mangue (GMW 2020)": ("gmw", [1])}


def ler_em(f, prof):
    with rasterio.open(f) as src, WarpedVRT(src, crs=prof["crs"], transform=prof["transform"], width=prof["width"],
                                            height=prof["height"], resampling=Resampling.nearest) as v:
        return v.read(1)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    linhas = []
    for d in sorted(glob.glob(os.path.join(R, "ell_*m"))):
        ell = int(os.path.basename(d)[4:-1])
        for setor in _v2.SETORES:
            fp = os.path.join(d, "geotiff", f"prob_{setor}_atual_2014.tif")
            if not os.path.exists(fp):
                continue
            with rasterio.open(fp) as src:
                p, prof = src.read(1), src.profile
            lc = ler_em(_v2.p("lulc", f"landcover_{setor}.tif"), prof)
            gmw = ler_em(_v2.p("habitat", f"gmw2020_{setor}.tif"), prof)
            p = np.where((p >= 0) & (p <= 1), p, np.nan)          # nodata e mar fora
            terra = np.isfinite(p)
            a_ha = abs(prof["transform"].a * prof["transform"].e) / 1e4
            prev = terra & (p >= 0.5)
            umido = np.isin(lc, [5, 32, 11]) | (gmw == 1)
            for nome, (fonte, cl) in HAB.items():
                h = terra & np.isin(lc if fonte == "mb" else gmw, cl)
                if not h.any():
                    continue
                linhas.append({"ell_m": ell, "setor": setor, "habitat": nome, "area_ha": round(h.sum() * a_ha, 1),
                               "frac_p_ge_0.5": float(prev[h].mean()), "p_medio": float(p[h].mean()),
                               "frac_p_ge_0.9": float((p[h] >= 0.9).mean())})
            linhas.append({"ell_m": ell, "setor": setor, "habitat": "Coerência: previsto (p ≥ 0,5) em habitat úmido",
                           "area_ha": round(prev.sum() * a_ha, 1), "frac_p_ge_0.5": float(umido[prev].mean()) if prev.any() else np.nan,
                           "p_medio": np.nan, "frac_p_ge_0.9": np.nan})
        _v2.log(f"entremarés ℓ = {ell} m")
    t = pd.DataFrame(linhas)
    # agregado da costa (ponderado pela área)
    tot = (t.assign(w=t.area_ha).groupby(["ell_m", "habitat"])
           .apply(lambda g: pd.Series({"area_ha": g.area_ha.sum(), "frac_p_ge_0.5": np.average(g["frac_p_ge_0.5"], weights=g.w),
                                       "p_medio": np.average(g.p_medio.fillna(0), weights=g.w) if g.p_medio.notna().all() else np.nan,
                                       "frac_p_ge_0.9": np.average(g["frac_p_ge_0.9"].fillna(0), weights=g.w) if g["frac_p_ge_0.9"].notna().all() else np.nan}))
           .reset_index().assign(setor="TOTAL_COSTA_BAHIA"))
    t = pd.concat([t, tot], ignore_index=True).round(4)
    t.to_csv(os.path.join(OUT, "entremares_por_ell.csv"), index=False, encoding="utf-8-sig")
    # figura: fração com p ≥ 0,5 por habitat × ℓ (costa)
    g = tot.pivot(index="habitat", columns="ell_m", values="frac_p_ge_0.5")
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    cores = plt.cm.viridis(np.linspace(0.15, 0.85, g.shape[1]))
    x = np.arange(len(g))
    for k, (ell, cor) in enumerate(zip(g.columns, cores)):
        ax.bar(x + (k - (g.shape[1] - 1) / 2) * 0.8 / g.shape[1], g[ell], 0.8 / g.shape[1], color=cor, label=f"ℓ = {ell} m")
    ax.set_xticks(x, [h.replace(" (", "\n(") for h in g.index], fontsize=8)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Fraction with p ≥ 0.5 (present day, MHWS)")
    ax.legend(frameon=False, fontsize=8, ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.22))
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(OUT, f"Fig_validacao_entremares.{ext}"), dpi=600)
    _v2.log(f"validação entremarés: {len(t)} linhas -> {OUT}")
