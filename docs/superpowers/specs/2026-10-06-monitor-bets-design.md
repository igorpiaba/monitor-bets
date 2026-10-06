# Monitor Bets — Especificação de design

**Data:** 2026-10-06
**Autor:** Igor (com Claude)
**Status:** aguardando revisão

## 1. Objetivo

Acompanhar a volta das casas de apostas regulamentadas no Brasil depois do bloqueio imposto pela Medida Provisória nº 1.394/2026 (em vigor desde 25/09/2026).

- **Uso principal:** projeto do curso de Claude Code (aprender Python, Git, GitHub Actions, GitHub Pages e a API do Telegram).
- **Uso secundário:** compartilhar com amigos do mercado de apostas.
- **Sucesso:** quando uma casa deixar de redirecionar para o gov.br, os amigos ficam sabendo pelo Telegram em até ~30 minutos, sem alarme falso, e o painel mostra o estado de todas as casas e há quanto tempo cada uma está assim.

## 2. Contexto técnico (verificado em 06/10/2026)

- Os domínios das casas (`*.bet.br`) seguem resolvendo DNS normalmente, para os servidores das próprias casas (Cloudflare, etc.), e retornam o mesmo resultado em resolvedores diferentes.
- Os servidores das casas respondem com HTTP 301/302 para `brasilsembets.gov.br` (ou `www.brasilsembets.gov.br`). O bloqueio é feito **pelas próprias casas**, e não pelo provedor de internet.
- Algumas casas têm proteção anti-robô (por exemplo, `www.bet365.bet.br` respondeu 403).
- Consequência: a checagem em princípio funciona de qualquer lugar. Isso **precisa ser confirmado** a partir dos servidores do GitHub (EUA) antes de ligar o robô (ver seção 11).

## 3. Decisões

| Tema | Decisão |
|---|---|
| Abordagem | Script próprio em Python + painel estático |
| Execução | GitHub Actions, agendado a cada ~10 min (o GitHub pode atrasar até ~15 min) |
| Painel | GitHub Pages |
| Alertas | Canal do Telegram, via bot |
| Lista de casas | Lista oficial da SPA/Fazenda + lista de autorizadas por decisão judicial (com etiqueta "liminar") |
| Repositório | Público, na conta pessoal do GitHub, com e-mail de commit "noreply" |
| Custo | Zero (repositório público) |

## 4. Estrutura do repositório

```
monitor-bets/
├── dados/
│   ├── casas.csv          # lista a monitorar
│   ├── status.json        # estado atual (lido pelo painel)
│   └── historico.csv      # mudanças confirmadas
├── monitor/
│   ├── checar.py          # checa um domínio e classifica
│   ├── estado.py          # aplica a regra de confirmação e gera mudanças
│   ├── telegram.py        # monta e envia as mensagens
│   └── rodada.py          # ponto de entrada: uma rodada completa
├── importar_lista.py      # gera dados/casas.csv a partir das listas oficiais
├── site/
│   └── index.html         # painel (HTML + JS puro)
├── tests/
└── .github/workflows/
    ├── monitor.yml        # robô agendado
    └── pages.yml          # publica o painel
```

Cada módulo tem uma responsabilidade: `checar.py` não sabe de estado, `estado.py` não faz rede, e `telegram.py` só formata e envia. Assim cada um pode ser testado sem os outros.

## 5. Detecção

**Entrada:** um domínio. **Saída:** status + motivo.

- Requisição GET para `https://<site>/`, com User-Agent de navegador, seguindo redirecionamentos e registrando cada salto.
- Timeout de 15 s por site, ~20 checagens em paralelo. Uma rodada completa deve levar menos de 1 minuto.

| Status | Regra |
|---|---|
| `bloqueado` 🔴 | Algum salto ou URL final tem host `brasilsembets.gov.br` ou um subdomínio dele |
| `respondendo` 🟢 | Resposta final 2xx sem passar pelo gov.br |
| `indeterminado` ⚪ | 403, 429, 5xx, outro código, timeout, falha de DNS, erro de TLS. O motivo é registrado |

O status se chama "respondendo", e não "voltou", porque o script mede só que o site parou de redirecionar e abriu, e não que voltou a aceitar apostas. As mensagens dizem exatamente isso.

## 6. Dados

### `dados/casas.csv`

Colunas: `casa, site, liminar`

- `casa`: nome da marca (ex.: `Betano`)
- `site`: domínio (ex.: `betano.bet.br`). Uma linha por domínio, então uma marca com dois domínios tem duas linhas.
- `liminar`: `sim` ou `nao`

Gerado por `importar_lista.py`, que roda **manualmente**:
- Baixa o CSV da lista de empresas autorizadas e a lista de autorizadas por determinação judicial, ambas da página de lista de empresas da SPA.
- Extrai marca e domínio(s) e junta as duas listas.
- Ignora domínios marcados como "a definir" (3 casos na lista de 01/10/2026).
- Valida o resultado: colunas `MARCAS` e `DOMÍNIOS` encontradas, ao menos 100 linhas, todo domínio com formato de nome de domínio válido. Nem todos terminam em `.bet.br`: a lista judicial tem domínios `.bet`, como `zeroum.bet`. Se falhar, para com erro e **não** sobrescreve o arquivo.
- Mostra a diferença em relação ao arquivo anterior (casas adicionadas ou removidas).

### `dados/status.json`

```json
{
  "ultima_rodada": "2026-10-06T14:30:00-03:00",
  "totais": {"bloqueado": 182, "respondendo": 3, "indeterminado": 5},
  "sites": {
    "betano.bet.br": {
      "casa": "Betano",
      "liminar": false,
      "status": "bloqueado",
      "desde": "2026-09-25T00:10:00-03:00",
      "motivo": "302 -> brasilsembets.gov.br",
      "ultima_checagem": "2026-10-06T14:30:00-03:00",
      "ultimo_definido": "bloqueado",
      "pendente": null
    }
  },
  "avisos_pendentes": []
}
```

- `pendente`: `{"status": "...", "visto_em": "..."}` quando um status diferente foi visto uma única vez e ainda espera confirmação.
- `ultimo_definido`: o último status `bloqueado` ou `respondendo` confirmado (ignora passagens por `indeterminado`). Serve para não alertar quando um site vai de 🔴 para ⚪ e volta para 🔴.
- `avisos_pendentes`: mudanças confirmadas cujo envio ao Telegram falhou.

### `dados/historico.csv`

Colunas: `data_hora, casa, site, de, para, motivo`. Uma linha por mudança **confirmada**.

Todos os horários usam o fuso `America/Sao_Paulo`.

O robô faz commit do `status.json` a cada rodada (*git scraping*), com mensagem padronizada ("atualiza status").

## 7. Regra de confirmação (`estado.py`)

Para cada site, comparando o status observado com o status atual:

1. Observado = atual → limpa `pendente`.
2. Observado ≠ atual e `pendente` vazio ou com outro status → grava `pendente` com o observado.
3. Observado ≠ atual e `pendente` com o mesmo status → **confirma a mudança**: atualiza `status` e `desde`, limpa `pendente`, acrescenta linha no histórico e gera um aviso (exceto quando o novo status for `indeterminado`).

**Proteção contra falha de rede:** se mais de 50% dos sites derem `indeterminado` na mesma rodada, a rodada é descartada. Nada muda além de `ultima_rodada`, e nenhum aviso sai.

**Primeira rodada (sem `status.json`):** o status observado vira o status inicial, sem pendência e sem aviso.

## 8. Alertas (`telegram.py`)

- Destino: um canal do Telegram em que o bot é administrador. Os amigos entram pelo link de convite.
- Credenciais `TELEGRAM_TOKEN` e `TELEGRAM_CHAT_ID` ficam nos **Secrets** do GitHub, nunca no código.
- **Uma mensagem por rodada** com todas as mudanças confirmadas, agrupadas:
  - 🟢 "Betano (betano.bet.br) parou de redirecionar para o gov.br e está respondendo. Bloqueada desde 25/09 00:10."
  - 🔴 "Betano (betano.bet.br) voltou a redirecionar para o gov.br."
- Mudanças para `indeterminado` não geram alerta.
- Uma mudança só gera alerta se o novo status for diferente de `ultimo_definido`. Exemplo: 🔴 → ⚪ → 🔴 não avisa nada; 🔴 → ⚪ → 🟢 avisa a volta.
- Toda mensagem termina com o link do painel.
- Se o envio falhar, as mudanças vão para `avisos_pendentes` e são reenviadas na rodada seguinte.
- Mensagens longas são divididas no limite do Telegram (4.096 caracteres).

## 9. Painel (`site/index.html`)

Uma página, responsiva (celular primeiro), em HTML + JavaScript puro, que lê `dados/status.json` e `dados/historico.csv` direto de `raw.githubusercontent.com` (o cache do GitHub pode atrasar até ~5 min). Assim o painel só precisa ser republicado quando o próprio `index.html` mudar.

- **Topo:** placar (🔴 / 🟢 / ⚪) e "Última checagem: há X min". Acima de 30 min, mostra o aviso amarelo "o monitor pode estar parado".
- **Lista:** uma linha por site, com status, casa, site, "há quanto tempo" e a etiqueta `liminar`. Ordenada pela mudança mais recente; o restante, em ordem alfabética. Tem busca por nome e filtro por status.
- **Últimas mudanças:** as 20 linhas mais recentes do histórico.
- **Fora do escopo (v2):** gráficos, página por casa, alternância de tema.

## 10. Erros

| Situação | Comportamento |
|---|---|
| Um site falha | Fica `indeterminado` com o motivo; a rodada continua |
| Mais de 50% falham | Rodada descartada (seção 7) |
| O Telegram falha | Reenvio na próxima rodada (seção 8) |
| O robô para | Aviso no painel; o GitHub manda e-mail em caso de falha. Reativar o workflow se o GitHub pausar por inatividade (60 dias) |
| `importar_lista.py` recebe um formato inesperado | Para com erro e não sobrescreve `casas.csv` |

## 11. Testes

Testes automatizados com `pytest`, sem acesso à internet (respostas HTTP simuladas):

- **Detecção:** redirecionamento para o gov (com e sem `www`) → `bloqueado`; 200 → `respondendo`; 403, 429, 5xx, timeout, DNS e TLS → `indeterminado` com o motivo certo.
- **Confirmação:** 1 observação não muda; 2 seguidas mudam; A→B→A não gera nada; primeira rodada não gera aviso; mais de 50% de indeterminados descarta a rodada.
- **Alertas:** agrupamento numa só mensagem; nenhum aviso para `indeterminado`; divisão de mensagens longas; reenvio dos pendentes.
- **Importação:** um CSV de exemplo gera `casas.csv` correto; um formato inválido não sobrescreve.

**Validação manual, antes de ligar o agendamento:**
1. Uma rodada completa a partir do Mac e outra a partir do GitHub Actions (execução manual). Comparar os status e investigar qualquer diferença (possível bloqueio por geolocalização).
2. Um alerta de teste no canal do Telegram.
3. O painel publicado aberto no celular.

## 12. Fora do escopo

- Saber se a casa voltou a **aceitar apostas** (só medimos se o site abre).
- Checagem com intervalo menor que ~10 min.
- Outros canais de alerta (WhatsApp, e-mail, Slack).
- Banco de dados externo.
