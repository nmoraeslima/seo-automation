"""#8 - Auditoria tecnica de SEO via crawl do site.

Faz um crawl (mesmo dominio) e detecta problemas comuns de SEO on-page e
tecnico. Gera uma lista de issues e escreve em uma aba do Google Sheets.
"""

from __future__ import annotations

import csv
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .config import REPO_ROOT, ClientConfig, Settings
from .google_clients import GoogleClients

USER_AGENT = "SEO-Automation-Bot/1.0 (+https://windsor.ai)"
AUDIT_HEADER = ["URL", "Problema", "Severidade", "Detalhe", "Recomendacao"]


@dataclass
class Issue:
    url: str
    problem: str
    severity: str  # "Alta", "Media", "Baixa"
    detail: str
    recommendation: str

    def as_row(self) -> list[str]:
        return [self.url, self.problem, self.severity, self.detail, self.recommendation]


@dataclass
class PageData:
    url: str
    status: int
    title: str
    meta_description: str
    h1s: list[str]
    images_without_alt: int
    has_canonical: bool
    noindex: bool
    load_ms: int
    links: list[str]


def _same_domain(base: str, url: str) -> bool:
    return urlparse(base).netloc == urlparse(url).netloc


def _normalize(url: str) -> str:
    parsed = urlparse(url)
    return parsed._replace(fragment="").geturl()


def fetch_page(session: requests.Session, url: str) -> PageData | None:
    start = time.time()
    try:
        resp = session.get(url, timeout=20, allow_redirects=True)
    except requests.RequestException:
        return PageData(url, 0, "", "", [], 0, False, 0, [])
    load_ms = int((time.time() - start) * 1000)

    content_type = resp.headers.get("Content-Type", "")
    if "text/html" not in content_type:
        return PageData(url, resp.status_code, "", "", [], 0, False, load_ms, [])

    soup = BeautifulSoup(resp.text, "lxml")
    title = (soup.title.string or "").strip() if soup.title else ""
    desc_tag = soup.find("meta", attrs={"name": "description"})
    meta_description = (desc_tag.get("content", "").strip() if desc_tag else "")
    h1s = [h.get_text(strip=True) for h in soup.find_all("h1")]
    images_without_alt = sum(
        1 for img in soup.find_all("img") if not img.get("alt", "").strip()
    )
    has_canonical = bool(soup.find("link", attrs={"rel": "canonical"}))
    robots_tag = soup.find("meta", attrs={"name": "robots"})
    noindex = "noindex" in (robots_tag.get("content", "").lower() if robots_tag else "")

    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        links.append(_normalize(urljoin(url, href)))

    return PageData(
        url=url,
        status=resp.status_code,
        title=title,
        meta_description=meta_description,
        h1s=h1s,
        images_without_alt=images_without_alt,
        has_canonical=has_canonical,
        noindex=noindex,
        load_ms=load_ms,
        links=links,
    )


def crawl(site_url: str, max_pages: int = 100) -> list[PageData]:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    start = _normalize(site_url)
    queue: deque[str] = deque([start])
    seen: set[str] = {start}
    pages: list[PageData] = []

    while queue and len(pages) < max_pages:
        url = queue.popleft()
        page = fetch_page(session, url)
        if page is None:
            continue
        pages.append(page)
        for link in page.links:
            if link not in seen and _same_domain(start, link) and len(seen) < max_pages * 3:
                seen.add(link)
                queue.append(link)
    return pages


def analyze(pages: list[PageData]) -> list[Issue]:
    issues: list[Issue] = []
    titles: dict[str, list[str]] = defaultdict(list)
    descriptions: dict[str, list[str]] = defaultdict(list)

    for p in pages:
        if p.status == 0:
            issues.append(
                Issue(p.url, "Pagina inacessivel", "Alta", "Falha ao carregar",
                      "Verificar disponibilidade/erro de servidor.")
            )
            continue
        if p.status >= 400:
            issues.append(
                Issue(p.url, f"Status {p.status}", "Alta",
                      f"Resposta HTTP {p.status}",
                      "Corrigir link quebrado ou redirecionar.")
            )
            continue
        if p.noindex:
            issues.append(
                Issue(p.url, "Pagina com noindex", "Media",
                      "meta robots=noindex",
                      "Confirmar se a pagina deveria ser indexavel.")
            )
        if not p.title:
            issues.append(
                Issue(p.url, "Title ausente", "Alta", "Sem <title>",
                      "Adicionar title unico de 50-60 caracteres.")
            )
        elif len(p.title) > 65:
            issues.append(
                Issue(p.url, "Title muito longo", "Baixa",
                      f"{len(p.title)} caracteres",
                      "Reduzir para ~60 caracteres.")
            )
        else:
            titles[p.title].append(p.url)

        if not p.meta_description:
            issues.append(
                Issue(p.url, "Meta description ausente", "Media",
                      "Sem meta description",
                      "Adicionar descricao de 120-160 caracteres.")
            )
        else:
            descriptions[p.meta_description].append(p.url)

        if not p.h1s:
            issues.append(
                Issue(p.url, "H1 ausente", "Media", "Pagina sem H1",
                      "Adicionar um unico H1 descritivo.")
            )
        elif len(p.h1s) > 1:
            issues.append(
                Issue(p.url, "Multiplos H1", "Baixa",
                      f"{len(p.h1s)} tags H1",
                      "Manter apenas um H1 por pagina.")
            )

        if p.images_without_alt:
            issues.append(
                Issue(p.url, "Imagens sem alt", "Baixa",
                      f"{p.images_without_alt} imagens",
                      "Adicionar texto alternativo descritivo.")
            )
        if not p.has_canonical:
            issues.append(
                Issue(p.url, "Canonical ausente", "Baixa", "Sem link canonical",
                      "Adicionar tag canonical.")
            )
        if p.load_ms > 3000:
            issues.append(
                Issue(p.url, "Carregamento lento", "Media",
                      f"{p.load_ms} ms",
                      "Otimizar performance (imagens, cache, etc).")
            )

    for title, urls in titles.items():
        if len(urls) > 1:
            for u in urls:
                issues.append(
                    Issue(u, "Title duplicado", "Media",
                          f'"{title[:60]}" em {len(urls)} paginas',
                          "Tornar cada title unico.")
                )
    for desc, urls in descriptions.items():
        if len(urls) > 1:
            for u in urls:
                issues.append(
                    Issue(u, "Meta description duplicada", "Baixa",
                          f"{len(urls)} paginas com a mesma descricao",
                          "Tornar cada description unica.")
                )
    return issues


def check_site_files(site_url: str) -> list[Issue]:
    issues: list[Issue] = []
    base = f"{urlparse(site_url).scheme}://{urlparse(site_url).netloc}"
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    for path, name in [("/robots.txt", "robots.txt"), ("/sitemap.xml", "sitemap.xml")]:
        try:
            r = session.get(base + path, timeout=15)
            if r.status_code >= 400:
                issues.append(
                    Issue(base + path, f"{name} ausente", "Media",
                          f"HTTP {r.status_code}",
                          f"Publicar {name} valido.")
                )
        except requests.RequestException:
            issues.append(
                Issue(base + path, f"{name} inacessivel", "Media",
                      "Falha na requisicao", f"Publicar {name} valido.")
            )
    return issues


def run_audit_for_client(
    client: ClientConfig,
    settings: Settings,
    google: GoogleClients | None,
) -> tuple[list[Issue], str]:
    """Roda a auditoria. Retorna (issues, destino).

    Escreve no Google Sheets se houver service account + spreadsheet id;
    caso contrario salva um CSV local em output/ e retorna o caminho.
    """
    if not client.site_url:
        return [], ""
    pages = crawl(client.site_url, client.audit_max_pages)
    issues = analyze(pages) + check_site_files(client.site_url)

    severity_order = {"Alta": 0, "Media": 1, "Baixa": 2}
    issues.sort(key=lambda i: severity_order.get(i.severity, 3))

    summary = (
        f"Auditoria de {client.site_url} | "
        f"{datetime.now(timezone.utc):%d/%m/%Y %H:%M UTC} | "
        f"{len(pages)} paginas | {len(issues)} problemas "
        f"(Alta: {sum(1 for i in issues if i.severity == 'Alta')}, "
        f"Media: {sum(1 for i in issues if i.severity == 'Media')}, "
        f"Baixa: {sum(1 for i in issues if i.severity == 'Baixa')})"
    )

    if google and settings.control_spreadsheet_id:
        sheet = f"Auditoria - {client.name}"[:99]
        rows = [[summary], [], AUDIT_HEADER] + [i.as_row() for i in issues]
        google.overwrite_sheet(settings.control_spreadsheet_id, sheet, rows)
        return issues, f"Sheets: aba '{sheet}'"

    return issues, _write_audit_csv(client, summary, issues)


def _write_audit_csv(
    client: ClientConfig, summary: str, issues: list[Issue]
) -> str:
    out_dir = REPO_ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"auditoria-{client.slug}.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([summary])
        writer.writerow([])
        writer.writerow(AUDIT_HEADER)
        for issue in issues:
            writer.writerow(issue.as_row())
    return str(path)
