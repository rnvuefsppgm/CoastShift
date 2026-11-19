"""12 — Pontos de referência ICESat-2 para validar e calibrar o erro do DEM (sem conta Earthdata).
Serviço público SlideRule Earth (Shean et al., 2023): ajuste de superfície ATL06-SR usando só fótons de terreno
classificados pelo ATL08 (atl08_ground), segmentos de 40 m a cada 20 m, confiança alta, 2019–2025.
Alturas elipsoidais (ITRF2014/WGS84, EPSG:7912); a conversão para o datum do pacote é feita no script 20.
Saídas: <BASE>/icesat2/atl08_ground_<setor>.csv (lon, lat, h_elip, h_sigma, n_fotons, data)
"""
import os

import pandas as pd

import _v2

T0, T1 = "2019-01-01T00:00:00Z", "2025-12-31T23:59:59Z"

if __name__ == "__main__":
    from sliderule import icesat2, sliderule

    sliderule.init(verbose=False)
    g, gs = _v2.aoi()
    import geopandas as gpd
    ba = gpd.read_file(_v2.p("aoi", "ibge_bahia.geojson")).union_all()
    for _, r in gs.iterrows():
        dest = _v2.p("icesat2", f"atl08_ground_{r.setor}.csv")
        if os.path.exists(dest):
            _v2.log("existe:", dest)
            continue
        terra = r.geometry.intersection(ba)
        if terra.is_empty:
            continue
        casca = terra.convex_hull.buffer(0.005).simplify(0.005)
        poly = [{"lon": x, "lat": y} for x, y in casca.exterior.coords]
        prm = {"poly": poly, "t0": T0, "t1": T1, "srt": icesat2.SRT_LAND, "cnf": icesat2.CNF_SURFACE_HIGH,
               "atl08_class": ["atl08_ground"], "len": 40.0, "res": 20.0, "ats": 5.0, "cnt": 5, "maxi": 5}
        df = icesat2.atl06p(prm)
        if df is None or len(df) == 0:
            _v2.log(f"{r.setor}: sem pontos")
            continue
        df = df[df.geometry.within(terra.buffer(0.001))]
        out = pd.DataFrame({"lon": df.geometry.x.values, "lat": df.geometry.y.values, "h_elip": df.h_mean.values,
                            "h_sigma": df.h_sigma.values, "n_fotons": df.n_fit_photons.values,
                            "data": df.index.astype(str)})
        out = out[(out.h_sigma < 0.5) & (out.n_fotons >= 10)]
        out.to_csv(dest, index=False)
        _v2.log(f"{r.setor}: {len(out):,} pontos de terreno ICESat-2")
