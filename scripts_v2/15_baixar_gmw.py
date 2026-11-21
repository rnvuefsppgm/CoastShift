"""15 — Global Mangrove Watch v3.0 (2020), raster de 25 m (Bunting et al., 2022; Zenodo 6894273, CC BY 4.0, sem conta).
Baixa o zip de GeoTIFFs de 2020 e reprojeta os blocos que cobrem a Bahia para a grade de cada setor (vizinho mais próximo).
Saída: <BASE>/habitat/gmw2020_<setor>.tif (1 = mangue, 0 = não mangue).
"""
import os
import zipfile

import requests

import _v2

URL = "https://zenodo.org/records/6894273/files/gmw_v3_2020_gtiff.zip?download=1"

if __name__ == "__main__":
    pasta = _v2.p("habitat")
    os.makedirs(pasta, exist_ok=True)
    z = os.path.join(pasta, "gmw_v3_2020_gtiff.zip")
    if not os.path.exists(z):
        with requests.get(URL, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(z + ".part", "wb") as f:
                for b in r.iter_content(1 << 20):
                    f.write(b)
        os.replace(z + ".part", z)
    w, s, e, n = _v2.aoi()[0].total_bounds

    def cobre(nome):                                   # blocos 1°×1° nomeados pelo canto superior esquerdo: GMW_S13W039_...
        b = os.path.basename(nome)
        if not b.lower().endswith(".tif"):
            return False
        lat = (-1 if b[4] == "S" else 1) * int(b[5:7])
        lon = (-1 if b[7] == "W" else 1) * int(b[8:11])
        return lon < e and lon + 1 > w and lat > s and lat - 1 < n
    fontes = [f"/vsizip/{z}/{m}" for m in zipfile.ZipFile(z).namelist() if cobre(m)]
    _v2.log(f"GMW 2020: {len(fontes)} blocos na Bahia")
    _v2.reprojetar_para_setores(fontes, "habitat", "gmw2020", resampling="nearest", dtype="uint8", nodata=255)
    _v2.log("GMW reprojetado por setor")
