"""02 — Copernicus DEM GLO-30 (AWS Open Data, sem login) recortado na zona costeira da Bahia.
Fonte: ESA/Airbus, Copernicus DEM GLO-30 (COG 1°×1°), s3://copernicus-dem-30m. Alturas ortométricas EGM2008.
Saídas: <BASE>/raw/cop30/*.tif e <BASE>/dem/dem_cop30_egm08_<setor>.tif (EPSG:31984, 30 m, bilinear).
"""
import math
import _v2

URL = "https://copernicus-dem-30m.s3.amazonaws.com/{n}/{n}.tif"


def nome(lat, lon):
    return (f"Copernicus_DSM_COG_10_{'N' if lat >= 0 else 'S'}{abs(lat):02d}_00_"
            f"{'E' if lon >= 0 else 'W'}{abs(lon):03d}_00_DEM")


if __name__ == "__main__":
    x0, y0, x1, y1 = _v2.aoi_bounds_ll()
    fontes = []
    for lat in range(math.floor(y0), math.ceil(y1)):
        for lon in range(math.floor(x0), math.ceil(x1)):
            n = nome(lat, lon)
            f = _v2.download(URL.format(n=n), _v2.p("raw", "cop30", n + ".tif"), quiet_404=True)
            if f:
                fontes.append(f)
    _v2.log(f"Copernicus: {len(fontes)} quadrículas")
    _v2.reprojetar_para_setores(fontes, "dem", "dem_cop30_egm08", "bilinear")
