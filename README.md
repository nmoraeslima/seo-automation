# SEO Automation

Automações de SEO para a agência:

- **#5 Briefings de conteúdo** (`briefings`): para cada palavra-chave alvo de cada
  cliente, puxa dados do Search Console (via Windsor.ai), gera um briefing de SEO
  (título, intenção de busca, estrutura H2/H3, FAQ, termos relacionados, contagem
  de palavras sugerida) em um **Google Doc** e registra um índice na planilha de
  controle (**Google Sheets**).
- **#8 Auditoria técnica** (`audit`): faz crawl do site de cada cliente e detecta
  problemas comuns (title/meta/H1 ausentes ou duplicados, links quebrados, imagens
  sem alt, canonical ausente, noindex, carregamento lento, robots.txt/sitemap.xml),
  escrevendo o resultado em uma aba do **Google Sheets**.

Ambas rodam semanalmente via GitHub Actions (`.github/workflows/weekly.yml`).

## Estrutura

```
src/seo_automation/
  config.py          # carrega .env e config/clients.yaml
  windsor.py         # cliente da API Windsor.ai (Search Console)
  google_clients.py  # Google Sheets / Docs / Drive (service account)
  llm.py             # geração opcional de texto via OpenAI
  briefing.py        # #5 briefings
  audit.py           # #8 auditoria técnica
  cli.py             # entrypoint (briefings | audit | all)
config/clients.example.yaml
.github/workflows/   # weekly.yml (agendado) e ci.yml (testes)
```

## Configuração

### 1. Credenciais (`.env`)

Copie `.env.example` para `.env` e preencha:

- `WINDSOR_API_KEY` — painel do Windsor.ai (Account > API).
- `GOOGLE_SERVICE_ACCOUNT_FILE` — caminho do JSON da service account do Google Cloud.
- `CONTROL_SPREADSHEET_ID` — ID da planilha de controle (da URL do Google Sheets).
- `OPENAI_API_KEY` *(opcional)* — melhora a qualidade dos briefings.

### 2. Service account do Google

1. No Google Cloud, crie uma service account e baixe o JSON.
2. Habilite as APIs **Google Sheets**, **Google Docs** e **Google Drive**.
3. Compartilhe a planilha de controle e a pasta do Drive de cada cliente com o
   e-mail da service account (`...@...iam.gserviceaccount.com`), como Editor.

### 3. Clientes (`config/clients.yaml`)

Copie `config/clients.example.yaml` para `config/clients.yaml` e configure cada
cliente (site, palavras-chave alvo, pasta do Drive, etc.).

## Uso local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env            # preencha as credenciais
cp config/clients.example.yaml config/clients.yaml  # configure os clientes

python -m seo_automation.cli briefings   # só briefings (#5)
python -m seo_automation.cli audit       # só auditoria (#8)
python -m seo_automation.cli all         # ambos
```

## Agendamento (GitHub Actions)

O workflow `weekly.yml` roda toda segunda 11:00 UTC (08:00 BRT). Configure os
**secrets** do repositório em *Settings > Secrets and variables > Actions*:

- `WINDSOR_API_KEY`
- `GOOGLE_SERVICE_ACCOUNT_JSON` — **conteúdo** do JSON da service account
- `CONTROL_SPREADSHEET_ID`
- `OPENAI_API_KEY` *(opcional)*

> O arquivo `config/clients.yaml` precisa estar commitado no repositório para o
> agendamento funcionar (ele não contém segredos).

## Testes

```bash
pip install -e . pytest ruff
ruff check src tests
pytest -q
```
