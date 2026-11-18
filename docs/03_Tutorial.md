# Tutorial do CoastShift — como usar cada aplicação

Este tutorial cobre as quatro formas de usar o CoastShift:

| Aplicação | Para quê | Precisa de Python? |
|---|---|---|
| **A. `CoastShift.exe`** | Rodar os modelos O1–O5 e a validação com interface gráfica | Não |
| **B. `app.py`** (código-fonte) | A mesma interface, a partir do código (Windows, Linux, macOS) | Sim |
| **C. Scripts `01`–`13`** (Colab ou local) | Baixar e preparar os dados reais da costa da Bahia e montar os pacotes de entrada | Sim (ou Google Colab) |
| **D. Biblioteca `coastshift`** e lote (`13`) | Rodar modelos por código, em série, sem interface | Sim |

Fluxo completo: **C (scripts 01–11) → pacotes → A/B (aplicativo) ou D (lote) → resultados (GeoTIFF + CSV) → QGIS/ArcGIS.**

As seções citadas como "métodos, §n" estão em [`01_Metodos_Opcao2_Bahia.md`](01_Metodos_Opcao2_Bahia.md). O formato dos pacotes está em [`02_Formato_Pacote.md`](02_Formato_Pacote.md).

---

## 1. Instalação

### 1.1 Executável (Windows 10/11, 64 bits)

1. Baixe `executavel/CoastShift.exe` do repositório (botão *Download raw file*; o arquivo tem ~172 MB e está no Git LFS) ou use a cópia local em `Ana_Model/CoastShift_Local/CoastShift.exe`.
2. Dê dois cliques. A primeira abertura leva 10–30 s (o executável se descompacta numa pasta temporária).
3. Se o Windows SmartScreen avisar "Windows protegeu o computador": **Mais informações → Executar assim mesmo** (o executável não é assinado digitalmente).
4. Não funciona em Windows 7/8 nem em 32 bits.

**Autoteste sem interface** (confirma que os cinco modelos rodam na sua máquina):

```bash
CoastShift.exe --selftest
```

Ele grava `coastshift_selftest.log` na pasta atual, com uma linha `ok` por modelo.

### 1.2 Código-fonte

```bash
git clone https://github.com/rnvuefsppgm/CoastShift.git
cd CoastShift
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Requer Python 3.10 ou superior. No Linux, use `source .venv/bin/activate` e instale o Tk (`sudo apt install python3-tk`). Para clonar com o executável, instale antes o Git LFS (`git lfs install`); sem ele, `executavel/CoastShift.exe` vem como um arquivo-ponteiro de poucos bytes.

Teste rápido da instalação:

```bash
python tests/test_smoke.py
```

### 1.3 Google Colab (para os scripts de dados)

Abra os notebooks de `scripts/notebooks/` no Colab (*Arquivo → Abrir notebook → GitHub* e cole o endereço do repositório). O notebook `01` monta o Google Drive, instala as dependências e clona o repositório em `/content/CoastShift`. Os dados ficam em `MyDrive/CoastShift_Bahia/`.

---

## 2. Primeiro uso em 5 minutos (dados de demonstração)

1. Abra o aplicativo (`CoastShift.exe` ou `python app.py`).
2. Aba **1 Dados → Gerar pacote de DEMONSTRAÇÃO (sintético)…** e escolha uma pasta vazia. É criada uma costa sintética de 200 × 200 células de 30 m (mar a leste, estuário, mangue e área urbana), com `params.json`, pontos de validação e uma mancha "observada".
3. Aba **2 Modelo**: deixe **O2 – Estático probabilístico** selecionado, marque SSP1-2.6, SSP2-4.5 e SSP5-8.5, horizontes `2050,2100`, e clique **▶ Executar modelo**.
4. Quando a barra terminar, escolha no topo do mapa a camada `probabilidade_ssp585_2100`. A tabela abaixo mostra área inundada, população e edificações expostas (média, p05, p95).
5. Aba **3 Validação → B) Validar mancha…** e selecione `observado_inundacao.tif` da pasta de demonstração.
6. **Exportar resultados…** e escolha uma pasta: saem um GeoTIFF por camada, `tabela.csv` e `metadados.json`.

> Os números da demonstração são ilustrativos. Não use para conclusões sobre a Bahia.

---

## 3. A interface, aba por aba

A janela tem um painel à esquerda (abas) e, à direita, o **mapa** (com zoom/pan na barra do Matplotlib), o seletor **Camada**, o botão **Exportar resultados…** e a **tabela** de resultados. A linha de status no rodapé mostra o andamento.

### Aba 1 Dados

| Controle | O que faz |
|---|---|
| **Abrir pacote (pasta com params.json + dem.tif)…** | Carrega um pacote criado pelo script 11 (ou pela demonstração). Confere se todos os rasters estão na mesma grade. |
| **Gerar pacote de DEMONSTRAÇÃO (sintético)…** | Cria e abre um pacote sintético para aprender e testar. |
| Caixa de texto | Resumo do pacote: setor, tamanho da grade, resolução, CRS, camadas presentes, cenários AR6 disponíveis. |

Ao abrir um pacote, o mapa mostra o DEM e a cobertura da terra.

### Aba 2 Modelo

| Campo | Usado por | Significado |
|---|---|---|
| Lista de modelos | todos | O1 a O5; a descrição aparece logo abaixo |
| **Cenários AR6** | todos | SSPs a simular (só os presentes no `params.json` são usados) |
| **Horizontes (anos, vírgula)** | todos | Ex.: `2030,2050,2100,2150` |
| **Quantil ΔRSL (O1/O3/O4)** | O1, O3, O4 | 0,5 = mediana; 0,83 = limite superior "provável"; 0,95 para cenário conservador. O2 e O5 amostram o quantil aleatoriamente |
| **Nível de referência** | O1, O2, O4 | NMM, MHHW (preamar superior média) ou MHWS (preamar de sizígia média). Para inundação recorrente use MHWS |
| **Tempo de retorno (anos; 0 = maré)** | O1, O2, O3 | 0 = só maré + ΔRSL; >0 soma o nível extremo GPD desse tempo de retorno (métodos, §5.3) |
| **Somar setup de ondas (Stockdon)** | O1, O2, O3 | Só em costa aberta exposta (S1, S4, S5, S6); não use dentro da Baía de Todos os Santos ou estuários |
| **Conectividade** | O1, O2, O4 | 8 (diagonais contam) ou 4 (mais conservador para diques/aterros estreitos) |
| **Realizações Monte Carlo (O2/O5)** | O2, O5 | 200 para explorar; 500–1000 para o resultado final (erro-padrão < 0,02) |
| **Duração simulada (h, O3/O5)** | O3, O5 | 13 h ≈ um ciclo de maré semidiurna (M2 = 12,42 h) |
| **Fator de agregação da grade (O3/O5)** | O3, O5 | 2 = células 2× maiores (≈ 4× mais rápido); 1 = resolução cheia |
| **Chuva (mm/h, O3)** | O3 | Chuva uniforme simultânea (eventos compostos) |
| **Fator de amplificação da maré (O3–O5)** | O1–O5 | Multiplica a amplitude da maré; use >1 no interior da BTS e estuários (ex.: 1,1–1,2), calibrado com marégrafos |
| **Níveis na biblioteca (O5)** | O5 | Número de simulações O3 que alimentam o emulador (5–8) |
| **Semente aleatória** | O2, O5 | Mesma semente = mesmo resultado (reprodutibilidade) |
| **▶ Executar modelo** | — | Roda em segundo plano; a barra mostra o progresso e a aba **Log** os detalhes |

### Aba 3 Validação

Ver a seção 5.

### Aba 4 Parâmetros

Editor do `params.json` do pacote aberto (marés, AR6, extremos, ondas, erro do DEM, Manning, linha de costa, habitats, danos). **Recarregar** descarta edições não salvas; **Aplicar e salvar params.json** valida o JSON e grava no pacote. O significado de cada campo está em [`02_Formato_Pacote.md`](02_Formato_Pacote.md).

### Aba Log

Registro de cada execução: opções usadas, tempo, avisos (ex.: cenário ausente no pacote) e erros com a pilha completa. Copie esse texto ao relatar um problema.

---

## 4. Os cinco modelos: quando usar e como ler os resultados

As camadas são nomeadas `<variável>_<ssp>_<ano>`, ex.: `probabilidade_ssp245_2100`.

### O1 — Bathtub hidraulicamente conectado

- **Quando:** triagem rápida de todo o estado; comparar cenários; mapas de primeira ordem.
- **Como funciona:** cota d'água = nível de referência (+ extremo de TR, + setup) + ΔRSL do AR6 no quantil escolhido. Inunda só células abaixo da cota **e** conectadas ao mar (métodos, §5.2–5.5).
- **Configuração sugerida:** MHWS, quantil 0,5 e 0,83, conectividade 8, TR 0.
- **Camadas:** `inundado_*` (0/1), `profundidade_*` (m), `nao_conectado_extra_*` (áreas baixas isoladas que um bathtub simples inundaria por engano).
- **Tabela:** área inundada (ha), mangue atingido (ha), população e edificações expostas.
- **Cuidado:** não tem incerteza do DEM nem dinâmica; superestima em áreas grandes e rasas protegidas.

### O2 — Estático probabilístico (recomendado para a Bahia)

- **Quando:** produto principal por setor; mapas de probabilidade para planejamento.
- **Como funciona:** em cada realização sorteia o quantil do AR6, os parâmetros GPD (dentro do erro-padrão), o setup e um campo de erro do DEM espacialmente correlacionado por classe MapBiomas (viés e desvio-padrão da validação; métodos, §5.4–5.6). A probabilidade é a fração de realizações em que a célula inunda.
- **Configuração sugerida:** MHWS; TR 0 (inundação recorrente) e TR 100 (evento extremo); N = 500; setup só em costa aberta.
- **Camadas:** `probabilidade_*` (0–1) e `erro_padrao_MC_*` (erro de Monte Carlo da probabilidade).
- **Tabela:** média, p05 e p95 da área, mangue, população e edificações.
- **Leitura:** p ≥ 0,66 = "provável"; 0,33–0,66 = "tão provável quanto não"; p < 0,1 = "improvável" (linguagem calibrada do IPCC).
- **Antes de rodar com dados reais:** faça a validação A (seção 5) com "Aplicar viés/dp por classe" marcado, para que o erro do DEM venha dos pontos ICESat-2 e não dos valores padrão.

### O3 — Hidrodinâmica 2D reduzida (inercial local)

- **Quando:** subdomínios urbanos e estuarinos (Salvador Comércio/Ribeira, Ilhéus, Canavieiras, Valença, Caravelas), onde a duração do evento limita a inundação.
- **Como funciona:** resolve as equações de águas rasas simplificadas (Bates et al., 2010) com um hidrograma de maré M2 + maré meteorológica gaussiana + ΔRSL imposto no mar; atrito por Manning variando com a cobertura (métodos, §8).
- **Configuração sugerida:** duração 13 h; agregação 2 para testar, 1 para o resultado final; quantil 0,5; TR 10 ou 100.
- **Camadas:** `prof_max_*` (m), `chegada_h_*` (hora em que a célula molha), `duracao_h_*` (horas molhada), `inundado_*`.
- **Cuidado:** sem ondas resolvidas, sem drenagem urbana; domínios grandes ficam lentos (use agregação).

### O4 — Linha de costa + habitats + inundação

- **Quando:** praias arenosas (recuo) e manguezais/apicuns (migração ou perda), ex.: Costa do Descobrimento, Costa das Baleias, Baixo Sul.
- **Como funciona:** recuo de Bruun R = ΔRSL·L*/(B + h*), com h* de Hallermeier e L* do perfil de Dean, aplicado às classes arenosas; habitats reclassificados pelo quadro de maré futuro, com acreção vertical, limiar de afogamento de 7 mm/ano (Saintilan et al., 2020) e bloqueio por área urbana (métodos, §8).
- **Camadas:** `habitat_*` (classes abaixo), `erosao_*` (0/1), `inundado_MHWS_*`.

  | Código | Classe |
  |---|---|
  | 0 | terra firme |
  | 1 | submerso / intermareal baixo |
  | 2 | mangue potencial |
  | 3 | apicum potencial |
  | 4 | migração bloqueada (urbano) |
  | 5 | erodido |

- **Tabela:** taxa de subida (mm/ano), recuo de Bruun (m), h* e L*, mangue atual × potencial (ha), migração bloqueada (ha), erosão (ha) e alerta de afogamento do mangue.
- **Cuidado:** a regra de Bruun é de ordem de grandeza (±50 % ou mais); ajuste `shoreline.d50_mm`, `berm_m`, `he_m` e `habitat.accretion_mm_yr` na aba 4.

### O5 — Integrado probabilístico (emulador + danos)

- **Quando:** estimar danos esperados anuais (EAD) e probabilidade anual de inundação num subdomínio.
- **Como funciona:** roda O3 em K níveis de mar → constrói um emulador por interpolação → valida o emulador num nível extra (RMSE, CSI) → Monte Carlo de máximos anuais (Poisson-GPD) + ΔRSL → profundidade → curva profundidade-dano → EAD (métodos, §8).
- **Configuração sugerida:** 5–8 níveis, agregação 2, N = 1000.
- **Camadas:** `EAD_*` (R$/ano por célula), `prob_anual_inund_*`.
- **Tabela:** EAD total e pessoas atingidas por ano (média). A validação do emulador (RMSE da profundidade e CSI; aceite CSI ≥ 0,7) vai para o Log e para `metadados.json` (`validacao_emulador`).
- **Cuidado:** a curva de dano e o valor por edificação do `params.json` são **ilustrativos**; substitua por curvas regionais (ex.: Huizinga et al., 2017, América do Sul) e valores locais.

### Qual modelo para cada setor da Bahia

| Setor | Modelos |
|---|---|
| S1 Litoral Norte | O2 (com setup) + O4 (praias, dunas) |
| S2 Salvador / BTS | O2 (sem setup, amplificação > 1) + O3/O5 em Comércio/Ribeira |
| S3 Baixo Sul | O2 + O4 (manguezais, apicuns) + O3 em Valença |
| S4 Costa do Cacau | O2 + O3 em Ilhéus e Canavieiras |
| S5 Costa do Descobrimento | O2 (com setup) + O4 (falésias e praias) |
| S6 Costa das Baleias | O2 + O4 + O3 em Caravelas |

---

## 5. Validação (aba 3)

### A) Erro vertical do DEM com pontos

1. Prepare um CSV com colunas `x, y, h_ref` no CRS e no datum do DEM. O script 11 já grava `validacao_pontos_dem.csv` no pacote (ICESat-2 convertido); você pode acrescentar pontos GNSS de campo.
2. Marque **Aplicar viés/dp por classe ao params.json** se quiser que o O2 use esses valores.
3. Clique **Validar DEM com pontos…**.
4. Saída: tabela por classe de cobertura com n, viés, MAE, RMSE, NMAD e LE90. Classes com menos de 30 pontos ficam com o valor padrão.
5. Metas: |viés| < 0,5 m e RMSE < 1,5 m em áreas urbanas/abertas. Mangue e floresta costumam ter viés positivo de 1–3 m (o DEM vê o dossel).

### B) Mancha de inundação observada

1. Prepare um GeoTIFF 0/1 **na mesma grade do pacote** (Sentinel-1/2 de um evento, levantamento da Defesa Civil, linha d'água de maré de sizígia).
2. No mapa, selecione a camada a comparar (ex.: `probabilidade_*` ou `inundado_*`).
3. Defina o **Limiar** (0,5 para probabilidade; 0,05–0,1 m para profundidade).
4. Clique **Validar mancha (CSI, HR, FAR, Brier)…**.
5. Saída: CSI, taxa de acerto (HR), falso alarme (FAR), viés de área, F1 e, para camadas de probabilidade, o escore de Brier com a tabela de confiabilidade.
6. Metas: CSI ≥ 0,6 (bom) e ≥ 0,7 (muito bom); Brier < 0,1.

### C) Série observada × modelada

CSV com colunas `obs, mod` (maré prevista × observada, nível extremo, posição de linha de costa). Saída: n, viés, RMSE, correlação (r) e NSE.

### Validação interna do O5

O emulador é testado automaticamente num nível que ficou fora da biblioteca; o RMSE e o CSI aparecem no Log e em `metadados.json`.

---

## 6. Exportar e abrir no SIG

**Exportar resultados…** grava numa pasta:

- `<camada>.tif`: GeoTIFF float32, mesmo CRS do pacote (EPSG:31984), NoData = -9999;
- `tabela.csv`: UTF-8 com BOM (abre direto no Excel);
- `metadados.json`: modelo, opções, versão do CoastShift e o `params.json` usado (reprodutibilidade).

No QGIS: arraste os `.tif`; para probabilidade use a rampa *Singleband pseudocolor* de 0 a 1. Para `habitat_*`, use *Paletted/Unique values* com a legenda da seção 4.

---

## 7. Pipeline de dados reais: scripts 01 a 13

### 7.1 Antes de começar

**Contas gratuitas:**

| Conta | Usada em | Onde criar |
|---|---|---|
| Google Earth Engine (com projeto Cloud registrado) | 02, 03, 04 | https://earthengine.google.com |
| Copernicus Climate Data Store | 08 | https://cds.climate.copernicus.eu (salve a chave em `~/.cdsapirc`) |
| NASA Earthdata | 09 | https://urs.earthdata.nasa.gov |

**Downloads manuais** (coloque nas pastas indicadas dentro da pasta de dados):

| Arquivo | Pasta | Fonte |
|---|---|---|
| Série horária do marégrafo de Salvador | `mares/salvador_rmpg.csv` | IBGE, Rede Maregráfica Permanente para Geodésia (RMPG) |
| Grade hgeoHNOR2020 | `hgeohnor/` | IBGE, Geodésia → modelos de ondulação |
| Constantes/tábuas das estações DHN | `mares/estacoes_dhn.csv` (modelo gerado pelo script 06) | Marinha do Brasil, CHM, Tábuas de Marés |
| Tiles ANADEM (opcional) | `anadem_tiles/` | ANA / IPH-UFRGS |

**Pasta de dados (`BASE`):** no Colab, `MyDrive/CoastShift_Bahia/`; localmente, `./dados_bahia` relativo à pasta onde o script é executado. Para outro local, defina a variável de ambiente `COASTSHIFT_BASE`:

```bash
set COASTSHIFT_BASE=D:\CoastShift_Bahia
```

### 7.2 Como executar

- **Colab:** abra o notebook de mesmo número em `scripts/notebooks/` e execute as células em ordem.
- **Local:** a partir da pasta do repositório:

```bash
python scripts/01_configurar_ambiente.py
```

Os arquivos `.py` têm células `# %%`; no VS Code/Spyder dá para rodar célula por célula.

### 7.3 Passo a passo

| # | Script | Entrada | Saída | O que conferir |
|---|---|---|---|---|
| 01 | `01_configurar_ambiente.py` | — | `config_bahia.json` | **Edite `gee_project`** (ID do seu projeto Cloud), `anadem_asset`, `dem_principal` e `nmm_salvador_sgb_m` (NMM de Salvador em altitude normal, do relatório RMPG). Ajuste as caixas dos setores se quiser |
| 02 | `02_gee_area_estudo_setores.py` | config | `zona_costeira_<setor>.geojson` no Drive | Abra no QGIS: a faixa deve cobrir a costa até 15 km e 25 m de cota |
| 03 | `03_gee_exportar_dems.py` | zona costeira | GeoTIFFs Copernicus, FABDEM (e ANADEM) por setor no Drive | Acompanhe em *Tasks* do Code Editor ou `ee.batch.Task.list()`; copie os arquivos para `<BASE>/gee/` |
| 04 | `04_gee_exportar_cobertura_exposicao.py` | zona costeira | MapBiomas, JRC GSW, GHS-POP, Open Buildings por setor | Mesma grade de 30 m dos DEMs; copie para `<BASE>/gee/` |
| 05 | `05_baixar_projecoes_ar6.py` | config | `ar6/ar6_setores.json` | Mensagem "ok" por setor; se der erro de nome de arquivo/variável, confira os nomes dentro do zip do Zenodo e ajuste no topo do script |
| 06 | `06_mares_niveis_referencia.py` | `mares/salvador_rmpg.csv`, `estacoes_dhn.csv` | `mares/mares_setores.json` | Salvador: MHWS ≈ 1,1–1,3 m acima do NMM. Preencha o CSV DHN para os outros setores |
| 07 | `07_extremos_pot_gpd.py` | série do 06 | `mares/extremos_setores.json` | Gráfico de nível de retorno com IC; o retroteste deve ter cobertura próxima do nominal (ex.: 90 %) |
| 08 | `08_ondas_era5_setup.py` | conta CDS | `ondas/ondas_setores.json` | Hs típico 1,5–2,5 m; setup só nos setores de costa aberta |
| 09 | `09_icesat2_pontos_validacao.py` | conta Earthdata | `icesat2/atl08_<setor>.csv` | Centenas a milhares de pontos por setor após o filtro de qualidade |
| 10 | `10_conversao_vertical_hgeohnor.py` | DEMs do 03, grade hgeoHNOR | `gee/dem_<fonte>_<setor>_nmm.tif` | **Se aparecer aviso de ETA_CONST, a grade hgeoHNOR não foi encontrada** e a conversão é aproximada |
| 11 | `11_preparar_pacote_modelo.py` | saídas 03–10 | `pacotes/<setor ou subdomínio>/` | Abra o pacote na aba 1 do aplicativo; o resumo deve listar dem, landcover, sea, pop, buildings |
| 12 | `12_gerar_notebooks_colab.py` | scripts `.py` | `scripts/notebooks/*.ipynb` | Rode só se editar os scripts e quiser atualizar os notebooks |
| 13 | `13_executar_modelos_lote.py` | pacotes do 11 | `resultados/<pacote>/<modelo>/` + `resultados/resumo_bahia_O2.csv` | O1 e O2 em todos os setores; O3 nos subdomínios. Pode levar horas com N = 300 |

**Ordem e dependências:** 01 → 02 → (03, 04 em paralelo) → (05, 06, 08, 09 em paralelo) → 07 (depende do 06) → 10 (depende do 03) → 11 → 13.

---

## 8. Uso como biblioteca Python (lote personalizado)

```python
import sys; sys.path.insert(0, r"C:\caminho\CoastShift")
from coastshift import io, models, validation

pkg = io.Package(r"C:\dados_bahia\pacotes\S2_Salvador_BTS")
opt = {"ssps": ["ssp245", "ssp585"], "years": [2050, 2100], "ref": "MHWS",
       "quantile": 0.5, "tr": 0, "setup": False, "conn": 8, "n": 500, "seed": 42, "amp": 1.1}
res = models.RUNNERS["O2"](pkg, opt, progress=lambda f, m: print(f"{f:.0%} {m}"))

print(res.table)                 # lista de dicionários (área, pessoas, edificações…)
p = res.layers["probabilidade_ssp585_2100"]
io.write_raster("prob_ssp585_2100.tif", p, pkg.profile)
```

Opções aceitas por `RUNNERS[...]`: `ssps`, `years`, `ref`, `quantile`, `tr`, `setup`, `conn`, `n`, `seed`, `amp`, `hours`, `coarsen`, `rain_mmh`, `library` (O5), `wet_thr`, `correct_bias` e `compare_unconnected` (O1). O script 13 é um exemplo completo de lote.

---

## 9. Recompilar o executável

```bash
pip install pyinstaller
build_exe.bat
```

Gera `dist/CoastShift.exe` a partir de `CoastShift.spec` (arquivo único, sem console). Depois rode `dist\CoastShift.exe --selftest` e confira o log.

---

## 10. Problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| O executável demora para abrir | Descompactação inicial | Normal; aguarde até 30 s |
| "X.tif não está alinhado ao dem.tif" ao abrir o pacote | Camadas com grades diferentes | Refaça o script 11; não edite os `.tif` à mão |
| Mapa todo inundado ou nada inundado | DEM em datum errado (EGM2008 em vez de NMM local) | Confira o script 10 e `nmm_salvador_sgb_m` no config |
| O2 com probabilidade alta em mangue | Viés do DEM sob dossel não corrigido | Rode a validação A com "Aplicar viés/dp" |
| O3 muito lento | Grade grande | Agregação 2–4 ou recorte menor (subdomínio) |
| `ee.Initialize` falha no Colab | Projeto GEE não registrado | Registre o projeto em code.earthengine.google.com e confira `gee_project` |
| Script 05 não acha a variável | Nome mudou no pacote Zenodo | Abra o `.nc` com `xarray.open_dataset` e ajuste o nome |
| Clone sem o `.exe` real | Git LFS não instalado | `git lfs install` e `git lfs pull` |
