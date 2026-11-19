---
title: "Tutorial dos scripts — fluxo V2 do CoastShift (Modelo 2, costa da Bahia)"
subtitle: "Ordem de execução, o que cada script faz, entradas, saídas, tempos e verificações"
---

# 1. Visão geral

O fluxo V2 baixa todas as bases por download direto (sem contas e sem tarefas no Google Earth Engine), monta um pacote de entrada por setor da costa e roda o Modelo 2 (estático probabilístico) com validação, sensibilidade e produtos finais. Os scripts estão em `scripts/`, na mesma numeração e ordem em que foram executados.

| Etapa | Scripts | Resultado | Tempo típico* |
|---|---|---|---|
| 1. Downloads (independentes) | 00 (orquestra), 01–14 | `dados_bahia_v2/` (~2,1 GB) | 45–60 min |
| 2. Pacotes do modelo | 20 | `dados_bahia_v2/pacotes/<setor>/` | 3–5 min |
| 3. Modelo 2 e áreas (ha) | 21 | `resultados_O2_Bahia/geotiff`, `tabelas` | ~60 min (N = 500, 16 combinações) |
| 4. Mapas Q1 | 22 | `resultados_O2_Bahia/mapas` | 20–30 min (600 dpi) |
| 5. Validação e sensibilidade | 23, 24, 25, 25b, 25c, 28 | `validacao/`, `sensibilidade/` | 1–1,5 h |
| 6. Produtos e gráficos de síntese | 26, 27 | `graficos/`, `tabelas/` | 5 min |

\*Computador com 20 núcleos e 64 GB de RAM; os scripts 21 e 24 usam 10 processos em paralelo.

**Fluxograma completo:** `../01_artigo/figuras/Fig_fluxograma_pt.png`.

# 2. Preparação (uma vez)

1. Instale o Python 3.10+ e as dependências:

```bash
pip install -r requirements.txt
pip install netCDF4 h5netcdf sliderule pystac-client planetary-computer scikit-image imageio-ffmpeg
```

2. Clone o repositório com a biblioteca `coastshift`:

```bash
git clone https://github.com/rnvuefsppgm/CoastShift.git
```

3. Os scripts ficam em `CoastShift/scripts_v2/`. Para rodar esta cópia da pasta de entrega, informe onde está o repositório:

```bash
set COASTSHIFT_REPO=C:\caminho\para\CoastShift
```

4. Pastas de trabalho (opcionais; o padrão é ao lado do repositório):

```bash
set COASTSHIFT_V2_BASE=D:\dados_bahia_v2
set COASTSHIFT_RESULTADOS=D:\resultados_O2_Bahia
```

`_v2.py` é o módulo comum (não se executa): área de estudo, setores S1–S6, download com retomada, reprojeção para EPSG:31984 a 30 m, séries de maré e ajuste harmônico. Todo script o importa.

# 3. Etapa 1 — downloads (scripts 00–14)

Cada script é **independente**: pode ser rodado sozinho, em qualquer ordem, e cria a zona costeira se ela ainda não existir. O orquestrador roda todos, 4 em paralelo, e continua mesmo se um falhar:

```bash
python 00_baixar_tudo.py              # todos
python 00_baixar_tudo.py --so 04,11   # só alguns
```

Resumo em `dados_bahia_v2/logs/status_downloads.json`; log detalhado por script em `logs/`.

| Script | O que faz | Fonte (acesso) | Saída principal | Como conferir |
|---|---|---|---|---|
| **01_area_costa_bahia** | Constrói a zona costeira: faixa terrestre de 15 km + faixa marinha de 5 km a partir da linha de costa do IBGE; recorta os setores S1–S6 | API de malhas do IBGE | `aoi/*.geojson` | 17.549 km²; áreas por setor no log |
| **02_dem_copernicus_glo30** | Baixa os blocos 1°×1° do Copernicus GLO-30 e reprojeta por setor (bilinear) | AWS Open Data | `dem/dem_cop30_egm08_<setor>.tif` | 100% da zona com dado |
| **03_dem_fabdem** | Baixa o bloco 10°×10° do FABDEM V1-2 e lê os tiles direto do zip | Univ. de Bristol | `dem/dem_fabdem_egm08_<setor>.tif` | idem; licença não comercial |
| **04_mapbiomas_lulc** | Pede a exportação do Estado da Bahia pela API da plataforma, espera ficar pronta e baixa o GeoTIFF; reprojeta (vizinho mais próximo) | API MapBiomas (`/maps/export`) | `lulc/landcover_<setor>.tif` | ano 2025; ~75% da zona (o mar não tem classe) |
| **05_agua_jrc_gsw** | Ocorrência de água 1984–2021 | JRC GSW (nuvem pública) | `agua/gsw_ocorrencia_<setor>.tif` | 0–100 % |
| **06_populacao_ghs_pop** | População 2025, convertida para pessoas por célula de 30 m preservando o total | servidor do JRC | `exposicao/pop_<setor>.tif` | total no log (~4,65 milhões) |
| **07_edificacoes_ms_buildings** | Baixa as partições (quadkeys) da Microsoft que tocam a zona e conta edificações por célula | Microsoft Building Footprints | `exposicao/buildings_<setor>.tif` | ~0,65 milhão |
| **08_projecoes_ar6** | Extrai do zip de 9,2 GB do Zenodo, por leitura parcial (HTTP Range), só os 5 arquivos `total_<ssp>` (~75 MB cada) e pega o ponto AR6 mais próximo de cada setor | Zenodo (IPCC AR6) | `ar6/ar6_setores.json` | SSP5-8.5 2100 ≈ 0,78 m |
| **09_mares_niveis_referencia** | Série horária de Salvador (UHSLC 708), ajuste harmônico, NMM, MHHW, MHWS, tendência; transfere aos setores pela razão M2+S2 de um modelo global | UHSLC + Open-Meteo Marine | `mares/mares_salvador.json`, `mares_setores.json` | MHWS Salvador 1,10 m |
| **10_extremos_pot_gpd** | Extremos POT-GPD (limiar p99, *declustering* de 72 h), bootstrap e retroteste | UHSLC 708 | `mares/extremos_salvador.json` | TR100 ≈ 1,62 m |
| **11_ondas_era5** | Ondas ERA5 1995–2024 no ponto ao largo de cada setor; Hs99, Tp e *setup* de Stockdon | Open-Meteo Marine (`era5_ocean`) | `ondas/ondas_setores.json` | *setup* 0,16–0,28 m |
| **12_icesat2_pontos_sliderule** | Pontos de terreno ICESat-2 (fótons ATL08 "ground") 2019–2025 por setor | SlideRule (público) | `icesat2/atl08_ground_<setor>.csv` | 160–295 mil pontos por setor |
| **13_geoide_egm08_hgeohnor** | Recorta o EGM2008 e lê a grade hgeoHNOR2020 (datum Imbituba) do IBGE | PROJ CDN + IBGE | `geoide/*.tif` | valores entre −15 e −5 m |
| **14_rmpg_ibge_salvador** | Baixa a série oficial da RMPG e a ficha de níveis; calcula o NMM de Salvador no SGB = média das leituras − K₁ | geoftp do IBGE | `mares/nmm_salvador_sgb.json` | 0,541 ± 0,090 m |

Dicas: se uma API responder 429 (limite de requisições), o módulo espera e repete; para refazer um item, apague o arquivo de saída e rode de novo só aquele script.

# 4. Etapa 2 — pacotes do Modelo 2 (script 20)

```bash
python 20_montar_pacotes_O2.py --dem fabdem
python 20_montar_pacotes_O2.py --dem cop30 --saida D:\dados_bahia_v2\pacotes_cop30   # para a sensibilidade
```

O que faz, por setor:

1. Converte o DEM: h = H + N(EGM2008) → Hₙ = h − η(hgeoHNOR2020) → z = Hₙ − NMM_SGB (lido do script 14).
2. Cria a máscara do mar: faixa marinha da zona ∪ água JRC ≥ 50 % conectada a ela; o DEM fica sem dado no mar.
3. Copia cobertura, população e edificações na mesma grade.
4. Converte os pontos ICESat-2 para o mesmo datum e calcula o viés e o desvio-padrão do erro do DEM por classe MapBiomas.
5. Escreve `params.json` com maré, extremos (escalados pela razão de maré), ondas, AR6 e erro do DEM.

Conferir: `pacotes/resumo_pacotes.csv` (viés, NMAD, RMSE do DEM por setor) e a lista `avisos` em cada `params.json` (deve estar vazia).

# 5. Etapa 3 — Modelo 2 em lote e áreas em hectares (script 21)

```bash
python 21_rodar_O2_resultados.py                        # padrão: 5 SSPs × 2030/2050/2100 + Atual, N = 500, MHWS
python 21_rodar_O2_resultados.py --ref NMM --ssps ssp245,ssp585 --anos 2050,2100 --n 300   # inundação permanente
python 21_rodar_O2_resultados.py --tr 100 --ssps ssp245,ssp585 --anos 2050,2100 --n 300   # episódica, TR 100 anos
```

Use `COASTSHIFT_RESULTADOS` para gravar cada variante numa pasta própria (foi assim que se geraram `episodico_NMM`, `episodico_TR10`, `episodico_TR100` e `horizonte_2150`).

O que faz: divide as N realizações em blocos (setor × 50 realizações, sementes registradas) e roda em 10 processos. Em cada realização sorteia uma única vez o quantil do AR6, o nível de referência e o campo de erro do DEM, e avalia o bathtub conectado para todas as combinações. Depois reclassifica a probabilidade nas classes IPCC (0: < 0,05; 1: 0,05–0,33; 2: 0,33–0,66; 3: 0,66–0,90; 4: ≥ 0,90) e calcula as áreas.

Saídas: `geotiff/prob_*.tif` e `classe_*.tif`; `tabelas/areas_por_classe_ha.csv`, `exposicao_O2.csv`, `resultados_O2_Bahia.xlsx` (inclui `TOTAL_COSTA_BAHIA`) e `metadados_execucao.json`.

# 6. Etapa 4 — mapas finais (script 22)

```bash
python 22_mapas_O2_Q1.py                       # todas as figuras
python 22_mapas_O2_Q1.py --so setores,areas    # só algumas
python 22_mapas_O2_Q1.py --amostra S2          # amostra para validar o layout
```

Gera, em 600 dpi + PDF: um mapa da costa por combinação (painel lateral com localização, legenda e áreas), painéis da costa por horizonte (5 SSPs), painéis por setor (Atual + cenários-chave) e o gráfico de áreas por classe.

# 7. Etapa 5 — validação, sensibilidade e verificação estrutural

| Script | O que faz | Saídas |
|---|---|---|
| **23_validacao_dem_icesat2** | Separa 30 % das passagens ICESat-2 (por data) para teste; calibra o viés por classe nos 70 % e avalia o erro bruto e o corrigido nos 30 %; ajusta o variograma gaussiano dos resíduos ao longo do traço para estimar ℓ | `validacao/dem_retencao_por_classe.csv`, `variograma.csv`, `resumo_dem.json` |
| **24_sensibilidade_convergencia** | Roda o O2 (N = 100, sementes pareadas) trocando um fator por vez: DEM Copernicus, conectividade 4, ℓ = 150/600 m, VLM ±1 mm/ano, amplificação da maré 0,9/1,1 (S2); e compara N = 250 com o resultado de N = 500 | `sensibilidade/sensibilidade.csv`, `convergencia.csv` |
| **25_validacao_sentinel2** | Validação secundária com cenas únicas do Sentinel-2 na maré mais alta disponível, rodando o O2 no nível observado da cena | `validacao/sentinel2_cena_unica_metricas.csv` |
| **25b_validacao_intermare_sentinel2** | Validação principal: pares de preamar e baixa-mar; água da maré = água na preamar e não na baixa-mar; modelo = p(nível alto) − p(nível baixo) com as mesmas sementes; CSI, HR, FAR, Brier, confiabilidade | `validacao/intermare_metricas.csv`, `intermare_confiabilidade.csv`, `intermare_<setor>.tif` |
| **25c_validacao_intermare_sentinel1** | **Validação principal por radar**: pares Sentinel-1 de preamar e baixa-mar na mesma órbita (cobertura ≥ 60 % do setor), água = γ⁰ VV < −17 dB; O2 nos dois níveis observados com as mesmas sementes; CSI, HR, FAR, Brier, confiabilidade. Motivo: o Sentinel-2 (12:50 UTC) nunca registra a preamar de sizígia na Bahia | `validacao/s1_intermare_metricas.csv`, `s1_intermare_confiabilidade.csv`, `s1_intermare_<setor>.tif` |
| **28_comparacao_O3_O2_salvador** | Compara O1, O2 e O3 (hidrodinâmico inercial) no subdomínio Itapagipe–Comércio, mesmo DEM e mesmo nível | `validacao/O3_O2_salvador.csv`, `graficos/Fig_O1_O2_O3_Salvador.*` |

# 8. Etapa 6 — produtos complementares e síntese

```bash
python 26_produtos_complementares.py
python 27_graficos_sintese.py
```

- **26**: tabela por município (malha IBGE), mapa de inundação adicional (já hoje / nova até 2050 / nova até 2100), exposição por setor com intervalos e mapas de incerteza (erro-padrão e concordância FABDEM × Copernicus).
- **27**: gráficos de validação do DEM e da maré, sensibilidade (tornado), convergência, comparação entre níveis de referência e trajetória da área até 2150; `tabelas/sintese_validacao.json`.

# 9. Lote de qualquer modelo (script 29)

```bash
python 29_lote_modelos.py --modelos O1,O2 --setores S1,S2 --ssps ssp245,ssp585 --anos 2050,2100 --n 300
python 29_lote_modelos.py --modelos O3,O5 --setores S2 --bbox -38.535,-12.985,-38.455,-12.900 --coarsen 1
```

Roda O1–O5 sem interface; O3 e O5 exigem subdomínio (`--bbox`). Detalhes em `05_tutorial_aplicacao`.

# 10. Ferramentas

- `ferramentas/fluxograma.py <pasta>` — fluxograma do processamento (EN/PT; PNG, PDF, SVG).
- `ferramentas/gravar_video_app.py` — vídeo narrado do aplicativo (voz do Windows + ffmpeg).
- `ferramentas/apresentacao.py` — gera a apresentação (.pptx).
- `ferramentas/montar_entregas.py` — monta artigo, suplementar, documento metodológico e apresentação.

# 11. Problemas comuns

| Sintoma | Causa | Solução |
|---|---|---|
| `429 Too Many Requests` | limite da Open-Meteo | o script espera e repete; rode de novo só o 09 ou o 11 |
| Erro de leitura de bloco do Sentinel-2 | falha transitória de rede | há novas tentativas automáticas; cenas inacessíveis são ignoradas e registradas no log |
| Aviso "η hgeoHNOR2020 incoerente" | grade não lida | rode o 13 de novo; o 20 usa N(EGM2008) como alternativa e registra o aviso |
| Pacote não abre no aplicativo | rasters em grades diferentes | rode o 20 de novo (nunca edite os .tif à mão) |
| Memória insuficiente no 21/24 | muitos processos | use `--proc 4` no 21 (cada processo usa ~1,5 GB no setor S1) |
