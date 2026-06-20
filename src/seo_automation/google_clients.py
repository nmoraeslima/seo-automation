"""Integracao com Google Sheets, Docs e Drive via service account."""

from __future__ import annotations

from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]


class GoogleClients:
    def __init__(self, service_account_file: str | Path):
        path = Path(service_account_file)
        if not path.exists():
            raise FileNotFoundError(
                f"Arquivo da service account nao encontrado: {path}. "
                "Defina GOOGLE_SERVICE_ACCOUNT_FILE no .env."
            )
        creds = Credentials.from_service_account_file(str(path), scopes=SCOPES)
        self.sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)
        self.docs = build("docs", "v1", credentials=creds, cache_discovery=False)
        self.drive = build("drive", "v3", credentials=creds, cache_discovery=False)

    # ---------- Sheets ----------
    def read_range(self, spreadsheet_id: str, a1_range: str) -> list[list[str]]:
        resp = (
            self.sheets.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=a1_range)
            .execute()
        )
        return resp.get("values", [])

    def ensure_sheet(self, spreadsheet_id: str, title: str) -> None:
        """Cria a aba se ela ainda nao existir."""
        meta = self.sheets.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        existing = {s["properties"]["title"] for s in meta.get("sheets", [])}
        if title in existing:
            return
        self.sheets.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": title}}}]},
        ).execute()

    def overwrite_sheet(
        self, spreadsheet_id: str, title: str, rows: list[list]
    ) -> None:
        """Limpa a aba e escreve as linhas a partir de A1."""
        self.ensure_sheet(spreadsheet_id, title)
        self.sheets.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id, range=f"{title}!A:ZZ"
        ).execute()
        self.sheets.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{title}!A1",
            valueInputOption="RAW",
            body={"values": rows},
        ).execute()

    def append_rows(
        self, spreadsheet_id: str, title: str, rows: list[list]
    ) -> None:
        self.ensure_sheet(spreadsheet_id, title)
        self.sheets.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{title}!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": rows},
        ).execute()

    # ---------- Docs / Drive ----------
    def create_doc(self, title: str, folder_id: str | None = None) -> str:
        """Cria um Google Doc (opcionalmente em uma pasta) e retorna o id."""
        file_metadata = {
            "name": title,
            "mimeType": "application/vnd.google-apps.document",
        }
        if folder_id:
            file_metadata["parents"] = [folder_id]
        doc = self.drive.files().create(
            body=file_metadata, fields="id", supportsAllDrives=True
        ).execute()
        return doc["id"]

    def write_doc_markdown(self, doc_id: str, blocks: list[tuple[str, str]]) -> None:
        """Escreve conteudo em um Doc.

        `blocks` e uma lista de (estilo, texto), onde estilo e um de:
        'TITLE', 'HEADING_1', 'HEADING_2', 'HEADING_3', 'NORMAL_TEXT', 'BULLET'.
        """
        requests_body: list[dict] = []
        index = 1
        for style, text in blocks:
            content = text + "\n"
            requests_body.append(
                {"insertText": {"location": {"index": index}, "text": content}}
            )
            end = index + len(content)
            named_style = "NORMAL_TEXT" if style == "BULLET" else style
            requests_body.append(
                {
                    "updateParagraphStyle": {
                        "range": {"startIndex": index, "endIndex": end},
                        "paragraphStyle": {"namedStyleType": named_style},
                        "fields": "namedStyleType",
                    }
                }
            )
            if style == "BULLET":
                requests_body.append(
                    {
                        "createParagraphBullets": {
                            "range": {"startIndex": index, "endIndex": end},
                            "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE",
                        }
                    }
                )
            index = end
        self.docs.documents().batchUpdate(
            documentId=doc_id, body={"requests": requests_body}
        ).execute()

    def doc_url(self, doc_id: str) -> str:
        return f"https://docs.google.com/document/d/{doc_id}/edit"
