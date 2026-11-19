---
title: "Tutorial do aplicativo CoastShift e execução dos modelos em lote"
subtitle: "Interface gráfica (executável ou código-fonte), modelos O1–O5, validação, exportação e lote sem interface"
---

# 1. O que é o aplicativo

O CoastShift é um aplicativo Python com interface gráfica para modelar a elevação do nível do mar e a inundação costeira a partir de um **pacote de entrada** por setor (relevo no nível médio local, cobertura da terra, máscara do mar, população, edificações e `params.json`). Os pacotes da costa da Bahia são gerados pelo fluxo V2 (`dados_bahia_v2/pacotes/<setor>`).

Código e executável: **https://github.com/rnvuefsppgm/CoastShift** (licença GPL-3.0).

| Modelo | Tipo | Quando usar | Saídas |
|---|---|---|---|
| O1 | Bathtub hidraulicamente conectado | triagem rápida, cenários determinísticos | inundado, profundidade, áreas desconectadas |
| **O2** | **Estático probabilístico (Monte Carlo)** — modelo do estudo | mapas de probabilidade e exposição com incerteza | probabilidade, erro-padrão, exposição (média, p05, p95) |
| O3 | Hidrodinâmico 2D (inercial local) | subdomínios urbanos/estuarinos | profundidade máxima, tempo de chegada, duração |
| O4 | Linha de costa (Bruun) + habitats | praias e manguezais | recuo, erosão, mangue/apicum potencial |
| O5 | Integrado (biblioteca O3 + emulador + danos) | dano esperado anual (EAD) | EAD, probabilidade anual |

# 2. Instalação

**Executável (Windows 10/11, 64 bits):** baixe `executavel/CoastShift.exe` do repositório (Git LFS) ou use `Ana_Model/CoastShift_Local/CoastShift.exe`. Dois cliques; a primeira abertura leva 10–30 s. Teste sem interface:

```bash
CoastShift.exe --selftest
```

**Código-fonte:**

```bash
git clone https://github.com/rnvuefsppgm/CoastShift.git
cd CoastShift
pip install -r requirements.txt
python app.py
```

# 3. Uso da interface — passo a passo com os dados da Bahia

1. **Aba 1 Dados → Abrir pacote…** e escolha `dados_bahia_v2/pacotes/S2_Salvador_BTS` (ou outro setor). O resumo mostra a grade (30 m, EPSG:31984), as camadas e os cenários AR6 disponíveis.
2. **Aba 4 Parâmetros**: confira níveis de maré (MHWS, MHHW), extremos (POT-GPD), ondas, AR6 e `dem_error` (viés e desvio por classe MapBiomas, calibrados com o ICESat-2). Edite e use **Aplicar e salvar** se precisar.
3. **Aba 2 Modelo**, para o Modelo 2:

| Campo | Valor recomendado | Justificativa |
|---|---|---|
| Modelo | O2 – Estático probabilístico | modelo do estudo |
| Cenários AR6 | SSP1-2.6, SSP2-4.5, SSP5-8.5 (ou os 5) | cobre a faixa do AR6 |
| Horizontes | 2030, 2050, 2100 | curto, médio e longo prazo |
| Nível de referência | MHWS | inundação recorrente (preamar de sizígia) |
| Tempo de retorno | 0 (maré) ou 10/100 (episódico) | separa recorrente de episódico |
| Setup de ondas | marcado só em S1, S4, S5, S6 | costa aberta |
| Conectividade | 8 | teste de sensibilidade com 4 |
| Realizações | 500 (resultado final); 50 para explorar | erro-padrão máximo 0,022 com N = 500 |
| Semente | fixa (ex.: 42) | reprodutibilidade |

4. **▶ Executar modelo**: roda em segundo plano; a barra mostra o progresso e a aba **Log** os detalhes.
5. **Mapa e tabela**: escolha a camada (`[O2] probabilidade_ssp585_2100`, `[O2] erro_padrao_MC_…`); a tabela mostra área, população, edificações e mangue (média, p05, p95).
6. **Aba 3 Validação**:
   - **A) DEM com pontos** → `validacao_pontos_dem.csv` do pacote (ICESat-2): viés, MAE, RMSE, NMAD, LE90 por classe. Desmarque "Aplicar viés/dp" se não quiser alterar o `params.json`.
   - **B) Mancha observada** → GeoTIFF 0/1 na grade do pacote (por exemplo `validacao/intermare_<setor>.tif` reclassificado, ou uma máscara Sentinel/Defesa Civil): CSI, acerto, falso alarme, Brier.
   - **C) Série observada × modelada** → CSV com colunas `obs, mod`.
7. **Exportar resultados…**: um GeoTIFF por camada, `tabela.csv` e `metadados.json` (modelo, opções, parâmetros e versão).

**Vídeo demonstrativo narrado:** `Ana_Model/video_app/CoastShift_demo_Modelo2_Bahia.mp4`.

# 4. Execução em lote (sem interface)

## 4.1 Modelo 2 para toda a costa, com áreas em hectares e mapas

```bash
cd CoastShift/scripts_v2
python 21_rodar_O2_resultados.py --n 500                 # 5 SSPs × 2030/2050/2100 + Atual (MHWS)
python 22_mapas_O2_Q1.py                                  # mapas 600 dpi + PDF
```

Variantes (cada uma numa pasta própria com `COASTSHIFT_RESULTADOS`):

```bash
set COASTSHIFT_RESULTADOS=D:\resultados_O2_Bahia\episodico_TR100
python 21_rodar_O2_resultados.py --tr 100 --ssps ssp245,ssp585 --anos 2050,2100 --n 300
python 22_mapas_O2_Q1.py --so costa,paineis,setores
```

| Opção do script 21 | Significado |
|---|---|
| `--n` | realizações de Monte Carlo (padrão 500) |
| `--ssps`, `--anos` | cenários e horizontes |
| `--ref` | `MHWS`, `MHHW` ou `NMM` |
| `--tr` | tempo de retorno do nível extremo (0 = maré) |
| `--sem-atual` | não calcula a linha de base atual |
| `--proc`, `--bloco` | processos paralelos e realizações por bloco |

## 4.2 Qualquer modelo O1–O5 (script 29)

```bash
python 29_lote_modelos.py --modelos O1,O2 --setores S1,S2 --ssps ssp245,ssp585 --anos 2050,2100 --n 300
python 29_lote_modelos.py --modelos O4 --setores S3,S6 --anos 2100
python 29_lote_modelos.py --modelos O3,O5 --setores S2 --bbox -38.535,-12.985,-38.455,-12.900 --coarsen 1
```

O3 e O5 (hidrodinâmicos) exigem um subdomínio (`--bbox` em lon/lat); o script recorta o pacote automaticamente. Saídas em `resultados/lote/<modelo>/<setor>/` (GeoTIFFs, `tabela.csv`, `meta.json`) e `lote/resumo_lote.csv`.

## 4.3 Pela biblioteca Python

```python
import sys; sys.path.insert(0, r"C:\caminho\CoastShift")
from coastshift import io, models

pk = io.Package(r"D:\dados_bahia_v2\pacotes\S2_Salvador_BTS")
opt = {"ssps": ["ssp245", "ssp585"], "years": [2050, 2100], "ref": "MHWS", "tr": 0,
       "setup": False, "conn": 8, "n": 500, "seed": 42}
res = models.RUNNERS["O2"](pk, opt)
print(res.table)
io.write_raster("prob_ssp585_2100.tif", res.layers["probabilidade_ssp585_2100"], pk.profile)
```

Para paralelizar como o script 21: `models.o2_realizacoes(pk, opt, n, seed)` devolve as contagens e as exposições de um bloco; some os blocos e chame `models.o2_resultado(pk, opt, contagens, totais, n_total)`.

# 5. Tempo de execução de referência (20 núcleos, 64 GB)

| Tarefa | Tempo |
|---|---|
| O2 num setor pela interface, N = 200, 6 combinações | 3–15 min |
| Script 21, costa toda, N = 500, 16 combinações, 10 processos | ~60 min |
| Script 22, todas as figuras a 600 dpi | 20–30 min |
| O3 no subdomínio de Salvador (13 h simuladas, 30 m) | ~4 min |

# 6. Problemas comuns

| Sintoma | Solução |
|---|---|
| "X.tif não está alinhado ao dem.tif" | refaça o pacote com o script 20 |
| O2 lento | reduza N para explorar; use o script 21 (paralelo) para o resultado final |
| O3 com profundidades irreais | use a versão ≥ 1.0.1 (passo de tempo CFL corrigido para todo o domínio) |
| Memória insuficiente | `--proc 4` no script 21; recorte subdomínios |
