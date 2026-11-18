# Formato do pacote de entrada do CoastShift

Um **pacote** é uma pasta, criada pelo script `11_preparar_pacote_modelo.py` ou pelo botão de demonstração do aplicativo, com rasters **alinhados** (mesma grade, mesmo CRS projetado em metros, ex.: EPSG:31984) e um `params.json`.

| Arquivo | Obrigatório | Conteúdo |
|---|---|---|
| `dem.tif` | sim | Cota do terreno em m **relativa ao NMM local** (Eqs. 1–3); NoData no mar |
| `sea.tif` | recomendado | 1 = água marinha/estuarina conectada ao oceano (sementes) |
| `landcover.tif` | recomendado | Classes MapBiomas (5 mangue, 32 apicum, 23 praia/duna, 24 urbano, 33 água…) |
| `pop.tif` | opcional | Pessoas por célula |
| `buildings.tif` | opcional | Edificações (contagem fracionária) por célula |
| `validacao_pontos_dem.csv` | opcional | x, y, h_ref (mesmo CRS e datum do DEM) — ICESat-2/GNSS |
| `params.json` | sim | Parâmetros (abaixo) |

## params.json

```json
{
  "sector": "S2_Salvador_BTS",
  "baseline": {"center_year": 2014},
  "tide": {"msl": 0.0, "mhhw": 1.05, "mhws": 1.25, "amplification_factor": 1.0},
  "ar6": {"quantiles": [0.05, 0.17, 0.5, 0.83, 0.95], "years": [2020, 2030, "..."],
          "scenarios": {"ssp245": [[0.03, 0.04, 0.05, 0.06, 0.07], "... um vetor por ano ..."]}},
  "vlm_extra_mm_yr": 0.0,
  "extremes": {"threshold": 1.30, "scale": 0.09, "shape": -0.10, "rate": 4.0, "scale_se": 0.01, "shape_se": 0.05},
  "waves": {"hs": 2.0, "tp": 9.0, "beach_slope": 0.04, "costa_aberta": true},
  "dem_error": {"default": {"bias": 0.3, "sd": 0.6}, "by_class": {"5": {"bias": 0.9, "sd": 1.0}}, "corr_length_m": 300},
  "manning": {"default": 0.035, "by_class": {"24": 0.10}},
  "shoreline": {"d50_mm": 0.3, "berm_m": 2.0, "he_m": 3.0, "te_s": 10.0, "sandy_classes": [23]},
  "habitat": {"mangrove_classes": [5], "apicum_classes": [32], "barrier_classes": [24],
              "accretion_mm_yr": 3.0, "apicum_band_m": 0.3, "max_rsl_rate_mm_yr": 7.0},
  "damage": {"value_per_building": 150000, "people_depth_threshold": 0.15,
             "curve_depth": [0, 0.5, 1, 2, 4, 6], "curve_frac": [0, 0.25, 0.4, 0.6, 0.85, 1.0]}
}
```

- Valores AR6 em **metros relativos a 1995–2014**. O modelo re-referencia para `baseline.center_year` (Eq. 6).
- `extremes`: POT-GPD do **nível total relativo ao NMM** (Eq. 8). `rate` = excessos/ano.
- `dem_error.bias` = média de (DEM − referência). O modelo subtrai o viés (Eq. 11).
- Todos os parâmetros podem ser editados na aba **4 Parâmetros** do aplicativo.
