"""Carregamento de configuracao (env vars + arquivo de clientes)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class ClientConfig:
    name: str
    site_url: str = ""
    windsor_account: str = ""
    drive_folder_id: str = ""
    audit_max_pages: int = 100
    keywords: list[str] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return "".join(
            c if c.isalnum() else "-" for c in self.name.lower()
        ).strip("-")


@dataclass
class Settings:
    windsor_api_key: str
    google_service_account_file: str
    control_spreadsheet_id: str
    openai_api_key: str
    openai_model: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            windsor_api_key=os.getenv("WINDSOR_API_KEY", ""),
            google_service_account_file=os.getenv(
                "GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json"
            ),
            control_spreadsheet_id=os.getenv("CONTROL_SPREADSHEET_ID", ""),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        )

    @property
    def service_account_path(self) -> Path:
        p = Path(self.google_service_account_file)
        return p if p.is_absolute() else REPO_ROOT / p


def load_clients(path: str | os.PathLike | None = None) -> list[ClientConfig]:
    """Carrega os clientes de config/clients.yaml (ou caminho informado)."""
    if path is None:
        candidate = REPO_ROOT / "config" / "clients.yaml"
        if not candidate.exists():
            candidate = REPO_ROOT / "config" / "clients.example.yaml"
        path = candidate
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo de clientes nao encontrado: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    clients = []
    for raw in data.get("clients", []):
        clients.append(
            ClientConfig(
                name=raw["name"],
                site_url=raw.get("site_url", ""),
                windsor_account=raw.get("windsor_account", ""),
                drive_folder_id=raw.get("drive_folder_id", ""),
                audit_max_pages=int(raw.get("audit_max_pages", 100)),
                keywords=list(raw.get("keywords", [])),
            )
        )
    return clients
