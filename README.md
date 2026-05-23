# Movimento Raul Livre — vaquinha auditável

Site estático do fundo de apoio ao Raul. Publica entradas (PIX recebidos)
e saídas (uso do fundo) com auditoria pública.

🔗 **https://raulout.pages.dev**

## Como funciona

- **Entradas:** extraídas do extrato bancário oficial, anonimizadas
  (primeiro nome + iniciais) e com hash de 6 caracteres pra quem doou
  conseguir identificar a própria contribuição.
- **Saídas:** lançadas com data, categoria, valor e link pro comprovante.
- **Saldo:** entradas − saídas. Tem que bater com o saldo da conta —
  qualquer divergência é pública.

## Stack

- Site estático em HTML/CSS puro (sem JS)
- Build: `python3 scripts/build.py`
- Host: Cloudflare Pages

## Privacidade

CSVs brutos do banco **nunca** entram no repo (`.gitignore`). Só o output
anonimizado em `site/` é público.
