"""Grava um vídeo narrado (pt-BR) mostrando o funcionamento do CoastShift.

1) Slides de introdução (como a aplicação funciona); 2) demonstração real do aplicativo (app.py) controlado
por script no pacote do setor S2 (fluxo V2), com captura da janela; 3) narração com a voz do Windows
(System.Speech, "Microsoft Maria") e legendas; 4) montagem MP4 (H.264 + AAC) com o ffmpeg do imageio-ffmpeg.
Uso: python tools/gravar_video_app.py [--pacote <pasta>] [--saida <pasta>] [--n 30]
"""
import argparse
import ctypes
import os
import shutil
import subprocess
import sys
import time
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageGrab

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
W, H, FPS = 1920, 1080, 4
FONT = "C:/Windows/Fonts/segoeui.ttf"
FONT_B = "C:/Windows/Fonts/segoeuib.ttf"
AZUL, BRANCO, LARANJA = (15, 32, 56), (245, 247, 250), (253, 141, 60)

NARR = {
    "s1": "Este vídeo apresenta o CoastShift, uma aplicação em Python para modelar a elevação do nível do mar e a "
          "inundação costeira na costa da Bahia.",
    "s2": "Como funciona. Primeiro, os scripts do fluxo V2 baixam automaticamente, sem login, todas as bases: relevo, "
          "cobertura MapBiomas, projeções do IPCC, marés, ondas e pontos do satélite ICESat-2. Em seguida, cada setor "
          "da costa vira um pacote de entrada, com rasters alinhados e um arquivo de parâmetros.",
    "s3": "No Modelo 2, o aplicativo sorteia centenas de realizações: a subida do mar do AR6, a maré e os extremos, as "
          "ondas e o erro do relevo calibrado por satélite. Em cada realização calcula a área inundada conectada ao mar. "
          "A fração de realizações em que cada célula alaga é a probabilidade de inundação.",
    "a1": "Esta é a janela principal. À esquerda ficam as abas de dados, modelo, validação e parâmetros. À direita, o "
          "mapa e a tabela de resultados.",
    "a2": "Na aba Dados, abrimos o pacote do setor Salvador e Baía de Todos os Santos, gerado pelo fluxo V2. O resumo "
          "mostra a grade, a resolução de trinta metros e os cenários disponíveis.",
    "a3": "Na aba Parâmetros vemos os valores usados: níveis de maré, extremos, ondas, projeções e o erro do relevo por "
          "classe de cobertura, estimado com o ICESat-2.",
    "a4": "Na aba Modelo escolhemos o Modelo 2, estático probabilístico, os cenários SSP2-4.5 e SSP5-8.5, os horizontes "
          "de 2050 e 2100 e a preamar de sizígia. Nesta demonstração usamos poucas realizações; nos resultados finais, "
          "quinhentas.",
    "a5": "Ao executar, o modelo roda em segundo plano e a barra mostra o progresso.",
    "a6": "Pronto. O mapa mostra a probabilidade de inundação em 2100 no cenário SSP5-8.5. A tabela traz a área "
          "inundada, a população, as edificações e o mangue expostos, com média e intervalo de noventa por cento.",
    "a7": "Podemos alternar entre camadas, por exemplo o cenário intermediário em 2050, e comparar a expansão da área "
          "atingida.",
    "a8": "Na aba Validação comparamos o relevo com os pontos do ICESat-2. A tabela mostra viés, erro médio e NMAD por "
          "classe de cobertura; esses valores corrigem o relevo no Monte Carlo.",
    "s4": "Os resultados podem ser exportados em GeoTIFF e tabelas. Para toda a costa, os scripts 21 e 22 rodam o "
          "modelo em lote, calculam as áreas em hectares e geram os mapas finais. Obrigado.",
}
SLIDES = {
    "s1": ("CoastShift", ["Elevação do nível do mar e inundação costeira", "Costa do Estado da Bahia · Modelo 2 (O2)",
                          "Python · interface gráfica · dados abertos (fluxo V2)"]),
    "s2": ("Como a aplicação funciona", ["1  Scripts V2 baixam as bases (sem login)",
                                         "    DEM · MapBiomas · IPCC AR6 · marés · ondas · ICESat-2",
                                         "2  Script 20 monta um pacote por setor (rasters + params.json)",
                                         "3  O aplicativo carrega o pacote, roda o modelo e valida",
                                         "4  Exporta GeoTIFF, tabelas e mapas"]),
    "s3": ("Modelo 2 — estático probabilístico", ["Para cada realização k = 1…N:",
                                                  "   ΔRSL (AR6, quantil sorteado) + maré/extremo + setup de ondas",
                                                  "   relevo corrigido: z − viés − dp · campo correlacionado",
                                                  "   inundação conectada ao mar (8 vizinhos)",
                                                  "Probabilidade p = fração das N realizações em que a célula alaga"]),
    "s4": ("Resultados e próximos passos", ["Exportar: GeoTIFF de probabilidade + tabelas de exposição",
                                            "Script 21: O2 para os 6 setores + áreas (ha) por classe",
                                            "Script 22: mapas finais (padrão Q1) e gráficos",
                                            "github.com/rnvuefsppgm/CoastShift"]),
}


def fonte(sz, bold=False):
    try:
        return ImageFont.truetype(FONT_B if bold else FONT, sz)
    except OSError:
        return ImageFont.load_default()


def tts(texto, wav):
    ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          "try { $s.SelectVoice('Microsoft Maria Desktop') } catch {}; $s.Rate = 0; "
          "$f = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(22050, "
          "[System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono); "
          f"$s.SetOutputToWaveFile('{wav}', $f); $s.Speak([IO.File]::ReadAllText('{wav}.txt')); $s.Dispose()")
    with open(wav + ".txt", "w", encoding="utf-8") as fh:
        fh.write(texto)
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
    with wave.open(wav) as w:
        return w.getnframes() / w.getframerate()


def legenda(img, texto):
    d = ImageDraw.Draw(img)
    f = fonte(30)
    linhas, cur = [], ""
    for p in texto.split():
        t = (cur + " " + p).strip()
        if d.textlength(t, font=f) > W - 240:
            linhas.append(cur)
            cur = p
        else:
            cur = t
    linhas.append(cur)
    linhas = linhas[-3:]
    h = 44 * len(linhas) + 30
    d.rectangle([0, H - h, W, H], fill=(0, 0, 0))
    for i, ln in enumerate(linhas):
        d.text((W // 2, H - h + 18 + 44 * i), ln, font=f, fill=BRANCO, anchor="ma")
    return img


def slide(chave):
    tit, itens = SLIDES[chave]
    img = Image.new("RGB", (W, H), AZUL)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 18, H], fill=LARANJA)
    d.text((140, 150), tit, font=fonte(78, True), fill=BRANCO)
    d.line([140, 270, 900, 270], fill=LARANJA, width=5)
    for i, it in enumerate(itens):
        d.text((140, 330 + 82 * i), it, font=fonte(44), fill=BRANCO)
    d.text((140, 920), "CoastShift v1.0 · Modelo 2 · Costa da Bahia", font=fonte(28), fill=(160, 175, 195))
    return img


def enquadrar(shot, texto):
    img = Image.new("RGB", (W, H), (32, 33, 36))
    shot.thumbnail((W, H - 150))
    img.paste(shot, ((W - shot.width) // 2, 10))
    return legenda(img, texto)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pacote", default=os.path.join(os.path.dirname(REPO), "dados_bahia_v2", "pacotes", "S2_Salvador_BTS"))
    ap.add_argument("--saida", default=os.path.join(os.path.dirname(REPO), "video_app"))
    ap.add_argument("--n", type=int, default=30)
    a = ap.parse_args()
    tmp = os.path.join(a.saida, "_tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(os.path.join(tmp, "frames"))
    dur = {k: tts(v, os.path.join(tmp, f"{k}.wav")) + 0.8 for k, v in NARR.items()}
    print("narração gerada:", {k: round(v, 1) for k, v in dur.items()})
    frames, eventos = [], []                                # eventos: (tempo inicial em s, chave de narração)

    def add_frame(img):
        p = os.path.join(tmp, "frames", f"f{len(frames):05d}.jpg")
        img.save(p, quality=90)
        frames.append(p)

    def add_slide(k):
        eventos.append((len(frames) / FPS, k))
        img = legenda(slide(k), NARR[k])
        for _ in range(int(np.ceil(dur[k] * FPS))):
            add_frame(img)

    for k in ("s1", "s2", "s3"):
        add_slide(k)
    # ----- demonstração no aplicativo
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa: BLE001
        pass
    import app as cs_app
    App = cs_app.App
    gui = App()
    gui.geometry("1600x900+40+40")
    gui.attributes("-topmost", True)
    nb = gui.tab_data.master
    cs_app.filedialog.askopenfilename = lambda **k: os.path.join(a.pacote, "validacao_pontos_dem.csv")
    gui.v_apply_err.set(False)

    def acao(k):
        if k == "a2":
            gui.open_pkg(a.pacote)
        elif k == "a3":
            nb.select(gui.tab_par)
        elif k == "a4":
            nb.select(gui.tab_model)
            gui.model_cb.current(1)
            gui.model_desc.config(text=cs_app.DESC["O2"])
            for s, v in gui.ssp_vars.items():
                v.set(s in ("ssp245", "ssp585"))
            gui.v_years.set("2050,2100")
            gui.ref_cb.set("MHWS")
            gui.v_n.set(str(a.n))
        elif k == "a5":
            gui.result = None
            gui.run()
        elif k == "a6":
            gui.layer_cb.set("[O2] probabilidade_ssp585_2100")
            gui.draw()
        elif k == "a7":
            gui.layer_cb.set("[O2] probabilidade_ssp245_2050")
            gui.draw()
        elif k == "a8":
            nb.select(gui.tab_val)
            gui.val_dem()

    passos = ["a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8"]
    estado = {"i": -1, "t0": 0.0, "f0": 0}

    def tick():
        agora = time.time()
        i = estado["i"]
        tempo_video = (len(frames) - estado["f0"]) / FPS          # duração medida em quadros gravados
        pronto = i < 0 or (tempo_video >= dur[passos[i]] and (passos[i] != "a5" or gui.result is not None))
        if pronto:
            if i + 1 >= len(passos):
                gui.after(800, gui.destroy)
                return
            estado["i"], estado["t0"], estado["f0"] = i + 1, agora, len(frames)
            eventos.append((len(frames) / FPS, passos[i + 1]))
            gui.update_idletasks()
            try:
                acao(passos[i + 1])
            except Exception as e:  # noqa: BLE001  (não interrompe a gravação)
                print("aviso na ação", passos[i + 1], e)
        gui.update_idletasks()
        x, y = gui.winfo_rootx(), gui.winfo_rooty()
        shot = ImageGrab.grab(bbox=(x, y, x + gui.winfo_width(), y + gui.winfo_height()))
        add_frame(enquadrar(shot, NARR[passos[max(estado["i"], 0)]]))
        gui.after(int(1000 / FPS), tick)

    gui.after(1500, tick)
    gui.mainloop()
    add_slide("s4")
    # ----- áudio: narrações posicionadas nos instantes de cada passo
    sr = 22050
    total = int(len(frames) / FPS * sr) + sr
    audio = np.zeros(total, "float32")
    for t, k in eventos:
        with wave.open(os.path.join(tmp, f"{k}.wav")) as w:
            x = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype("float32")
        s = int(t * sr)
        audio[s:s + len(x)] += x[:max(0, total - s)]
    audio = np.clip(audio, -32767, 32767).astype("<i2")
    with wave.open(os.path.join(tmp, "narracao.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(audio.tobytes())
    import imageio_ffmpeg
    out = os.path.join(a.saida, "CoastShift_demo_Modelo2_Bahia.mp4")
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-framerate", str(FPS), "-i",
                    os.path.join(tmp, "frames", "f%05d.jpg"), "-i", os.path.join(tmp, "narracao.wav"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "128k",
                    "-shortest", out], check=True, capture_output=True)
    with open(os.path.join(a.saida, "roteiro_narracao.txt"), "w", encoding="utf-8") as fh:
        for t, k in eventos:
            fh.write(f"[{int(t // 60):02d}:{t % 60:04.1f}] {NARR[k]}\n")
    shutil.copy(os.path.join(tmp, "narracao.wav"), os.path.join(a.saida, "narracao.wav"))
    shutil.rmtree(tmp, ignore_errors=True)
    print("vídeo:", out, f"{len(frames) / FPS:.0f} s")
