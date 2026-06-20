"""#5 - Geracao de briefings de conteudo SEO por palavra-chave.

Fluxo:
  1. Puxa dados do Search Console (via Windsor) para o cliente.
  2. Para cada keyword-alvo, calcula metricas atuais e queries relacionadas.
  3. (Opcional) usa LLM para gerar titulo/estrutura/FAQ.
  4. Cria um Google Doc com o briefing e registra no Sheets de controle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .config import REPO_ROOT, ClientConfig, Settings
from .google_clients import GoogleClients
from .llm import LLMClient
from .windsor import SearchConsoleRow, WindsorClient

INDEX_SHEET = "Briefings"
INDEX_HEADER = [
    "Data",
    "Cliente",
    "Keyword",
    "Posicao atual",
    "Cliques (28d)",
    "Impressoes (28d)",
    "CTR",
    "Link do briefing",
]


@dataclass
class KeywordBriefing:
    keyword: str
    position: float
    clicks: float
    impressions: float
    ctr: float
    related_queries: list[str] = field(default_factory=list)
    title: str = ""
    intent: str = ""
    summary: str = ""
    headings: list[str] = field(default_factory=list)
    faq: list[str] = field(default_factory=list)
    suggested_word_count: int = 0


def _tokens(text: str) -> set[str]:
    return {t for t in text.lower().split() if len(t) > 2}


def build_keyword_briefing(
    keyword: str,
    rows: list[SearchConsoleRow],
    llm: LLMClient | None = None,
) -> KeywordBriefing:
    kw_lower = keyword.lower()
    kw_tokens = _tokens(keyword)

    exact = [r for r in rows if r.query.lower() == kw_lower]
    related_rows = [
        r
        for r in rows
        if r.query.lower() != kw_lower and kw_tokens & _tokens(r.query)
    ]

    if exact:
        agg = exact
    elif related_rows:
        agg = related_rows
    else:
        agg = []

    clicks = sum(r.clicks for r in agg)
    impressions = sum(r.impressions for r in agg)
    positions = [r.position for r in agg if r.position > 0]
    position = round(sum(positions) / len(positions), 1) if positions else 0.0
    ctr = round((clicks / impressions), 4) if impressions else 0.0

    related_queries = sorted(
        {r.query for r in related_rows},
        key=lambda q: -next((x.impressions for x in related_rows if x.query == q), 0),
    )[:30]

    briefing = KeywordBriefing(
        keyword=keyword,
        position=position,
        clicks=clicks,
        impressions=impressions,
        ctr=ctr,
        related_queries=related_queries,
        suggested_word_count=_suggest_word_count(position),
    )

    outline = llm.briefing_outline(keyword, related_queries) if llm else None
    if outline:
        briefing.title = outline.get("title", "")
        briefing.intent = outline.get("intent", "")
        briefing.summary = outline.get("summary", "")
        briefing.headings = list(outline.get("headings", []))
        briefing.faq = list(outline.get("faq", []))
    else:
        briefing.title = f"Guia completo: {keyword}"
        briefing.intent = "informacional (estimado)"
        briefing.headings = [
            f"H2: O que e {keyword}",
            f"H2: Por que {keyword} importa",
            f"H2: Como aplicar {keyword} na pratica",
            "H2: Erros comuns a evitar",
            "H2: Conclusao e proximos passos",
        ]
        briefing.faq = related_queries[:8]
    return briefing


def _suggest_word_count(position: float) -> int:
    if position == 0:
        return 1500
    if position <= 3:
        return 2000
    if position <= 10:
        return 1500
    return 1200


def _briefing_doc_blocks(
    client: ClientConfig, b: KeywordBriefing
) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = [
        ("TITLE", f"Briefing SEO - {b.keyword}"),
        ("NORMAL_TEXT", f"Cliente: {client.name}"),
        (
            "NORMAL_TEXT",
            f"Gerado em: {datetime.now(timezone.utc):%d/%m/%Y %H:%M UTC}",
        ),
        ("HEADING_1", "Resumo"),
        ("NORMAL_TEXT", b.summary or "(sem resumo de IA)"),
        ("HEADING_1", "Dados atuais (Search Console - 28 dias)"),
        ("BULLET", f"Posicao media: {b.position or 'n/d'}"),
        ("BULLET", f"Cliques: {int(b.clicks)}"),
        ("BULLET", f"Impressoes: {int(b.impressions)}"),
        ("BULLET", f"CTR: {b.ctr * 100:.2f}%"),
        ("HEADING_1", "Recomendacoes do briefing"),
        ("BULLET", f"Titulo sugerido: {b.title}"),
        ("BULLET", f"Intencao de busca: {b.intent}"),
        ("BULLET", f"Contagem de palavras sugerida: {b.suggested_word_count}"),
        ("HEADING_1", "Estrutura sugerida (H2/H3)"),
    ]
    for h in b.headings:
        blocks.append(("BULLET", h))
    blocks.append(("HEADING_1", "Perguntas para responder (FAQ / People Also Ask)"))
    for q in b.faq or ["(sem dados de FAQ)"]:
        blocks.append(("BULLET", q))
    blocks.append(("HEADING_1", "Termos relacionados (do Search Console)"))
    blocks.append(
        ("NORMAL_TEXT", ", ".join(b.related_queries) or "(sem termos relacionados)")
    )
    return blocks


def _write_briefing_markdown(
    client: ClientConfig, b: KeywordBriefing
) -> str:
    out_dir = REPO_ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"briefing-{client.slug}-{_kw_slug(b.keyword)}.md"
    lines = []
    for style, text in _briefing_doc_blocks(client, b):
        if style == "TITLE":
            lines.append(f"# {text}")
        elif style == "HEADING_1":
            lines.append(f"## {text}")
        elif style == "BULLET":
            lines.append(f"- {text}")
        else:
            lines.append(text)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def _kw_slug(keyword: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in keyword.lower()).strip("-")


def run_briefings_for_client(
    client: ClientConfig,
    settings: Settings,
    google: GoogleClients | None,
    windsor: WindsorClient,
    llm: LLMClient | None,
) -> list[tuple[KeywordBriefing, str]]:
    """Gera os briefings de um cliente. Retorna [(briefing, destino)].

    Cria Google Docs se houver service account; caso contrario escreve
    arquivos Markdown locais em output/.
    """
    rows = windsor.search_console(
        account=client.windsor_account or None,
    )
    results: list[tuple[KeywordBriefing, str]] = []
    index_rows: list[list] = []
    today = f"{datetime.now(timezone.utc):%Y-%m-%d}"

    for keyword in client.keywords:
        b = build_keyword_briefing(keyword, rows, llm)
        if google:
            doc_id = google.create_doc(
                f"Briefing SEO - {client.name} - {keyword}",
                folder_id=client.drive_folder_id or None,
            )
            google.write_doc_markdown(doc_id, _briefing_doc_blocks(client, b))
            dest = google.doc_url(doc_id)
        else:
            dest = _write_briefing_markdown(client, b)
        results.append((b, dest))
        index_rows.append(
            [
                today,
                client.name,
                keyword,
                b.position or "",
                int(b.clicks),
                int(b.impressions),
                f"{b.ctr * 100:.2f}%",
                dest,
            ]
        )

    if google and settings.control_spreadsheet_id and index_rows:
        google.ensure_sheet(settings.control_spreadsheet_id, INDEX_SHEET)
        existing = google.read_range(
            settings.control_spreadsheet_id, f"{INDEX_SHEET}!A1:A1"
        )
        if not existing:
            google.append_rows(
                settings.control_spreadsheet_id, INDEX_SHEET, [INDEX_HEADER]
            )
        google.append_rows(
            settings.control_spreadsheet_id, INDEX_SHEET, index_rows
        )
    return results
