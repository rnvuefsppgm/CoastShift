"""16 — Conferência do fator de transferência da maré (f_s) com o modelo EOT20 (Hart-Davis et al., 2021; SEANOE
10.17882/79489, CC BY 4.0, sem conta).

Lê do zip remoto (2,3 GB) só as componentes M2 e S2 da maré oceânica, por requisições HTTP Range, e calcula:
  f_s(EOT20) = (A_M2 + A_S2) no ponto_mar do setor ÷ (A_M2 + A_S2) no marégrafo de Salvador.
Também compara a amplitude EOT20 em Salvador com a observada (análise harmônica do script 08).
Saídas: <BASE>/mares/eot20/{M2,S2}*.nc e <BASE>/mares/fs_eot20.csv
"""
import io
import json
import os
import zipfile

import numpy as np
import pandas as pd
import requests
import xarray as xr

import _v2

URL = "https://www.seanoe.org/data/00683/79489/data/85762.zip"
SALVADOR = (-38.518, -12.974)                                     # marégrafo (lon, lat)


class Remoto(io.RawIOBase):
    """Arquivo HTTP somente leitura com busca (Range), suficiente para o zipfile."""
    def __init__(self, url):
        self.url, self.pos = url, 0
        self.size = int(requests.head(url, allow_redirects=True, timeout=60).headers["Content-Length"])

    def seekable(self):
        return True

    def readable(self):
        return True

    def seek(self, off, whence=0):
        self.pos = {0: off, 1: self.pos + off, 2: self.size + off}[whence]
        return self.pos

    def tell(self):
        return self.pos

    def read(self, n=-1):
        fim = self.size - 1 if n < 0 else min(self.pos + n, self.size) - 1
        if fim < self.pos:
            return b""
        for k in range(5):
            try:
                r = requests.get(self.url, headers={"Range": f"bytes={self.pos}-{fim}"}, timeout=300)
                r.raise_for_status()
                break
            except requests.RequestException:
                if k == 4:
                    raise
        self.pos += len(r.content)
        return r.content

    def readinto(self, b):
        d = self.read(len(b))
        b[:len(d)] = d
        return len(d)


def amp(ds, lon, lat):
    """Amplitude (m) na célula oceânica válida mais próxima."""
    v = [k for k in ds.data_vars if k.lower().startswith("amp")][0]
    a = ds[v]
    lo = lon % 360 if float(ds.lon.max()) > 180 else lon
    sub = a.sel(lat=slice(lat - 1, lat + 1), lon=slice(lo - 1, lo + 1)).load()
    la, ln = np.meshgrid(sub.lat.values, sub.lon.values, indexing="ij")
    ok = np.isfinite(sub.values)
    d = np.where(ok, (la - lat) ** 2 + (ln - lo) ** 2, np.inf)
    i = np.unravel_index(np.argmin(d), d.shape)
    fator = 0.01 if "cm" in str(a.attrs.get("units", "cm")).lower() else 1.0
    return float(sub.values[i]) * fator, float(np.sqrt(d[i]) * 111)


def aplicar():
    """Adota f_s do EOT20 em mares_setores.json (S2 = 1,0: o marégrafo está no setor); guarda a versão Open-Meteo."""
    fs = pd.read_csv(_v2.p("mares", "fs_eot20.csv")).set_index("local").fs_EOT20
    sal = json.load(open(_v2.p("mares", "mares_salvador.json"), encoding="utf-8"))
    f0 = _v2.p("mares", "mares_setores.json")
    old = json.load(open(f0, encoding="utf-8"))
    json.dump(old, open(_v2.p("mares", "mares_setores_openmeteo.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    out = {}
    for s in _v2.SETORES:
        f = 1.0 if s.startswith("S2_") else float(fs[s])
        out[s] = {"msl": 0.0, "mhhw": round(sal["mhhw_m"] * f, 3), "mhws": round(sal["mhws_m"] * f, 3), "amplification_factor": 1.0,
                  "fator_transferencia_salvador": round(f, 3), "fator_openmeteo": old[s]["fator_transferencia_salvador"],
                  "fonte": "UHSLC 708 Salvador × razão (M2+S2) EOT20 (Hart-Davis et al., 2021); S2 = marégrafo; conferido com FEMAR/DHN"}
        _v2.log(f"  {s}: f_s {old[s]['fator_transferencia_salvador']:.3f} -> {f:.3f}; MHWS {old[s]['mhws']:.3f} -> {out[s]['mhws']:.3f} m")
    json.dump(out, open(f0, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    import sys
    if "--aplicar" in sys.argv:
        aplicar()
        raise SystemExit
    pasta = _v2.p("mares", "eot20")
    loc = os.path.join(pasta, "ocean_tides.zip")
    if not os.path.exists(loc):                                     # zip interno comprimido: baixa só a parte oceânica
        zr = zipfile.ZipFile(io.BufferedReader(Remoto(URL), buffer_size=32 << 20))
        with zr.open("ocean_tides.zip") as src, open(loc + ".part", "wb") as dst:
            while True:
                b = src.read(16 << 20)
                if not b:
                    break
                dst.write(b)
        os.replace(loc + ".part", loc)
    z = zipfile.ZipFile(loc)
    alvo = {c: [m for m in z.namelist() if "ocean" in m.lower() and os.path.basename(m).upper().startswith(c + "_") and m.endswith(".nc")]
            for c in ("M2", "S2")}
    ds = {}
    for c, ms in alvo.items():
        f = os.path.join(pasta, os.path.basename(ms[0]))
        if not os.path.exists(f):
            with z.open(ms[0]) as src, open(f, "wb") as dst:
                dst.write(src.read())
        ds[c] = xr.open_dataset(f)
        _v2.log(f"EOT20 {c}: {ms[0]}")
    sal = {c: amp(ds[c], *SALVADOR) for c in ds}
    obs = json.load(open(_v2.p("mares", "mares_salvador.json"), encoding="utf-8"))["amplitudes_m"]
    mares = json.load(open(_v2.p("mares", "mares_setores.json"), encoding="utf-8"))
    ref = sal["M2"][0] + sal["S2"][0]
    linhas = [{"local": "Salvador (marégrafo)", "A_M2_EOT20_m": sal["M2"][0], "A_S2_EOT20_m": sal["S2"][0],
               "dist_celula_km": sal["M2"][1], "A_M2_obs_m": obs.get("M2"), "A_S2_obs_m": obs.get("S2"),
               "fs_atual": 1.0, "fs_EOT20": 1.0}]
    for s, cfg in _v2.SETORES.items():
        a2, d2 = amp(ds["M2"], *cfg["ponto_mar"])
        s2, _ = amp(ds["S2"], *cfg["ponto_mar"])
        fs_e, fs_a = (a2 + s2) / ref, mares[s]["fator_transferencia_salvador"]
        linhas.append({"local": s, "A_M2_EOT20_m": a2, "A_S2_EOT20_m": s2, "dist_celula_km": d2,
                       "fs_atual": fs_a, "fs_EOT20": fs_e, "dif_%": 100 * (fs_a / fs_e - 1),
                       "MHWS_atual_m": mares[s]["mhws"], "MHWS_EOT20_m": round(mares[s]["mhws"] * fs_e / fs_a, 3)})
    t = pd.DataFrame(linhas).round(4)
    t.to_csv(_v2.p("mares", "fs_eot20.csv"), index=False, encoding="utf-8-sig")
    _v2.log("f_s EOT20 × atual:\n" + t[["local", "fs_atual", "fs_EOT20", "dif_%"]].to_string(index=False))
