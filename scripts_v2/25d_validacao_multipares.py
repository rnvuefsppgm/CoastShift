"""25d — Validação da inundação pela maré com vários pares preamar/baixa-mar por setor (Sentinel-1 e Sentinel-2).

Etapa `obs` (uma vez; independe de ℓ): para cada setor e sensor, escolhe até K pares (as K datas de maior e as K de
menor nível observado no marégrafo de Salvador × fator do setor; cobertura ≥ 60 % da parte terrestre; Sentinel-1 na
órbita relativa de maior amplitude) e grava as máscaras de água em cache (<VALSAT>/cache, <VALSAT>/pares.csv).
Água de maré observada = água na preamar e não na baixa-mar, nas células válidas nas duas datas, fora da água
permanente (GSW ≥ 50 %).

Etapa `avaliar` (por rodada; ℓ via COASTSHIFT_ELL): O2 com N = 100 em todos os níveis observados do setor com os mesmos
campos de erro do DEM (sementes comuns), p_maré = p(alta) − p(baixa); métricas por par, por setor e na costa, com e
sem mangue, e curva de confiabilidade. Saídas em <COASTSHIFT_RESULTADOS>/validacao/{s1,s2}_multipares_*.csv e um
resumo em <VALSAT>/resumo_ell_<ℓ>.csv.

Uso: python 25d_validacao_multipares.py obs [--k 3] [--proc 6]
     python 25d_validacao_multipares.py avaliar [--proc 3]
"""
import argparse
import importlib.util
import json
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
import rasterio

import _v2


def _mod(nome, arq):
    spec = importlib.util.spec_from_file_location(nome, os.path.join(os.path.dirname(os.path.abspath(__file__)), arq))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


v25 = _mod("v25", "25_validacao_sentinel2.py")
v25b = _mod("v25b", "25b_validacao_intermare_sentinel2.py")
v25c = _mod("v25c", "25c_validacao_intermare_sentinel1.py")
csio = v25.csio
from coastshift import core  # noqa: E402

VALSAT = os.environ.get("COASTSHIFT_VALSAT", os.path.join(os.path.dirname(_v2.REPO), "resultados_O2_Bahia", "validacao_satelite"))
CACHE = os.path.join(VALSAT, "cache")
SENS = {"s1": dict(col="sentinel-1-rtc", ini="2017-01-01", query=None),
        "s2": dict(col="sentinel-2-l2a", ini="2019-01-01", query={"eo:cloud_cover": {"lt": 10}})}


# ------------------------------------------------------------------------------------------------ etapa obs
def _escolhe_pares(df, k):
    altas = df.sort_values("nivel", ascending=False).head(k)
    baixas = df[~df.dia.isin(altas.dia)].sort_values("nivel").head(k).copy()
    pares = []
    for _, a in altas.iterrows():
        if baixas.empty:
            break
        j = (baixas.dia - a.dia).abs().idxmin()                     # baixa-mar mais próxima no tempo
        b = baixas.loc[j]
        baixas = baixas.drop(j)
        pares.append((a, b))
    return pares


def obs_setor(args):
    setor, k = args
    import planetary_computer
    import pystac_client
    from shapely.geometry import shape
    from shapely.ops import unary_union
    import geopandas as gpd
    cat = pystac_client.Client.open(v25.STAC, modifier=planetary_computer.sign_inplace)
    sal = json.load(open(_v2.p("mares", "mares_salvador.json"), encoding="utf-8"))
    mares = json.load(open(_v2.p("mares", "mares_setores.json"), encoding="utf-8"))
    sv = (_v2.serie_uhslc(708, ("b",), fast=True) - sal["nmm_zero_estacao_m"]).dropna()
    _, gs = _v2.aoi()
    ba = gpd.read_file(_v2.p("aoi", "ibge_bahia.geojson")).union_all()
    terra_ll = gs[gs.setor == setor].geometry.iloc[0].intersection(ba)
    pk = csio.Package(os.path.join(_v2.BASE, "pacotes", setor))
    prof = pk.profile
    linhas = []
    for sen, cfg in SENS.items():
        kw = dict(collections=[cfg["col"]], bbox=list(gs[gs.setor == setor].total_bounds), datetime=f"{cfg['ini']}/2025-12-31")
        if cfg["query"]:
            kw["query"] = cfg["query"]
        its = list(cat.search(**kw).items())
        if not its:
            continue
        df = pd.DataFrame({"item": its, "t": pd.to_datetime([i.datetime for i in its]).tz_convert(None),
                           "orbita": [i.properties.get("sat:relative_orbit", 0) for i in its]})
        df["nivel"] = np.interp(df.t.values.astype("datetime64[s]").astype("int64"),
                                sv.index.values.astype("datetime64[s]").astype("int64"), sv.values, left=np.nan,
                                right=np.nan) * mares[setor]["fator_transferencia_salvador"]
        df = df.dropna(subset=["nivel"])
        df["dia"] = df.t.dt.floor("D")
        df["geo"] = [shape(i.geometry) for i in df.item]
        chave = ["orbita", "dia"] if sen == "s1" else ["dia"]
        cobre = df.groupby(chave).agg(nivel=("nivel", "mean"), geo=("geo", lambda g: unary_union(list(g)))).reset_index()
        cobre["cobertura"] = [terra_ll.intersection(g).area / terra_ll.area for g in cobre.geo]
        cobre = cobre[cobre.cobertura >= 0.6]
        if sen == "s1":
            orb = cobre.groupby("orbita").nivel.agg(lambda x: x.max() - x.min()).idxmax()
            cobre, df = cobre[cobre.orbita == orb], df[df.orbita == orb]
        for i, (a, b) in enumerate(_escolhe_pares(cobre, k)):
            ok_par = True
            for d in (a.dia, b.dia):
                f = os.path.join(CACHE, f"{sen}_{setor}_{d:%Y%m%d}.npz")
                if os.path.exists(f):
                    continue
                try:
                    w, ok = (v25c.agua_s1 if sen == "s1" else v25b.agua)(df[df.dia == d].item, prof)
                    if not ok.any():
                        raise RuntimeError("sem pixels válidos")
                    np.savez_compressed(f, w=np.packbits(w), ok=np.packbits(ok), shape=np.array(w.shape))
                except Exception as e:  # noqa: BLE001
                    _v2.log(f"{sen} {setor} {d:%Y-%m-%d} ignorada: {str(e)[:80]}")
                    ok_par = False
            if ok_par:
                linhas.append({"setor": setor, "sensor": sen, "par": i + 1, "dia_alta": f"{a.dia:%Y-%m-%d}",
                               "nivel_alta_m": round(float(a.nivel), 3), "dia_baixa": f"{b.dia:%Y-%m-%d}",
                               "nivel_baixa_m": round(float(b.nivel), 3), "MHWS_m": mares[setor]["mhws"]})
        _v2.log(f"obs {sen} {setor}: {sum(1 for x in linhas if x['sensor'] == sen)} pares")
    return linhas


# -------------------------------------------------------------------------------------------- etapa avaliar
def _ler(sen, setor, dia):
    z = np.load(os.path.join(CACHE, f"{sen}_{setor}_{dia.replace('-', '')}.npz"))
    n = int(np.prod(z["shape"]))
    return (np.unpackbits(z["w"])[:n].reshape(z["shape"]).astype(bool),
            np.unpackbits(z["ok"])[:n].reshape(z["shape"]).astype(bool))


def p_niveis(pk, niveis, n=100, seed=4242):
    """Probabilidade O2 (MHWS substituída pelo nível observado) para vários níveis com campos de erro comuns."""
    p = pk.params
    rng = np.random.default_rng(seed)
    bias, sd = core.dem_error_maps(pk.layers["landcover"], p.get("dem_error", {}))
    corr = float(os.environ.get("COASTSHIFT_ELL") or p["dem_error"]["corr_length_m"]) / pk.cell
    base = {}
    for lv, ano in niveis:
        pr = json.loads(json.dumps(p))
        pr["tide"]["mhws"] = float(lv)
        base[(lv, ano)] = core.sea_level_event(pr, "MHWS", 0)
    cnt = {kk: np.zeros(pk.dem.shape, "uint16") for kk in niveis}
    for _ in range(n):
        u = rng.uniform()
        eps = core.correlated_field(pk.dem.shape, corr, rng)
        z = pk.dem - bias - sd * eps
        for kk in niveis:
            cnt[kk] += core.connected_flood(z, base[kk] + core.delta_rsl(p, "ssp245", kk[1], u), pk.sea, 8)
    return {kk: v.astype("float32") / n for kk, v in cnt.items()}


def avaliar_setor(args):
    setor, pares = args
    pk = csio.Package(os.path.join(_v2.BASE, "pacotes", setor))
    niveis = sorted({(r.nivel_alta_m, int(r.dia_alta[:4])) for r in pares.itertuples()}
                    | {(r.nivel_baixa_m, int(r.dia_baixa[:4])) for r in pares.itertuples()})
    P = p_niveis(pk, niveis)
    terra = np.isfinite(pk.dem) & ~pk.sea
    with rasterio.open(_v2.p("agua", f"gsw_ocorrencia_{setor}.tif")) as g:
        perm = g.read(1) >= 50
    mang = pk.layers["landcover"] == 5
    linhas, conf = [], []
    for r in pares.itertuples():
        w_a, ok_a = _ler(r.sensor, setor, r.dia_alta)
        w_b, ok_b = _ler(r.sensor, setor, r.dia_baixa)
        msk = terra & ~perm & ok_a & ok_b
        obs = w_a & ~w_b & msk
        p = np.clip(P[(r.nivel_alta_m, int(r.dia_alta[:4]))] - P[(r.nivel_baixa_m, int(r.dia_baixa[:4]))], 0, 1)
        m, m2 = v25.metricas(p, obs, msk), v25.metricas(p, obs, msk & ~mang)
        ativo = msk & ((p > 0.01) | obs)
        sq = float(((p[ativo] - obs[ativo]) ** 2).sum())
        linhas.append({"setor": setor, "sensor": r.sensor, "par": r.par, "dia_alta": r.dia_alta, "nivel_alta_m": r.nivel_alta_m,
                       "dia_baixa": r.dia_baixa, "nivel_baixa_m": r.nivel_baixa_m, **m, "soma_quad": sq, "n_ativo": int(ativo.sum()),
                       **{f"sem_mangue_{k}": v for k, v in m2.items()}})
        for b0 in np.arange(0, 1, 0.1):
            sel = ativo & (p >= b0) & ((p < b0 + 0.1) if b0 < 0.9 else (p <= 1))
            if sel.sum():
                conf.append({"setor": setor, "sensor": r.sensor, "faixa_p": round(b0 + 0.05, 2), "p_media": float(p[sel].mean()),
                             "freq_obs": float(obs[sel].mean()), "n": int(sel.sum())})
    _v2.log(f"avaliado {setor}: {len(pares)} pares, {len(niveis)} níveis")
    return linhas, conf


def agrega(d, rot):
    t = {k: int(d[k].sum()) for k in ("TP", "FP", "FN", "n_celulas")}
    t2 = {k: int(d[f"sem_mangue_{k}"].sum()) for k in ("TP", "FP", "FN")}
    return {"setor": rot, "n_pares": len(d), **t, "CSI": t["TP"] / max(t["TP"] + t["FP"] + t["FN"], 1),
            "HR": t["TP"] / max(t["TP"] + t["FN"], 1), "FAR": t["FP"] / max(t["TP"] + t["FP"], 1),
            "vies_area": (t["TP"] + t["FP"]) / max(t["TP"] + t["FN"], 1), "Brier": d.soma_quad.sum() / max(d.n_ativo.sum(), 1),
            "sem_mangue_CSI": t2["TP"] / max(t2["TP"] + t2["FP"] + t2["FN"], 1), "sem_mangue_HR": t2["TP"] / max(t2["TP"] + t2["FN"], 1),
            "sem_mangue_FAR": t2["FP"] / max(t2["TP"] + t2["FP"], 1)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("etapa", choices=["obs", "avaliar"])
    ap.add_argument("--k", type=int, default=3, help="pares por setor e sensor")
    ap.add_argument("--proc", type=int, default=3)
    a = ap.parse_args()
    os.makedirs(CACHE, exist_ok=True)
    fp = os.path.join(VALSAT, "pares.csv")
    if a.etapa == "obs":
        with ProcessPoolExecutor(a.proc) as ex:
            res = list(ex.map(obs_setor, [(s, a.k) for s in _v2.SETORES]))
        pd.DataFrame([x for r in res for x in r]).to_csv(fp, index=False, encoding="utf-8-sig")
        open(os.path.join(VALSAT, "obs_pronto.flag"), "w").write("ok")
        _v2.log(f"obs concluída: {sum(len(r) for r in res)} pares -> {fp}")
    else:
        pares = pd.read_csv(fp)
        with ProcessPoolExecutor(a.proc) as ex:
            res = list(ex.map(avaliar_setor, [(s, pares[pares.setor == s]) for s in _v2.SETORES if (pares.setor == s).any()]))
        pp = pd.DataFrame([x for r in res for x in r[0]])
        cf = pd.DataFrame([x for r in res for x in r[1]])
        val = os.path.join(v25.RES, "validacao")
        os.makedirs(val, exist_ok=True)
        ell = os.environ.get("COASTSHIFT_ELL", "pacote")
        resumo = []
        for sen in ("s1", "s2"):
            d = pp[pp.sensor == sen]
            if d.empty:
                continue
            tab = pd.DataFrame([agrega(d[d.setor == s], s) for s in d.setor.unique()] + [agrega(d, "TOTAL")])
            tab.round(4).to_csv(os.path.join(val, f"{sen}_multipares_metricas.csv"), index=False, encoding="utf-8-sig")
            d.round(4).to_csv(os.path.join(val, f"{sen}_multipares_por_par.csv"), index=False, encoding="utf-8-sig")
            cf[cf.sensor == sen].to_csv(os.path.join(val, f"{sen}_multipares_confiabilidade.csv"), index=False, encoding="utf-8-sig")
            resumo.append({"ell_m": ell, "sensor": sen, **tab.iloc[-1].to_dict()})
            _v2.log(f"{sen} multipares ℓ={ell}: {len(d)} pares, CSI {tab.iloc[-1].CSI:.3f}, HR {tab.iloc[-1].HR:.2f}, "
                    f"FAR {tab.iloc[-1].FAR:.2f}, Brier {tab.iloc[-1].Brier:.3f}")
        pd.DataFrame(resumo).round(4).to_csv(os.path.join(VALSAT, f"resumo_ell_{ell}.csv"), index=False, encoding="utf-8-sig")
