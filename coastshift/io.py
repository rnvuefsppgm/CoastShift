"""Leitura/escrita de rasters e do 'pacote' de entrada do modelo."""
import json
import os

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject

LAYERS = {  # nome lógico -> arquivo no pacote
    "dem": "dem.tif",                # cota do terreno relativa ao NMM local (m)
    "landcover": "landcover.tif",    # classes MapBiomas
    "sea": "sea.tif",                # 1 = semente oceânica/estuarina
    "pop": "pop.tif",                # pessoas por célula
    "buildings": "buildings.tif",    # edificações (contagem fracionária) por célula
}


def read_raster(path):
    with rasterio.open(path) as src:
        arr = src.read(1).astype("float32")
        if src.nodata is not None:
            arr[arr == src.nodata] = np.nan
        return arr, src.profile.copy()


def write_raster(path, arr, profile, dtype="float32", nodata=-9999.0):
    prof = profile.copy()
    prof.update(driver="GTiff", count=1, dtype=dtype, nodata=nodata, compress="deflate")
    out = np.where(np.isfinite(arr), arr, nodata).astype(dtype)
    with rasterio.open(path, "w", **prof) as dst:
        dst.write(out, 1)


def align_to(src_path, ref_profile, resampling=Resampling.nearest):
    """Reprojeta um raster para a grade de referência."""
    with rasterio.open(src_path) as src:
        dst = np.full((ref_profile["height"], ref_profile["width"]), np.nan, "float32")
        reproject(rasterio.band(src, 1), dst, src_nodata=src.nodata, dst_nodata=np.nan,
                  dst_transform=ref_profile["transform"], dst_crs=ref_profile["crs"],
                  resampling=resampling)
    return dst


def cell_size_m(profile):
    t = profile["transform"]
    crs = profile.get("crs")
    if crs is not None and crs.is_geographic:  # aproximação em graus -> metros
        lat = t.f + t.e * profile["height"] / 2
        return abs(t.a) * 111320 * np.cos(np.radians(lat))
    return abs(t.a)


class Package:
    """Pasta com params.json + rasters alinhados (ver docs/02_Formato_Pacote.md)."""

    def __init__(self, folder):
        self.folder = folder
        with open(os.path.join(folder, "params.json"), encoding="utf-8") as f:
            self.params = json.load(f)
        self.layers, self.profile = {}, None
        for key, fname in LAYERS.items():
            p = os.path.join(folder, fname)
            if os.path.exists(p):
                arr, prof = read_raster(p)
                self.layers[key] = arr
                if key == "dem":
                    self.profile = prof
        if "dem" not in self.layers:
            raise FileNotFoundError("dem.tif ausente no pacote")
        shape = self.layers["dem"].shape
        for k, v in list(self.layers.items()):
            if v.shape != shape:
                raise ValueError(f"{k}.tif não está alinhado ao dem.tif")
        self.layers.setdefault("sea", (np.isnan(self.layers["dem"])).astype("float32"))
        self.layers.setdefault("landcover", np.zeros(shape, "float32"))
        self.layers.setdefault("pop", np.zeros(shape, "float32"))
        self.layers.setdefault("buildings", np.zeros(shape, "float32"))
        self.cell = cell_size_m(self.profile)

    @property
    def dem(self):
        return self.layers["dem"]

    @property
    def sea(self):
        return self.layers["sea"] > 0.5

    def save_params(self):
        with open(os.path.join(self.folder, "params.json"), "w", encoding="utf-8") as f:
            json.dump(self.params, f, indent=2, ensure_ascii=False)
