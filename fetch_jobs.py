import json
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
import hashlib
import re
import html
from pathlib import Path
from datetime import datetime, timezone

BASE = Path(__file__).parent
SOURCE_FILE = BASE / "sources.json"
JOBS_FILE = BASE / "jobs.json"


def clean(value):
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def get_child(element, names):
    for child in element:
        tag = child.tag.split("}")[-1].lower()
        if tag in names:
            return "".join(child.itertext()).strip()
    return ""


def get_link(element):
    for child in element:
        if child.tag.split("}")[-1].lower() == "link":
            href = child.attrib.get("href")
            if href:
                return href
            if child.text:
                return child.text.strip()
    return ""


def fetch_feed(source):
    request = urllib.request.Request(
        source["url"],
        headers={"User-Agent": "CareerAlertUpdater/1.0"}
    )

    with urllib.request.urlopen(request, timeout=25) as response:
        root = ET.fromstring(response.read())

    jobs = []

    for item in root.iter():
        tag = item.tag.split("}")[-1].lower()

        if tag not in ("item", "entry"):
            continue

        title = clean(get_child(item, {"title"}))
        link = get_link(item)

        description = clean(
            get_child(item, {
                "description", "summary", "content", "encoded"
            })
        )

        published = get_child(item, {
            "pubdate", "published", "updated", "date"
        })

        if not title or not link:
            continue

        unique = hashlib.sha256(
            (link or title).encode("utf-8")
        ).hexdigest()

        jobs.append({
            "id": unique,
            "title": title,
            "link": link,
            "description": description,
            "category": source["category"],
            "source": source["name"],
            "published": published,
            "fetchedAt": datetime.now(timezone.utc).isoformat()
        })

    return jobs


def main():
    if not SOURCE_FILE.exists():
        SOURCE_FILE.write_text(
            json.dumps({"feeds": []}, indent=2),
            encoding="utf-8"
        )

    config = json.loads(SOURCE_FILE.read_text(encoding="utf-8"))
    feeds = config.get("feeds", [])

    existing = []

    if JOBS_FILE.exists():
        existing = json.loads(JOBS_FILE.read_text(encoding="utf-8"))

    if not isinstance(existing, list):
        raise ValueError("jobs.json must contain a JSON list")

    all_jobs = {job["id"]: job for job in existing if "id" in job}

    for source in feeds:
        try:
            fetched = fetch_feed(source)

            for job in fetched:
                all_jobs[job["id"]] = job

            print(f"SUCCESS: {source['name']} - {len(fetched)} jobs")

        except Exception as error:
            print(f"ERROR: {source.get('name', 'Unknown')} - {error}")

    result = sorted(
        all_jobs.values(),
        key=lambda job: job.get("published", ""),
        reverse=True
    )

    JOBS_FILE.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"Total saved jobs: {len(result)}")


if __name__ == "__main__":
    main()
