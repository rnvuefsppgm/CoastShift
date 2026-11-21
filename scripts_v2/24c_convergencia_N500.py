"""Convergência com N = 500 (pedido 20/11): repete a base com sementes independentes (9100 + i) e N = 500,
para os mesmos 21 cenário×ano do 24b --todos; compara com a base do 24b (diferença ≈ erro de Monte Carlo × √2)."""
import importlib.util, os, sys
import pandas as pd
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("s24b", os.path.join(os.path.dirname(os.path.abspath(__file__)), "24b_sensibilidade_parametros.py"))
s24b = importlib.util.module_from_spec(spec); spec.loader.exec_module(s24b)
_v2 = s24b._v2
OUT = s24b.OUT + "_todos"
s24b.VAR["convergencia_N500"] = {}


def tarefa(*a):
    return s24b.tarefa(*a)

if __name__ == "__main__":
    os.environ.pop("COASTSHIFT_ELL", None)
    jobs = [(s_, y) for s_ in ("ssp119", "ssp126", "ssp245", "ssp370", "ssp585") for y in (2030, 2050, 2100, 2150)] + [("ssp245", 2014)]
    tar = [("convergencia_N500", s, jobs, 500, 9100 + i) for i, s in enumerate(_v2.SETORES)]
    linhas = []
    with ProcessPoolExecutor(6) as ex:
        for var, setor, res in ex.map(tarefa, *zip(*tar)):
            for (ssp, ano), r in res.items():
                linhas.append({"variante": var, "setor": setor, "cenario": "atual" if ano == 2014 else ssp, "ano": ano, **r})
            _v2.log(f"convergência N500: {setor} ok")
    d = pd.DataFrame(linhas)
    d = pd.concat([d, d.groupby(["variante", "cenario", "ano"], as_index=False)[["E_A_ha", "pop"]].sum().assign(setor="TOTAL_COSTA_BAHIA")], ignore_index=True)
    b = pd.read_csv(os.path.join(OUT, "sensibilidade_parametros.csv"))
    b = b[b.variante == "base"].set_index(["setor", "cenario", "ano"])["E_A_ha"]
    d["dif_vs_base_%"] = [100 * (r.E_A_ha / b.get((r.setor, r.cenario, r.ano), float("nan")) - 1) for r in d.itertuples()]
    d.round(3).to_csv(os.path.join(OUT, "convergencia_N500.csv"), index=False, encoding="utf-8-sig")
    t = d[d.setor == "TOTAL_COSTA_BAHIA"]
    _v2.log(f"convergência N500 concluída; costa |dif| máx = {t['dif_vs_base_%'].abs().max():.2f} %; setores |dif| máx = {d['dif_vs_base_%'].abs().max():.2f} %")
