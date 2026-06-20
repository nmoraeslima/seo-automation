"""Cliente da API de dados do Windsor.ai.

Docs: https://windsor.ai/api-fields/ e https://connectors.windsor.ai/

O endpoint de dados retorna JSON no formato {"data": [ {linha}, ... ]}.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

BASE_URL = "https://connectors.windsor.ai"
DEFAULT_TIMEOUT = 60


@dataclass
class SearchConsoleRow:
    query: str
    page: str
    clicks: float
    impressions: float
    ctr: float
    position: float


class WindsorError(RuntimeError):
    pass


class WindsorClient:
    def __init__(self, api_key: str, session: requests.Session | None = None):
        if not api_key:
            raise WindsorError("WINDSOR_API_KEY nao configurada.")
        self.api_key = api_key
        self.session = session or requests.Session()

    def fetch(
        self,
        connector: str = "all",
        *,
        fields: list[str],
        date_preset: str = "last_7d",
        date_from: str | None = None,
        date_to: str | None = None,
        extra_params: dict | None = None,
    ) -> list[dict]:
        """Consulta generica ao Windsor. Retorna a lista de linhas (dicts)."""
        params: dict[str, str] = {
            "api_key": self.api_key,
            "fields": ",".join(fields),
        }
        if date_from and date_to:
            params["date_from"] = date_from
            params["date_to"] = date_to
        else:
            params["date_preset"] = date_preset
        if extra_params:
            params.update(extra_params)

        url = f"{BASE_URL}/{connector}"
        resp = self.session.get(url, params=params, timeout=DEFAULT_TIMEOUT)
        if resp.status_code != 200:
            raise WindsorError(
                f"Windsor respondeu {resp.status_code}: {resp.text[:300]}"
            )
        try:
            payload = resp.json()
        except ValueError as exc:
            raise WindsorError(f"Resposta nao-JSON do Windsor: {resp.text[:300]}") from exc

        if isinstance(payload, dict) and "error" in payload:
            raise WindsorError(f"Erro do Windsor: {payload['error']}")
        data = payload.get("data") if isinstance(payload, dict) else payload
        return data or []

    def search_console(
        self,
        *,
        date_preset: str = "last_28d",
        account: str | None = None,
        connector: str = "google_search_console",
    ) -> list[SearchConsoleRow]:
        """Dados de query do Google Search Console via Windsor."""
        fields = ["query", "page", "clicks", "impressions", "ctr", "position"]
        extra = {"account": account} if account else None
        try:
            rows = self.fetch(
                connector,
                fields=fields,
                date_preset=date_preset,
                extra_params=extra,
            )
        except WindsorError as exc:
            # Search Console pode nao estar conectado nesta conta do Windsor.
            if "connector" in str(exc).lower():
                print(
                    f"[aviso] Windsor sem conector '{connector}' "
                    "(Search Console nao conectado?); briefing sem dados organicos."
                )
                return []
            raise
        result: list[SearchConsoleRow] = []
        for r in rows:
            result.append(
                SearchConsoleRow(
                    query=str(r.get("query", "")),
                    page=str(r.get("page", "")),
                    clicks=_to_float(r.get("clicks")),
                    impressions=_to_float(r.get("impressions")),
                    ctr=_to_float(r.get("ctr")),
                    position=_to_float(r.get("position")),
                )
            )
        return result


def _to_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
