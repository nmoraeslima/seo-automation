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


def _build_context(need_windsor: bool):
    settings = Settings.from_env()
    google = GoogleClients(settings.service_account_path)
    windsor = (
        WindsorClient(settings.windsor_api_key) if need_windsor else None
    )
    llm = LLMClient(settings.openai_api_key, settings.openai_model)
    return settings, google, windsor, llm


def cmd_briefings(args) -> int:
    settings, google, windsor, llm = _build_context(need_windsor=True)
    clients = load_clients(args.clients)
    for client in clients:
        if not client.keywords:
            continue
        print(f"[briefings] {client.name} ({len(client.keywords)} keywords)")
        results = run_briefings_for_client(client, settings, google, windsor, llm)
        for briefing, url in results:
            print(f"  - {briefing.keyword}: {url}")
    return 0


def cmd_audit(args) -> int:
    settings, google, windsor, llm = _build_context(need_windsor=False)
    clients = load_clients(args.clients)
    for client in clients:
        if not client.site_url:
            continue
        print(f"[audit] {client.name} -> {client.site_url}")
        issues = run_audit_for_client(client, settings, google)
        print(f"  {len(issues)} problemas encontrados")
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
