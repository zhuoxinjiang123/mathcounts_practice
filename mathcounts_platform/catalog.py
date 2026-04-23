import html
import re

from mathcounts_platform.db import upsert_resource


GRADABLE_ROUNDS = {"Sprint", "Target", "Team"}


def _clean_label(value):
    without_tags = re.sub(r"<[^>]+>", "", value)
    return html.unescape(without_tags).replace("\ufeff", "").strip()


def parse_national_resources(html_text):
    catalog = []
    year_blocks = re.finditer(
        r'<div class="paragraph">.*?<font size="6">(?P<year>\d{4})</font>.*?</div>',
        html_text,
        re.DOTALL,
    )

    for match in year_blocks:
        block = match.group(0)
        national_match = re.search(
            r"<strong>NATIONAL:.*?</strong>(?P<national>.*?)(?:<br\s*/?>|</div>)",
            block,
            re.DOTALL,
        )
        if not national_match:
            continue

        resources = []
        for url, raw_label in re.findall(
            r'<a href="([^"]+)"[^>]*>(.*?)</a>',
            national_match.group("national"),
            re.DOTALL,
        ):
            label = _clean_label(raw_label)
            if not label:
                continue
            resources.append(
                {
                    "label": label,
                    "url": html.unescape(url),
                    "kind": "paper" if label in GRADABLE_ROUNDS else "reference",
                    "gradable": label in GRADABLE_ROUNDS,
                }
            )

        if resources:
            catalog.append({"year": int(match.group("year")), "resources": resources})

    return sorted(catalog, key=lambda item: item["year"], reverse=True)


def seed_catalog(conn, catalog_items):
    for item in catalog_items:
        for resource in item["resources"]:
            upsert_resource(
                conn,
                item["year"],
                resource["label"],
                resource.get("kind", "reference"),
                resource["url"],
                resource.get("gradable", False),
            )
