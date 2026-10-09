# ecowitt-baixar

Baixa os dados de uma estação meteorológica **Ecowitt** usando apenas o **link de compartilhamento** (não precisa ser dono da conta).

Gera os mesmos arquivos `.xlsx` do botão *Export* do site ecowitt.net, **um arquivo por dia**, nas unidades °C, hPa, m/s, mm e W/m².

- Resolução: a que a nuvem ainda guardar (5 min nos últimos ~90 dias, 30 min antes disso).
- Horário: o local da estação, como no site.
- Só baixa os dias que ainda não existem na pasta; nunca sobrescreve.
- Usa só a biblioteca padrão do Python 3.9+ (nada para instalar).

## Uso

Com janela (cole o link, escolha a data inicial e a pasta):

```bash
python ecowitt_baixar.py
```

A janela tem duas abas:

- **Baixar**: link, data inicial e pasta. O programa lembra o último link e a última pasta usados (em `~/.ecowitt_baixar.json`, fora do repositório). Se o link mudar, é só colar o novo.
- **Sobre**: dados da estação (edite o texto `SOBRE` no início do script) e o botão *Consultar estação pelo link*, que mostra o que a Ecowitt informa sobre a estação compartilhada.

Se a data inicial tiver mais de 90 dias, o programa avisa que esses dias vêm com resolução de 30 min em vez de 5 min.

Sem janela (útil para o Agendador de Tarefas / cron):

```bash
python ecowitt_baixar.py "LINK_DE_COMPARTILHAMENTO" 19/06/2026 [PASTA]
```

Se a pasta não for informada, os arquivos vão para `dados/` ao lado do script.

Teste rápido das funções internas:

```bash
python ecowitt_baixar.py --teste
```

## Atenção

Não coloque o link de compartilhamento da sua estação no repositório: quem tiver o link consegue ver os dados.
