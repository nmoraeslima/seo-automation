"""Entrypoint de linha de comando para as automacoes de SEO."""

from __future__ import annotations

import argparse
import sys

from .audit import run_audit_for_client
from .briefing import run_briefings_for_client
from .config import Settings, load_clients
from .google_clients import GoogleClients
from .llm import LLMClient
from .windsor import WindsorClient


def _build_google(settings: Settings) -> GoogleClients | None:
    """Constroi o cliente Google se a service account existir; senao None.

    Sem Google, as automacoes caem para saida local (CSV/Markdown em output/).
    """
    if settings.service_account_path.exists():
        return GoogleClients(settings.service_account_path)
    print(
        "[aviso] service account do Google nao encontrada "
        f"({settings.service_account_path}); usando saida local em output/."
    )
    return None


def cmd_briefings(args) -> int:
    settings = Settings.from_env()
    google = _build_google(settings)
    windsor = WindsorClient(settings.windsor_api_key)
    llm = LLMClient(settings.openai_api_key, settings.openai_model)
    clients = load_clients(args.clients)
    for client in clients:
        if not client.keywords:
            continue
        print(f"[briefings] {client.name} ({len(client.keywords)} keywords)")
        results = run_briefings_for_client(client, settings, google, windsor, llm)
        for briefing, dest in results:
            print(f"  - {briefing.keyword}: {dest}")
    return 0


def cmd_audit(args) -> int:
    settings = Settings.from_env()
    google = _build_google(settings)
    clients = load_clients(args.clients)
    for client in clients:
        if not client.site_url:
            continue
        print(f"[audit] {client.name} -> {client.site_url}")
        issues, dest = run_audit_for_client(client, settings, google)
        print(f"  {len(issues)} problemas encontrados -> {dest}")
    return 0


def cmd_all(args) -> int:
    rc = cmd_briefings(args)
    rc |= cmd_audit(args)
    return rc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Automacoes de SEO da agencia")
    parser.add_argument(
        "--clients", default=None, help="Caminho para o YAML de clientes"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("briefings", help="Gera briefings de conteudo (#5)")
    sub.add_parser("audit", help="Roda a auditoria tecnica (#8)")
    sub.add_parser("all", help="Roda briefings + auditoria")

    args = parser.parse_args(argv)
    if args.command == "briefings":
        return cmd_briefings(args)
    if args.command == "audit":
        return cmd_audit(args)
    if args.command == "all":
        return cmd_all(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
