# Fluxo V2 — download direto dos dados do Modelo 2 (sem tasks do GEE)

Substitui os scripts 02–09 do fluxo V1 (que exportavam do Google Earth Engine e exigiam contas CDS/Earthdata).
**Nenhum login é necessário.** Limite espacial: zona costeira do Estado da Bahia — faixa terrestre de 15 km e
faixa marinha de 5 km a partir da linha de costa do IBGE — dividida nos setores S1–S6 (EPSG:31984, 30 m).

Cada script de download (01–14) é **independente**: pode ser executado sozinho, em qualquer ordem, e baixa
também a área de estudo se ela ainda não existir. O script 20 monta os pacotes do O2 com o que estiver disponível.

```bash
pip install -r ../requirements.txt netCDF4 h5netcdf sliderule
python 00_baixar_tudo.py            # todos os downloads (4 em paralelo); ou --so 04,09
python 20_montar_pacotes_O2.py --dem fabdem --nmm-sgb <NMM de Salvador no SGB, m>
```

Pasta de dados: `Ana_Model/dados_bahia_v2/` (mude com a variável `COASTSHIFT_V2_BASE`). Os pacotes ficam em
`dados_bahia_v2/pacotes/<setor>/` e abrem direto no aplicativo (aba **1 Dados → Abrir pacote**).

## Variáveis do O2 e fontes

| # | Script | Variável do O2 | Fonte (acesso) | Saída |
|---|---|---|---|---|
| 01 | `01_area_costa_bahia.py` | Zona costeira e setores | IBGE, API de malhas (estado 29 e país) | `aoi/*.geojson` |
| 02 | `02_dem_copernicus_glo30.py` | DEM (alternativo) | Copernicus GLO-30, AWS Open Data | `dem/dem_cop30_egm08_<setor>.tif` |
| 03 | `03_dem_fabdem.py` | DEM principal (sem prédios/vegetação) | FABDEM V1-2, Univ. Bristol (leitura direta do zip) | `dem/dem_fabdem_egm08_<setor>.tif` |
| 04 | `04_mapbiomas_lulc.py` | Cobertura (classes, erro do DEM, Manning, mangue) | MapBiomas, API da plataforma `/maps/export` (Coleção vigente, 2025) | `lulc/landcover_<setor>.tif` |
| 05 | `05_agua_jrc_gsw.py` | Máscara de água/mar | JRC Global Surface Water v1.4 (GCS) | `agua/gsw_ocorrencia_<setor>.tif` |
| 06 | `06_populacao_ghs_pop.py` | População exposta | GHS-POP R2023A 2025, servidor do JRC | `exposicao/pop_<setor>.tif` |
| 07 | `07_edificacoes_ms_buildings.py` | Edificações expostas | Microsoft Global ML Building Footprints (quadkeys) | `exposicao/buildings_<setor>.tif` |
| 08 | `08_projecoes_ar6.py` | ΔRSL (quantis por SSP e ano) | IPCC AR6, Zenodo (extração parcial do zip por HTTP Range) | `ar6/ar6_setores.json` |
| 09 | `09_mares_niveis_referencia.py` | NMM, MHHW, MHWS por setor; tendência | UHSLC 708 Salvador + Open-Meteo Marine (transferência M2+S2) | `mares/mares_*.json` |
| 10 | `10_extremos_pot_gpd.py` | Extremos POT-GPD (+ erro-padrão, retroteste) | UHSLC 708 Salvador | `mares/extremos_salvador.json` |
| 11 | `11_ondas_era5.py` | Hs, Tp, setup de Stockdon | ERA5 via Open-Meteo Marine (1995–2024) | `ondas/ondas_setores.json` |
| 12 | `12_icesat2_pontos_sliderule.py` | Pontos de referência p/ erro do DEM | ICESat-2 (fótons de terreno ATL08) via SlideRule público | `icesat2/atl08_ground_<setor>.csv` |
| 13 | `13_geoide_egm08_hgeohnor.py` | Conversão vertical | EGM2008 (PROJ CDN) + hgeoHNOR2020 Imbituba (IBGE) | `geoide/*.tif` |
| 14 | `14_rmpg_ibge_salvador.py` | NMM de Salvador no SGB; série oficial | RMPG/IBGE (geoftp) | `raw/rmpg/` |
| 20 | `20_montar_pacotes_O2.py` | Pacote completo do O2 | saídas 02–13 | `pacotes/<setor>/` |

## Diferenças em relação ao V1 e cuidados

- **ANADEM** não tem download automático público; o DEM principal passa a ser o FABDEM (licença CC BY-NC-SA 4.0,
  uso não comercial). Para uso comercial, use `--dem cop30`.
- **Marés dos setores** sem marégrafo: MHHW/MHWS de Salvador × razão das amplitudes M2+S2 de um modelo global
  (Open-Meteo Marine). Substitua pelos valores das Tábuas da DHN quando disponíveis (edite `params.json`).
- **Extremos** transferidos pela mesma razão (hipótese simplificadora; conferir com CoDEC/GTSM).
- **NMM de Salvador no SGB**: leia no relatório baixado pelo script 14 (`raw/rmpg/niveis_referencia_Salvador/`)
  e informe em `--nmm-sgb`. Sem ele, as cotas ficam relativas ao datum de Imbituba e o `params.json` registra o aviso.
- **Edificações**: contagem de polígonos Microsoft (2014–2023). Para a área construída, alternativa GHS-BUILT-S.
- Cada `params.json` tem a lista `avisos` com o que foi aproximado no setor.
