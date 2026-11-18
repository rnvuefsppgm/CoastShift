# Inventário geoespacial — aplicação à costa da Bahia (Produto 3, extensão regional)

As bases globais já documentadas (D01–D32) estão na aba **Bases** da planilha; aqui aparecem (a) as **novas** bases brasileiras/baianas (D33+) e (b) a indicação de **quais D01–D32 usar na Bahia**. Confira sempre versão, datum e licença no arquivo efetivamente baixado. Rótulos: `[V]` verificado · `[C]` consolidado, não reconsultado · `[NV]` conferir.

## A. Bases globais já inventariadas — uso recomendado na Bahia

| Uso | IDs da planilha | Observação para a Bahia |
|---|---|---|
| Projeção RSL | D01 (AR6), D02 (NASA tool) | Extrair ponto de grade 1° por setor; não usar D03 (NOAA) como fonte primária — cenários desenhados para os EUA |
| Maré | D09 (FES2022) | Validar contra DHN/RMPG; FES tende a ser melhor em costa aberta que no interior da BTS `[I]` |
| Extremos | D08 (C3S/GTSM), D07 (ERA5) | GTSM sem ondas; ERA5 para vento/pressão de frentes frias e ondas offshore |
| Altimetria | D04 (DUACS), D10 (SWOT) | SWOT útil para gradientes de nível em estuários largos (BTS, Camamu) `[I]` |
| DEM | D12 (Copernicus), D14 (FABDEM), D32 (DeltaDTM), D11 (SRTM) | Usar em conjunto com ANADEM (D33) para ensemble de erro vertical |
| Batimetria | D15 (GEBCO) + D18 (DHN) | GEBCO apenas na plataforma externa; cartas DHN dentro de baías |
| VLM | D20 (SONEL), D21 (Sentinel-1) | Poucas estações GNSS costeiras na Bahia; InSAR exige processamento próprio |
| Cobertura/habitat | D27 (MapBiomas 10.1), D24 (GMW v3), D22 (Sentinel-2), D23 (WorldCover) | MapBiomas tem classes costeiras (mangue, apicum, praia/duna) — preferir para Bahia |
| População | D25 (WorldPop), D28 (GHS-POP), D30 (SSP pop.) | Preferir Censo 2022 (D39) para presente; D30 para futuro por SSP |
| Infraestrutura | D26 (OSM) | Completar com Open Buildings (D40) |
| Hidrologia | D31 (HidroWeb) | Vazões de Paraguaçu, Jequitinhonha, Pardo, Contas, Jaguaripe |
| Características costeiras | D29 (GCC Deltares) | Triagem; resolução grosseira para municípios |

## B. Novas bases (Brasil/Bahia)

| ID | Base | Instituição | Variáveis | Escala | Resolução | Período | Formato | Acesso | URL | Aplicação | Limitações | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D33 | ANADEM v1 – MDT da América do Sul | ANA / IPH-UFRGS | Terreno (viés de vegetação removido do Copernicus GLO-30 por ML com GEDI) | Continental | 30 m | Base COPDEM (2011–2015) | GeoTIFF (tiles MGRS); asset GEE | Gratuito | https://www.ufrgs.br/hge/anadem-modelo-digital-de-terreno-mdt/ | Bathtub, SFINCS, triagem | Viés médio reduzido de 9,6 m (COPDEM) para 1,5 m na validação dos autores; desempenho urbano e em mangue a testar localmente | [V] |
| D34 | TOPODATA | INPE | SRTM refinado + derivadas (declividade etc.) | Nacional | 1″ (~30 m) | 2000 | GeoTIFF | Gratuito | http://www.dsr.inpe.br/topodata/ | Comparação/ensemble DEM | Herda erros SRTM (DSM, EGM96, banda C) | [C] |
| D35 | hgeoHNOR2020 | IBGE | Fator η (h → altitude normal) e desvio-padrão | Nacional | Grade (ver relatório) | Rel. metodológico 2ª ed. 2023 | Grade + aplicativo | Gratuito | https://www.ibge.gov.br/geociencias/modelos-digitais-de-superficie/modelos-digitais-de-superficie/31312-modelo-de-conversao-de-altitudes.html | Harmonização vertical de DEM/LiDAR/GNSS | Não é geoide gravimétrico; diferença p/ MAPGEO2015 < 50 cm na maior parte do país | [V] |
| D36 | Marégrafo de Salvador (RMPG/IBGE; GLOSS) | IBGE | Nível do mar horário/alta frequência, ligação a RN | Local | Pontual; minutos/hora | 2004–2024 analisado por Lessa et al. | TXT/CSV | Gratuito (portal IBGE) | https://www.ibge.gov.br/geociencias/informacoes-sobre-posicionamento-geodesico/rede-geodesica/10862-rmpg-rede-maregrafica-permanente-para-geodesia.html | Linha de base, extremos (POT-GPD), validação de modelos | Série curta para tendência; lacunas | [V] série / [NV] URL exata |
| D37 | Tábuas de marés e catálogo de estações | Marinha – CHM/DHN; FEMAR | Constantes harmônicas, NR, Z0, previsões | Estações (Salvador, Aratu, Madre de Deus, Ilhéus, Porto Seguro etc.) | Pontual | Variável por estação | PDF/HTML; constantes por solicitação | Gratuito/solicitação | https://www.marinha.mil.br/chm/tabuas-de-mare | Nível de preamar por setor; validar FES2022 | Ligação ao SGB nem sempre publicada | [C] |
| D38 | Cartas náuticas e BNDO | Marinha – DHN/CHM | Sondagens, linha de costa náutica, NR | Baías e acessos portuários | 1:5.000 a 1:300.000 | Levantamentos de várias épocas | Raster/ENC; dados BNDO por solicitação | Gratuito/restrito por produto | https://www.marinha.mil.br/chm/ | Batimetria da BTS, Camamu, Ilhéus | Datum NR; épocas antigas; densidade variável | [C] |
| D39 | Censo 2022 – setores e Grade Estatística | IBGE | População, domicílios | Nacional | Setor censitário; grade 200 m (urbano)/1 km | 2022 | SHP/GPKG/CSV | Gratuito | https://www.ibge.gov.br/estatisticas/sociais/populacao/22827-censo-demografico-2022.html | Exposição atual | Grade 2022: conferir disponibilidade/resolução final `[NV]` | [C] |
| D40 | Google Open Buildings v3 | Google Research | Polígonos de edificações + confiança | América Latina incl. Brasil | Edificação | ~2022–2023 | CSV/GeoJSON; GEE | Gratuito (CC BY 4.0 / ODbL) | https://sites.research.google/open-buildings/ | Exposição de edificações, rugosidade urbana | Omissões em áreas densas/informais; sem altura em v3 | [C] |
| D41 | Base cartográfica SEI (1:100.000) e nova base 1:25.000/1:50.000 (SEIGEO) | SEI-BA | Hidrografia, sistema viário, limites, toponímia | Estadual | 1:100.000; 1:25.000–1:50.000 em produção | 2008; atualização 2020s | SHP/WMS | Gratuito (portal SEI) | https://www.ba.gov.br/sei | Máscaras de água, vias, sementes de conectividade | Cobertura da nova base ainda parcial | [V] |
| D42 | MDE de Salvador (SEI/PMS) | SEI / Prefeitura de Salvador | Elevação (resolução altimétrica 1,8 m citada pelo SGB) | Municipal | Ver metadados | 2010 | Raster | A confirmar | https://rigeo.sgb.gov.br/ (mapa de Salvador cita a fonte) | Teste local vs DEM global | Precisão vertical insuficiente para SLR < 1 m `[I]` | [V] menção / [NV] acesso |
| D43 | Aerolevantamentos CONDER (RMS) / PMS | CONDER-BA; Prefeitura de Salvador | Ortofotos, restituição, curvas/MDT | RMS/Salvador | 1:2.000–1:10.000 | 2009–2010 e posteriores | Vetorial/raster | Solicitação | https://www.conder.ba.gov.br | DEM urbano de alta resolução (S2) | Disponibilidade e licença | [NV] |
| D44 | GeoSGB – geologia, geodiversidade, recursos minerais | Serviço Geológico do Brasil | Litologia, Formação Barreiras, depósitos quaternários | Estadual | 1:1.000.000 (Bahia); folhas 1:250.000/1:100.000 | Várias | SHP/WMS | Gratuito | https://geosgb.sgb.gov.br | Erodibilidade, falésias, planícies quaternárias | Escala grosseira para praia | [C] |
| D45 | MapBiomas – Coleção 10.1 (zona costeira) | Rede MapBiomas | Mangue, apicum, praia/duna, água, urbano (anual) | Nacional | 30 m | 1985–2024 | GeoTIFF; GEE | Gratuito (CC BY) | https://brasil.mapbiomas.org | Habitats, transições, exposição de ecossistemas | Mistura espectral em franjas de mangue | [V] (D27) |
| D46 | Atlas dos Manguezais do Brasil | ICMBio | Extensão de manguezais, UCs | Nacional | ~1:50.000 equiv. | 2018 | SHP/PDF | Gratuito | https://www.gov.br/icmbio | Validação de mangue | Estático | [C] |
| D47 | SMC-Brasil (GOW, GOT, GOS) | IH Cantabria / MMA | Reanálise de ondas (~60 anos, 1948–2008), maré e maré meteorológica downscaled | Costa brasileira | Pontos/malhas costeiras | 1948–2008 | Acesso só pelo software SMC | Gratuito (software); **dados brutos não exportáveis** | https://smcbrasil.ihcantabria.com | Clima de ondas nearshore, runup, transporte | Dados de propriedade do IH Cantabria; série encerra em 2008 | [V] |
| D48 | WAVERYS – Global Ocean Waves Reanalysis | Copernicus Marine | Hs, Tp, Dir espectrais | Global | 0,2°; 3 h | 1993–presente | NetCDF | Gratuito (cadastro) | https://data.marine.copernicus.eu | Ondas offshore p/ SWAN/XBeach/runup | Resolução offshore; propagar até a costa | [C] |
| D49 | RBMC – estações GNSS (ex.: SSA1 Salvador) | IBGE | Coordenadas, séries diárias | Estações | Pontual | 1990s–presente | RINEX | Gratuito | https://www.ibge.gov.br/geociencias/informacoes-sobre-posicionamento-geodesico/rede-geodesica/16258-rede-brasileira-de-monitoramento-continuo-dos-sistemas-gnss-rbmc.html | VLM (taxas verticais) | Poucas estações na orla; séries com saltos | [C] |
| D50 | NGL – séries GNSS processadas (MIDAS) | Nevada Geodetic Laboratory | Velocidades verticais | Global | Pontual | Variável | TXT | Gratuito | http://geodesy.unr.edu | VLM rápido sem processar RINEX | Referencial IGS; comparar com SONEL (D20) | [C] |
| D51 | ICESat-2 ATL08/ATL03 | NASA / NSIDC | Elevação de terreno e dossel (fótons) | Global | Perfis ~100 m (ATL08) | 2018–presente | HDF5 | Gratuito (Earthdata) | https://nsidc.org/data/icesat-2 | **Validação independente de DEMs** na costa baiana | Faixas espaçadas; filtrar qualidade | [C] |
| D52 | ASF HyP3 / Sentinel-1 InSAR sob demanda | Alaska Satellite Facility | Interferogramas, deslocamento LOS | Por cena | ~20–80 m | 2014–presente | GeoTIFF | Gratuito (Earthdata) | https://hyp3-docs.asf.alaska.edu | VLM em Salvador/Ilhéus; mapear inundações observadas | Coerência baixa em mangue/vegetação | [C] |
| D53 | JRC Global Surface Water | JRC / Google | Ocorrência e transições de água | Global | 30 m | 1984–2021+ | GeoTIFF; GEE | Gratuito | https://global-surface-water.appspot.com | Máscara de água permanente, sementes | Mudanças de maré confundem ocorrência | [C] |
| D54 | ANA – BHO (hidrografia ottocodificada) e estações | ANA | Rede hidrográfica, bacias | Nacional | 1:250.000 / 1:100.000 | Atual | GPKG/SHP | Gratuito | https://metadados.snirh.gov.br | Contornos fluviais, foz | Escala | [C] |
| D55 | Panorama da Erosão Costeira no Brasil (cap. Bahia) | MMA (org. D. Muehe) | Diagnóstico de erosão por trecho | Estadual | Descritivo/mapas | 2018 | PDF | Gratuito | https://www.gov.br/mma | Seleção de hotspots e validação qualitativa | Não é série quantitativa | [C] |
| D56 | Climate Central – Coastal Risk Screening Tool | Climate Central | Mapas de exposição (CoastalDEM) por cenário | Global | ~90 m (visualização) | Cenários até 2150 | Web | Gratuito (visualização) | https://coastal.climatecentral.org | Comunicação e comparação grosseira | **Visualizador**, não método reprodutível; CoastalDEM sob licença | [V] menção |
| D57 | AdaptaBrasil MCTI | MCTI / RNP / INPE | Índices de risco climático por município/setor | Nacional | Municipal | Cenários atuais/futuros | Web/CSV | Gratuito | https://adaptabrasil.mcti.gov.br | Contexto de vulnerabilidade social | Conferir se há indicador de SLR/zona costeira `[NV]` | [NV] |

## C. Prioridade de aquisição para a Bahia `[I]`

1. **D01/D02 + D36 + D37 + D35** — sem isso não há referência de água nem datum (custo: dias).
2. **D33 + D14 + D32 + D51** — ensemble de DEMs com validação ICESat-2 (custo: dias; GEE reduz download).
3. **D45 + D39 + D40** — exposição e habitats (custo: horas em GEE).
4. **D38 + D15 + D09 + D08 + D48** — só se for usar hidrodinâmica (Opções 3–5).
5. **D43/D42 e LiDAR novo** — essenciais para projeto em Salvador; solicitar cedo (prazo institucional).
