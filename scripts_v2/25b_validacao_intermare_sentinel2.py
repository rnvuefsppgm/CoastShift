"""25b — Validação da inundação pela maré com pares Sentinel-2 de preamar e baixa-mar (métricas principais).

Para cada setor escolhem-se, entre as cenas 2019–2025 com nuvens < 10 %, a de maior e a de menor nível observado
(marégrafo de Salvador × fator do setor). Água observada pela maré = água (MNDWI > 0) na preamar e não na baixa-mar,
nas células válidas nas duas cenas — elimina lagoas, chuva acumulada e áreas úmidas permanentes.
Modelo: O2 (N = 100) nos dois níveis com as mesmas sementes (mesmos campos de erro do DEM), de modo que
p_maré = p_alta − p_baixa é exatamente a probabilidade de a célula alagar só entre os dois níveis.
Métricas: CSI, HR, FAR, viés de área (p ≥ 0,5), Brier e curva de confiabilidade, com e sem mangue (classe 5).
Saídas: <resultados>/validacao/{intermare_metricas.csv, intermare_confiabilidade.csv, intermare_<setor>.tif}
"""
import importlib.util
import json
import os

import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling

import _v2

spec = importlib.util.spec_from_file_location("v25", os.path.join(os.path.dirname(__file__), "25_validacao_sentinel2.py"))
v25 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v25)
csio, models = v25.csio, v25.models
OUT = v25.OUT


def agua(itens, prof):
    a = np.zeros((prof["height"], prof["width"]), bool)
    ok_ = np.zeros_like(a)
    for it in itens:
        try:
            g3 = v25.ler(it.assets["B03"].href, prof, Resampling.average)
            b11 = v25.ler(it.assets["B11"].href, prof, Resampling.average)
            scl = v25.ler(it.assets["SCL"].href, prof, Resampling.nearest)
        except Exception as e:  # noqa: BLE001  (cena inacessível: ignorada e registrada)
            _v2.log(f"cena ignorada {it.id}: {str(e)[:80]}")
            continue
        ok = (g3 > 0) & (b11 > 0) & ~np.isin(scl, [0, 1, 3, 8, 9, 10])
        a |= ok & ((g3 - b11) / np.maximum(g3 + b11, 1) > 0)
        ok_ |= ok
    return a, ok_


def p_nivel(pk, nivel, ano):
    pr = json.loads(json.dumps(pk.params))
    pr["tide"]["mhws"] = float(nivel)
    p0, pk.params = pk.params, pr
    cnt, _ = models.o2_realizacoes(pk, {"jobs": [("ssp245", ano)], "ref": "MHWS", "tr": 0, "conn": 8, "setup": False},
                                   100, 4242)
    pk.params = p0
    p = np.full(pk.dem.size, 0.0, "float32")
    p[np.flatnonzero(np.isfinite(pk.dem))] = cnt[("ssp245", ano)] / 100
    return p.reshape(pk.dem.shape)


if __name__ == "__main__":
    import planetary_computer
    import pystac_client
    cat = pystac_client.Client.open(v25.STAC, modifier=planetary_computer.sign_inplace)
    sal = json.load(open(_v2.p("mares", "mares_salvador.json"), encoding="utf-8"))
    mares = json.load(open(_v2.p("mares", "mares_setores.json"), encoding="utf-8"))
    sv = (_v2.serie_uhslc(708, ("b",), fast=True) - sal["nmm_zero_estacao_m"]).dropna()
    _, gs = _v2.aoi()
    linhas, conf = [], []
    for setor in _v2.SETORES:
        pk = csio.Package(os.path.join(_v2.BASE, "pacotes", setor))
        prof = pk.profile
        its = list(cat.search(collections=["sentinel-2-l2a"], bbox=list(gs[gs.setor == setor].total_bounds),
                              datetime="2019-01-01/2025-12-31", query={"eo:cloud_cover": {"lt": 10}}).items())
        df = pd.DataFrame({"item": its, "t": pd.to_datetime([i.datetime for i in its]).tz_convert(None)})
        df["nivel"] = np.interp(df.t.values.astype("datetime64[s]").astype("int64"),
                                sv.index.values.astype("datetime64[s]").astype("int64"), sv.values, left=np.nan,
                                right=np.nan) * mares[setor]["fator_transferencia_salvador"]
        df["dia"] = df.t.dt.floor("D")
        dias = df.dropna().groupby("dia").nivel.mean().sort_values()
        d_bx, d_al = dias.index[0], dias.index[-1]
        n_bx, n_al = float(dias.iloc[0]), float(dias.iloc[-1])
        w_al, ok_al = agua(df[df.dia == d_al].item, prof)
        w_bx, ok_bx = agua(df[df.dia == d_bx].item, prof)
        terra = np.isfinite(pk.dem) & ~pk.sea
        with rasterio.open(_v2.p("agua", f"gsw_ocorrencia_{setor}.tif")) as g:
            perm = g.read(1) >= 50
        msk = terra & ~perm & ok_al & ok_bx
        obs = w_al & ~w_bx & msk
        p = np.clip(p_nivel(pk, n_al, d_al.year) - p_nivel(pk, n_bx, d_bx.year), 0, 1)
        mang = pk.layers["landcover"] == 5
        m = v25.metricas(p, obs, msk)
        m2 = v25.metricas(p, obs, msk & ~mang)
        linhas.append({"setor": setor, "preamar": str(d_al.date()), "nivel_preamar_m": round(n_al, 2),
                       "baixamar": str(d_bx.date()), "nivel_baixamar_m": round(n_bx, 2),
                       **{k: (round(v, 3) if isinstance(v, float) else v) for k, v in m.items()},
                       **{f"sem_mangue_{k}": (round(v, 3) if isinstance(v, float) else v) for k, v in m2.items()}})
        ativo = msk & ((p > 0.01) | obs)
        for b0 in np.arange(0, 1, 0.1):
            sel = ativo & (p >= b0) & ((p < b0 + 0.1) if b0 < 0.9 else (p <= 1))
            if sel.sum():
                conf.append({"setor": setor, "faixa_p": round(b0 + 0.05, 2), "p_media": float(p[sel].mean()),
                             "freq_obs": float(obs[sel].mean()), "n": int(sel.sum())})
        cat_ = np.full(p.shape, 255, "uint8")                        # 0 neg., 1 acerto, 2 falso alarme, 3 omissão
        pr_ = p >= 0.5
        cat_[msk] = 0
        cat_[msk & pr_ & obs], cat_[msk & pr_ & ~obs], cat_[msk & ~pr_ & obs] = 1, 2, 3
        with rasterio.open(os.path.join(OUT, f"intermare_{setor}.tif"), "w",
                           **dict(prof, dtype="uint8", nodata=255, count=1, compress="deflate")) as w:
            w.write(cat_, 1)
        _v2.log(f"intermaré {setor}: {n_bx:.2f}→{n_al:.2f} m, CSI {m['CSI']:.2f} (sem mangue {m2['CSI']:.2f}), "
                f"HR {m['HR']:.2f}, FAR {m['FAR']:.2f}")
    d = pd.DataFrame(linhas)
    t = {k: int(d[k].sum()) for k in ("TP", "FP", "FN", "n_celulas")}
    t.update(setor="TOTAL", CSI=t["TP"] / (t["TP"] + t["FP"] + t["FN"]), HR=t["TP"] / (t["TP"] + t["FN"]),
             FAR=t["FP"] / (t["TP"] + t["FP"]), vies_area=(t["TP"] + t["FP"]) / (t["TP"] + t["FN"]),
             Brier=float(np.average(d.Brier, weights=d.n_celulas)))
    t2 = {k: int(d[f"sem_mangue_{k}"].sum()) for k in ("TP", "FP", "FN")}
    t.update(sem_mangue_CSI=t2["TP"] / (t2["TP"] + t2["FP"] + t2["FN"]))
    pd.concat([d, pd.DataFrame([t])], ignore_index=True).round(3).to_csv(
        os.path.join(OUT, "intermare_metricas.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame(conf).to_csv(os.path.join(OUT, "intermare_confiabilidade.csv"), index=False, encoding="utf-8-sig")
    _v2.log(f"intermaré TOTAL: CSI {t['CSI']:.2f}, sem mangue {t['sem_mangue_CSI']:.2f}, HR {t['HR']:.2f}, "
            f"FAR {t['FAR']:.2f}, Brier {t['Brier']:.3f}")
