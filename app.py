"""CoastShift — interface gráfica (Tkinter) para os modelos O1–O5 e validação.
Executar: python app.py   |   Compilar: build_exe.bat"""
import json
import os
import queue
import sys
import threading
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from coastshift import __version__, demo, io, models, validation  # noqa: E402

DESC = {
    "O1": "Cota d'água = nível de referência (NMM/MHHW/MHWS ou TR) + ΔRSL(AR6, quantil). "
          "Mantém só células conectadas ao mar. Rápido; triagem estadual.",
    "O2": "Monte Carlo: amostra ΔRSL (quantil aleatório), parâmetros GPD, setup de ondas e campo de erro "
          "correlacionado do DEM por classe. Saída: probabilidade de inundação e intervalos de exposição.",
    "O3": "Solver 2D inercial local (Bates et al., 2010) com hidrograma de maré + maré meteorológica + ΔRSL "
          "no contorno marinho. Saída: profundidade máxima, chegada e duração. Use 'agregação' para acelerar.",
    "O4": "Recuo de Bruun (h* Hallermeier, perfil de Dean) em classes arenosas + evolução de habitats pelo "
          "quadro de maré com acreção, limiar de afogamento e barreiras urbanas + inundação MHWS amplificada.",
    "O5": "Biblioteca de simulações O3 em K níveis → emulador por interpolação (validado em nível extra) → "
          "Monte Carlo de máximos anuais (Poisson-GPD) + ΔRSL → danos (curva profundidade-dano) e EAD.",
}
SSPS = ["ssp119", "ssp126", "ssp245", "ssp370", "ssp585"]
HAB_CMAP = ListedColormap(["#d9c9a3", "#4a90d9", "#1b7837", "#e0b050", "#d6604d", "#7b3294"])


def resource_dir():
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"CoastShift {__version__} — Elevação do nível do mar · Costa da Bahia")
        self.geometry("1360x860")
        self.pkg, self.result, self.q = None, None, queue.Queue()
        self.view_layers = {}
        self._build()
        self.after(100, self._poll)

    # ------------------------------------------------------------------ layout
    def _build(self):
        pw = ttk.PanedWindow(self, orient="horizontal")
        pw.pack(fill="both", expand=True)
        left = ttk.Frame(pw, width=430)
        right = ttk.Frame(pw)
        pw.add(left, weight=0)
        pw.add(right, weight=1)
        nb = ttk.Notebook(left)
        nb.pack(fill="both", expand=True, padx=4, pady=4)
        self.tab_data, self.tab_model, self.tab_val, self.tab_par, self.tab_log = (ttk.Frame(nb) for _ in range(5))
        for t, n in [(self.tab_data, "1 Dados"), (self.tab_model, "2 Modelo"), (self.tab_val, "3 Validação"),
                     (self.tab_par, "4 Parâmetros"), (self.tab_log, "Log")]:
            nb.add(t, text=n)
        self._build_data()
        self._build_model()
        self._build_val()
        self._build_par()
        self.log = tk.Text(self.tab_log, height=30, wrap="word")
        self.log.pack(fill="both", expand=True)
        # direita: mapa + tabela
        top = ttk.Frame(right)
        top.pack(fill="x")
        ttk.Label(top, text="Camada:").pack(side="left", padx=4)
        self.layer_cb = ttk.Combobox(top, width=48, state="readonly")
        self.layer_cb.pack(side="left")
        self.layer_cb.bind("<<ComboboxSelected>>", lambda e: self.draw())
        ttk.Button(top, text="Exportar resultados…", command=self.export).pack(side="right", padx=4)
        self.fig = Figure(figsize=(8, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        NavigationToolbar2Tk(self.canvas, right).update()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.tree = ttk.Treeview(right, height=8, show="headings")
        self.tree.pack(fill="x")
        sb = ttk.Scrollbar(right, orient="horizontal", command=self.tree.xview)
        sb.pack(fill="x")
        self.tree.configure(xscrollcommand=sb.set)
        self.status = ttk.Label(self, text="Abra um pacote de dados (aba 1) ou gere a demonstração.", anchor="w")
        self.status.pack(fill="x")

    def _row(self, parent, label, default, width=12):
        f = ttk.Frame(parent)
        f.pack(fill="x", padx=6, pady=2)
        ttk.Label(f, text=label, width=30).pack(side="left")
        v = tk.StringVar(value=str(default))
        ttk.Entry(f, textvariable=v, width=width).pack(side="left")
        return v

    def _build_data(self):
        f = self.tab_data
        ttk.Button(f, text="Abrir pacote (pasta com params.json + dem.tif)…", command=self.open_pkg).pack(fill="x", padx=6, pady=4)
        ttk.Button(f, text="Gerar pacote de DEMONSTRAÇÃO (sintético)…", command=self.make_demo).pack(fill="x", padx=6, pady=4)
        self.info = tk.Text(f, height=16, wrap="word")
        self.info.pack(fill="both", expand=True, padx=6, pady=6)
        ttk.Label(f, text="Pacotes reais são gerados pelos scripts 01–10 (pasta scripts/).", wraplength=380).pack(padx=6)

    def _build_model(self):
        f = self.tab_model
        self.model_cb = ttk.Combobox(f, values=list(models.MODELS.values()), state="readonly", width=52)
        self.model_cb.current(1)
        self.model_cb.pack(padx=6, pady=4)
        self.model_desc = ttk.Label(f, text=DESC["O2"], wraplength=400, foreground="#444")
        self.model_desc.pack(padx=6, pady=2, fill="x")
        self.model_cb.bind("<<ComboboxSelected>>", lambda e: self.model_desc.config(text=DESC[self._mid()]))
        sf = ttk.LabelFrame(f, text="Cenários AR6")
        sf.pack(fill="x", padx=6, pady=4)
        self.ssp_vars = {}
        for s in SSPS:
            v = tk.BooleanVar(value=s in ("ssp126", "ssp245", "ssp585"))
            ttk.Checkbutton(sf, text=s.upper(), variable=v).pack(side="left", padx=2)
            self.ssp_vars[s] = v
        self.v_years = self._row(f, "Horizontes (anos, vírgula)", "2050,2100", 16)
        self.v_q = self._row(f, "Quantil ΔRSL (O1/O3/O4)", 0.5)
        fr = ttk.Frame(f)
        fr.pack(fill="x", padx=6, pady=2)
        ttk.Label(fr, text="Nível de referência", width=30).pack(side="left")
        self.ref_cb = ttk.Combobox(fr, values=["NMM", "MHHW", "MHWS"], width=9, state="readonly")
        self.ref_cb.set("MHWS")
        self.ref_cb.pack(side="left")
        self.v_tr = self._row(f, "Tempo de retorno (anos; 0 = maré)", 0)
        self.v_setup = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="Somar setup de ondas (Stockdon) — costa aberta", variable=self.v_setup).pack(anchor="w", padx=6)
        self.v_conn = tk.IntVar(value=8)
        cf = ttk.Frame(f)
        cf.pack(fill="x", padx=6)
        ttk.Label(cf, text="Conectividade", width=30).pack(side="left")
        ttk.Radiobutton(cf, text="8", variable=self.v_conn, value=8).pack(side="left")
        ttk.Radiobutton(cf, text="4", variable=self.v_conn, value=4).pack(side="left")
        self.v_n = self._row(f, "Realizações Monte Carlo (O2/O5)", 200)
        self.v_hours = self._row(f, "Duração simulada (h, O3/O5)", 13)
        self.v_coarsen = self._row(f, "Fator de agregação da grade (O3/O5)", 2)
        self.v_rain = self._row(f, "Chuva (mm/h, O3)", 0)
        self.v_amp = self._row(f, "Fator de amplificação da maré (O3–O5)", 1.0)
        self.v_lib = self._row(f, "Níveis na biblioteca (O5)", 5)
        self.v_seed = self._row(f, "Semente aleatória", 42)
        self.run_btn = ttk.Button(f, text="▶ Executar modelo", command=self.run)
        self.run_btn.pack(fill="x", padx=6, pady=8)
        self.pbar = ttk.Progressbar(f, maximum=1.0)
        self.pbar.pack(fill="x", padx=6)

    def _build_val(self):
        f = self.tab_val
        ttk.Label(f, text="A) Erro vertical do DEM — CSV com colunas x, y, h_ref no CRS do DEM "
                          "(ex.: saída do script 09 ICESat-2).", wraplength=400).pack(padx=6, pady=4, anchor="w")
        self.v_apply_err = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="Aplicar viés/dp por classe ao params.json", variable=self.v_apply_err).pack(anchor="w", padx=6)
        ttk.Button(f, text="Validar DEM com pontos…", command=self.val_dem).pack(fill="x", padx=6, pady=4)
        ttk.Separator(f).pack(fill="x", pady=6)
        ttk.Label(f, text="B) Mancha observada (GeoTIFF 0/1 na grade do pacote: Sentinel-1/2, Defesa Civil) "
                          "vs camada atual do mapa.", wraplength=400).pack(padx=6, anchor="w")
        self.v_thr = self._row(f, "Limiar p/ probabilidade/profundidade", 0.5)
        ttk.Button(f, text="Validar mancha (CSI, HR, FAR, Brier)…", command=self.val_flood).pack(fill="x", padx=6, pady=4)
        ttk.Separator(f).pack(fill="x", pady=6)
        ttk.Label(f, text="C) Série observada × modelada (CSV com colunas obs, mod): maré, nível, linha de costa.",
                  wraplength=400).pack(padx=6, anchor="w")
        ttk.Button(f, text="Validar série…", command=self.val_series).pack(fill="x", padx=6, pady=4)
        ttk.Label(f, text="O5 valida o emulador automaticamente (RMSE e CSI num nível fora da biblioteca).",
                  wraplength=400, foreground="#444").pack(padx=6, pady=8, anchor="w")

    def _build_par(self):
        f = self.tab_par
        self.par_txt = tk.Text(f, wrap="none", font=("Consolas", 9))
        self.par_txt.pack(fill="both", expand=True)
        b = ttk.Frame(f)
        b.pack(fill="x")
        ttk.Button(b, text="Recarregar", command=self.show_params).pack(side="left", padx=4, pady=4)
        ttk.Button(b, text="Aplicar e salvar params.json", command=self.save_params).pack(side="left", padx=4)

    # ------------------------------------------------------------------ dados
    def _mid(self):
        return list(models.MODELS)[self.model_cb.current()]

    def open_pkg(self, folder=None):
        folder = folder or filedialog.askdirectory(title="Pasta do pacote")
        if not folder:
            return
        try:
            self.pkg = io.Package(folder)
        except Exception as e:
            messagebox.showerror("Erro ao abrir pacote", str(e))
            return
        p, shp = self.pkg.params, self.pkg.dem.shape
        txt = [f"Pacote: {folder}", f"Setor: {p.get('sector')}", p.get("aviso", ""),
               f"Grade: {shp[1]} × {shp[0]} células, {self.pkg.cell:.1f} m", f"CRS: {self.pkg.profile.get('crs')}",
               f"Camadas: {', '.join(self.pkg.layers)}", f"Cenários AR6: {', '.join(p['ar6']['scenarios'])}",
               f"Maré: {p['tide']}", f"Extremos: {p.get('extremes', {})}"]
        self.info.delete("1.0", "end")
        self.info.insert("end", "\n".join(txt))
        for s, v in self.ssp_vars.items():
            if s not in p["ar6"]["scenarios"]:
                v.set(False)
        self.view_layers = {f"[dados] {k}": v for k, v in self.pkg.layers.items()}
        self._refresh_layers("[dados] dem")
        self.show_params()
        self.msg(f"Pacote carregado: {p.get('sector')}")

    def make_demo(self):
        folder = filedialog.askdirectory(title="Pasta onde criar o pacote de demonstração")
        if not folder:
            return
        demo.make_demo(os.path.join(folder, "pacote_demo"))
        self.open_pkg(os.path.join(folder, "pacote_demo"))

    def show_params(self):
        if self.pkg:
            self.par_txt.delete("1.0", "end")
            self.par_txt.insert("end", json.dumps(self.pkg.params, indent=2, ensure_ascii=False))

    def save_params(self):
        if not self.pkg:
            return
        try:
            self.pkg.params = json.loads(self.par_txt.get("1.0", "end"))
            self.pkg.save_params()
            self.msg("params.json salvo.")
        except Exception as e:
            messagebox.showerror("JSON inválido", str(e))

    # ------------------------------------------------------------------ execução
    def _options(self):
        g = lambda v, t=float: t(v.get().replace(",", ".")) if t is not str else v.get()  # noqa: E731
        return {"ssps": [s for s, v in self.ssp_vars.items() if v.get()],
                "years": [int(y) for y in self.v_years.get().split(",") if y.strip()],
                "quantile": g(self.v_q), "ref": self.ref_cb.get(), "tr": g(self.v_tr), "setup": self.v_setup.get(),
                "conn": self.v_conn.get(), "n": int(g(self.v_n)), "hours": g(self.v_hours),
                "coarsen": int(g(self.v_coarsen)), "rain_mmh": g(self.v_rain), "amp": g(self.v_amp),
                "library": int(g(self.v_lib)), "seed": int(g(self.v_seed))}

    def run(self):
        if not self.pkg:
            messagebox.showwarning("CoastShift", "Abra um pacote primeiro.")
            return
        try:
            opt = self._options()
            assert opt["ssps"] and opt["years"], "Selecione cenário(s) e ano(s)."
        except Exception as e:
            messagebox.showerror("Opções inválidas", str(e))
            return
        mid = self._mid()
        self.run_btn.config(state="disabled")
        self.msg(f"Executando {models.MODELS[mid]} …")

        def work():
            try:
                res = models.RUNNERS[mid](self.pkg, opt, progress=lambda f, m: self.q.put(("prog", f, m)))
                self.q.put(("done", res))
            except Exception:
                self.q.put(("error", traceback.format_exc()))
        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        try:
            while True:
                item = self.q.get_nowait()
                if item[0] == "prog":
                    self.pbar["value"] = item[1]
                    self.status.config(text=item[2])
                elif item[0] == "done":
                    self._on_done(item[1])
                elif item[0] == "error":
                    self.run_btn.config(state="normal")
                    self.msg("ERRO:\n" + item[1])
                    messagebox.showerror("Erro na execução", item[1][-800:])
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _on_done(self, res):
        self.result = res
        self.run_btn.config(state="normal")
        self.pbar["value"] = 1.0
        for k, v in res.layers.items():
            self.view_layers[f"[{res.meta['modelo']}] {k}"] = v
        first = f"[{res.meta['modelo']}] {next(iter(res.layers))}" if res.layers else None
        self._refresh_layers(first)
        self.show_table(pd.DataFrame(res.table))
        extra = {k: v for k, v in res.meta.items() if k in ("validacao_emulador", "legenda_habitat")}
        self.msg(f"{res.meta['modelo']} concluído. {len(res.layers)} camadas. {extra if extra else ''}")

    # ------------------------------------------------------------------ visualização
    def _refresh_layers(self, select=None):
        self.layer_cb["values"] = list(self.view_layers)
        if select in self.view_layers:
            self.layer_cb.set(select)
        self.draw()

    def draw(self):
        name = self.layer_cb.get()
        if not name or not self.pkg:
            return
        arr = self.view_layers[name]
        t, (ny, nx) = self.pkg.profile["transform"], self.pkg.dem.shape
        ext = [t.c, t.c + t.a * nx, t.f + t.e * ny, t.f]
        self.fig.clf()
        self.ax = self.fig.add_subplot(111)
        self.ax.imshow(np.where(self.pkg.sea, np.nan, self.pkg.dem), cmap="gray", extent=ext, alpha=0.55)
        key = name.split("] ")[-1]
        data = np.where(np.nan_to_num(arr) == 0, np.nan, arr) if key.startswith(("inundado", "erosao", "nao_conectado", "prob", "EAD")) else arr
        if key.startswith("habitat"):
            im = self.ax.imshow(arr, cmap=HAB_CMAP, vmin=-0.5, vmax=5.5, extent=ext, interpolation="nearest")
            cb = self.fig.colorbar(im, ax=self.ax, ticks=range(6))
            cb.ax.set_yticklabels(["terra", "submerso", "mangue", "apicum", "bloqueado", "erodido"])
        else:
            cmap = {"dem": "terrain", "prob": "viridis", "prof": "Blues", "dura": "Purples", "cheg": "magma_r",
                    "EAD": "OrRd", "landcover": "tab20", "pop": "YlOrRd", "build": "YlOrRd"}
            cm = next((v for k, v in cmap.items() if k in key), "Blues")
            vmin, vmax = (0, 1) if key.startswith(("prob", "inundado", "erosao", "nao_con")) else (None, None)
            im = self.ax.imshow(data, cmap=cm, extent=ext, vmin=vmin, vmax=vmax, interpolation="nearest")
            self.fig.colorbar(im, ax=self.ax, shrink=0.8)
        self.ax.set_title(name, fontsize=10)
        self.ax.ticklabel_format(useOffset=False, style="plain")
        self.canvas.draw_idle()

    def show_table(self, df):
        self.tree.delete(*self.tree.get_children())
        cols = list(df.columns)
        self.tree["columns"] = cols
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=max(80, 8 * len(c)), stretch=False)
        for _, r in df.iterrows():
            self.tree.insert("", "end", values=[r[c] for c in cols])

    # ------------------------------------------------------------------ validação
    def val_dem(self):
        if not self.pkg:
            return
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            df, err = validation.dem_vs_points(self.pkg.dem, self.pkg.profile, self.pkg.layers["landcover"], path)
        except Exception as e:
            messagebox.showerror("Validação do DEM", str(e))
            return
        self.show_table(df)
        if self.v_apply_err.get():
            err["corr_length_m"] = self.pkg.params.get("dem_error", {}).get("corr_length_m", 300)
            self.pkg.params["dem_error"] = err
            self.pkg.save_params()
            self.show_params()
        self.msg(f"Validação do DEM concluída. Erro aplicado: {self.v_apply_err.get()}")

    def val_flood(self):
        name = self.layer_cb.get()
        if not self.pkg or not name:
            return
        path = filedialog.askopenfilename(filetypes=[("GeoTIFF", "*.tif *.tiff")])
        if not path:
            return
        try:
            obs = validation.read_mask_aligned(path, self.pkg.profile)
            arr = self.view_layers[name]
            thr = float(self.v_thr.get().replace(",", "."))
            land = ~self.pkg.sea
            res = validation.flood_skill(np.nan_to_num(arr) >= thr, obs, land)
            if "prob" in name:
                res["Brier"], rel = validation.brier(arr, obs, land)
                self.msg("Confiabilidade:\n" + rel.to_string(index=False))
            self.show_table(pd.DataFrame([{"camada": name, **res}]))
            self.msg(f"Validação da mancha: {res}")
        except Exception as e:
            messagebox.showerror("Validação da mancha", str(e))

    def val_series(self):
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if path:
            try:
                r = validation.series_skill(path)
                self.show_table(pd.DataFrame([r]))
                self.msg(f"Série: {r}")
            except Exception as e:
                messagebox.showerror("Validação de série", str(e))

    # ------------------------------------------------------------------ exportação
    def export(self):
        if not self.result:
            messagebox.showinfo("CoastShift", "Execute um modelo antes de exportar.")
            return
        folder = filedialog.askdirectory(title="Pasta de saída")
        if not folder:
            return
        m = self.result.meta["modelo"]
        out = os.path.join(folder, f"resultado_{m}")
        os.makedirs(out, exist_ok=True)
        for k, v in self.result.layers.items():
            io.write_raster(os.path.join(out, f"{k}.tif"), v, self.pkg.profile)
        pd.DataFrame(self.result.table).to_csv(os.path.join(out, "tabela.csv"), index=False, encoding="utf-8-sig")
        with open(os.path.join(out, "metadados.json"), "w", encoding="utf-8") as f:
            json.dump({"meta": self.result.meta, "params": self.pkg.params, "versao": __version__}, f,
                      indent=2, ensure_ascii=False, default=str)
        self.msg(f"Resultados exportados em {out}")

    def msg(self, text):
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.status.config(text=text.splitlines()[0][:200])


def main():
    if "--selftest" in sys.argv:  # usado para testar o executável sem interface
        import tempfile
        d = demo.make_demo(os.path.join(tempfile.gettempdir(), "coastshift_selftest"), n=80)
        pkg = io.Package(d)
        o = {"ssps": ["ssp245"], "years": [2100], "n": 20, "hours": 3, "coarsen": 2, "library": 3}
        lines = []
        for k, fn in models.RUNNERS.items():
            r = fn(pkg, o)
            lines.append(f"{k} ok {len(r.layers)} camadas")
        with open("coastshift_selftest.log", "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\nSELFTEST OK\n")
        print("\n".join(lines))
        return
    App().mainloop()


if __name__ == "__main__":
    main()
