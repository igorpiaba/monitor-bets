# Volta das Bets

Acompanha, a cada ~10 minutos, se as casas de apostas regulamentadas no Brasil continuam fora do ar desde a MP nº 1.394/2026: redirecionando para o gov.br ou mostrando um aviso próprio. Avisa num canal do Telegram quando uma casa volta e publica um painel.

- **Painel:** https://igorpiaba.github.io/monitor-bets/
- **Alertas:** canal privado do Telegram (peça o link de convite ao Igor)

## Como funciona

1. **Etapa 1 (HTTP):** se o site redireciona para `brasilsembets.gov.br` → 🔴.
2. **Etapa 2 (navegador real, Playwright):** os demais são abertos e o texto da página é comparado com os marcadores de `dados/marcadores.txt`. Com aviso → 🔴; anti-robô, erro ou página vazia → ⚪; página normal sem aviso → 🟢.
3. Uma mudança só vale depois de **2 checagens seguidas**. Só a volta (🔴 → 🟢) ou um novo bloqueio (🟢 → 🔴) geram alerta.

A checagem roda **no Mac do Igor** (algumas casas bloqueiam só acessos do Brasil, então servidores nos EUA dariam falsos "voltou"). Enquanto o Mac está dormindo ou desligado, não há checagem, e o painel mostra "o monitor pode estar parado".

## Rodar e manter

```bash
python3 -m venv .venv && .venv/bin/pip install httpx playwright pytest
.venv/bin/python -m playwright install chromium
.venv/bin/pytest            # testes
./rodar.sh                  # uma rodada manual (envia alertas e faz push)
```

- **Agendamento (launchd):** `com.igorpiaba.monitor-bets.plist`, instalado em `~/Library/LaunchAgents/`. Log em `.logs/monitor.log`.
  - Parar: `launchctl bootout gui/$(id -u)/com.igorpiaba.monitor-bets`
  - Ligar: `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.igorpiaba.monitor-bets.plist`
- **Token do Telegram:** fica no Keychain do macOS (serviço `monitor-bets-telegram`), nunca no repositório.
- **Atualizar a lista oficial da SPA:** `.venv/bin/python importar_lista.py` (mostra as casas que entraram e saíram).
- **Aviso novo que não é reconhecido:** acrescente uma linha em `dados/marcadores.txt`.
