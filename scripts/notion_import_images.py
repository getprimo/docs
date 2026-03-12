#!/usr/bin/env python3
"""Download image blocks from a Notion documentation source.

The script queries all pages from a Notion database or data source, walks each
page block tree, downloads every image it finds, and writes a Markdown manifest
that records where each image appeared in the source content.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import mimetypes
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


NOTION_API_BASE = "https://api.notion.com/v1"
API_VERSION_CANDIDATES = ("2025-09-03",)
IMAGE_BLOCK_TYPE = "image"
IMAGE_EXTENSIONS_BY_CONTENT_TYPE = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "image/heic": ".heic",
    "image/heif": ".heif",
}


class NotionAPIError(RuntimeError):
    """Raised when the Notion API returns an unrecoverable error."""


def normalize_notion_id(raw_value: str) -> str:
    clean = raw_value.replace("-", "").strip()
    if not re.fullmatch(r"[0-9a-fA-F]{32}", clean):
        raise ValueError(f"Unsupported Notion ID format: {raw_value}")
    return (
        f"{clean[0:8]}-{clean[8:12]}-{clean[12:16]}-"
        f"{clean[16:20]}-{clean[20:32]}"
    ).lower()


def extract_notion_id(source: str) -> str:
    match = re.search(r"([0-9a-fA-F]{32}|[0-9a-fA-F]{8}-[0-9a-fA-F-]{27})", source)
    if not match:
        raise ValueError(f"Could not find a Notion ID in: {source}")
    return normalize_notion_id(match.group(1))


def slugify(value: str, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    return slug or fallback


def markdown_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("`", "\\`")


def excerpt(text: str, limit: int = 160) -> str:
    collapsed = re.sub(r"\s+", " ", text).strip()
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 1].rstrip() + "…"


def join_rich_text(items: list[dict[str, Any]] | None) -> str:
    if not items:
        return ""
    return "".join(item.get("plain_text", "") for item in items).strip()


def extract_block_text(block: dict[str, Any]) -> str:
    block_type = block.get("type", "")
    payload = block.get(block_type, {})
    if block_type == "table_row":
        cells = payload.get("cells", [])
        values = [join_rich_text(cell) for cell in cells]
        return " | ".join(value for value in values if value)
    if block_type == "child_page":
        return payload.get("title", "").strip()
    if block_type == "link_to_page":
        linked_type = payload.get("type")
        if linked_type:
            return f"Linked {linked_type}"
        return "Linked page"
    if block_type == IMAGE_BLOCK_TYPE:
        return join_rich_text(payload.get("caption"))
    if isinstance(payload, dict):
        if "rich_text" in payload:
            return join_rich_text(payload.get("rich_text"))
        if "caption" in payload:
            return join_rich_text(payload.get("caption"))
    return ""


def page_title_from_properties(page: dict[str, Any]) -> str:
    for property_value in page.get("properties", {}).values():
        if property_value.get("type") == "title":
            title = join_rich_text(property_value.get("title"))
            if title:
                return title
    return f"Untitled {page['id'][:8]}"


def heading_level(block_type: str) -> int | None:
    levels = {"heading_1": 1, "heading_2": 2, "heading_3": 3}
    return levels.get(block_type)


def ensure_suffix_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    suffix = Path(parsed.path).suffix.lower()
    if suffix and len(suffix) <= 8:
        return suffix
    return ""


class NotionClient:
    def __init__(self, token: str, api_versions: tuple[str, ...] = API_VERSION_CANDIDATES):
        self.token = token
        self.api_versions = api_versions
        self.selected_version: str | None = None

    def _headers(self, notion_version: str, has_body: bool = False) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": notion_version,
        }
        if has_body:
            headers["Content-Type"] = "application/json"
        return headers

    def request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        versions = (self.selected_version,) if self.selected_version else self.api_versions
        for version in versions:
            try:
                response = self._request(method, path, params=params, body=body, notion_version=version)
                self.selected_version = version
                return response
            except NotionAPIError as error:
                last_error = error
                if "Notion-Version" not in str(error) or version == versions[-1]:
                    raise
            except Exception as error:  # pragma: no cover - defensive retry path
                last_error = error
                if version == versions[-1]:
                    raise
        raise RuntimeError("Notion API request failed") from last_error

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None,
        body: dict[str, Any] | None,
        notion_version: str,
    ) -> dict[str, Any]:
        url = f"{NOTION_API_BASE}{path}"
        if params:
            encoded_params = urllib.parse.urlencode(params)
            url = f"{url}?{encoded_params}"

        request_body = None
        if body is not None:
            request_body = json.dumps(body).encode("utf-8")

        request = urllib.request.Request(
            url,
            data=request_body,
            method=method.upper(),
            headers=self._headers(notion_version, has_body=body is not None),
        )

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raw_body = exc.read().decode("utf-8", errors="replace")
            try:
                error_payload = json.loads(raw_body)
            except json.JSONDecodeError:
                error_payload = {"message": raw_body}
            message = error_payload.get("message", raw_body)
            code = error_payload.get("code", "unknown_error")
            raise NotionAPIError(f"{exc.code} {code}: {message}") from exc

    def download_file(self, url: str) -> tuple[bytes, str | None]:
        request = urllib.request.Request(url)
        with urllib.request.urlopen(request, timeout=60) as response:
            content_type = response.headers.get_content_type()
            return response.read(), content_type


class PageWalker:
    def __init__(self, client: NotionClient):
        self.client = client

    def collect_page_images(self, page: dict[str, Any]) -> list[dict[str, Any]]:
        state = {
            "block_index": 0,
            "text_block_index": 0,
            "char_offset": 0,
            "heading_stack": [],
            "events": [],
            "images": [],
            "visited_block_ids": set(),
        }
        self._walk_children(page["id"], page, state)
        self._annotate_neighbors(state["events"], state["images"])
        return state["images"]

    def _walk_children(self, block_id: str, page: dict[str, Any], state: dict[str, Any]) -> None:
        next_cursor: str | None = None
        while True:
            params = {"page_size": 100}
            if next_cursor:
                params["start_cursor"] = next_cursor
            response = self.client.request_json("GET", f"/blocks/{block_id}/children", params=params)
            for block in response.get("results", []):
                self._visit_block(page, block, state)
            if not response.get("has_more"):
                return
            next_cursor = response.get("next_cursor")

    def _visit_block(self, page: dict[str, Any], block: dict[str, Any], state: dict[str, Any]) -> None:
        if block["id"] in state["visited_block_ids"]:
            return
        state["visited_block_ids"].add(block["id"])

        block_type = block.get("type", "")
        level = heading_level(block_type)
        if level is not None:
            heading_text = extract_block_text(block)
            state["heading_stack"] = [
                item for item in state["heading_stack"] if item["level"] < level
            ]
            state["heading_stack"].append({"level": level, "text": heading_text})

        state["block_index"] += 1
        block_number = state["block_index"]
        current_headings = [item["text"] for item in state["heading_stack"] if item["text"]]

        if block_type == IMAGE_BLOCK_TYPE:
            image_entry = {
                "page_id": page["id"],
                "page_title": page_title_from_properties(page),
                "page_url": page.get("url"),
                "block_id": block["id"],
                "block_index": block_number,
                "text_block_index": state["text_block_index"],
                "char_offset_before_block": state["char_offset"],
                "heading_path": current_headings,
                "caption": extract_block_text(block),
                "source": self._image_source(block),
            }
            if image_entry["source"]:
                state["images"].append(image_entry)
                state["events"].append({"type": "image", "payload": image_entry})

        block_text = extract_block_text(block)
        if block_text:
            state["text_block_index"] += 1
            state["events"].append(
                {
                    "type": "text",
                    "payload": {
                        "block_id": block["id"],
                        "block_index": block_number,
                        "text": block_text,
                    },
                }
            )
            state["char_offset"] += len(block_text) + 2

        if block.get("has_children"):
            self._walk_children(block["id"], page, state)

    def _image_source(self, block: dict[str, Any]) -> dict[str, Any] | None:
        payload = block.get(IMAGE_BLOCK_TYPE, {})
        source_type = payload.get("type")
        if source_type == "file":
            file_data = payload.get("file", {})
            return {"kind": "file", "url": file_data.get("url"), "expiry_time": file_data.get("expiry_time")}
        if source_type == "external":
            external_data = payload.get("external", {})
            return {"kind": "external", "url": external_data.get("url")}
        if source_type == "file_upload":
            upload_data = payload.get("file_upload", {})
            return {"kind": "file_upload", "id": upload_data.get("id"), "url": None}
        return None

    def _annotate_neighbors(self, events: list[dict[str, Any]], images: list[dict[str, Any]]) -> None:
        image_lookup = {id(image): image for image in images}
        previous_text = ""
        for event in events:
            if event["type"] == "text":
                previous_text = event["payload"]["text"]
                continue
            payload = event["payload"]
            if id(payload) in image_lookup:
                payload["previous_text"] = excerpt(previous_text)

        next_text = ""
        for event in reversed(events):
            if event["type"] == "text":
                next_text = event["payload"]["text"]
                continue
            payload = event["payload"]
            if id(payload) in image_lookup:
                payload["next_text"] = excerpt(next_text)


def resolve_source(client: NotionClient, source: str) -> dict[str, Any]:
    source_id = extract_notion_id(source)

    try:
        database = client.request_json("GET", f"/databases/{source_id}")
    except NotionAPIError:
        return {
            "kind": "data_source",
            "database_id": None,
            "database_title": None,
            "data_source_id": source_id,
            "data_source_name": None,
        }

    data_sources = database.get("data_sources") or []
    database_title = join_rich_text(database.get("title"))
    if data_sources:
        primary_source = data_sources[0]
        return {
            "kind": "database",
            "database_id": database["id"],
            "database_title": database_title,
            "data_source_id": primary_source["id"],
            "data_source_name": primary_source.get("name"),
        }

    return {
        "kind": "legacy_database",
        "database_id": database["id"],
        "database_title": database_title,
        "data_source_id": None,
        "data_source_name": None,
    }


def query_pages(client: NotionClient, source_info: dict[str, Any]) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    next_cursor: str | None = None

    if source_info["kind"] == "legacy_database":
        path = f"/databases/{source_info['database_id']}/query"
    else:
        path = f"/data_sources/{source_info['data_source_id']}/query"

    while True:
        body: dict[str, Any] = {"page_size": 100}
        if next_cursor:
            body["start_cursor"] = next_cursor
        response = client.request_json("POST", path, body=body)
        for result in response.get("results", []):
            if result.get("object") == "page":
                pages.append(result)
        if not response.get("has_more"):
            return pages
        next_cursor = response.get("next_cursor")


def download_images(
    client: NotionClient,
    images: list[dict[str, Any]],
    output_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    downloaded: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    output_dir.mkdir(parents=True, exist_ok=True)

    for page_image_number, image in enumerate(images, start=1):
        if page_image_number == 1 or page_image_number % 25 == 0:
            print(
                f"Downloading image {page_image_number}/{len(images)}: {image['page_title']}",
                file=sys.stderr,
                flush=True,
            )
        source = image.get("source") or {}
        url = source.get("url")
        if not url:
            image["download_status"] = "skipped"
            image["skip_reason"] = f"Unsupported image source type: {source.get('kind', 'unknown')}"
            skipped.append(image)
            continue

        try:
            file_bytes, content_type = client.download_file(url)
        except Exception as error:  # pragma: no cover - network path
            image["download_status"] = "failed"
            image["skip_reason"] = str(error)
            skipped.append(image)
            continue

        extension = (
            IMAGE_EXTENSIONS_BY_CONTENT_TYPE.get(content_type or "")
            or ensure_suffix_from_url(url)
            or mimetypes.guess_extension(content_type or "")
            or ".bin"
        )
        page_slug = slugify(image["page_title"], fallback=image["page_id"][:8])
        filename = (
            f"{page_slug}__img-{page_image_number:03d}__"
            f"block-{image['block_index']:04d}__{image['block_id'].replace('-', '')[:8]}{extension}"
        )
        destination = output_dir / filename
        destination.write_bytes(file_bytes)

        image["download_status"] = "downloaded"
        image["file_name"] = filename
        image["file_path"] = str(destination.relative_to(Path.cwd()))
        image["content_type"] = content_type
        image["file_size_bytes"] = len(file_bytes)
        downloaded.append(image)

    return downloaded, skipped


def write_manifest(
    manifest_path: Path,
    output_dir: Path,
    source_info: dict[str, Any],
    pages: list[dict[str, Any]],
    downloaded: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
) -> None:
    generated_at = dt.datetime.now(dt.timezone.utc).isoformat()
    lines = [
        "# Notion image import manifest",
        "",
        f"- Generated at: `{generated_at}`",
        f"- Output directory: `{output_dir.relative_to(Path.cwd())}`",
        f"- Pages scanned: `{len(pages)}`",
        f"- Images downloaded: `{len(downloaded)}`",
        f"- Images skipped: `{len(skipped)}`",
    ]

    if source_info.get("database_id"):
        lines.append(f"- Database ID: `{source_info['database_id']}`")
    if source_info.get("database_title"):
        lines.append(f"- Database title: `{markdown_escape(source_info['database_title'])}`")
    if source_info.get("data_source_id"):
        lines.append(f"- Data source ID: `{source_info['data_source_id']}`")
    if source_info.get("data_source_name"):
        lines.append(f"- Data source name: `{markdown_escape(source_info['data_source_name'])}`")

    lines.extend(["", "## Downloaded images", ""])

    if not downloaded:
        lines.append("No images were downloaded.")
    else:
        for index, image in enumerate(downloaded, start=1):
            heading_path = " > ".join(image.get("heading_path", [])) or "(root)"
            page_url = image.get("page_url") or ""
            lines.extend(
                [
                    f"### {index}. {markdown_escape(image['page_title'])}",
                    "",
                    f"- File: `{image['file_name']}`",
                    f"- Path: `{markdown_escape(image['file_path'])}`",
                    f"- Page ID: `{image['page_id']}`",
                    f"- Page URL: {page_url}",
                    f"- Block ID: `{image['block_id']}`",
                    f"- Block position: block `{image['block_index']}`, text block `{image['text_block_index']}`, char offset `{image['char_offset_before_block']}`",
                    f"- Heading path: `{markdown_escape(heading_path)}`",
                    f"- Previous text: \"{markdown_escape(image.get('previous_text', ''))}\"",
                    f"- Next text: \"{markdown_escape(image.get('next_text', ''))}\"",
                    f"- Caption: \"{markdown_escape(image.get('caption', ''))}\"",
                    f"- Source kind: `{image['source'].get('kind', 'unknown')}`",
                    f"- Source URL: {image['source'].get('url', '')}",
                    "",
                ]
            )

    lines.extend(["## Skipped images", ""])
    if not skipped:
        lines.append("No images were skipped.")
    else:
        for index, image in enumerate(skipped, start=1):
            lines.extend(
                [
                    f"### {index}. {markdown_escape(image['page_title'])}",
                    "",
                    f"- Page ID: `{image['page_id']}`",
                    f"- Page URL: {image.get('page_url', '')}",
                    f"- Block ID: `{image['block_id']}`",
                    f"- Reason: {markdown_escape(image.get('skip_reason', 'Unknown error'))}",
                    "",
                ]
            )

    manifest_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        required=True,
        help="Notion database or data source URL/ID that contains the articles.",
    )
    parser.add_argument(
        "--output-dir",
        default="images/notion-import",
        help="Directory where images and the manifest will be written.",
    )
    parser.add_argument(
        "--manifest-name",
        default="manifest.md",
        help="Manifest file name written inside the output directory.",
    )
    parser.add_argument(
        "--token-env",
        default="NOTION_TOKEN",
        help="Environment variable that stores the Notion integration token.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.environ.get(args.token_env)
    if not token:
        print(
            f"Missing Notion token. Set {args.token_env} before running the script.",
            file=sys.stderr,
        )
        return 1

    client = NotionClient(token)
    output_dir = Path(args.output_dir).resolve()
    manifest_path = output_dir / args.manifest_name

    try:
        source_info = resolve_source(client, args.source)
        pages = query_pages(client, source_info)
        walker = PageWalker(client)

        page_images: list[dict[str, Any]] = []
        for index, page in enumerate(pages, start=1):
            if index == 1 or index % 25 == 0:
                print(
                    f"Scanning page {index}/{len(pages)}: {page_title_from_properties(page)}",
                    file=sys.stderr,
                    flush=True,
                )
            page_images.extend(walker.collect_page_images(page))

        print(
            f"Collected {len(page_images)} image blocks across {len(pages)} pages.",
            file=sys.stderr,
            flush=True,
        )
        downloaded, skipped = download_images(client, page_images, output_dir)
        write_manifest(manifest_path, output_dir, source_info, pages, downloaded, skipped)
    except (NotionAPIError, ValueError) as error:
        print(f"Notion import failed: {error}", file=sys.stderr)
        print(
            "Check that the source URL/ID is correct and that the database or data source is shared "
            "with the Notion integration behind your token.",
            file=sys.stderr,
        )
        return 1

    print(f"Scanned {len(pages)} pages.")
    print(f"Downloaded {len(downloaded)} images to {output_dir.relative_to(Path.cwd())}.")
    print(f"Wrote manifest to {manifest_path.relative_to(Path.cwd())}.")
    if skipped:
        print(f"Skipped {len(skipped)} images.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
