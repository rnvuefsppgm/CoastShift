# CoastShift

A geospatial modeling application that uses sea-level rise projections to map potential coastal flooding, shoreline change, and exposure of communities, infrastructure, and ecosystems under different climate scenarios.

**Aplicação: costa do Estado da Bahia (Brasil).** Interface gráfica + biblioteca Python + scripts de aquisição de dados (Google Earth Engine / Colab / Python) + documento de métodos.

## Modelos (níveis de complexidade da revisão)

| ID | Modelo | Saídas principais |
|---|---|---|
| O1 | Bathtub hidraulicamente conectado | Extensão e profundidade potencial; diferença conectado × não conectado |
| **O2** | **Estático probabilístico (Monte Carlo: AR6 + extremos GPD + setup de ondas + erro correlacionado do DEM)** — *recomendado para a Bahia* | Probabilidade de inundação, erro-padrão, exposição (média, p05, p95) |
| O3 | Hidrodinâmica 2D reduzida (inercial local, Bates et al., 2010) | Profundidade máxima, tempo de chegada, duração |
| O4 | Linha de costa (Bruun) + habitats (quadro de maré, acreção, afogamento, barreiras) + inundação | Recuo, áreas erodidas, mangue/apicum potencial, migração bloqueada |
| O5 | Integrado probabilístico (biblioteca O3 → emulador → máximos anuais Poisson-GPD → danos) | EAD, probabilidade anual de inundação, pessoas atingidas; validação do emulador |

O3–O5 são implementações **reduzidas** para triagem e ensino da cadeia de processos. Para projeto de engenharia, use solvers completos (SFINCS, Delft3D FM, SCHISM, XBeach). Ver `docs/01_Metodos_Opcao2_Bahia.md` §8.

## Estrutura

```
CoastShift/
├── app.py                      interface gráfica (Tkinter + Matplotlib)
├── coastshift/                 biblioteca: io, core (equações), models (O1–O5), validation, demo
├── scripts/                    01–13: aquisição GEE/Colab/Python → pacotes → lote
│   └── notebooks/              versões .ipynb para o Google Colab
├── docs/
│   ├── 00_PLANO_ECONOMIA_TOKENS.md
│   ├── 01_Metodos_Opcao2_Bahia.md   métodos, equações, dados, validação
│   └── 02_Formato_Pacote.md
├── tests/test_smoke.py
├── CoastShift.spec / build_exe.bat  compilação do executável
└── requirements.txt
```

## Uso rápido

**Executável (Windows 10/11, 64 bits):** baixe `CoastShift.exe` em *Releases*, abra-o e use **1 Dados → Gerar pacote de DEMONSTRAÇÃO**. Depois escolha o modelo em **2 Modelo → Executar**. Não precisa de Python.

**A partir do código:**
```bash
pip install -r requirements.txt
python app.py
python tests/test_smoke.py
```

## Sequência de processamento dos dados reais (Bahia)

| # | Script | Ambiente | O que faz |
|---|---|---|---|
| 01 | `01_configurar_ambiente.py` | Colab/local | Config, setores S1–S6, subdomínios, autenticação GEE |
| 02 | `02_gee_area_estudo_setores.py` | GEE | Zona costeira (≤15 km do oceano, ≤25 m) por setor |
| 03 | `03_gee_exportar_dems.py` | GEE | Copernicus GLO-30 (+WBM), FABDEM, ANADEM |
| 04 | `04_gee_exportar_cobertura_exposicao.py` | GEE | MapBiomas C10, JRC GSW, GHS-POP, Open Buildings |
| 05 | `05_baixar_projecoes_ar6.py` | Python | AR6 regional (Zenodo) por setor |
| 06 | `06_mares_niveis_referencia.py` | Python | NMM, MHHW, MHWS (RMPG Salvador + DHN) |
| 07 | `07_extremos_pot_gpd.py` | Python | POT-GPD, bootstrap, retroteste |
| 08 | `08_ondas_era5_setup.py` | Python | ERA5 ondas → setup de Stockdon |
| 09 | `09_icesat2_pontos_validacao.py` | Python | ICESat-2 ATL08 para validar o DEM |
| 10 | `10_conversao_vertical_hgeohnor.py` | Python | EGM2008 → elipsoide → hgeoHNOR2020 → NMM local |
| 11 | `11_preparar_pacote_modelo.py` | Python | Pacotes por setor/subdomínio (entrada do app) |
| 12 | `12_gerar_notebooks_colab.py` | Python | Gera os notebooks Colab |
| 13 | `13_executar_modelos_lote.py` | Python | Roda O1/O2 (setores) e O3 (subdomínios) em lote |

**Contas necessárias (gratuitas):** Google Earth Engine (projeto Cloud), Copernicus CDS (ERA5), NASA Earthdata (ICESat-2).
**Downloads manuais:** série do marégrafo de Salvador (RMPG/IBGE), grade hgeoHNOR2020 (IBGE), tábuas de marés (DHN) e, opcionalmente, tiles do ANADEM.

## Compilar o executável

```bash
build_exe.bat
```
Gera `dist/CoastShift.exe` (PyInstaller, arquivo único, sem console). Teste sem interface: `CoastShift.exe --selftest` (grava `coastshift_selftest.log`).

## Licenças e citação

- Código: GPL-3.0.
- Dados: cada base tem sua licença (FABDEM: CC BY-NC-SA 4.0, não comercial; MapBiomas: CC BY 4.0; AR6: CC BY 4.0).
- Para citar o método, use o documento de métodos e as referências nele.
