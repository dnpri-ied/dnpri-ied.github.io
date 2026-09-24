#!/usr/bin/env python3
"""Build the weekly press-highlights feed using public Google News RSS results."""

from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "prensa_destacada.js"
SOURCES = ("Bloomberg", "Ámbito Financiero", "The Economist", "Reuters", "Financial Times")
QUERY = '(inversión OR inversiones OR empresa OR economía) Argentina ({sources}) when:7d'
MAX_ITEMS = 8


def feed_url(source: str) -> str:
    query = QUERY.format(sources=f'source:"{source}"')
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": query, "hl": "es-419", "gl": "AR", "ceid": "AR:es-419"}
    )


def clean(value: str | None) -> str:
    value = html.unescape(re.sub(r"<[^>]+>", " ", value or ""))
    return re.sub(r"\s+", " ", value).strip()


def parse_feed(payload: bytes, expected_source: str) -> list[dict[str, str]]:
    root = ET.fromstring(payload)
    results = []
    for item in root.findall("./channel/item"):
        title = clean(item.findtext("title"))
        source = clean(item.findtext("source")) or expected_source
        suffix = f" - {source}"
        if title.endswith(suffix):
            title = title[: -len(suffix)].strip()
        published = email.utils.parsedate_to_datetime(item.findtext("pubDate") or "")
        results.append(
            {
                "titulo": title,
                "fuente": source,
                "fecha": published.date().isoformat(),
                "url": clean(item.findtext("link")),
            }
        )
    return results


def fetch(source: str) -> list[dict[str, str]]:
    request = urllib.request.Request(feed_url(source), headers={"User-Agent": "DNPRI-IED/1.0"})
    with urllib.request.urlopen(request, timeout=25) as response:
        return parse_feed(response.read(), source)


def collect() -> tuple[list[dict[str, str]], list[str]]:
    items, errors = [], []
    for source in SOURCES:
        try:
            items.extend(fetch(source))
        except (OSError, ValueError, ET.ParseError) as exc:
            errors.append(f"{source}: {exc}")
    unique = {item["url"]: item for item in items if item["titulo"] and item["url"]}
    ordered = sorted(unique.values(), key=lambda item: item["fecha"], reverse=True)
    return ordered[:MAX_ITEMS], errors


def write(items: list[dict[str, str]], updated: str) -> None:
    data = {
        "meta": {
            "actualizado": updated,
            "frecuencia": "semanal",
            "criterio": "Noticias económicas sobre Argentina publicadas en los últimos 7 días.",
        },
        "datos": items,
    }
    OUTPUT.write_text(
        "// Archivo generado automáticamente; no editar manualmente.\n"
        f"window.PRENSA_DESTACADA={json.dumps(data, ensure_ascii=False, separators=(',', ':'))};\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Fecha ISO usada como marca de actualización")
    parser.add_argument("--allow-empty", action="store_true", help="Permite reemplazar el feed por uno vacío")
    args = parser.parse_args()
    today = args.date or dt.datetime.now(dt.timezone.utc).date().isoformat()
    items, errors = collect()
    if not items and not args.allow_empty:
        raise SystemExit("No se encontraron noticias; se conserva el archivo publicado. " + "; ".join(errors))
    write(items, today)
    print(f"Actualizadas {len(items)} noticias ({today}).")
    if errors:
        print("Fuentes no disponibles: " + "; ".join(errors))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
