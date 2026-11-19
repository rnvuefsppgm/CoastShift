"""25c — Validação principal da inundação pela maré com radar Sentinel-1 (RTC, Planetary Computer, sem conta).

Motivação: o Sentinel-2 passa às ~12:50 UTC e, em Salvador, a preamar de sizígia nunca coincide com esse horário
(nível máximo observado nas passagens ≈ 0,6 m, metade da MHWS). O Sentinel-1 passa às ~08 UTC e registra preamares
de até ~1,3–1,7 m, acima da MHWS — permitindo validar o modelo no nível de interesse.
Para cada setor, na órbita relativa com mais cenas: cena de preamar (maior nível) × cena de baixa-mar (menor nível).
Água no radar: γ⁰ VV médio em 30 m < −17 dB. Água da maré = água na preamar e não na baixa-mar (remove lagoas e
áreas sempre alagadas). Modelo: p_maré = p(nível alto) − p(nível baixo), O2 com N = 100 e as mesmas sementes.
Métricas: CSI, HR, FAR, viés de área (p ≥ 0,5), Brier e confiabilidade, com e sem mangue (o dossel do mangue
alagado gera reflexão dupla e não aparece como água).
Saídas: <resultados>/validacao/s1_intermare_metricas.csv, s1_intermare_confiabilidade.csv, s1_intermare_<setor>.tif
"""
import importlib.util
import json
import os

import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling

import _v2

spec = importlib.util.spec_from_file_location("v25b", os.path.join(os.path.dirname(__file__), "25b_validacao_intermare_sentinel2.py"))
v25b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v25b)
v25, csio = v25b.v25, v25b.csio
OUT = v25.OUT
LIMIAR_DB = -17.0


def ler_s1(href, prof):
    from rasterio.vrt import WarpedVRT
    for k in range(4):
        try:
            with rasterio.open(href) as src, WarpedVRT(src, crs=prof["crs"], transform=prof["transform"],
                                                       width=prof["width"], height=prof["height"],
                                                       resampling=Resampling.average, src_nodata=-32768,
                                                       nodata=np.nan, dtype="float32") as v:
                return v.read(1)
        except rasterio.errors.RasterioIOError:
            if k == 3:
                raise
            import time
            time.sleep(10 * (k + 1))


def agua_s1(itens, prof):
    soma = np.zeros((prof["height"], prof["width"]), "float64")
    cont = np.zeros_like(soma)
    for it in itens:
        try:
            vv = ler_s1(it.assets["vv"].href, prof)
        except Exception as e:  # noqa: BLE001
            _v2.log(f"cena S1 ignorada {it.id}: {str(e)[:80]}")
            continue
        ok = np.isfinite(vv) & (vv > 0)
        soma[ok] += vv[ok]
        cont[ok] += 1
    g = np.where(cont > 0, soma / np.maximum(cont, 1), np.nan)
    db = 10 * np.log10(np.where(g > 0, g, np.nan))
    return np.nan_to_num(db < LIMIAR_DB), np.isfinite(db)


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
        its = list(cat.search(collections=["sentinel-1-rtc"], bbox=list(gs[gs.setor == setor].total_bounds),
                              datetime="2017-01-01/2025-12-31").items())
        df = pd.DataFrame({"item": its, "t": pd.to_datetime([i.datetime for i in its]).tz_convert(None),
                           "orbita": [i.properties.get("sat:relative_orbit") for i in its]})
        df["nivel"] = np.interp(df.t.values.astype("datetime64[s]").astype("int64"),
                                sv.index.values.astype("datetime64[s]").astype("int64"), sv.values, left=np.nan,
                                right=np.nan) * mares[setor]["fator_transferencia_salvador"]
        from shapely.geometry import shape
        from shapely.ops import unary_union
        import geopandas as gpd
        ba = gpd.read_file(_v2.p("aoi", "ibge_bahia.geojson")).union_all()
        terra_ll = gs[gs.setor == setor].geometry.iloc[0].intersection(ba)
        df["geo"] = [shape(i.geometry) for i in df.item]
        df = df.dropna(subset=["nivel"])
        df["dia"] = df.t.dt.floor("D")
        cobre = df.groupby(["orbita", "dia"]).agg(nivel=("nivel", "mean"), geo=("geo", lambda g: unary_union(list(g))))
        cobre["cobertura"] = [terra_ll.intersection(g).area / terra_ll.area for g in cobre.geo]
        cobre = cobre[cobre.cobertura >= 0.6].reset_index()
        orb = cobre.groupby("orbita").nivel.agg(lambda x: x.max() - x.min()).idxmax()     # órbita com maior amplitude
        cc = cobre[cobre.orbita == orb].sort_values("nivel")
        d_bx, d_al = cc.dia.iloc[0], cc.dia.iloc[-1]
        n_bx, n_al = float(cc.nivel.iloc[0]), float(cc.nivel.iloc[-1])
        d = df[df.orbita == orb]
        w_al, ok_al = agua_s1(d[d.dia == d_al].item, prof)
        w_bx, ok_bx = agua_s1(d[d.dia == d_bx].item, prof)
        terra = np.isfinite(pk.dem) & ~pk.sea
        with rasterio.open(_v2.p("agua", f"gsw_ocorrencia_{setor}.tif")) as g:
            perm = g.read(1) >= 50
        msk = terra & ~perm & ok_al & ok_bx
        obs = w_al & ~w_bx & msk
        p = np.clip(v25b.p_nivel(pk, n_al, d_al.year) - v25b.p_nivel(pk, n_bx, d_bx.year), 0, 1)
        mang = pk.layers["landcover"] == 5
        m = v25.metricas(p, obs, msk)
        m2 = v25.metricas(p, obs, msk & ~mang)
        linhas.append({"setor": setor, "orbita_relativa": int(orb), "preamar": str(d_al.date()), "nivel_preamar_m": round(n_al, 2),
                       "MHWS_m": mares[setor]["mhws"], "baixamar": str(d_bx.date()), "nivel_baixamar_m": round(n_bx, 2),
                       **{k: (round(v, 3) if isinstance(v, float) else v) for k, v in m.items()},
                       **{f"sem_mangue_{k}": (round(v, 3) if isinstance(v, float) else v) for k, v in m2.items()}})
        ativo = msk & ((p > 0.01) | obs)
        for b0 in np.arange(0, 1, 0.1):
            sel = ativo & (p >= b0) & ((p < b0 + 0.1) if b0 < 0.9 else (p <= 1))
            if sel.sum():
                conf.append({"setor": setor, "faixa_p": round(b0 + 0.05, 2), "p_media": float(p[sel].mean()),
                             "freq_obs": float(obs[sel].mean()), "n": int(sel.sum())})
        cat_ = np.full(p.shape, 255, "uint8")
        pr_ = p >= 0.5
        cat_[msk] = 0
        cat_[msk & pr_ & obs], cat_[msk & pr_ & ~obs], cat_[msk & ~pr_ & obs] = 1, 2, 3
        with rasterio.open(os.path.join(OUT, f"s1_intermare_{setor}.tif"), "w",
                           **dict(prof, dtype="uint8", nodata=255, count=1, compress="deflate")) as w:
            w.write(cat_, 1)
        _v2.log(f"S1 intermaré {setor}: {n_bx:.2f}→{n_al:.2f} m (MHWS {mares[setor]['mhws']:.2f}), CSI {m['CSI']:.2f} "
                f"(sem mangue {m2['CSI']:.2f}), HR {m['HR']:.2f}, FAR {m['FAR']:.2f}, obs {int(obs.sum())} células")
    dd = pd.DataFrame(linhas)
    t = {k: int(dd[k].sum()) for k in ("TP", "FP", "FN", "n_celulas")}
    t.update(setor="TOTAL", CSI=t["TP"] / max(t["TP"] + t["FP"] + t["FN"], 1), HR=t["TP"] / max(t["TP"] + t["FN"], 1),
             FAR=t["FP"] / max(t["TP"] + t["FP"], 1), vies_area=(t["TP"] + t["FP"]) / max(t["TP"] + t["FN"], 1),
             Brier=float(np.average(dd.Brier, weights=dd.n_celulas)))
    t2 = {k: int(dd[f"sem_mangue_{k}"].sum()) for k in ("TP", "FP", "FN")}
    t.update(sem_mangue_CSI=t2["TP"] / max(t2["TP"] + t2["FP"] + t2["FN"], 1),
             sem_mangue_HR=t2["TP"] / max(t2["TP"] + t2["FN"], 1), sem_mangue_FAR=t2["FP"] / max(t2["TP"] + t2["FP"], 1))
    pd.concat([dd, pd.DataFrame([t])], ignore_index=True).round(3).to_csv(
        os.path.join(OUT, "s1_intermare_metricas.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame(conf).to_csv(os.path.join(OUT, "s1_intermare_confiabilidade.csv"), index=False, encoding="utf-8-sig")
    _v2.log(f"S1 intermaré TOTAL: CSI {t['CSI']:.2f} (sem mangue {t['sem_mangue_CSI']:.2f}), HR {t['HR']:.2f}, "
            f"FAR {t['FAR']:.2f}, Brier {t['Brier']:.3f}")
