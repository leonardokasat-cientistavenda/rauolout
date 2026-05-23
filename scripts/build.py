#!/usr/bin/env python3
"""raulout — build estático.

Pipeline:
  data/extratos/*.csv (exports do banco)
  data/saidas.json    (lançamentos de saída mantidos pelo curador)
  config.json         (config da campanha)
            ↓
  parse + filtra + dedup + anonimiza
            ↓
  site/index.html, entradas.html, saidas.html, contribuir.html
"""
from __future__ import annotations
import csv
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from html import escape

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SITE = ROOT / "site"
CFG = json.loads((ROOT / "config.json").read_text())

CUTOFF = datetime.fromisoformat(CFG["campanha_inicio"])
SALT = CFG["hash_salt"]

# ── Parsing ───────────────────────────────────────────────────────────────────

VALOR_RE = re.compile(r"-?R\$\s*([\d\.]+),(\d{2})")
PIX_RECEBIDO_RE = re.compile(r"^Pix recebido de\s+(.+?)\s*$", re.IGNORECASE)


def parse_valor(s: str) -> float:
    m = VALOR_RE.search(s)
    if not m:
        return 0.0
    inteiro = m.group(1).replace(".", "")
    cents = m.group(2)
    sign = -1.0 if s.strip().startswith("-") else 1.0
    return sign * float(f"{inteiro}.{cents}")


def parse_data(d: str, h: str) -> datetime:
    # 23/05/26 13:19:35
    return datetime.strptime(f"{d} {h}", "%d/%m/%y %H:%M:%S")


def anonimiza_nome(nome: str) -> str:
    """'Silvio Moura Velho' -> 'Silvio M. V.'  |  'Joao' -> 'Joao'"""
    partes = [p for p in re.split(r"\s+", nome.strip()) if p]
    if not partes:
        return "—"
    if len(partes) == 1:
        return partes[0]
    primeiro = partes[0]
    iniciais = " ".join(f"{p[0].upper()}." for p in partes[1:] if p[0].isalpha())
    return f"{primeiro} {iniciais}".strip()


def hash_curto(nome: str) -> str:
    h = hashlib.sha256(f"{SALT}|{nome.strip().lower()}".encode()).hexdigest()
    return h[:6]


# ── Coleta entradas ───────────────────────────────────────────────────────────

def coletar_entradas() -> list[dict]:
    entradas: list[dict] = []
    vistos: set[tuple] = set()  # dedup por (datetime, valor, nome)
    for csv_path in sorted((DATA / "extratos").glob("*.csv")):
        with csv_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                desc = (row.get("Descricao") or "").strip()
                m = PIX_RECEBIDO_RE.match(desc)
                if not m:
                    continue
                nome = m.group(1)
                dt = parse_data(row["Data"], row["Hora"])
                if dt < CUTOFF:
                    continue
                valor = parse_valor(row.get("Valor", ""))
                if valor <= 0:
                    continue
                key = (dt.isoformat(), valor, nome.lower())
                if key in vistos:
                    continue
                vistos.add(key)
                entradas.append({
                    "datetime": dt.isoformat(),
                    "data": dt.strftime("%d/%m/%Y"),
                    "hora": dt.strftime("%H:%M"),
                    "nome_anon": anonimiza_nome(nome),
                    "hash": hash_curto(nome),
                    "valor": valor,
                })
    entradas.sort(key=lambda x: x["datetime"], reverse=True)
    return entradas


def coletar_saidas() -> list[dict]:
    raw = json.loads((DATA / "saidas.json").read_text()).get("saidas", [])
    out = []
    for s in raw:
        dt = datetime.fromisoformat(s["data"])
        out.append({
            "datetime": dt.isoformat(),
            "data": dt.strftime("%d/%m/%Y"),
            "categoria": s.get("categoria", "outros"),
            "descricao": s.get("descricao", ""),
            "valor": float(s["valor"]),
            "comprovante_url": s.get("comprovante_url"),
        })
    out.sort(key=lambda x: x["datetime"], reverse=True)
    return out


# ── Render ────────────────────────────────────────────────────────────────────

def fmt_brl(v: float) -> str:
    s = f"{abs(v):,.2f}"
    s = s.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {s}"


CATEGORIA_LABEL = {
    "advogado": "Advogado / honorários",
    "pensao": "Pensão alimentícia",
    "familia": "Família / sustento",
    "custas": "Custas judiciais",
    "outros": "Outros",
}

CSS = """
:root {
  --bg: #0E0D0B; --paper: #18160F; --paper-2: #221E14;
  --ink: #F8F4EC; --ink-soft: #D8CFC0; --muted: #8B7F6D; --muted-light: #5C5446;
  --gold: #F5B82E; --gold-dark: #C9971F; --amber: #E89B2C;
  --line: rgba(245,184,46,0.18); --line-strong: rgba(245,184,46,0.35);
  --in: #F5B82E; --out: #E05548;
}
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: 'Nunito Sans', -apple-system, sans-serif; background:var(--bg); color:var(--ink); line-height:1.6;
  background-image: radial-gradient(ellipse at top, rgba(245,184,46,0.06), transparent 60%); }

.topbar { background:rgba(14,13,11,0.92); backdrop-filter:blur(8px);
  border-bottom:1px solid var(--line); padding:14px 32px;
  display:flex; align-items:center; gap:16px; position:sticky; top:0; z-index:50; }
.topbar-brand { font-family:'Anton', sans-serif; font-weight:400; color:var(--ink); font-size:20px;
  letter-spacing:0.04em; text-transform:uppercase; }
.topbar-brand em { font-style:normal; color:var(--gold); }
.topbar-path { font-family:'JetBrains Mono', monospace; font-size:11px; color:var(--muted); flex:1;
  letter-spacing:0.08em; text-transform:uppercase; }
.topbar-links { display:flex; gap:8px; }
.topbar-links a { font-family:'JetBrains Mono', monospace; font-size:11px; font-weight:700;
  color:var(--ink-soft); text-decoration:none; padding:6px 12px; border:1px solid var(--line);
  border-radius:4px; letter-spacing:0.12em; text-transform:uppercase; transition:all .15s; }
.topbar-links a:hover, .topbar-links a.active { background:var(--gold); border-color:var(--gold); color:#0E0D0B; }

.updated-bar { background:rgba(245,184,46,0.06); border-bottom:1px solid var(--line);
  padding:8px 32px; font-family:'JetBrains Mono', monospace; font-size:11px;
  color:var(--ink-soft); letter-spacing:0.08em; text-transform:uppercase;
  display:flex; justify-content:center; align-items:center; gap:8px; }
.updated-bar::before { content:''; width:8px; height:8px; border-radius:50%;
  background:var(--gold); box-shadow:0 0 8px var(--gold); animation:pulse 2s ease-in-out infinite; }
.updated-bar strong { color:var(--gold); font-weight:700; }
@keyframes pulse { 0%, 100% { opacity:1; } 50% { opacity:0.5; } }

/* hero with image */
.hero-image { position:relative; max-width:720px; margin:24px auto 0; overflow:hidden; border-radius:12px;
  border:1px solid var(--line); }
.hero-image img { width:100%; display:block; max-height:320px; object-fit:cover; object-position:center 22%; }
.hero-image::after { content:''; position:absolute; left:0; right:0; bottom:0; height:80px;
  background:linear-gradient(180deg, transparent, rgba(14,13,11,0.9)); pointer-events:none; }

.hero { max-width:1100px; margin:0 auto; padding:32px 48px 28px; }
.hero.no-image { padding-top:72px; }
.eyebrow { font-family:'JetBrains Mono', monospace; font-size:12px; font-weight:700; color:var(--gold);
  letter-spacing:0.22em; text-transform:uppercase; margin-bottom:18px; display:inline-block;
  padding:6px 14px; border:1px solid var(--line-strong); border-radius:4px; background:rgba(245,184,46,0.06); }
.hero h1 { font-family:'Anton', sans-serif; font-size:96px; font-weight:400;
  letter-spacing:0.005em; line-height:0.95; color:var(--ink); margin-bottom:22px;
  text-transform:uppercase; }
.hero h1 em { font-style:normal; color:var(--gold);
  text-shadow:0 0 32px rgba(245,184,46,0.35); }
.hero .subtitle { font-family:'Nunito', sans-serif; font-size:21px; font-weight:600;
  color:var(--ink-soft); max-width:820px; line-height:1.35; margin-bottom:28px; }
.hero .meta { font-family:'JetBrains Mono', monospace; font-size:12px; color:var(--muted);
  letter-spacing:0.06em; border-top:1px solid var(--line); padding-top:18px; }
.hero .meta strong { color:var(--gold); font-weight:700; }

section { max-width:1100px; margin:0 auto; padding:40px 48px; }
section.bordered { border-top:1px solid var(--line); }
h2 { font-family:'Anton', sans-serif; font-size:56px; font-weight:400; letter-spacing:0.01em;
  line-height:1.0; color:var(--ink); margin-bottom:14px; text-transform:uppercase; }
h2 em { font-style:normal; color:var(--gold); text-shadow:0 0 24px rgba(245,184,46,0.3); }
.lede { font-size:17px; color:var(--ink-soft); margin-bottom:32px; max-width:880px; line-height:1.55; }
.lede a { color:var(--gold); text-decoration:none; border-bottom:1px solid var(--line-strong); }
.lede a:hover { border-bottom-color:var(--gold); }

.stats { display:grid; grid-template-columns:repeat(3, 1fr); gap:16px; margin:24px 0 8px; }
.stat { background:var(--paper); border:1px solid var(--line); border-radius:12px; padding:26px 28px;
  border-top:4px solid var(--gold); position:relative; overflow:hidden; }
.stat.out { border-top-color:var(--out); }
.stat::after { content:''; position:absolute; top:0; right:0; width:120px; height:120px;
  background:radial-gradient(circle, rgba(245,184,46,0.10), transparent 70%); pointer-events:none; }
.stat .label { font-family:'JetBrains Mono', monospace; font-size:11px; font-weight:700;
  color:var(--muted); letter-spacing:0.14em; text-transform:uppercase; margin-bottom:12px; }
.stat .value { font-family:'Anton', sans-serif; font-size:44px; font-weight:400;
  color:var(--ink); letter-spacing:0.01em; line-height:1; }
.stat.in .value { color:var(--gold); }
.stat.out .value { color:var(--out); }
.stat .sub { font-size:12px; color:var(--muted); margin-top:8px; font-family:'JetBrains Mono', monospace; }

.cards { display:grid; grid-template-columns:repeat(3, 1fr); gap:14px; margin-top:24px; }
.card { background:var(--paper); border:1px solid var(--line); border-radius:10px; padding:18px 20px;
  border-left:4px solid var(--gold); transition:all .15s; }
.card:hover { transform:translateY(-2px); border-color:var(--line-strong);
  box-shadow:0 6px 20px rgba(245,184,46,0.10); }
.card .top { display:flex; justify-content:space-between; align-items:baseline; margin-bottom:8px; gap:12px; }
.card .nome { font-family:'Nunito', sans-serif; font-weight:800; font-size:15px; color:var(--ink); }
.card .valor { font-family:'Anton', sans-serif; font-weight:400; font-size:22px; color:var(--gold); letter-spacing:0.01em; }
.card .meta { font-family:'JetBrains Mono', monospace; font-size:10px; color:var(--muted);
  letter-spacing:0.06em; display:flex; justify-content:space-between; }
.card .hash { color:var(--muted-light); }

table { width:100%; border-collapse:collapse; background:var(--paper); border:1px solid var(--line);
  border-radius:10px; overflow:hidden; margin-top:18px; }
th, td { padding:14px 18px; text-align:left; border-bottom:1px solid var(--line); font-size:14px; }
th { background:rgba(245,184,46,0.06); font-family:'JetBrains Mono', sans-serif; font-weight:700; font-size:11px;
  color:var(--gold); text-transform:uppercase; letter-spacing:0.12em; }
td.valor { font-family:'JetBrains Mono', monospace; font-weight:700; text-align:right; font-size:14px; }
td.valor.in { color:var(--gold); }
td.valor.out { color:var(--out); }
td.hash { font-family:'JetBrains Mono', monospace; color:var(--muted); font-size:11px; }
td.data { font-family:'JetBrains Mono', monospace; font-size:12px; color:var(--muted); white-space:nowrap; }
tr:last-child td { border-bottom:none; }
tr:hover td { background:rgba(245,184,46,0.03); }
.tag { display:inline-block; font-family:'JetBrains Mono', monospace; font-size:10px; font-weight:700;
  text-transform:uppercase; letter-spacing:0.08em; padding:3px 9px; border-radius:3px;
  background:rgba(245,184,46,0.12); color:var(--gold); margin-right:6px; }

.banner { background:var(--paper-2); border:1px solid var(--line); border-radius:12px; padding:32px 36px; margin:24px 0;
  position:relative; overflow:hidden; }
.banner::before { content:''; position:absolute; top:0; left:0; width:80px; height:4px; background:var(--gold); }
.banner h3 { font-family:'Anton', sans-serif; font-size:28px; font-weight:400; color:var(--gold); margin-bottom:12px;
  letter-spacing:0.02em; text-transform:uppercase; }
.banner p { font-size:15px; line-height:1.6; color:var(--ink-soft); max-width:820px; }
.banner code { font-family:'JetBrains Mono', monospace; background:rgba(245,184,46,0.12); padding:2px 8px;
  border-radius:3px; font-size:13px; color:var(--gold); }

footer { max-width:1100px; margin:0 auto; padding:32px 48px 64px; border-top:1px solid var(--line);
  font-family:'JetBrains Mono', monospace; font-size:11px; color:var(--muted);
  letter-spacing:0.06em; }
footer a { color:var(--gold); text-decoration:none; }

.hashtags { font-family:'JetBrains Mono', monospace; font-size:12px; color:var(--gold);
  letter-spacing:0.08em; margin-top:24px; font-weight:600; }

/* contribuir page */
.pix-wrapper { display:grid; grid-template-columns: 320px 1fr; gap:48px; align-items:start; margin-top:8px; }
.pix-qr { background:var(--paper); border:1px solid var(--line-strong); border-radius:14px;
  padding:24px; text-align:center; box-shadow:0 0 60px rgba(245,184,46,0.15); }
.pix-qr img { width:100%; height:auto; max-width:280px; display:block; margin:0 auto;
  border-radius:8px; }
.pix-qr-hint { font-family:'JetBrains Mono', monospace; font-size:11px; color:var(--muted);
  letter-spacing:0.12em; text-transform:uppercase; margin-top:14px; }
.pix-info h2 { font-size:44px; margin-bottom:20px; }
.pix-meta { display:flex; flex-direction:column; gap:10px; margin-bottom:24px; }
.pix-meta > div { display:flex; align-items:baseline; gap:12px; padding:10px 14px;
  background:var(--paper); border:1px solid var(--line); border-radius:8px; }
.pix-meta .k { font-family:'JetBrains Mono', monospace; font-size:10px; color:var(--muted);
  letter-spacing:0.14em; text-transform:uppercase; min-width:90px; font-weight:700; }
.pix-meta .v { font-family:'Nunito', sans-serif; font-weight:700; color:var(--ink); font-size:15px; }
.pix-brcode-wrap { background:var(--paper-2); border:1px solid var(--line-strong); border-radius:10px;
  padding:16px; }
.pix-brcode-wrap textarea { width:100%; min-height:80px; background:transparent; border:none;
  color:var(--ink-soft); font-family:'JetBrains Mono', monospace; font-size:11px; line-height:1.5;
  word-break:break-all; resize:none; outline:none; padding:0; }
.pix-brcode-wrap button { width:100%; margin-top:12px; padding:14px 18px; background:var(--gold);
  color:#0E0D0B; border:none; border-radius:8px; font-family:'Anton', sans-serif; font-size:18px;
  letter-spacing:0.04em; text-transform:uppercase; cursor:pointer; transition:all .15s; }
.pix-brcode-wrap button:hover { background:var(--gold-dark); transform:translateY(-1px); }
.pix-brcode-wrap button.copied { background:#77BC00; color:#0E0D0B; }
.pix-note { font-size:13px; color:var(--muted); margin-top:14px; font-family:'JetBrains Mono', monospace;
  letter-spacing:0.04em; }

@media (max-width: 1024px) {
  .hero h1 { font-size:72px; }
  h2 { font-size:44px; }
  .cards { grid-template-columns:repeat(2, 1fr); }
  .hero-image img { max-height:260px; }
}
@media (max-width: 900px) {
  .pix-wrapper { grid-template-columns:1fr; gap:24px; }
  .pix-qr { max-width:340px; margin:0 auto; }
}
@media (max-width: 720px) {
  .topbar { padding:10px 16px; flex-wrap:wrap; gap:10px; }
  .topbar-brand { font-size:16px; }
  .topbar-path { display:none; }
  .topbar-links { width:100%; justify-content:space-between; gap:4px; }
  .topbar-links a { padding:5px 8px; font-size:10px; letter-spacing:0.08em; flex:1; text-align:center; }
  .updated-bar { padding:7px 16px; font-size:10px; letter-spacing:0.06em; }
  .hero { padding:24px 20px 20px; }
  .hero.no-image { padding-top:40px; }
  .hero h1 { font-size:44px; line-height:0.95; }
  .hero .subtitle { font-size:17px; }
  .hero-image { max-width:calc(100% - 40px); margin:16px auto 0; }
  .hero-image img { max-height:220px; object-position:center 20%; }
  .hero-image::after { height:50px; }
  section { padding:28px 20px; }
  h2 { font-size:34px; }
  .stats { grid-template-columns:1fr; gap:12px; }
  .stat { padding:20px 22px; }
  .stat .value { font-size:36px; }
  .cards { grid-template-columns:1fr; gap:10px; }
  .banner { padding:24px 22px; }
  .banner h3 { font-size:22px; }
  table { font-size:13px; }
  th, td { padding:10px 12px; }
  td.hash { display:none; } /* hide hash column on mobile */
  th:nth-child(3) { display:none; }
  footer { padding:24px 20px 48px; }
  .hashtags { font-size:10px; word-break:break-word; }
}
@media (max-width: 380px) {
  .hero h1 { font-size:36px; }
  .topbar-links a { font-size:9px; padding:4px 6px; }
}
"""

GOOGLE_FONTS = '<link href="https://fonts.googleapis.com/css2?family=Anton&family=Nunito:wght@400;600;700;800;900&family=Nunito+Sans:wght@400;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">'


def topbar(active: str) -> str:
    def link(name, href, label):
        cls = ' class="active"' if name == active else ""
        return f'<a href="{href}"{cls}>{label}</a>'
    return f"""<div class="topbar">
  <div class="topbar-brand">FUNDO <em>RAUL</em></div>
  <div class="topbar-path">raulout · vaquinha auditável</div>
  <div class="topbar-links">
    {link('home', 'index.html', 'Home')}
    {link('entradas', 'entradas.html', 'Entradas')}
    {link('saidas', 'saidas.html', 'Saídas')}
    {link('contribuir', 'contribuir.html', 'Contribuir')}
  </div>
</div>"""


def updated_bar(now: str) -> str:
    return f'<div class="updated-bar">Última atualização <strong>{now}</strong></div>'


def page(active: str, title: str, body: str, now: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape(title)} — Fundo Raul</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
{GOOGLE_FONTS}
<style>{CSS}</style>
</head>
<body>
{topbar(active)}
{updated_bar(now)}
{body}
<footer>
  Atualizado em <strong>{now}</strong> · código-fonte em <a href="https://github.com">github</a> ·
  toda movimentação aparece aqui — entradas vêm do extrato bancário exportado e anonimizado,
  saídas são publicadas com comprovante.
</footer>
</body>
</html>"""


def page_home(entradas, saidas, now):
    total_in = sum(e["valor"] for e in entradas)
    total_out = sum(s["valor"] for s in saidas)
    saldo = total_in - total_out
    qtd = len(entradas)
    primeiros_cards = "".join(
        f"""<div class="card">
          <div class="top">
            <span class="nome">{escape(e['nome_anon'])}</span>
            <span class="valor">{fmt_brl(e['valor'])}</span>
          </div>
          <div class="meta"><span>{e['data']} · {e['hora']}</span><span class="hash">#{e['hash']}</span></div>
        </div>""" for e in entradas[:12]
    )
    body = f"""
<div class="hero-image">
  <img src="raul-livre.jpg" alt="Movimento Raul Livre">
</div>
<div class="hero">
  <div class="eyebrow">vaquinha auditável · atualizada {now}</div>
  <h1>Movimento <em>Raul Livre</em></h1>
  <div class="subtitle">Vaquinha do clube pra trazer o Raul de volta. Toda doação que entra e tudo que sai aparece aqui, com data, valor e hash de verificação. Mente livre. Corpo forte. Espírito inquebrável.</div>
  <div class="meta">campanha iniciada em <strong>22/05/2026</strong> · {qtd} doações recebidas · fonte: extrato bancário exportado periodicamente</div>
  <div class="hashtags">#RAULLIVRE · #MENTELIVRE · #CORPOFORTE · #ESPIRITOINQUEBRAVEL</div>
</div>

<section>
  <div class="stats">
    <div class="stat in"><div class="label">Total arrecadado</div><div class="value">{fmt_brl(total_in)}</div><div class="sub">{qtd} doações</div></div>
    <div class="stat out"><div class="label">Total destinado</div><div class="value">{fmt_brl(total_out)}</div><div class="sub">{len(saidas)} saídas</div></div>
    <div class="stat saldo"><div class="label">Saldo em caixa</div><div class="value">{fmt_brl(saldo)}</div><div class="sub">entradas − saídas</div></div>
  </div>
</section>

<section class="bordered">
  <h2>Últimas <em>doações</em></h2>
  <p class="lede">Quem contribuiu nas últimas 12 entradas. Veja o <a href="entradas.html">extrato completo</a> ou <a href="contribuir.html">contribua</a>.</p>
  <div class="cards">{primeiros_cards}</div>
</section>

<section class="bordered">
  <div class="banner">
    <h3>Como funciona a auditoria</h3>
    <p>Cada doação é capturada do extrato bancário oficial e exibida com nome anonimizado (primeiro nome + iniciais) e um <code>#hash</code> de 6 caracteres derivado do nome completo. Quem doou consegue achar a própria contribuição pelo hash. As saídas são lançadas manualmente com categoria, descrição e link pro comprovante. O total de entradas menos saídas precisa bater com o saldo da conta — qualquer divergência é pública.</p>
  </div>
</section>
"""
    return page("home", "Início", body, now)


def page_entradas(entradas, now):
    rows = "".join(
        f"""<tr>
          <td class="data">{e['data']} {e['hora']}</td>
          <td>{escape(e['nome_anon'])}</td>
          <td class="hash">#{e['hash']}</td>
          <td class="valor in">{fmt_brl(e['valor'])}</td>
        </tr>""" for e in entradas
    )
    total = sum(e["valor"] for e in entradas)
    body = f"""
<div class="hero no-image">
  <div class="eyebrow">extrato · entradas</div>
  <h1>Todas as <em>entradas</em></h1>
  <div class="subtitle">Lista completa de doações. {len(entradas)} lançamentos · total <strong>{fmt_brl(total)}</strong>.</div>
  <div class="meta">cada linha vem direto do extrato bancário · nome anonimizado · #hash permite o doador identificar a própria contribuição</div>
</div>
<section>
  <table>
    <thead><tr><th>Data</th><th>Quem</th><th>Hash</th><th style="text-align:right">Valor</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</section>
"""
    return page("entradas", "Entradas", body, now)


def page_saidas(saidas, now):
    if not saidas:
        body = f"""
<div class="hero no-image">
  <div class="eyebrow">extrato · saídas</div>
  <h1>Todas as <em>saídas</em></h1>
  <div class="subtitle">Pra onde foi cada centavo do fundo. Por enquanto, nada foi destinado.</div>
  <div class="meta">categorias previstas: advogado · pensão · família · custas judiciais · outros</div>
</div>
<section>
  <div class="banner">
    <h3>Sem destinações ainda</h3>
    <p>Quando o fundo começar a ser usado (pagamento de advogado, pensão, sustento da família, custas judiciais), cada saída vai aparecer aqui com data, categoria, valor e link pro comprovante. Toda saída precisa ter comprovante. Sem exceção.</p>
  </div>
</section>
"""
    else:
        rows = "".join(
            f"""<tr>
              <td class="data">{s['data']}</td>
              <td><span class="tag">{escape(CATEGORIA_LABEL.get(s['categoria'], s['categoria']))}</span> {escape(s['descricao'])}</td>
              <td class="valor out">-{fmt_brl(s['valor'])}</td>
              <td>{f'<a href={escape(s["comprovante_url"])}>comprovante</a>' if s.get('comprovante_url') else '<span style="color:var(--muted-light)">—</span>'}</td>
            </tr>""" for s in saidas
        )
        total = sum(s["valor"] for s in saidas)
        body = f"""
<div class="hero no-image">
  <div class="eyebrow">extrato · saídas</div>
  <h1>Todas as <em>saídas</em></h1>
  <div class="subtitle">Pra onde foi cada centavo. {len(saidas)} lançamentos · total <strong>{fmt_brl(total)}</strong>.</div>
</div>
<section>
  <table>
    <thead><tr><th>Data</th><th>Destinação</th><th style="text-align:right">Valor</th><th>Comprovante</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</section>
"""
    return page("saidas", "Saídas", body, now)


def page_contribuir(now):
    pix_key = CFG.get("pix_chave", "")
    pix_nome = CFG.get("pix_nome", "")
    pix_cidade = CFG.get("pix_cidade", "")
    pix_brcode = CFG.get("pix_brcode", "")
    body = f"""
<div class="hero no-image">
  <div class="eyebrow">contribuir</div>
  <h1>Como <em>ajudar</em></h1>
  <div class="subtitle">Toda doação vai pra um único objetivo: trazer o Raul de volta pra família. Qualquer valor faz diferença.</div>
</div>

<section>
  <div class="pix-wrapper">
    <div class="pix-qr">
      <img src="qr-pix.svg" alt="QR Code PIX" width="280" height="280">
      <p class="pix-qr-hint">Aponta a câmera do seu banco</p>
    </div>
    <div class="pix-info">
      <h2>PIX <em>copia &amp; cola</em></h2>
      <div class="pix-meta">
        <div><span class="k">Chave PIX</span><span class="v">{escape(pix_key)}</span></div>
        <div><span class="k">Recebedor</span><span class="v">{escape(pix_nome)}</span></div>
        <div><span class="k">Cidade</span><span class="v">{escape(pix_cidade)}</span></div>
      </div>
      <div class="pix-brcode-wrap">
        <textarea id="brcode" readonly>{escape(pix_brcode)}</textarea>
        <button onclick="copyBrcode()" id="copy-btn">📋 Copiar código PIX</button>
      </div>
      <p class="pix-note">Cole no app do seu banco em "PIX → Copia e Cola" e escolha o valor que quiser doar.</p>
    </div>
  </div>
</section>

<section class="bordered">
  <div class="banner">
    <h3>Por que dá pra confiar</h3>
    <p>Todas as entradas vêm direto do extrato bancário exportado, não de digitação manual. Toda saída tem comprovante linkado. Quem quiser auditar pode bater o saldo de caixa com a soma de entradas menos saídas a qualquer momento. O <a href="https://github.com/leonardokasat-cientistavenda/rauolout" style="color:var(--gold)">código-fonte</a> deste site é público.</p>
  </div>
  <p class="lede" style="margin-top:24px">Assim que você fizer o PIX, sua doação vai aparecer na <a href="entradas.html">página de entradas</a> na próxima atualização (com nome anonimizado e hash de verificação).</p>
</section>

<script>
function copyBrcode() {{
  const t = document.getElementById('brcode');
  t.select();
  navigator.clipboard.writeText(t.value).then(() => {{
    const b = document.getElementById('copy-btn');
    const orig = b.innerHTML;
    b.innerHTML = '✓ Copiado!';
    b.classList.add('copied');
    setTimeout(() => {{ b.innerHTML = orig; b.classList.remove('copied'); }}, 2000);
  }});
}}
</script>
"""
    return page("contribuir", "Contribuir", body, now)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    SITE.mkdir(exist_ok=True)
    entradas = coletar_entradas()
    saidas = coletar_saidas()
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    (SITE / "index.html").write_text(page_home(entradas, saidas, now), encoding="utf-8")
    (SITE / "entradas.html").write_text(page_entradas(entradas, now), encoding="utf-8")
    (SITE / "saidas.html").write_text(page_saidas(saidas, now), encoding="utf-8")
    (SITE / "contribuir.html").write_text(page_contribuir(now), encoding="utf-8")

    total = sum(e["valor"] for e in entradas)
    print(f"✓ {len(entradas)} entradas · {fmt_brl(total)}")
    print(f"✓ {len(saidas)} saídas")
    print(f"✓ {SITE}/index.html")


if __name__ == "__main__":
    main()
