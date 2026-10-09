"""
Baixador de dados Ecowitt pelo LINK DE COMPARTILHAMENTO (não precisa ser dono da conta).

Gera o mesmo .xlsx do botão "Export" do site, um arquivo por dia, em °C, hPa, m/s,
mm e W/m², com o mesmo nome do site, ex.:
    EasyWeatherPro-8D9C1E(202607140000-202607142359).xlsx

- Resolução: a que a nuvem ainda tiver (5 min nos últimos ~90 dias, 30 min antes).
- Horário: o local da estação, como no site.
- Só baixa os dias que ainda não existem na pasta; nunca sobrescreve.
- A janela lembra o último link e a última pasta usados (em ~/.ecowitt_baixar.json,
  fora do repositório).

Uso:
    python ecowitt_baixar.py                                    # abre a janela
    python ecowitt_baixar.py LINK 19/06/2026 [PASTA]            # sem janela (agendador)

Só usa a biblioteca padrão do Python 3.9+.
"""

import json
import sys
import threading
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

# Edite este texto com os dados da sua estação; ele aparece na aba "Sobre".
SOBRE = """Baixador de dados Ecowitt

Estação: Ecowitt (modelo: preencher)
Local: (preencher)
Responsável: (preencher)
"""

DIAS_ALTA_RESOLUCAO = 90
AVISO_90 = (f"A nuvem da Ecowitt só guarda dados a cada 5 min nos últimos ~{DIAS_ALTA_RESOLUCAO} dias. "
            "Dias mais antigos vêm com resolução de 30 min.")

SITE = "https://www.ecowitt.net"
# Unidades: temperatura °C (1), pressão hPa (3), vento m/s (6), chuva mm (12), radiação W/m² (16)
COOKIE = "; ".join(
    f"ousaite_unit_cookie_{k}={v}" for k, v in {1: 1, 2: 3, 3: 6, 4: 12, 5: 16}.items()
)
CABECALHOS = {"Cookie": COOKIE, "User-Agent": "Mozilla/5.0"}
CONFIG = Path.home() / ".ecowitt_baixar.json"


def post(caminho, dados):
    req = urllib.request.Request(
        SITE + caminho, data=urllib.parse.urlencode(dados).encode(),
        headers={**CABECALHOS, "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def ler_data(texto):
    """dd/mm/aaaa (também aceita dd-mm-aaaa e dd.mm.aaaa)."""
    t = texto.strip().replace("-", "/").replace(".", "/")
    return datetime.strptime(t, "%d/%m/%Y").date()


def codigo_do_link(link):
    """Aceita o link inteiro (…share?authorize=ABC123…) ou só o código."""
    link = link.strip()
    q = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
    return q["authorize"][0] if "authorize" in q else link


def antigo(dia):
    """True se o dia já saiu da janela de alta resolução da nuvem."""
    return dia < date.today() - timedelta(days=DIAS_ALTA_RESOLUCAO)


def dispositivos(authorize):
    """Dados brutos das estações compartilhadas por esse link (como o site devolve)."""
    lista = post("/index/get_device_list", {"authorize": authorize}).get("list") or []
    if not lista:
        raise RuntimeError("Link inválido ou sem estações. Confira o link de compartilhamento.")
    return lista


def estacoes(authorize):
    """Lista [(device_id, nome)] das estações compartilhadas por esse link."""
    return [(d["device_id"], d["name"]) for d in dispositivos(authorize)]


def baixar_dia(authorize, device_id, dia, pasta):
    for tentativa in range(3):
        try:
            resp = post(f"/index/export_excel?time={int(time.time() * 1000)}", {
                "device_id": device_id, "authorize": authorize, "mode": 0,
                "sdate": f"{dia} 00:00", "edate": f"{dia} 23:59",
                "sortList": "1|3|4|5|6", "hideList": "",
            })
            if str(resp.get("errcode")) != "0" or not resp.get("url"):
                raise RuntimeError(f"resposta do site: {resp.get('errmsg')}")
            url = resp["url"]
            with urllib.request.urlopen(urllib.request.Request(url, headers=CABECALHOS), timeout=60) as r:
                conteudo = r.read()
            if not conteudo.startswith(b"PK"):  # todo .xlsx é um zip
                raise RuntimeError("o arquivo recebido não é um .xlsx")
            destino = pasta / urllib.parse.unquote(url.rsplit("/", 1)[-1])
            destino.write_bytes(conteudo)
            return destino.name
        except Exception as erro:
            ultimo = erro
            time.sleep(10 * (tentativa + 1))
    raise RuntimeError(f"falhou 3 vezes ({ultimo})")


def baixar(link, inicio, pasta, log=print, parar=lambda: False):
    """Baixa de `inicio` até ontem tudo o que falta na pasta."""
    authorize = codigo_do_link(link)
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    fim = date.today() - timedelta(days=1)
    if antigo(inicio):
        log(f"ATENÇÃO: {AVISO_90}")
    falhas = 0
    for device_id, nome in estacoes(authorize):
        log(f"Estação {nome}: {inicio:%d/%m/%Y} a {fim:%d/%m/%Y}")
        dia = inicio
        while dia <= fim and not parar():
            if not any(pasta.glob(f"{nome}({dia:%Y%m%d}0000-*.xlsx")):
                try:
                    res = " (30 min)" if antigo(dia) else ""
                    log(f"  {dia:%d/%m/%Y}  ok{res}  {baixar_dia(authorize, device_id, dia, pasta)}")
                except RuntimeError as erro:
                    falhas += 1
                    log(f"  {dia:%d/%m/%Y}  ERRO: {erro}")
                time.sleep(2)  # gentileza com o servidor
            dia += timedelta(days=1)
    log("Interrompido." if parar() else
        f"Concluído. {'Rode de novo para tentar os ' + str(falhas) + ' dias com erro.' if falhas else 'Nenhum erro.'}")


def janela():
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk

    raiz = tk.Tk()
    raiz.title("Baixar dados Ecowitt")
    abas = ttk.Notebook(raiz)
    abas.pack(fill="both", expand=True)
    aba_baixar, aba_sobre = tk.Frame(abas), tk.Frame(abas)
    abas.add(aba_baixar, text="Baixar")
    abas.add(aba_sobre, text="Sobre")

    # ---- aba Baixar ----
    try:
        salvo = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        salvo = {}
    padrao = {
        "Link de compartilhamento": salvo.get("link", ""),
        "Baixar a partir de (dd/mm/aaaa)": f"{date.today() - timedelta(days=30):%d/%m/%Y}",
        "Pasta de destino": salvo.get("pasta", str(Path.home() / "Documents" / "dados_ecowitt")),
    }
    campos = {}
    for i, (rotulo, valor) in enumerate(padrao.items()):
        tk.Label(aba_baixar, text=rotulo).grid(row=i, column=0, sticky="w", padx=6, pady=3)
        e = tk.Entry(aba_baixar, width=60)
        e.insert(0, valor)
        e.grid(row=i, column=1, padx=6, pady=3)
        campos[rotulo] = e

    def escolher_pasta():
        p = filedialog.askdirectory()
        if p:
            campos["Pasta de destino"].delete(0, "end")
            campos["Pasta de destino"].insert(0, p)

    tk.Button(aba_baixar, text="…", command=escolher_pasta).grid(row=2, column=2, padx=6)

    saida = scrolledtext.ScrolledText(aba_baixar, width=90, height=20, state="disabled")
    saida.grid(row=4, column=0, columnspan=3, padx=6, pady=6)

    def log(msg):  # chamado da thread de download; o Tk só pode ser mexido na thread principal
        raiz.after(0, lambda: (saida.configure(state="normal"), saida.insert("end", msg + "\n"),
                               saida.see("end"), saida.configure(state="disabled")))

    parar = threading.Event()

    def iniciar():
        link = campos["Link de compartilhamento"].get().strip()
        pasta = campos["Pasta de destino"].get()
        try:
            inicio = ler_data(campos["Baixar a partir de (dd/mm/aaaa)"].get())
        except ValueError:
            return log("Data inválida. Use o formato dd/mm/aaaa, ex.: 19/06/2026")
        if not link:
            return log("Cole o link de compartilhamento da estação.")
        if antigo(inicio) and not messagebox.askokcancel("Atenção", AVISO_90 + "\n\nContinuar?"):
            return
        try:
            CONFIG.write_text(json.dumps({"link": link, "pasta": pasta}), encoding="utf-8")
        except OSError:
            pass  # lembrar o link é só conveniência
        parar.clear()
        botao.configure(state="disabled")

        def trabalho():
            try:
                baixar(link, inicio, pasta, log, parar.is_set)
            except Exception as erro:
                log(f"ERRO: {erro}")
            raiz.after(0, lambda: botao.configure(state="normal"))

        threading.Thread(target=trabalho, daemon=True).start()

    botao = tk.Button(aba_baixar, text="Baixar", width=15, command=iniciar)
    botao.grid(row=3, column=1, sticky="w", padx=6)
    tk.Button(aba_baixar, text="Parar", width=15, command=parar.set).grid(row=3, column=1, sticky="e", padx=6)

    # ---- aba Sobre ----
    tk.Label(aba_sobre, text=SOBRE + "\n" + AVISO_90, justify="left", wraplength=620).pack(
        anchor="w", padx=10, pady=10)
    info = scrolledtext.ScrolledText(aba_sobre, width=90, height=14, state="disabled")

    def escrever_info(msg):
        info.configure(state="normal")
        info.delete("1.0", "end")
        info.insert("end", msg)
        info.configure(state="disabled")

    def consultar():
        link = campos["Link de compartilhamento"].get().strip()
        if not link:
            return escrever_info("Cole o link na aba Baixar.")
        escrever_info("Consultando…")

        def trabalho():
            try:
                linhas = []
                for d in dispositivos(codigo_do_link(link)):
                    linhas += [f"{k}: {v}" for k, v in d.items()
                               if isinstance(v, (str, int, float)) and str(v) != ""]
                    linhas.append("")
                msg = "\n".join(linhas)
            except Exception as erro:
                msg = f"ERRO: {erro}"
            raiz.after(0, lambda: escrever_info(msg))

        threading.Thread(target=trabalho, daemon=True).start()

    tk.Button(aba_sobre, text="Consultar estação pelo link", command=consultar).pack(anchor="w", padx=10)
    info.pack(padx=10, pady=6)
    raiz.mainloop()


if __name__ == "__main__":
    if len(sys.argv) == 1:
        janela()
    elif sys.argv[1:] == ["--teste"]:
        assert codigo_do_link("https://www.ecowitt.net/home/share?authorize=ABC123&device_id=x") == "ABC123"
        assert codigo_do_link("ABC123") == "ABC123"
        assert ler_data(" 19/06/2026 ") == ler_data("19-06-2026") == date(2026, 6, 19)
        assert antigo(date.today() - timedelta(days=91)) and not antigo(date.today() - timedelta(days=89))
        print("ok")
    else:
        pasta = sys.argv[3] if len(sys.argv) > 3 else Path(__file__).resolve().parent / "dados"
        baixar(sys.argv[1], ler_data(sys.argv[2]), pasta)
