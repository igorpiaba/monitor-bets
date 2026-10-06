# Monitor Bets — Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Robô no GitHub Actions que checa a cada ~10 min se as ~190 casas regulamentadas ainda redirecionam para o gov.br, avisa as mudanças num canal do Telegram e publica um painel no GitHub Pages.

**Architecture:** Pacote Python `monitor/` com módulos isolados: arquivos (I/O), checar (rede), estado (regras puras), telegram (mensagens) e rodada (orquestração). O estado vive em `dados/*.json|csv` dentro do repositório, gravado por commit a cada rodada. O painel é um HTML estático que lê esses arquivos de `raw.githubusercontent.com`.

**Tech Stack:** Python ≥ 3.12, `httpx` (HTTP, com `httpx.MockTransport` nos testes), `pytest`, `zoneinfo`, GitHub Actions, GitHub Pages, Telegram Bot API, HTML + JS puro.

**Spec:** `docs/superpowers/specs/2026-10-06-monitor-bets-design.md`

## Global Constraints

- Pasta do projeto: `~/projetos/monitor-bets` (**fora** do Google Drive, porque o Git em pasta sincronizada corrompe). Os documentos `docs/superpowers/**` são copiados do Drive para lá na Task 1.
- Python ≥ 3.12; dependências de execução: só `httpx`. Testes: `pytest`.
- Status são exatamente as strings `bloqueado`, `respondendo`, `indeterminado`.
- Host do bloqueio: `brasilsembets.gov.br` e qualquer subdomínio dele (ex.: `www.brasilsembets.gov.br`).
- Timeout 15 s por site; 20 checagens em paralelo; no máximo 10 redirecionamentos.
- Confirmação: 2 observações seguidas. Rodada descartada se > 50% dos sites derem `indeterminado`.
- Fuso de todos os horários: `America/Sao_Paulo`, em ISO 8601 com offset (ex.: `2026-10-06T14:30:00-03:00`).
- Arquivos de dados em UTF-8; `casas.csv` com cabeçalho `casa,site,liminar`; `historico.csv` com cabeçalho `data_hora,casa,site,de,para,motivo`.
- Limite de mensagem do Telegram: 4.096 caracteres.
- Painel avisa "o monitor pode estar parado" quando a última rodada tiver mais de 30 min.
- Segredos só em GitHub Secrets: `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`. URL do painel em variável do repositório `PAINEL_URL`.
- Textos para o usuário em português.

## Review Focus

1. **Site muda de domínio no redirecionamento** (ex.: `betano.bet.br` → `www.betano.bet.br` → gov.br): o caminho inteiro precisa ser seguido até achar o gov.br. Teste na Task 2: `test_redirecionamento_em_cadeia_ate_gov`.
2. **Falha parcial de rede (< 50%) faz vários sites passarem por ⚪ e voltar**: não pode gerar alertas 🔴 "voltou a redirecionar". Teste na Task 3: `test_ida_e_volta_por_indeterminado_nao_gera_alerta`.
3. **Casa adicionada ou removida da lista entre rodadas**: casa nova entra sem alerta, casa removida sai do `status.json`. Teste na Task 3: `test_casa_nova_entra_sem_alerta_e_removida_sai`.
4. **Rodada descartada** precisa preservar as pendências (sem confirmar nem apagar). Teste na Task 3: `test_rodada_descartada_preserva_pendentes`.
5. **Redirecionamento sem cabeçalho `Location`** ou com `Location` relativo (`/home`): não pode quebrar a rodada. Teste na Task 2: `test_location_relativo_e_ausente`.

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `monitor/arquivos.py` | `Casa`; ler `casas.csv`; ler/salvar `status.json`; anexar ao `historico.csv` |
| `monitor/checar.py` | `Resultado`; checar um site; checar todos em paralelo |
| `monitor/estado.py` | `Mudanca`; aplicar a regra de confirmação (função pura, sem I/O) |
| `monitor/telegram.py` | montar mensagens; enviar |
| `monitor/rodada.py` | orquestrar uma rodada; `python -m monitor.rodada` |
| `importar_lista.py` | gerar `dados/casas.csv` a partir das listas da SPA |
| `site/index.html` | painel |
| `.github/workflows/monitor.yml` | robô agendado |
| `.github/workflows/pages.yml` | publicação do painel |
| `tests/test_*.py` | um arquivo por módulo |

---

### Task 1: Projeto, ambiente e leitura/escrita de arquivos

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `README.md`, `monitor/__init__.py`, `monitor/arquivos.py`, `tests/test_arquivos.py`
- Copy: `docs/superpowers/**` do Drive (`.../Meu Drive/Curso Claude Code/monitor-bets/docs`) para o repositório

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class Casa: casa: str; site: str; liminar: bool`
  - `ler_casas(caminho: Path) -> list[Casa]`; `liminar` vem de `sim`/`nao`
  - `escrever_casas(caminho: Path, casas: list[Casa]) -> None`
  - `ler_estado(caminho: Path) -> dict`: devolve `{}` se o arquivo não existir
  - `salvar_estado(caminho: Path, estado: dict) -> None`: JSON com `ensure_ascii=False, indent=2`, chaves de `sites` ordenadas
  - `anexar_historico(caminho: Path, linhas: list[dict]) -> None`: cria com cabeçalho se não existir; cada dict tem as chaves do cabeçalho

- [ ] **Step 1: Preparar a pasta e o Git**

```bash
mkdir -p ~/projetos/monitor-bets && cd ~/projetos/monitor-bets
git init -b main
git config user.name "<usuário do GitHub>"
git config user.email "<ID>+<usuário>@users.noreply.github.com"   # e-mail noreply, em GitHub > Settings > Emails
cp -R "/Users/igor.sa/Library/CloudStorage/GoogleDrive-igorfariadesa.backup@gmail.com/Meu Drive/Curso Claude Code/monitor-bets/docs" .
python3 -m venv .venv && .venv/bin/pip install httpx pytest
```

O `pyproject.toml` declara `requires-python = ">=3.12"`, `dependencies = ["httpx"]` e o extra `dev = ["pytest"]`. O `.gitignore` cobre `.venv/`, `__pycache__/` e `.pytest_cache/`. O `README.md` traz uma frase de descrição e os comandos de teste e de rodada local.

- [ ] **Step 2: Escrever os testes que falham** em `tests/test_arquivos.py`
  - `test_casas_ida_e_volta`: `escrever_casas` seguido de `ler_casas` devolve a mesma lista; o arquivo começa com `casa,site,liminar`; `liminar=True` vira `sim`.
  - `test_ler_estado_inexistente`: `ler_estado(tmp_path / "x.json") == {}`.
  - `test_salvar_estado_utf8`: um estado com `"casa": "Betão"` é gravado com `Betão` literal (sem `ã`) e lido de volta igual.
  - `test_anexar_historico_cria_cabecalho_uma_vez`: dois `anexar_historico` com 1 linha cada → arquivo com 3 linhas, a primeira sendo `data_hora,casa,site,de,para,motivo`.

- [ ] **Step 3: Rodar e ver falhar:** `.venv/bin/pytest tests/test_arquivos.py -v`. Esperado: FAIL (`ModuleNotFoundError`).

- [ ] **Step 4: Implementar `monitor/arquivos.py`** com `csv` e `json` da biblioteca padrão.

- [ ] **Step 5: Rodar e ver passar:** `.venv/bin/pytest -v`. Esperado: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "chore: estrutura do projeto e leitura/escrita de dados"
```

---

### Task 2: Detecção (`checar.py`)

**Files:**
- Create: `monitor/checar.py`, `tests/test_checar.py`

**Interfaces:**
- Produces:
  - constantes `BLOQUEADO = "bloqueado"`, `RESPONDENDO = "respondendo"`, `INDETERMINADO = "indeterminado"`
  - `@dataclass(frozen=True) class Resultado: status: str; motivo: str`
  - `checar(site: str, cliente: httpx.Client) -> Resultado`
  - `checar_todos(sites: list[str], cliente: httpx.Client, paralelo: int = 20) -> dict[str, Resultado]`
  - `novo_cliente() -> httpx.Client`: `follow_redirects=False`, `timeout=15`, User-Agent de Chrome desktop, `Accept-Language: pt-BR`

- [ ] **Step 1: Escrever os testes que falham** em `tests/test_checar.py`, todos usando `httpx.Client(transport=httpx.MockTransport(handler))`:
  - `test_redirect_para_gov`: `302 Location: https://brasilsembets.gov.br/` → `Resultado("bloqueado", "302 -> brasilsembets.gov.br")`.
  - `test_redirect_para_www_gov`: `Location: https://www.brasilsembets.gov.br/` → `bloqueado`.
  - `test_redirecionamento_em_cadeia_ate_gov`: `x.bet.br` 301 → `www.x.bet.br` 302 → gov → `bloqueado`, e o handler **nunca** recebe requisição para o host do gov.
  - `test_200_respondendo`: 200 direto → `Resultado("respondendo", "200")`; e 301 → `www.x.bet.br` 200 → `respondendo`.
  - `test_codigos_indeterminados`: 403, 429 e 503 → `indeterminado` com motivo `"403"`, `"429"`, `"503"`.
  - `test_erros_de_rede`: o handler levanta `httpx.ConnectTimeout` → motivo `"timeout"`; `httpx.ConnectError("[Errno 8] nodename nor servname")` → motivo começando com `"erro de conexão"`.
  - `test_location_relativo_e_ausente`: `302 Location: /home` seguido de 200 em `/home` → `respondendo`; `302` sem `Location` → `indeterminado` com motivo `"302 sem Location"`.
  - `test_excesso_de_redirecionamentos`: 11 redirecionamentos em laço → `indeterminado`, motivo `"redirecionamentos demais"`.
  - `test_checar_todos`: 3 sites → dict com 3 chaves e o status certo de cada um.
  - `test_host_parecido_nao_e_gov`: `Location: https://brasilsembets.gov.br.golpe.com/` → **não** é `bloqueado`.

- [ ] **Step 2: Rodar e ver falhar:** `.venv/bin/pytest tests/test_checar.py -v`. Esperado: FAIL.

- [ ] **Step 3: Implementar `checar` com redirecionamento manual**

O redirecionamento é seguido à mão (o cliente não segue sozinho), para identificar o gov.br **sem precisar baixar a página do governo**:

```
url = f"https://{site}/"
repetir até 10 vezes:
    resp = cliente.get(url)
    se resp.is_redirect:
        loc = resp.headers.get("location"); se vazio → indeterminado "<código> sem Location"
        destino = resp.url.join(loc)
        se destino.host == "brasilsembets.gov.br" ou termina com ".brasilsembets.gov.br":
            → bloqueado, motivo f"{código} -> {destino.host}"
        url = destino; continua
    se 200 <= código < 300 → respondendo, motivo str(código)
    senão → indeterminado, motivo str(código)
esgotou → indeterminado "redirecionamentos demais"
exceções: httpx.TimeoutException → "timeout"; httpx.ConnectError → "erro de conexão: <msg>";
          httpx.HTTPError (demais) → "erro: <classe>"
```

`checar_todos` usa `concurrent.futures.ThreadPoolExecutor(max_workers=paralelo)`; o `httpx.Client` pode ser compartilhado entre threads.

- [ ] **Step 4: Rodar e ver passar:** `.venv/bin/pytest -v`. Esperado: todos passam.

- [ ] **Step 5: Teste manual contra a internet (não automatizado)**

```bash
.venv/bin/python -c "from monitor.checar import *; c=novo_cliente(); print({s: checar(s,c) for s in ['vaidebet.bet.br','betano.bet.br','bet365.bet.br']})"
```

Esperado: as duas primeiras `bloqueado`; a bet365 provavelmente `indeterminado` ("403").

- [ ] **Step 6: Commit:** `git add -A && git commit -m "feat: detecção de bloqueio por redirecionamento"`

---

### Task 3: Regra de confirmação (`estado.py`)

**Files:**
- Create: `monitor/estado.py`, `tests/test_estado.py`

**Interfaces:**
- Consumes: `Casa` (Task 1), `Resultado` e constantes (Task 2)
- Produces:
  - `@dataclass(frozen=True) class Mudanca: data_hora: str; casa: str; site: str; de: str; para: str; motivo: str; desde_anterior: str; alertar: bool`, com `para_dict() -> dict` e `@classmethod de_dict(d: dict) -> Mudanca`
  - `aplicar_rodada(estado: dict, casas: list[Casa], observados: dict[str, Resultado], agora: datetime) -> tuple[dict, list[Mudanca]]`: **não** altera o `estado` recebido (trabalha numa cópia). Devolve o novo estado no formato da spec, seção 6 (`ultima_rodada`, `totais`, `sites`, `avisos_pendentes` preservado como veio), e as mudanças confirmadas nesta rodada.
  - `LIMITE_DESCARTE = 0.5`

Regras (spec, seções 7 e 8):
- Site sem entrada no estado (primeira rodada ou casa nova): entra com o status observado, `desde = agora`, `pendente = None`, `ultimo_definido` = o status se não for `indeterminado`, senão `None`. Sem `Mudanca`.
- Sites que estão no estado mas não em `casas` são removidos.
- `casa` e `liminar` vêm sempre de `casas` (a lista pode ter mudado o nome).
- Confirmação: `Mudanca.alertar = para != INDETERMINADO and para != ultimo_definido`. Ao confirmar para um status definido, `ultimo_definido = para`.
- `desde_anterior` = o `desde` antes da mudança.
- Descarte: se `observados` com status `indeterminado` / `len(observados) > LIMITE_DESCARTE`, devolve uma cópia do estado com só `ultima_rodada` atualizado e a lista de mudanças vazia.
- `ultima_checagem` e `motivo` de cada site são atualizados em toda rodada não descartada.

- [ ] **Step 1: Escrever os testes que falham** em `tests/test_estado.py`. Use um helper `rodada(estado, obs: dict[str, str], minuto: int)` que monta `casas` fixas (`a.bet.br`, `b.bet.br`, `c.bet.br`) e `agora = datetime(2026,10,6,14,minuto,tzinfo=ZoneInfo("America/Sao_Paulo"))`.
  - `test_primeira_rodada_sem_mudancas`: estado `{}` → 3 sites gravados, `[]` de mudanças, `totais == {"bloqueado": 3, "respondendo": 0, "indeterminado": 0}`, `ultima_rodada == "2026-10-06T14:00:00-03:00"`.
  - `test_uma_observacao_so_marca_pendente`: `a` bloqueado → respondendo uma vez → `status` continua `bloqueado`, `pendente["status"] == "respondendo"`, sem mudanças.
  - `test_duas_observacoes_confirmam`: duas seguidas → 1 `Mudanca(de="bloqueado", para="respondendo", alertar=True, desde_anterior=<desde original>)`; `status == "respondendo"`, `desde` = horário da 2ª rodada, `pendente is None`.
  - `test_oscilacao_nao_confirma`: bloqueado → respondendo → bloqueado → nenhuma mudança e `pendente is None`.
  - `test_ida_e_volta_por_indeterminado_nao_gera_alerta`: bloqueado → ⚪ ⚪ (confirma, `alertar=False`) → 🔴 🔴 (confirma, `alertar=False`).
  - `test_indeterminado_para_respondendo_alerta`: bloqueado → ⚪ ⚪ → 🟢 🟢 → a última `Mudanca` tem `de="indeterminado"`, `para="respondendo"`, `alertar=True`.
  - `test_rodada_descartada_preserva_pendentes`: com `a` pendente e 2 de 3 sites ⚪ → nada muda além de `ultima_rodada`; `a` continua pendente.
  - `test_casa_nova_entra_sem_alerta_e_removida_sai`: estado com `a,b,c`, casas agora `a,b,d` → `c` sumiu, `d` entrou, sem mudanças.
  - `test_nao_altera_estado_recebido`: `copy.deepcopy` antes e `==` depois.
  - `test_mudanca_dict_ida_e_volta`: `Mudanca.de_dict(m.para_dict()) == m`.

- [ ] **Step 2: Rodar e ver falhar:** `.venv/bin/pytest tests/test_estado.py -v`.

- [ ] **Step 3: Implementar `monitor/estado.py`**

- [ ] **Step 4: Rodar e ver passar:** `.venv/bin/pytest -v`.

- [ ] **Step 5: Commit:** `git add -A && git commit -m "feat: regra de confirmação de mudanças"`

---

### Task 4: Mensagens e envio no Telegram (`telegram.py`)

**Files:**
- Create: `monitor/telegram.py`, `tests/test_telegram.py`

**Interfaces:**
- Consumes: `Mudanca` (Task 3)
- Produces:
  - `montar_mensagens(mudancas: list[Mudanca], painel_url: str) -> list[str]`: considera só `alertar=True`; devolve `[]` se nenhuma
  - `enviar(mensagens: list[str], token: str, chat_id: str, cliente: httpx.Client) -> bool`: `True` só se todas forem aceitas (`ok: true`)
  - `LIMITE = 4096`

Texto exato (spec, seção 8). Horário formatado como `dd/mm HH:MM`:
- 🟢: `🟢 {casa} ({site}) parou de redirecionar para o gov.br e está respondendo.` Se `de == "bloqueado"`, acrescenta ` Bloqueada desde {desde_anterior}.`
- 🔴: `🔴 {casa} ({site}) voltou a redirecionar para o gov.br.`
- Mensagem: as linhas 🟢 primeiro, depois as 🔴, uma por linha, e no fim uma linha em branco e `Painel: {painel_url}`.
- Divisão: se passar de `LIMITE`, quebra **entre linhas** de mudança; cada parte termina com a linha do painel.

Envio: `POST https://api.telegram.org/bot{token}/sendMessage` com JSON `{"chat_id": ..., "text": ..., "disable_web_page_preview": true}`.

- [ ] **Step 1: Escrever os testes que falham**
  - `test_mensagem_verde_com_desde`: o texto exato de 🟢 para `desde_anterior="2026-09-25T00:10:00-03:00"` termina com `Bloqueada desde 25/09 00:10.`
  - `test_verde_vindo_de_indeterminado_sem_desde`: `de="indeterminado"` → sem o trecho "Bloqueada desde".
  - `test_agrupa_numa_mensagem_verdes_primeiro`: 1 🔴 + 2 🟢 → 1 mensagem, linhas 🟢 antes de 🔴, termina com `Painel: https://x`.
  - `test_ignora_nao_alertaveis`: só mudanças `alertar=False` → `[]`.
  - `test_divide_mensagens_longas`: 200 mudanças → toda mensagem com `len <= 4096`, todas terminando com a linha do painel, e nenhuma linha de mudança perdida ou cortada.
  - `test_enviar_sucesso_e_falha`: `MockTransport` respondendo `{"ok": true}` → `True` e o corpo tem `chat_id` e `text`; respondendo 400/`{"ok": false}` → `False`; `httpx.ConnectError` → `False` (sem exceção).

- [ ] **Step 2: Rodar e ver falhar:** `.venv/bin/pytest tests/test_telegram.py -v`.
- [ ] **Step 3: Implementar `monitor/telegram.py`**
- [ ] **Step 4: Rodar e ver passar:** `.venv/bin/pytest -v`.
- [ ] **Step 5: Commit:** `git add -A && git commit -m "feat: alertas no Telegram"`

---

### Task 5: Orquestração da rodada (`rodada.py`)

**Files:**
- Create: `monitor/rodada.py`, `tests/test_rodada.py`

**Interfaces:**
- Consumes: tudo das Tasks 1–4
- Produces:
  - `executar(pasta_dados: Path, cliente: httpx.Client, agora: datetime, enviar_fn: Callable[[list[str]], bool] | None, painel_url: str) -> list[Mudanca]`
  - `main() -> None`: lê `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` e `PAINEL_URL` do ambiente. Sem token, `enviar_fn=None` (modo local: só imprime as mensagens). Chama `executar(Path("dados"), novo_cliente(), datetime.now(ZoneInfo("America/Sao_Paulo")), ...)` e imprime um resumo de uma linha (totais e número de mudanças).
  - Rodável com `python -m monitor.rodada`.

Fluxo de `executar`:
1. `casas = ler_casas(pasta/"casas.csv")`; `estado = ler_estado(pasta/"status.json")`
2. `observados = checar_todos([c.site for c in casas], cliente)`
3. `novo, mudancas = aplicar_rodada(estado, casas, observados, agora)`
4. `anexar_historico(pasta/"historico.csv", [linhas de cada mudança])`, inclusive as não alertáveis
5. `a_avisar = [Mudanca.de_dict(d) for d in novo["avisos_pendentes"]] + [m for m in mudancas if m.alertar]`
6. Se `a_avisar` e `enviar_fn` → `ok = enviar_fn(montar_mensagens(a_avisar, painel_url))`; se falhar, `novo["avisos_pendentes"] = [m.para_dict() for m in a_avisar]`, senão `[]`. Sem `enviar_fn`, imprime as mensagens e limpa os pendentes.
7. `salvar_estado(pasta/"status.json", novo)`; devolve `mudancas`.

- [ ] **Step 1: Escrever os testes que falham** com `tmp_path`, um `casas.csv` de 2 sites, `MockTransport` e um `enviar_fn` falso que registra as chamadas.
  - `test_primeira_rodada_cria_arquivos`: cria `status.json`, não cria linhas no histórico e não chama `enviar_fn`.
  - `test_mudanca_confirmada_avisa_e_registra`: 3 rodadas (🔴, 🟢, 🟢) → `historico.csv` com 1 linha de dados e `enviar_fn` chamado uma vez com texto contendo `parou de redirecionar`.
  - `test_falha_no_envio_guarda_e_reenvia`: `enviar_fn` devolve `False` → `avisos_pendentes` com 1 item; na rodada seguinte, sem mudanças novas, devolve `True` → é chamado de novo com a mesma mudança e `avisos_pendentes == []`.

- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar `monitor/rodada.py`**
- [ ] **Step 4: Rodar e ver passar:** `.venv/bin/pytest -v`.
- [ ] **Step 5: Commit:** `git add -A && git commit -m "feat: orquestração da rodada"`

---

### Task 6: Importar a lista oficial (`importar_lista.py`)

**Files:**
- Create: `importar_lista.py`, `tests/test_importar_lista.py`, `tests/fixtures/spa.csv`, `tests/fixtures/judicial.csv`
- Create (gerado): `dados/casas.csv`

**Interfaces:**
- Consumes: `Casa`, `ler_casas` e `escrever_casas` (Task 1)
- Produces:
  - `URL_SPA = "https://www.gov.br/fazenda/pt-br/composicao/orgaos/secretaria-de-premios-e-apostas/transparencia-ativa-processos-de-autorizacao-de-apostas-de-quota-fixa/planilha-de-autorizacoes-1.csv"`
  - `URL_JUDICIAL = "https://www.gov.br/fazenda/pt-br/composicao/orgaos/secretaria-de-premios-e-apostas/transparencia-ativa-processos-de-autorizacao-de-apostas-de-quota-fixa/ProcessosjudiciaisSPA04.02.26.csv"`
  - `extrair_pares(texto: str) -> list[tuple[str, str]]`: (marca, domínio)
  - `montar_casas(spa: list[tuple[str,str]], judicial: list[tuple[str,str]]) -> list[Casa]`
  - `validar(casas: list[Casa]) -> None`: levanta `ValueError` com a mensagem do problema
  - `main()`: baixa, monta, valida, mostra a diferença em relação ao `dados/casas.csv` atual e grava

Formato real dos arquivos (conferido em 06/10/2026): UTF-8 com BOM, separador `;`, linhas de título antes do cabeçalho, uma linha por marca e domínio (as linhas de continuação deixam empresa e CNPJ vazios), espaços sobrando nas células. O CSV judicial tem **dois** blocos, cada um com seu cabeçalho. Por isso, `extrair_pares`:
- decodifica com `utf-8-sig` e lê com `csv.reader(delimiter=";")`;
- ao encontrar uma linha que contém `MARCAS` e `DOMÍNIOS`, guarda os índices dessas colunas (vale até o próximo cabeçalho);
- nas linhas seguintes, pega `(marca.strip(), dominio.strip().lower())` quando os dois estão preenchidos;
- descarta domínio `a definir`, ignorando caixa;
- se nenhum cabeçalho for encontrado, levanta `ValueError("cabeçalho MARCAS/DOMÍNIOS não encontrado")`.

`montar_casas`: o nome da casa vira *title case* (`VAIDEBET` → `Vaidebet`); `liminar=True` para os judiciais; domínio repetido fica com a primeira ocorrência, priorizando a SPA; ordena por `casa`.

`validar`: ao menos 100 casas; todo `site` casa com `^[a-z0-9-]+(\.[a-z0-9-]+)+$`.

- [ ] **Step 1: Criar as fixtures:** trechos reais com os mesmos formatos.
  - `spa.csv`: linha de título; cabeçalho `;PORTARIA DE AUTORIZAÇÃO;DENOMINAÇÃO SOCIAL DA EMPRESA;CNPJ;MARCAS;DOMÍNIOS;NÚMERO E ANO DO REQUERIMENTO`; BPX com VAIDEBET, BETPIX365 e OBABET em 3 linhas; uma linha `HILGARDO;a definir`; linhas vazias no fim.
  - `judicial.csv`: os dois blocos reais (ZEROUM/ENERGIA/SPORTVIP com `.bet`, ZONA DE JOGO/APOSTAONLINE/ONLYBETS), incluindo os espaços como `' zeroum.bet'`.
  - Ambos gravados em UTF-8 com BOM.
- [ ] **Step 2: Escrever os testes que falham**
  - `test_extrair_spa`: os pares `[("VAIDEBET","vaidebet.bet.br"), ("BETPIX365","betpix365.bet.br"), ("OBABET","obabet.bet.br")]`, sem o "a definir".
  - `test_extrair_judicial_dois_blocos`: 6 pares, incluindo `("ZEROUM", "zeroum.bet")` sem espaço.
  - `test_sem_cabecalho_erro`: texto `"a;b\n1;2"` → `ValueError`.
  - `test_montar_casas`: `Casa("Vaidebet","vaidebet.bet.br",False)` e `Casa("Zeroum","zeroum.bet",True)`; domínio presente nas duas listas aparece uma vez, com `liminar=False`.
  - `test_validar`: 99 casas válidas → `ValueError`; 100 válidas → ok; um site `"a definir"` → `ValueError`.
- [ ] **Step 3: Rodar e ver falhar.**
- [ ] **Step 4: Implementar `importar_lista.py`**: o download usa `httpx.get(url, timeout=30, headers={"User-Agent": <navegador>}, follow_redirects=True)`, porque o gov.br devolve 404 para clientes sem User-Agent de navegador.
- [ ] **Step 5: Rodar e ver passar:** `.venv/bin/pytest -v`.
- [ ] **Step 6: Gerar a lista real:** `.venv/bin/python importar_lista.py`. Esperado: ~191 casas (185 da SPA + 6 judiciais) e `dados/casas.csv` criado. Abra o arquivo e confira 5 linhas no olho.
- [ ] **Step 7: Commit:** `git add -A && git commit -m "feat: importação da lista oficial da SPA"`

---

### Task 7: Primeira rodada real e publicação no GitHub

**Files:**
- Create (gerados): `dados/status.json`

Esta task depende de ações **do Igor**, marcadas com 👤.

- [ ] **Step 1: Rodada local completa:** `.venv/bin/python -m monitor.rodada`. Esperado: termina em menos de ~1 min, imprime totais com a grande maioria `bloqueado` e grava `dados/status.json`. Guarde uma cópia: `cp dados/status.json /tmp/status-mac.json`.
- [ ] **Step 2: Revisar os indeterminados:** liste os sites `indeterminado` e os motivos. Se algum `respondendo` parecer suspeito (ex.: página "em breve"), anote para discutir; **não** mude a regra sem falar com o Igor.
- [ ] **Step 3: 👤 Instalar e autenticar o GitHub CLI:** `brew install gh` e depois `gh auth login` (GitHub.com → HTTPS → login pelo navegador). Verificar com `gh auth status`.
- [ ] **Step 4: Criar o repositório público e enviar**

```bash
git add -A && git commit -m "dados: primeira rodada local"
gh repo create monitor-bets --public --source . --push
```

Esperado: o repositório aparece em `https://github.com/<usuário>/monitor-bets`.

---

### Task 8: Robô no GitHub Actions + validação de geolocalização

**Files:**
- Create: `.github/workflows/monitor.yml`

Conteúdo decidido:
- Gatilhos: `schedule: - cron: "*/10 * * * *"` e `workflow_dispatch`.
- `permissions: contents: write`; `concurrency: { group: monitor, cancel-in-progress: false }`.
- Passos: checkout → `actions/setup-python` (3.12) → `pip install httpx` → `python -m monitor.rodada` com `env` vindo de `secrets.TELEGRAM_TOKEN`, `secrets.TELEGRAM_CHAT_ID` e `vars.PAINEL_URL` → commit e push de `dados/` como `github-actions[bot]`, com a mensagem `atualiza status`. Só faz commit se `git status --porcelain dados/` não estiver vazio; antes do push, `git pull --rebase`.
- `timeout-minutes: 5`.

- [ ] **Step 1: Escrever `monitor.yml` com o `schedule` comentado**, para que só a execução manual funcione por enquanto. Commit e push.
- [ ] **Step 2: Rodar manualmente:** `gh workflow run monitor.yml` e acompanhar com `gh run watch`. Esperado: sucesso e um commit novo `atualiza status`.
- [ ] **Step 3: Comparar Mac × GitHub:** `git pull` e comparar o `status` de cada site entre `/tmp/status-mac.json` e `dados/status.json`. Esperado: os mesmos `bloqueado`. Qualquer site `bloqueado` no Mac e `respondendo` no GitHub indica bloqueio por país. **Pare e avise o Igor** antes de seguir, porque muda a arquitetura (spec, seção 2).
- [ ] **Step 4: 👤 Criar o bot e o canal do Telegram**
  1. No Telegram, falar com **@BotFather** → `/newbot` → guardar o token.
  2. Criar um **canal** (ex.: "Monitor Bets BR") e adicionar o bot como **administrador** com permissão de publicar.
  3. Publicar qualquer mensagem no canal e descobrir o `chat_id` com `curl "https://api.telegram.org/bot<TOKEN>/getUpdates"`. Ele aparece como `-100…`. Para um canal público, também vale `@nome_do_canal`.
  4. Salvar no repositório: `gh secret set TELEGRAM_TOKEN`, `gh secret set TELEGRAM_CHAT_ID`.
- [ ] **Step 5: Mensagem de teste:** `.venv/bin/python -c "from monitor.telegram import enviar; import httpx,os; print(enviar(['Teste do Monitor Bets ✅'], os.environ['TELEGRAM_TOKEN'], os.environ['TELEGRAM_CHAT_ID'], httpx.Client()))"`, com as duas variáveis exportadas no terminal. Esperado: `True` e a mensagem no canal.
- [ ] **Step 6: Commit** de qualquer ajuste.

---

### Task 9: Painel (`site/index.html`) e publicação no Pages

**Files:**
- Create: `site/index.html`, `.github/workflows/pages.yml`

Decisões:
- Origem dos dados: se `location.hostname` termina em `.github.io`, `usuário = hostname.split(".")[0]` e `repo = pathname.split("/")[1]`, e a base é `https://raw.githubusercontent.com/${usuário}/${repo}/main/dados/`. Caso contrário (teste local), a base é `../dados/`. Adiciona `?t=${Date.now()}` para evitar o cache do navegador.
- Conteúdo (spec, seção 9): placar 🔴/🟢/⚪; "Última checagem: há X min" e faixa amarela `o monitor pode estar parado` acima de 30 min; busca por nome; filtro por status (todos/🔴/🟢/⚪); lista com status, casa, site (link), "há X dias/horas" desde `desde`, etiqueta `liminar`; ordenação por `desde` mais recente primeiro; seção "Últimas mudanças" com as 20 linhas finais do histórico, mais recentes primeiro.
- O `historico.csv` é lido com um parser CSV mínimo: os campos não têm vírgula, exceto talvez `motivo`, que fica por último, então junte o restante da linha nele.
- Atualiza sozinho a cada 5 min.
- Celular primeiro: uma coluna, fonte do sistema, cores em variáveis CSS com suporte a `prefers-color-scheme: dark`, sem bibliotecas externas.
- `pages.yml`: `on: push` em `main` com `paths: ["site/**"]`, mais `workflow_dispatch`; usa `actions/upload-pages-artifact` (path `site`) e `actions/deploy-pages`; `permissions: pages: write, id-token: write`.

- [ ] **Step 1: Escrever `site/index.html`.**
- [ ] **Step 2: Teste local:** `.venv/bin/python -m http.server 8000` na raiz do projeto e abrir `http://localhost:8000/site/`. Conferir: o placar bate com `totais`; busca e filtro funcionam; editando `ultima_rodada` para 1 h atrás num `status.json` temporário, a faixa amarela aparece. Testar também na largura de celular (DevTools, 375 px).
- [ ] **Step 3: Escrever `pages.yml`, fazer commit e push.**
- [ ] **Step 4: 👤 Ativar o Pages:** GitHub → Settings → Pages → Source: **GitHub Actions**. Rodar `gh workflow run pages.yml`.
- [ ] **Step 5: Registrar a URL:** `gh variable set PAINEL_URL --body "https://<usuário>.github.io/monitor-bets/"`. Abrir a URL no celular e conferir que carrega os dados reais.

---

### Task 10: Ligar o agendamento e validar de ponta a ponta

**Files:**
- Modify: `.github/workflows/monitor.yml` (descomentar o `schedule`)
- Modify: `README.md` (link do painel e do canal; como atualizar a lista; como reativar o robô)

- [ ] **Step 1: Descomentar o `schedule`, atualizar o README, fazer commit e push.**
- [ ] **Step 2: Esperar ~30 min** e conferir com `gh run list --workflow monitor.yml`. Esperado: ≥ 2 execuções agendadas com sucesso e commits `atualiza status`.
- [ ] **Step 3: Simular uma volta (teste de ponta a ponta do alerta)**
  1. Adicionar ao `casas.csv` uma linha de teste, `Teste,example.com,nao` (example.com responde 200), fazer commit e push.
  2. Na primeira rodada, ela entra como `respondendo` sem alerta. Isso confirma que casa nova não alerta.
  3. Editar `dados/status.json` direto no GitHub, mudando `example.com` para `"status": "bloqueado"` e `"ultimo_definido": "bloqueado"`.
  4. Em 2 rodadas, deve chegar ao canal: `🟢 Teste (example.com) parou de redirecionar para o gov.br…`, e o histórico ganha uma linha.
  5. Remover a linha de teste do `casas.csv` e fazer commit e push. Ela some do `status.json` na rodada seguinte.
- [ ] **Step 4: Mandar o link do canal e do painel para o Igor** compartilhar com os amigos.
