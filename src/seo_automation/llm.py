"""Geracao opcional de texto via LLM para enriquecer os briefings.

Se OPENAI_API_KEY nao estiver definida, as funcoes retornam None e o
briefing e montado apenas com dados/estrutura (sem texto de IA).
"""

from __future__ import annotations

import json


class LLMClient:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.enabled = bool(api_key)
        self.model = model
        self._client = None
        if self.enabled:
            from openai import OpenAI

            self._client = OpenAI(api_key=api_key)

    def briefing_outline(
        self, keyword: str, related_queries: list[str]
    ) -> dict | None:
        """Gera titulo, intencao de busca, resumo e estrutura H2/H3.

        Retorna dict com chaves: title, intent, summary, headings (lista),
        faq (lista). Retorna None se o LLM estiver desabilitado/falhar.
        """
        if not self.enabled or self._client is None:
            return None

        related = ", ".join(related_queries[:25]) or "(nenhuma)"
        prompt = (
            "Voce e um especialista em SEO de uma agencia de marketing brasileira. "
            "Crie um briefing de conteudo em portugues do Brasil para a palavra-chave "
            f'alvo: "{keyword}".\n'
            f"Palavras-chave relacionadas (do Search Console): {related}.\n\n"
            "Responda APENAS com JSON valido no formato:\n"
            "{\n"
            '  "title": "titulo de artigo otimizado",\n'
            '  "intent": "intencao de busca (informacional/transacional/etc)",\n'
            '  "summary": "1-2 frases sobre o angulo do conteudo",\n'
            '  "headings": ["H2: ...", "H3: ...", ...],\n'
            '  "faq": ["pergunta 1?", "pergunta 2?", ...]\n'
            "}\n"
        )
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content or "{}"
            return json.loads(content)
        except Exception:  # noqa: BLE001 - LLM e best-effort
            return None
