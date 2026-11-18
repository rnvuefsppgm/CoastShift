"""Gera um pacote SINTÉTICO para testar o CoastShift sem baixar dados.
Os valores AR6 do demo replicam a ordem de grandeza GLOBAL do AR6 (Tabela 9.9) e NÃO são
projeções para a Bahia."""
import json
import os

import numpy as np
import pandas as pd
from rasterio.transform import from_origin

from .io import write_raster


def make_demo(folder, n=200, cell=30.0, seed=1):
    os.makedirs(folder, exist_ok=True)
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:n, 0:n].astype("float32")
    shore = n * 0.78 + 6 * np.sin(y / 17)                       # mar a leste
    dist = (shore - x) * cell                                   # m para o interior
    z = 0.004 * dist + 0.8 + 0.5 * np.exp(-((dist - 60) / 40) ** 2) * 2.0  # rampa + cordão de dunas
    est = np.exp(-((y - n * 0.45) / (n * 0.06)) ** 2)           # estuário
    z -= est * np.clip(1.8 - dist / 4000, 0, 1.8)
    z += rng.normal(0, 0.15, z.shape)
    sea = dist < 0
    sea |= (est > 0.85) & (dist < n * cell * 0.45)              # canal estuarino
    z[sea] = np.nan
    lc = np.full(z.shape, 15, "float32")                        # pastagem
    lc[(dist > 0) & (dist < 120)] = 23                          # praia/duna
    lc[(est > 0.3) & ~sea & (z < 1.6)] = 5                      # mangue
    lc[(est > 0.2) & (est <= 0.3) & ~sea] = 32                  # apicum
    urb = (y > n * 0.6) & (y < n * 0.8) & (dist > 150) & (dist < 1800)
    lc[urb] = 24
    lc[sea] = 33
    pop = np.where(urb, rng.gamma(2, 6, z.shape), rng.gamma(1, 0.2, z.shape)).astype("float32")
    pop[sea] = 0
    bld = np.where(urb, rng.gamma(2, 1.5, z.shape), 0).astype("float32")
    prof = {"crs": "EPSG:31984", "transform": from_origin(500000, 8560000, cell, cell),
            "width": n, "height": n}
    write_raster(os.path.join(folder, "dem.tif"), z, prof)
    write_raster(os.path.join(folder, "landcover.tif"), lc, prof, "int16", -1)
    write_raster(os.path.join(folder, "sea.tif"), sea.astype("float32"), prof, "uint8", 255)
    write_raster(os.path.join(folder, "pop.tif"), pop, prof)
    write_raster(os.path.join(folder, "buildings.tif"), bld, prof)
    q = [0.05, 0.17, 0.5, 0.83, 0.95]
    years = [2020, 2030, 2040, 2050, 2060, 2070, 2080, 2090, 2100, 2150]
    g = {"ssp126": [0.38, 0.44, 0.68], "ssp245": [0.45, 0.56, 0.92], "ssp585": [0.55, 0.77, 1.32]}

    def table(m2100, m2150):
        rows = []
        for yr in years:
            if yr <= 2100:
                med = 0.04 + (m2100 - 0.04) * ((yr - 2020) / 80) ** 1.4
            else:
                med = m2100 + (m2150 - m2100) * (yr - 2100) / 50
            spread = 0.25 * med + 0.01
            rows.append([round(med + k * spread, 3) for k in (-1.6, -1, 0, 1, 1.6)])
        return rows
    params = {
        "sector": "DEMO_sintetico", "aviso": "DADOS SINTÉTICOS – apenas para teste do software",
        "baseline": {"center_year": 2014},
        "tide": {"msl": 0.0, "mhhw": 1.05, "mhws": 1.25, "amplification_factor": 1.0},
        "ar6": {"quantiles": q, "years": years, "source": "ilustrativo",
                "scenarios": {k: table(v[1], v[2]) for k, v in g.items()}},
        "vlm_extra_mm_yr": 0.0,
        "extremes": {"threshold": 1.30, "scale": 0.09, "shape": -0.10, "rate": 4.0,
                     "scale_se": 0.01, "shape_se": 0.05, "reference": "nível total rel. NMM"},
        "waves": {"hs": 2.0, "tp": 9.0, "beach_slope": 0.04},
        "dem_error": {"default": {"bias": 0.3, "sd": 0.6}, "corr_length_m": 300,
                      "by_class": {"5": {"bias": 0.9, "sd": 1.0}, "24": {"bias": 0.7, "sd": 0.9}}},
        "manning": {"default": 0.04, "by_class": {"24": 0.10, "5": 0.12, "3": 0.12, "33": 0.025}},
        "shoreline": {"d50_mm": 0.35, "berm_m": 2.0, "he_m": 2.8, "te_s": 10.0, "sandy_classes": [23]},
        "habitat": {"mangrove_classes": [5], "apicum_classes": [32], "barrier_classes": [24],
                    "accretion_mm_yr": 3.0, "mangrove_min": 0.0, "mangrove_max_above_mhws": 0.0,
                    "apicum_band_m": 0.3, "max_rsl_rate_mm_yr": 7.0},
        "damage": {"value_per_building": 150000.0, "people_depth_threshold": 0.15,
                   "curve_depth": [0, 0.5, 1, 1.5, 2, 3, 4, 6], "curve_frac": [0, 0.25, 0.4, 0.5, 0.6, 0.75, 0.85, 1.0],
                   "curve_source": "curva ilustrativa – substituir por Huizinga et al. (2017), América do Sul"},
    }
    with open(os.path.join(folder, "params.json"), "w", encoding="utf-8") as f:
        json.dump(params, f, indent=2, ensure_ascii=False)
    # pontos 'ICESat-2' sintéticos para testar a validação do DEM
    k = rng.choice(np.flatnonzero(~sea.ravel()), 600, replace=False)
    rr, cc = np.unravel_index(k, z.shape)
    true = z[rr, cc] - np.where(lc[rr, cc] == 5, 0.9, 0.3) + rng.normal(0, 0.3, k.size)
    xs, ys = 500000 + (cc + 0.5) * cell, 8560000 - (rr + 0.5) * cell
    pd.DataFrame({"x": xs, "y": ys, "h_ref": true}).to_csv(os.path.join(folder, "validacao_pontos_dem.csv"), index=False)
    # máscara 'observada' sintética (preamar atual) para testar CSI
    obs = (~sea) & (z - 0.3 <= 1.25 + rng.normal(0, 0.1, z.shape))
    write_raster(os.path.join(folder, "observado_inundacao.tif"), obs.astype("float32"), prof, "uint8", 255)
    return folder
