"""25 — Validação da mancha de inundação atual com Sentinel-2 L2A em preamares (métodos §4.8).

Para cada setor: busca no catálogo público do Planetary Computer (STAC, sem conta) cenas 2019–2025 com nuvens
< 10 %; o nível do mar no instante da passagem vem do marégrafo de Salvador (UHSLC 708, observado) escalado pelo
fator de maré do setor; escolhem-se as 2 datas de maior nível. Como no horário da passagem (~12:50 UTC) o nível não alcança a MHWS,
roda-se o O2 (N = 100) no nível observado de cada cena (ΔRSL do ano da cena) e compara-se com a água observada.
Água observada: MNDWI = (B03 − B11)/(B03 + B11) > 0, com máscara de nuvem/sombra (SCL). Avaliação nas células
terrestres da zona costeira, excluindo água permanente (ocorrência JRC ≥ 50 %): CSI, HR, FAR, viés de área (p ≥ 0,5) e escore de Brier com confiabilidade.
Ressalva: sob dossel de mangue a água não é visível na imagem (resultado também reportado sem a classe 5).
Saídas: <resultados_O2_Bahia>/validacao/{sentinel2_metricas.csv, sentinel2_confiabilidade.csv, cenas.csv,
        obs_s2_<setor>.tif, Fig_validacao_S2_<setor>.png/pdf}
"""
import json
import os
import sys

import numpy as np
import pandas as pd
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling

import _v2

sys.path.insert(0, _v2.REPO)
from coastshift import io as csio, models  # noqa: E402

RES = os.environ.get("COASTSHIFT_RESULTADOS", os.path.join(os.path.dirname(_v2.REPO), "resultados_O2_Bahia"))
OUT = os.path.join(RES, "validacao")
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"


os.environ.update(GDAL_HTTP_MAX_RETRY="6", GDAL_HTTP_RETRY_DELAY="3", GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR")


def ler(href, prof, rs):
    for k in range(4):                                               # repete em falhas transitórias de rede
        try:
            with rasterio.open(href) as src, WarpedVRT(src, crs=prof["crs"], transform=prof["transform"],
                                                       width=prof["width"], height=prof["height"], resampling=rs) as v:
                return v.read(1).astype("float32")
        except rasterio.errors.RasterioIOError:
            if k == 3:
                raise
            import time
            time.sleep(10 * (k + 1))


def metricas(p, o, msk):
    pp, oo = p[msk], o[msk]
    pr = pp >= 0.5
    tp, fp, fn = int((pr & oo).sum()), int((pr & ~oo).sum()), int((~pr & oo).sum())
    ativo = (pp > 0.01) | oo
    return {"TP": tp, "FP": fp, "FN": fn, "CSI": tp / max(tp + fp + fn, 1), "HR": tp / max(tp + fn, 1),
            "FAR": fp / max(tp + fp, 1), "vies_area": (tp + fp) / max(tp + fn, 1),
            "Brier": float(np.mean((pp[ativo] - oo[ativo]) ** 2)) if ativo.any() else np.nan, "n_celulas": int(msk.sum())}


if __name__ == "__main__":
    import planetary_computer
    import pystac_client
    os.makedirs(OUT, exist_ok=True)
    cat = pystac_client.Client.open(STAC, modifier=planetary_computer.sign_inplace)
    sal = json.load(open(_v2.p("mares", "mares_salvador.json"), encoding="utf-8"))
    mares = json.load(open(_v2.p("mares", "mares_setores.json"), encoding="utf-8"))
    serie = _v2.serie_uhslc(708, ("b",), fast=True) - sal["nmm_zero_estacao_m"]
    _, gs = _v2.aoi()
    linhas, conf, cenas = [], [], []
    for setor in _v2.SETORES:
        pk = csio.Package(os.path.join(_v2.BASE, "pacotes", setor))
        prof = pk.profile
        f, mhws = mares[setor]["fator_transferencia_salvador"], mares[setor]["mhws"]
        bbox = list(gs[gs.setor == setor].total_bounds)
        itens = list(cat.search(collections=["sentinel-2-l2a"], bbox=bbox, datetime="2019-01-01/2025-12-31",
                                query={"eo:cloud_cover": {"lt": 10}}).items())
        df = pd.DataFrame([{"id": it.id, "t": pd.Timestamp(it.datetime).tz_convert(None), "nuvens": it.properties["eo:cloud_cover"],
                            "item": it} for it in itens])
        if df.empty:
            continue
        df["dia"] = df.t.dt.floor("D")
        sv = serie.dropna()
        nivel = np.interp(df.t.values.astype("datetime64[s]").astype("int64"),
                          sv.index.values.astype("datetime64[s]").astype("int64"), sv.values, left=np.nan, right=np.nan) * f
        df["nivel_m"] = nivel
        dias = df.groupby("dia").agg(nivel_m=("nivel_m", "mean"), nuvens=("nuvens", "mean")).dropna()
        dias = dias.sort_values("nivel_m", ascending=False).head(2)       # as 2 passagens de maré mais alta
        terra = np.isfinite(pk.dem) & ~pk.sea
        with rasterio.open(_v2.p("agua", f"gsw_ocorrencia_{setor}.tif")) as g:
            perm = g.read(1) >= 50
        mang = pk.layers["landcover"] == 5
        obs_acc = np.zeros(pk.dem.shape, "float32")
        val_acc = np.zeros(pk.dem.shape, bool)
        for dia, r in dias.iterrows():
            its = df[df.dia == dia].item.tolist()
            pr = json.loads(json.dumps(pk.params))                        # O2 no nível observado da cena
            pr["tide"]["mhws"] = float(r.nivel_m)
            pk.params, p0 = pr, pk.params
            cnt, _ = models.o2_realizacoes(pk, {"jobs": [("ssp245", int(dia.year))], "ref": "MHWS", "tr": 0,
                                                "conn": 8, "setup": False}, 100, 4242)
            pk.params = p0
            p = np.full(pk.dem.size, np.nan, "float32")
            p[np.flatnonzero(np.isfinite(pk.dem))] = cnt[("ssp245", int(dia.year))] / 100
            p = p.reshape(pk.dem.shape)
            agua = np.zeros(pk.dem.shape, bool)
            valido = np.zeros(pk.dem.shape, bool)
            for it in its:
                g3 = ler(it.assets["B03"].href, prof, Resampling.average)
                b11 = ler(it.assets["B11"].href, prof, Resampling.average)
                scl = ler(it.assets["SCL"].href, prof, Resampling.nearest)
                ok = (g3 > 0) & (b11 > 0) & ~np.isin(scl, [0, 1, 3, 8, 9, 10])
                mndwi = (g3 - b11) / np.maximum(g3 + b11, 1)
                agua |= ok & (mndwi > 0)
                valido |= ok
            msk = terra & ~perm & valido & np.isfinite(p)
            obs = agua & msk
            m = metricas(np.nan_to_num(p), obs, msk)
            m2 = metricas(np.nan_to_num(p), obs, msk & ~mang)
            linhas.append({"setor": setor, "data": str(dia.date()), "nivel_rel_NMM_m": round(r.nivel_m, 2),
                           "MHWS_setor_m": mhws, **{k: round(v, 3) if isinstance(v, float) else v for k, v in m.items()},
                           **{f"sem_mangue_{k}": round(v, 3) for k, v in m2.items() if k in ("CSI", "HR", "FAR", "Brier")}})
            cenas += [{"setor": setor, "data": str(dia.date()), "item": it.id} for it in its]
            ativo = msk & ((np.nan_to_num(p) > 0.01) | obs)
            for b0 in np.arange(0, 1, 0.1):
                sel = ativo & (np.nan_to_num(p) >= b0) & (np.nan_to_num(p) < b0 + 0.1 + (1e-9 if b0 >= 0.9 else 0))
                if sel.sum():
                    conf.append({"setor": setor, "data": str(dia.date()), "faixa_p": f"{b0:.1f}-{b0 + 0.1:.1f}",
                                 "p_media": float(np.nan_to_num(p)[sel].mean()), "freq_obs": float(obs[sel].mean()),
                                 "n": int(sel.sum())})
            obs_acc = np.where(msk, obs, obs_acc)
            val_acc |= msk
            _v2.log(f"S2 {setor} {dia.date()}: nível {r.nivel_m:.2f} m, CSI {m['CSI']:.2f}, sem mangue {m2['CSI']:.2f}")
        with rasterio.open(os.path.join(OUT, f"obs_s2_{setor}.tif"), "w",
                           **dict(prof, dtype="uint8", nodata=255, compress="deflate", count=1)) as w:
            w.write(np.where(val_acc, obs_acc, 255).astype("uint8"), 1)
    d = pd.DataFrame(linhas)
    tot = {"setor": "TOTAL", **{k: int(d[k].sum()) for k in ("TP", "FP", "FN", "n_celulas")}}
    tot.update(CSI=tot["TP"] / (tot["TP"] + tot["FP"] + tot["FN"]), HR=tot["TP"] / (tot["TP"] + tot["FN"]),
               FAR=tot["FP"] / (tot["TP"] + tot["FP"]), vies_area=(tot["TP"] + tot["FP"]) / (tot["TP"] + tot["FN"]),
               Brier=float(np.average(d.Brier, weights=d.n_celulas)))
    d = pd.concat([d, pd.DataFrame([tot])], ignore_index=True)
    d.round(3).to_csv(os.path.join(OUT, "sentinel2_metricas.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame(conf).to_csv(os.path.join(OUT, "sentinel2_confiabilidade.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame(cenas).to_csv(os.path.join(OUT, "sentinel2_cenas.csv"), index=False, encoding="utf-8-sig")
    _v2.log(f"Sentinel-2 total: CSI {tot['CSI']:.2f}, HR {tot['HR']:.2f}, FAR {tot['FAR']:.2f}, Brier {tot['Brier']:.3f}")
