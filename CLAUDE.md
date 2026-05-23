# raulout — vaquinha auditável do Raul

Site estático que publica entradas (doações via PIX) e saídas (uso do fundo)
do amigo Raul, com auditoria pública e anonimização leve.

## Fluxo

1. Leo exporta extrato bancário (30d, CSV) e coloca em `data/extratos/`.
2. Eu (claude) rodo `python3 scripts/build.py` → regenera `site/*.html`.
3. Commit + push → GitHub Pages publica.

## Estrutura

- `config.json` — chave PIX, nome do recebedor, cutoff da campanha, salt do hash.
- `data/extratos/*.csv` — exports brutos do banco (mantém histórico pra audit).
- `data/saidas.json` — lançamentos de saída (curados manualmente, com comprovante).
- `scripts/build.py` — parse + filtra + dedup + anonimiza + render HTML.
- `site/` — output estático (servido pelo GH Pages).

## Regras

- **Cutoff:** entradas anteriores a `config.campanha_inicio` são ignoradas
  (separa a campanha do uso pessoal/PJ da conta).
- **Filtro de entrada:** só linhas `Pix recebido de ...` viram doação.
- **Dedup:** chave `(datetime, valor, nome_lower)` — exports sobrepostos não duplicam.
- **Anonimização:** `Primeiro + Iniciais` (ex: `Silvio M. V.`) + hash sha256(salt|nome)[:6].
- **Saídas:** sempre com `comprovante_url`. Sem comprovante = não publicar.

## TODO antes de publicar

- [ ] preencher `config.json` com chave PIX real e nome do recebedor
- [ ] decidir host: GH Pages (repo público) — `gh repo create raulout --public`
- [ ] adicionar mais exports conforme rolam (anexar arquivo em `data/extratos/`)
