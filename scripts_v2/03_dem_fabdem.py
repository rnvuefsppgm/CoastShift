"""03 — FABDEM V1-2 (Hawker et al., 2022; Universidade de Bristol) — DEM sem prédios e florestas.
Licença CC BY-NC-SA 4.0 (uso não comercial). Download direto do bloco 10°×10° S20W040-S10W030 (~351 MB),
leitura dos tiles 1°×1° direto do zip (sem extrair). Alturas ortométricas EGM2008.
Saídas: <BASE>/raw/fabdem/*.zip e <BASE>/dem/dem_fabdem_egm08_<setor>.tif
"""
import math
import zipfile
import _v2

URL = "https://data.bris.ac.uk/datasets/s5hqmjcdj8yo2ibzi9b4ew3sn/{z}"


def bloco(lat, lon):
    la0, lo0 = math.floor(lat / 10) * 10, math.floor(lon / 10) * 10
    f = lambda v, p, n: f"{p if v >= 0 else n}{abs(v):0{3 if p == 'E' else 2}d}"  # noqa: E731
    return f"{f(la0, 'N', 'S')}{f(lo0, 'E', 'W')}-{f(la0 + 10, 'N', 'S')}{f(lo0 + 10, 'E', 'W')}_FABDEM_V1-2.zip"


if __name__ == "__main__":
    x0, y0, x1, y1 = _v2.aoi_bounds_ll()
    zips = sorted({bloco(la, lo) for la in (y0, y1) for lo in (x0, x1)})
    fontes = []
    for z in zips:
        f = _v2.download(URL.format(z=z), _v2.p("raw", "fabdem", z))
        if not f:
            continue
        for n in zipfile.ZipFile(f).namelist():
            if not n.lower().endswith(".tif"):
                continue
            b = n.split("/")[-1][:7]            # ex.: S13W039
            lat = (-1 if b[0] == "S" else 1) * int(b[1:3])
            lon = (-1 if b[3] == "W" else 1) * int(b[4:7])
            if lat + 1 > y0 and lat < y1 and lon + 1 > x0 and lon < x1:
                fontes.append(f"/vsizip/{f}/{n}")
    _v2.log(f"FABDEM: {len(fontes)} tiles na zona costeira")
    _v2.reprojetar_para_setores(fontes, "dem", "dem_fabdem_egm08", "bilinear")
