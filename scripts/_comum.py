"""Utilitários compartilhados pelos scripts 02–13 (carregar config, iniciar GEE)."""
import json
import os
import sys

IN_COLAB = "google.colab" in sys.modules
BASE = os.environ.get("COASTSHIFT_BASE",
                      "/content/drive/MyDrive/CoastShift_Bahia" if IN_COLAB else os.path.abspath("dados_bahia"))


def load_config():
    with open(os.path.join(BASE, "config_bahia.json"), encoding="utf-8") as f:
        return json.load(f)


def path(*p):
    return os.path.join(BASE, *p)


def init_ee(cfg):
    import ee
    try:
        ee.Initialize(project=cfg["gee_project"])
    except Exception:
        ee.Authenticate()
        ee.Initialize(project=cfg["gee_project"])
    return ee


def add_repo_to_path():
    """Permite importar o pacote coastshift (clone do repositório ao lado dos scripts)."""
    here = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
    for cand in (os.path.dirname(here), here, "/content/CoastShift"):
        if os.path.isdir(os.path.join(cand, "coastshift")):
            sys.path.insert(0, cand)
            return cand
    raise ImportError("Clone https://github.com/rnvuefsppgm/CoastShift e rode a partir da pasta scripts/")


# ---------------------------------------------------------------- conversão vertical (Eqs. 1–3)
import glob  # noqa: E402

import numpy as np  # noqa: E402


def ondulacao_egm08(lon, lat):
    """N_EGM08 = h − H para H = 0 (transformação de EPSG:4326+3855 para EPSG:4979)."""
    from pyproj import Transformer
    t = Transformer.from_crs("EPSG:4326+3855", "EPSG:4979", always_xy=True)
    _, _, h = t.transform(lon.ravel(), lat.ravel(), np.zeros(lon.size))
    return np.asarray(h).reshape(lon.shape)


def eta_hgeohnor(lon, lat, eta_const=None):
    fs = glob.glob(path("hgeohnor", "*.tif")) + glob.glob(path("hgeohnor", "*.txt")) + glob.glob(path("hgeohnor", "*.csv"))
    if not fs:
        if eta_const is None:
            raise FileNotFoundError("Baixe a grade hgeoHNOR2020 do IBGE para hgeohnor/ ou defina ETA_CONST.")
        print("AVISO: usando η constante =", eta_const)
        return np.full(lon.shape, eta_const)
    f = fs[0]
    if f.endswith(".tif"):
        import rasterio
        with rasterio.open(f) as src:
            vals = np.array([v[0] for v in src.sample(zip(lon.ravel(), lat.ravel()))])
        return vals.reshape(lon.shape)
    xyz = np.loadtxt(f, comments="#", delimiter=None if f.endswith(".txt") else ",", usecols=(0, 1, 2))
    m = (xyz[:, 0] > lon.min() - 0.5) & (xyz[:, 0] < lon.max() + 0.5) & (xyz[:, 1] > lat.min() - 0.5) & (xyz[:, 1] < lat.max() + 0.5)
    from scipy.interpolate import griddata
    return griddata(xyz[m, :2], xyz[m, 2], (lon, lat), method="cubic")


