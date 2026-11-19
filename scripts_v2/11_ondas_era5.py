"""11 — Clima de ondas ERA5 (Hersbach et al., 2020) via Open-Meteo Marine (modelo era5_ocean; sem conta CDS).
Série horária 1995–2024 no ponto offshore de cada setor e estatísticas para o setup de Stockdon et al. (2006):
<η> = 0,35 β (H0 L0)^0,5, L0 = g Tp² / 2π. Hs de projeto = percentil 99 (ressaca frequente);
Tp = mediana de Tp nas horas com Hs ≥ p95.
Saídas: <BASE>/ondas/era5_<setor>.csv e ondas_setores.json
"""
import os
import time

import numpy as np
import pandas as pd

import _v2

OM = "https://marine-api.open-meteo.com/v1/marine"

if __name__ == "__main__":
    out = {}
    for setor, cfg in _v2.SETORES.items():
        lo, la = cfg["ponto_mar"]
        f_csv = _v2.p("ondas", f"era5_{setor}.csv")
        if os.path.exists(f_csv):                       # reaproveita a série já baixada
            df = pd.read_csv(f_csv, index_col="time", parse_dates=True)
            d = {"longitude": lo, "latitude": la}
        else:
            time.sleep(20)                              # respeita o limite da API gratuita
            d = _v2.get_json(OM, {"latitude": la, "longitude": lo, "start_date": "1995-01-01", "end_date": "2024-12-31",
                              "hourly": "wave_height,wave_peak_period,wave_direction", "models": "era5_ocean",
                              "timezone": "GMT"})
            h = d["hourly"]
            df = pd.DataFrame({"hs": h["wave_height"], "tp": h["wave_peak_period"], "dir": h["wave_direction"]},
                              index=pd.to_datetime(h["time"]), dtype=float)
            df.to_csv(f_csv, index_label="time")
        hs99, hs95 = float(df.hs.quantile(0.99)), float(df.hs.quantile(0.95))
        tp = float(df.tp[df.hs >= hs95].median())
        beta = cfg["declividade_praia"]
        setup = 0.35 * beta * np.sqrt(hs99 * 9.81 * tp ** 2 / (2 * np.pi))
        rad = np.deg2rad(df.dir.dropna())
        out[setor] = {"hs": round(hs99, 2), "tp": round(tp, 1), "beach_slope": beta, "costa_aberta": cfg["aberta"],
                      "hs_p50": round(float(df.hs.median()), 2), "hs_p95": round(hs95, 2),
                      "hs_max_anual_medio": round(float(df.hs.groupby(df.index.year).max().mean()), 2),
                      "dir_media_graus": round(float(np.rad2deg(np.arctan2(np.sin(rad).mean(), np.cos(rad).mean())) % 360)),
                      "setup_stockdon_m": round(float(setup), 3), "ponto_modelo": [d["longitude"], d["latitude"]],
                      "fracao_valida": round(float(df.hs.notna().mean()), 3),
                      "fonte": "ERA5 via Open-Meteo Marine (era5_ocean), 1995-2024"}
        _v2.log(f"{setor}: Hs50={out[setor]['hs_p50']} Hs99={out[setor]['hs']} m, Tp={out[setor]['tp']} s, "
                f"setup={out[setor]['setup_stockdon_m']} m")
    _v2.salvar_json(out, "ondas", "ondas_setores.json")
