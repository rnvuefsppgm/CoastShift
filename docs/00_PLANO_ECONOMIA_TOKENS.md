# Plano de economia de tokens — etapa CoastShift

1. **Uma pasta, um repositório.** Tudo (scripts, documentos, código, executável) fica em `Ana_Model/CoastShift`, que é o clone de `rnvuefsppgm/CoastShift`. Nada é copiado duas vezes.
2. **Reuso da revisão.** O documento de métodos cita a revisão e os inventários existentes por ID (E/D/M/C) em vez de repeti-los.
3. **Uma biblioteca, três usos.** O pacote `coastshift/` (modelos O1–O5 e validação) é usado pela interface gráfica, pelos scripts numerados e pelos testes. Não há lógica duplicada.
4. **Notebooks gerados, não escritos.** Os scripts `.py` usam células `# %%`; o script `12_gerar_notebooks_colab.py` converte-os em `.ipynb` para o Colab.
5. **Teste com dados sintéticos.** Um gerador de dados de demonstração valida os cinco modelos sem baixar gigabytes.
6. **Saídas curtas.** Build e testes rodam com log resumido. O executável é compilado uma única vez, depois que os testes passam.
7. **Verificação mínima na web.** Só os IDs de ativos do GEE foram conferidos (FABDEM, MapBiomas, Copernicus DEM). O ID do ANADEM no GEE não foi localizado: o script aceita o asset do usuário ou tiles baixados.

## Etapa 4 — cópia local + tutorial (plano de economia)

1. Ler só cabeçalhos dos scripts e rótulos da interface (grep), sem reler arquivos inteiros.
2. Um único tutorial (`docs/03_Tutorial.md`) cobrindo executável, aplicativo, modelos O1–O5, validação, scripts 01–13, lote e biblioteca; README só aponta para ele.
3. Cópia local feita por `robocopy` (sem reescrever arquivos), no mesmo layout do repositório para os scripts continuarem achando a biblioteca.
4. Um commit e um push; o executável continua no Git LFS (sem novo upload, pois não mudou).
