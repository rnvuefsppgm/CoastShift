"""04 — MapBiomas Brasil, cobertura e uso da terra 30 m, via API pública da plataforma
(https://plataforma.brasil.mapbiomas.org/api/docs): POST /maps/export (território Estado da Bahia) →
GET /maps/exports/{id} → /download?kind=tif (URL assinada). Coleção vigente na plataforma (Coleção 11 em 2026).
Classes usadas pelo O2: 5 mangue, 32 apicum (hipersalino), 23 praia/duna/areal, 24 urbano, 33 rio/lago/oceano,
3 floresta, 15 pastagem, 49 restinga arbórea, 50 restinga herbácea, 11 área úmida, 31 aquicultura.
Saídas: <BASE>/raw/mapbiomas/mapbiomas_bahia_<ano>.tif e <BASE>/lulc/landcover_<setor>.tif (vizinho mais próximo).
Uso: python 04_mapbiomas_lulc.py [ano]
"""
import sys
import time
import _v2

API = "https://plataforma.brasil.mapbiomas.org/api/v1/brazil"
H = {"tenant-id": "mapbiomas"}
SUBTEMA = "coverage_coverage-30m-droufo"      # "Cobertura 30m" (tema coverage)


def territorio_bahia():
    d = _v2.get_json(f"{API}/territories", {"search": "Bahia", "categoryId": 214, "pageSize": 10}, H)
    return [t for t in d["territories"] if t["name"] == "Bahia"][0]["id"]


def exportar(ano):
    tid = territorio_bahia()
    r = _v2.get_json(f"{API}/maps/export", headers=H, method="POST",
                     body={"territoryId": tid, "subthemeKey": SUBTEMA, "year": [ano], "exportType": "range"})
    ex = (r.get("exports") or [r])[0]
    eid = ex["id"]
    for _ in range(240):                          # até 1 h
        st = ex.get("status", "").upper()
        if st == "READY":
            break
        if st in ("FAILED", "ERROR"):
            raise RuntimeError(f"exportação falhou: {ex}")
        time.sleep(15)
        ex = _v2.get_json(f"{API}/maps/exports/{eid}", headers=H)
    url = f"{API}/maps/exports/{eid}/download?kind=tif"
    return _v2.download(url, _v2.p("raw", "mapbiomas", f"mapbiomas_bahia_{ano}.tif"), headers=H)


if __name__ == "__main__":
    anos = [int(sys.argv[1])] if len(sys.argv) > 1 else [2025, 2024]
    f = None
    for ano in anos:
        try:
            f = exportar(ano)
            _v2.log(f"MapBiomas {ano}: {f}")
            break
        except Exception as e:  # noqa: BLE001
            _v2.log(f"MapBiomas {ano} indisponível: {e}")
    if not f:
        raise SystemExit("MapBiomas: nenhum ano disponível")
    _v2.reprojetar_para_setores([f], "lulc", "landcover", "nearest", dtype="uint8", nodata=0, src_nodata=0)
