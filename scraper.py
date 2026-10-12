
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

SOURCE_URL = (
    "https://betproof.co.za/casino-bonuses-south-africa/"
)
USER_AGENT = "CasinoBonusAssessmentBot/1.0"
GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
)
DEFAULT_MODEL = "gemini-2.5-flash"
OUTPUT_FILE = Path(__file__).with_name("bonuses.json")

# Three records from the same comparison table.
TARGETS = {
    "Hollywoodbets": "Hollywoodbets",
    "Betway South Africa": "Betway South Africa",
    "PlayaBets": "PlayaBets",
}


def check_robots_permission(url):
    """Fail closed if robots.txt cannot be checked."""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    response = requests.get(
        robots_url,
        headers={"User-Agent": USER_AGENT},
        timeout=15,
    )
    response.raise_for_status()

    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(response.text.splitlines())

    if not parser.can_fetch(USER_AGENT, url):
        raise RuntimeError(
            f"Robots policy does not permit fetching {url}"
        )

    print("Robots permission check passed.")


def fetch_page(url):
    response = requests.get(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html",
        },
        timeout=20,
    )
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    if "html" not in content_type.lower():
        raise RuntimeError("Source did not return HTML.")

    return response.text


def extract_source_rows(html):
    """Extract real rows from the source's comparison table."""
    soup = BeautifulSoup(html, "html.parser")
    results = {}
    required_headers = {
        "casino": {"casino"},
        "bonus": {"bonus"},
        "wagering": {"wagering"},
        "minimum_deposit": {"min deposit", "minimum deposit"},
    }

    for table in soup.find_all("table"):
        rows = table.find_all("tr")

        if not rows:
            continue

        headers = [
            " ".join(cell.get_text(" ", strip=True).lower().split())
            for cell in rows[0].find_all(["th", "td"])
        ]

        column_indexes = {}
        for field, aliases in required_headers.items():
            column_indexes[field] = next(
                (
                    index
                    for index, header in enumerate(headers)
                    if header in aliases
                ),
                None,
            )

        if any(index is None for index in column_indexes.values()):
            continue

        for row in rows[1:]:
            cells = row.find_all(["th", "td"])
            if len(cells) <= max(column_indexes.values()):
                continue

            casino_cell = cells[column_indexes["casino"]]
            casino_link = casino_cell.find("a")
            casino_name = (
                casino_link.get_text(" ", strip=True)
                if casino_link
                else casino_cell.get_text(" ", strip=True)
            )

            for target in TARGETS:
                if target.lower() in casino_name.lower():
                    results[target] = {
                        "casino": casino_name,
                        "raw_bonus": cells[
                            column_indexes["bonus"]
                        ].get_text(" ", strip=True),
                        "raw_wagering": cells[
                            column_indexes["wagering"]
                        ].get_text(" ", strip=True),
                        "raw_minimum_deposit": cells[
                            column_indexes["minimum_deposit"]
                        ].get_text(" ", strip=True),
                    }

        if len(results) == len(TARGETS):
            break

    missing = set(TARGETS) - set(results)
    if missing:
        raise RuntimeError(
            "Could not extract all three casinos from the "
            f"comparison table. Missing: {sorted(missing)}. "
            "The source layout may have changed."
        )

    return [results[name] for name in TARGETS]


def structure_with_llm(raw_rows):
    """Use Gemini's free-tier API to interpret the source's free-text terms."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing from .env. Create a free-tier "
            "key in Google AI Studio and add it to .env."
        )

    model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    schema = {
        "type": "OBJECT",
        "properties": {
            "welcome_bonus": {"type": "STRING"},
            "wagering_requirement": {"type": "STRING", "nullable": True},
            "minimum_deposit": {"type": "STRING", "nullable": True},
        },
        "required": [
            "welcome_bonus",
            "wagering_requirement",
            "minimum_deposit",
        ],
    }

    structured = []

    for row in raw_rows:
        raw_terms = (
            f"Casino: {row['casino']}\n"
            f"Bonus: {row['raw_bonus']}\n"
            f"Wagering: {row['raw_wagering']}\n"
            f"Minimum deposit: {row['raw_minimum_deposit']}"
        )

        response = requests.post(
            f"{GEMINI_API_URL}{model}:generateContent",
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
            json={
                "contents": [
                    {
                        "role": "user",
                        "parts": [{
                            "text": (
                                "Extract the casino bonus fields from "
                                "the source text below. Preserve the "
                                "original currency, wording and separate "
                                "wagering multipliers. Never guess or add "
                                "facts. Use null for missing values.\n\n"
                                f"{raw_terms}"
                            ),
                        }],
                    },
                ],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseSchema": schema,
                    "temperature": 0,
                },
            },
            timeout=120,
        )
        response.raise_for_status()

        result = response.json()
        candidates = result.get("candidates", [])
        parts = (
            candidates[0].get("content", {}).get("parts", [])
            if candidates
            else []
        )
        content = "".join(
            part.get("text", "")
            for part in parts
            if isinstance(part.get("text"), str)
        )
        if not content:
            raise RuntimeError(
                f"Empty Gemini response for {row['casino']}"
            )

        data = json.loads(content)

        required = {
            "welcome_bonus",
            "wagering_requirement",
            "minimum_deposit",
        }
        if set(data) != required:
            raise RuntimeError(
                f"Unexpected LLM schema for {row['casino']}"
            )

        for key in required:
            value = data[key]
            if value is not None and not isinstance(value, str):
                raise RuntimeError(
                    f"Invalid type for {key}: {row['casino']}"
                )

        if not data["welcome_bonus"]:
            raise RuntimeError(
                f"Missing welcome bonus for {row['casino']}"
            )

        structured.append({
            "casino": row["casino"],
            "welcome_bonus": data["welcome_bonus"],
            "wagering_requirement": data["wagering_requirement"],
            "minimum_deposit": data["minimum_deposit"],
            "source_url": SOURCE_URL,
            "raw_terms": {
                "bonus": row["raw_bonus"],
                "wagering": row["raw_wagering"],
                "minimum_deposit": row["raw_minimum_deposit"],
            },
        })

    return structured


def main():
    try:
        check_robots_permission(SOURCE_URL)
        html = fetch_page(SOURCE_URL)
        raw_rows = extract_source_rows(html)
        records = structure_with_llm(raw_rows)

        output = {
            "source_url": SOURCE_URL,
            "scraped_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "count": len(records),
            "casinos": records,
        }

        # Validate the final JSON before writing it.
        encoded = json.dumps(
            output, indent=2, ensure_ascii=False
        )
        json.loads(encoded)
        OUTPUT_FILE.write_text(encoded + "\n", encoding="utf-8")

        print(f"Successfully saved {len(records)} records.")
        print(f"Output: {OUTPUT_FILE}")
        print(json.dumps(records, indent=2, ensure_ascii=False))

    except Exception as exc:
        print(f"Scraper failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
