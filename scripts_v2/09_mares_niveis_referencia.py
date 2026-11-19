"""09 — Níveis de referência de maré (NMM, MHHW, MHWS).
Marégrafo de Salvador: UHSLC 708 (research quality 2004–2018 + fast delivery até o presente; estação da RMPG/IBGE).
Transferência para os setores: razão das amplitudes semidiurnas (M2+S2) do nível do mar modelado da Open-Meteo
Marine (sea_level_height_msl, 2024) entre o ponto offshore do setor e Salvador.
Equações (métodos §5.3): MHWS = NMM + A(M2) + A(S2); MHHW = média das preamares mais altas diárias (previsão 2005–2023).
Saídas: <BASE>/mares/uhslc_*.csv, mares_salvador.json, mares_setores.json
"""
import numpy as np
import pandas as pd

import _v2

OM = "https://marine-api.open-meteo.com/v1/marine"


def amp_modelo(lon, lat):
    d = _v2.get_json(OM, {"latitude": lat, "longitude": lon, "start_date": "2024-01-01", "end_date": "2024-12-31",
                          "hourly": "sea_level_height_msl", "timezone": "GMT"})
    s = pd.Series(d["hourly"]["sea_level_height_msl"], index=pd.to_datetime(d["hourly"]["time"]), dtype=float)
    if s.notna().mean() < 0.5:
        return None
    amp, _, _, _ = _v2.harmonicos(s - s.mean(), ["M2", "S2", "N2", "K2", "K1", "O1", "M4"])
    return amp


if __name__ == "__main__":
    s = _v2.serie_uhslc(708, ("b",), fast=True)
    _v2.log(f"Salvador: {s.index[0]} a {s.index[-1]}, {s.notna().mean():.0%} válidos")
    ep = s["2004":"2024"]
    anual = ep.groupby(ep.index.year).agg(["mean", "count"])
    anual = anual[anual["count"] > 0.8 * 8760]
    nmm = float(ep.mean())
    tend = float(np.polyfit(anual.index.values, anual["mean"].values * 1000, 1)[0]) if len(anual) > 5 else float("nan")
    amp, fase, _, prever = _v2.harmonicos(ep - nmm)
    idx = pd.date_range("2005-01-01", "2023-12-31 23:00", freq="h")
    pred = pd.Series(prever(idx), index=idx)
    mhhw = float(pred.groupby(pred.index.date).max().mean())
    obs_mhhw = float((ep - nmm).groupby(ep.index.date).max().mean())
    mhws = amp["M2"] + amp["S2"]
    sal = {"estacao": "Salvador (UHSLC 708 / RMPG SAL)", "epoca": [int(ep.index[0].year), int(ep.index[-1].year)],
           "nmm_zero_estacao_m": round(nmm, 4), "mhhw_m": round(mhhw, 3), "mhhw_obs_m": round(obs_mhhw, 3),
           "mhws_m": round(mhws, 3), "tendencia_mm_ano": round(tend, 2), "anos_validos": int(len(anual)),
           "amplitudes_m": {k: round(v, 4) for k, v in amp.items()},
           "fases_graus": {k: round(v, 1) for k, v in fase.items()}, "referencia": "níveis relativos ao NMM da época"}
    _v2.salvar_json(sal, "mares", "mares_salvador.json")
    _v2.log(f"Salvador: MHHW={mhhw:.2f} m, MHWS={mhws:.2f} m (rel. NMM), tendência {tend:.2f} mm/ano")
    ref = amp_modelo(-38.55, -13.05)
    out = {}
    for setor, cfg in _v2.SETORES.items():
        a = amp_modelo(*cfg["ponto_mar"])
        f = 1.0 if (a is None or ref is None) else (a["M2"] + a["S2"]) / (ref["M2"] + ref["S2"])
        out[setor] = {"msl": 0.0, "mhhw": round(mhhw * f, 3), "mhws": round(mhws * f, 3), "amplification_factor": 1.0,
                      "fator_transferencia_salvador": round(f, 3),
                      "fonte": "UHSLC 708 Salvador × razão (M2+S2) Open-Meteo Marine 2024"}
        _v2.log(f"  {setor}: fator {f:.3f} -> MHHW {out[setor]['mhhw']:.2f} m, MHWS {out[setor]['mhws']:.2f} m")
    _v2.salvar_json(out, "mares", "mares_setores.json")
