"""01 — Zona costeira da Bahia e setores S1–S6 (malhas do IBGE, API pública).
Saídas: <BASE>/aoi/aoi_costa_bahia.geojson, setores_costa_bahia.geojson, linha_costa_bahia.geojson, ibge_bahia.geojson
Zona = faixa terrestre de 15 km + faixa marinha de 5 km a partir da linha de costa do IBGE (parâmetros em _v2.py).
"""
import _v2

if __name__ == "__main__":
    g, s = _v2.aoi(force=True)
    print(s[["setor", "area_km2", "aberta"]].to_string(index=False))
