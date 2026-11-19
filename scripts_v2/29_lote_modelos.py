"""29 — Execução em lote (sem interface) de qualquer modelo O1–O5 sobre os pacotes V2.

Exemplos:
  python 29_lote_modelos.py --modelos O1,O2 --setores S1,S2 --ssps ssp245,ssp585 --anos 2050,2100 --n 300
  python 29_lote_modelos.py --modelos O3,O5 --setores S2 --bbox -38.535,-12.985,-38.455,-12.900 --coarsen 1
  python 29_lote_modelos.py --modelos O4 --setores S3,S6 --anos 2100

O3 e O5 (hidrodinâmicos) devem rodar em subdomínios (--bbox em lon/lat) — o setor inteiro é grande demais.
Saídas: <resultados>/lote/<modelo>/<setor>/{<camada>.tif, tabela.csv, meta.json} e lote/resumo_lote.csv
"""
import argparse
import json
import os
import shutil
import sys
import time

import pandas as pd
import rasterio
from rasterio.windows import from_bounds

import _v2

sys.path.insert(0, _v2.REPO)
from coastshift import io as csio, models  # noqa: E402

RES = os.environ.get("COASTSHIFT_RESULTADOS", os.path.join(os.path.dirname(_v2.REPO), "resultados_O2_Bahia"))


def subdominio(src, bbox_ll, dst):
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:4326", _v2.CRS, always_xy=True)
    x0, y0 = tr.transform(bbox_ll[0], bbox_ll[1])
    x1, y1 = tr.transform(bbox_ll[2], bbox_ll[3])
    os.makedirs(dst, exist_ok=True)
    for f in os.listdir(src):
        if f.endswith(".tif"):
            with rasterio.open(os.path.join(src, f)) as r:
                w = from_bounds(x0, y0, x1, y1, transform=r.transform).round_offsets().round_lengths()
                a = r.read(1, window=w)
                prof = dict(r.profile, width=w.width, height=w.height, transform=r.window_transform(w))
            with rasterio.open(os.path.join(dst, f), "w", **prof) as o:
                o.write(a, 1)
    shutil.copy(os.path.join(src, "params.json"), dst)
    return dst


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelos", default="O2")
    ap.add_argument("--setores", default="S1,S2,S3,S4,S5,S6")
    ap.add_argument("--ssps", default="ssp245,ssp585")
    ap.add_argument("--anos", default="2050,2100")
    ap.add_argument("--ref", default="MHWS")
    ap.add_argument("--tr", type=float, default=0)
    ap.add_argument("--quantil", type=float, default=0.5)
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--horas", type=float, default=13)
    ap.add_argument("--coarsen", type=int, default=2)
    ap.add_argument("--biblioteca", type=int, default=5)
    ap.add_argument("--bbox", default="", help="lon0,lat0,lon1,lat1 (subdomínio; obrigatório para O3/O5)")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    out = os.path.join(RES, "lote")
    resumo = []
    for setor in [s for s in _v2.SETORES if s.split("_")[0] in a.setores.split(",")]:
        pasta = os.path.join(_v2.BASE, "pacotes", setor)
        if a.bbox:
            pasta = subdominio(pasta, [float(v) for v in a.bbox.split(",")], os.path.join(out, "_subdominio", setor))
        pk = csio.Package(pasta)
        for m in a.modelos.split(","):
            if m in ("O3", "O5") and not a.bbox:
                _v2.log(f"{m} {setor}: informe --bbox (subdomínio) — pulado")
                continue
            opt = {"ssps": a.ssps.split(","), "years": [int(y) for y in a.anos.split(",")], "ref": a.ref, "tr": a.tr,
                   "quantile": a.quantil, "n": a.n, "hours": a.horas, "coarsen": a.coarsen, "library": a.biblioteca,
                   "setup": bool(pk.params["waves"].get("costa_aberta")), "conn": 8, "seed": a.seed}
            t0 = time.time()
            res = models.RUNNERS[m](pk, opt, progress=lambda f, msg: None)
            dst = os.path.join(out, m, setor)
            os.makedirs(dst, exist_ok=True)
            for k, v in res.layers.items():
                csio.write_raster(os.path.join(dst, f"{k}.tif"), v, pk.profile)
            pd.DataFrame(res.table).to_csv(os.path.join(dst, "tabela.csv"), index=False, encoding="utf-8-sig")
            json.dump({**res.meta, "opcoes": opt}, open(os.path.join(dst, "meta.json"), "w", encoding="utf-8"),
                      indent=1, default=str, ensure_ascii=False)
            resumo += [{"modelo": m, "setor": setor, **r} for r in res.table]
            _v2.log(f"lote {m} {setor}: {len(res.layers)} camadas em {(time.time() - t0) / 60:.1f} min")
    pd.DataFrame(resumo).to_csv(os.path.join(out, "resumo_lote.csv"), index=False, encoding="utf-8-sig")
    _v2.log(f"lote concluído -> {out}")
