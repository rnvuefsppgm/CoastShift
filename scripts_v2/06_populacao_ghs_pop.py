"""06 — População residente GHS-POP R2023A, época 2025, 3 arc-seg (~90 m), EPSG:4326 (Schiavina et al., 2023; JRC).
Download direto dos blocos do servidor do JRC; conversão para pessoas por célula de 30 m preservando o total
(densidade por m² → média → ×900 m²). Para o Censo 2022 (IBGE), substitua o raster mantendo a grade.
Saídas: <BASE>/raw/ghs_pop/*.zip e <BASE>/exposicao/pop_<setor>.tif
"""
import zipfile
import numpy as np
import rasterio
import _v2

URL = ("https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_POP_GLOBE_R2023A/"
       "GHS_POP_E2025_GLOBE_R2023A_4326_3ss/V1-0/tiles/GHS_POP_E2025_GLOBE_R2023A_4326_3ss_V1_0_R{r}_C{c}.zip")


def densidade_30m(arr, src, win):
    t = src.window_transform(win)
    lat = t.f + (np.arange(arr.shape[0]) + 0.5) * t.e
    area = abs(t.a) * 111320.0 * np.cos(np.deg2rad(lat)) * abs(t.e) * 110574.0     # m² por célula
    return arr / area[:, None] * (_v2.RES ** 2)


if __name__ == "__main__":
    x0, y0, x1, y1 = _v2.aoi_bounds_ll()
    fontes = []
    for r in range(9, 14):
        for c in range(13, 17):
            f = _v2.download(URL.format(r=r, c=c), _v2.p("raw", "ghs_pop", f"R{r}_C{c}.zip"), quiet_404=True)
            if not f:
                continue
            tif = [n for n in zipfile.ZipFile(f).namelist() if n.endswith(".tif")][0]
            path = f"/vsizip/{f}/{tif}"
            with rasterio.open(path) as s:
                b = s.bounds
            if b.left < x1 and b.right > x0 and b.bottom < y1 and b.top > y0:
                fontes.append(path)
    _v2.log(f"GHS-POP: {len(fontes)} blocos intersectam a zona costeira")
    out = _v2.reprojetar_para_setores(fontes, "exposicao", "pop", "average", transform_fn=densidade_30m)
    for f in out:
        with rasterio.open(f) as s:
            a = s.read(1, masked=True)
        _v2.log(f"  {f.split('pop_')[-1]}: {a.sum():,.0f} pessoas na zona costeira")
