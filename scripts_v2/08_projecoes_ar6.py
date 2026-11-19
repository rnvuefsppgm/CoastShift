"""08 — Projeções regionais do nível relativo do mar do IPCC AR6 (Garner et al., 2021; Fox-Kemper et al., 2021).
Zenodo doi:10.5281/zenodo.6382554, pacote ar6-regional-confidence.zip (9,2 GB). Este script NÃO baixa o zip
inteiro: lê o diretório remoto por requisições HTTP Range e extrai só total_<ssp>_medium_confidence_values.nc
(~75 MB cada; nível relativo total com movimento vertical do terreno, mm, rel. 1995–2014).
Para cada setor usa o ponto AR6 mais próximo do ponto offshore (e do marégrafo de Salvador).
Saídas: <BASE>/raw/ar6/*.nc e <BASE>/ar6/ar6_setores.json (m; formato do params.json do CoastShift)
"""
import io
import os
import zipfile

import numpy as np
import requests

import _v2

URL = "https://zenodo.org/records/6382554/files/ar6-regional-confidence.zip"
SSPS = ["ssp119", "ssp126", "ssp245", "ssp370", "ssp585"]
QS = [0.01, 0.05, 0.10, 0.17, 0.25, 0.33, 0.50, 0.67, 0.75, 0.83, 0.90, 0.95, 0.99]


class HTTPRange(io.RawIOBase):
    """Arquivo remoto somente-leitura com seek, via cabeçalho HTTP Range."""

    def __init__(self, url):
        self.url, self.pos, self.s = url, 0, requests.Session()
        r = self.s.get(url, headers=dict(_v2.UA, Range="bytes=0-0"), timeout=120)
        self.size = int(r.headers["Content-Range"].split("/")[1])

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else (self.pos + off if whence == 1 else self.size + off)
        return self.pos

    def readinto(self, b):
        if self.pos >= self.size:
            return 0
        end = min(self.pos + len(b), self.size) - 1
        for k in range(5):
            try:
                d = self.s.get(self.url, headers=dict(_v2.UA, Range=f"bytes={self.pos}-{end}"), timeout=300).content
                break
            except Exception:  # noqa: BLE001
                if k == 4:
                    raise
        b[:len(d)] = d
        self.pos += len(d)
        return len(d)


def extrair():
    zf = zipfile.ZipFile(io.BufferedReader(HTTPRange(URL), buffer_size=8 << 20))
    nomes = {i.filename: i for i in zf.infolist()}
    out = {}
    for ssp in SSPS:
        n = (f"ar6-regional-confidence/regional/confidence_output_files/medium_confidence/{ssp}/"
             f"total_{ssp}_medium_confidence_values.nc")
        if n not in nomes:
            _v2.log("ausente no zip:", n)
            continue
        dest = _v2.p("raw", "ar6", os.path.basename(n))
        if not (os.path.exists(dest) and os.path.getsize(dest) == nomes[n].file_size):
            _v2.log(f"extraindo {os.path.basename(n)} ({nomes[n].file_size / 1e6:.0f} MB) por HTTP Range…")
            with zf.open(n) as src, open(dest + ".part", "wb") as dst:
                while True:
                    c = src.read(8 << 20)
                    if not c:
                        break
                    dst.write(c)
            os.replace(dest + ".part", dest)
        out[ssp] = dest
    return out


if __name__ == "__main__":
    import xarray as xr

    arqs = extrair()
    pontos = {k: v["ponto_mar"] for k, v in _v2.SETORES.items()}
    pontos["Salvador_maregrafo"] = list(_v2.SALVADOR)
    res = {k: {"quantiles": QS, "scenarios": {}, "unidade": "m rel. 1995-2014", "doi": "10.5281/zenodo.6382554",
               "fonte": "IPCC AR6 regional, medium confidence, total (inclui movimento vertical do terreno)"} for k in pontos}
    for ssp, f in arqs.items():
        ds = xr.open_dataset(f)
        v = ds["sea_level_change"]
        lat, lon = ds["lat"].values, ds["lon"].values
        anos = [int(a) for a in ds["years"].values if a <= 2150]
        qv = ds["quantiles"].values
        arr = v.sel(years=anos).transpose("quantiles", "years", "locations").values
        ok = np.isfinite(arr).all(axis=(0, 1))
        for k, (lo, la) in pontos.items():
            d = np.hypot((lon - lo) * np.cos(np.deg2rad(la)), lat - la) * 111.0
            d[~ok] = np.inf
            i = int(np.argmin(d))
            tab = arr[:, :, i]
            res[k]["scenarios"][ssp] = [[round(float(np.interp(q, qv, tab[:, j])) / 1000.0, 4) for q in QS]
                                        for j in range(len(anos))]
            res[k].update(years=anos, location_id=int(ds["locations"].values[i]), lat=float(lat[i]), lon=float(lon[i]),
                          dist_km=round(float(d[i]), 1))
        _v2.log(f"{ssp}: ok ({len(anos)} anos)")
    _v2.salvar_json(res, "ar6", "ar6_setores.json")
    for k, r in res.items():
        if "ssp585" in r["scenarios"] and 2100 in r["years"]:
            med = r["scenarios"]["ssp585"][r["years"].index(2100)][QS.index(0.5)]
            _v2.log(f"  {k}: ponto AR6 {r['location_id']} ({r['dist_km']} km), SSP5-8.5 2100 mediana = {med:.2f} m")
