#!/usr/bin/env python3
"""Keep relevant English Notion images and inject them into MDX files."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMPORT_DIR = ROOT / "images" / "notion-import"
MANIFEST_PATH = IMPORT_DIR / "manifest.md"

TITLE_TO_DOC = {
    "Buy Apple Care Enterprise guarantees": Path("procurement/applecare-enterprise.mdx"),
    "CIS Benchmarks": Path("mdm/scripts/cis-benchmarks.mdx"),
    "Connect an HRIS to Primo": Path("employees/connect-hris.mdx"),
    "Connect your apps": Path("saas/connect-apps.mdx"),
    "Device Orders with Zero-Touch": Path("mdm/zero-touch/device-orders-zero-touch.mdx"),
    "Employee MDM Installation Guide": Path("mdm/rollout/employee-mdm-installation.mdx"),
    "Employee experience for OS Updates": Path("mdm/guides/os-updates-employee-experience.mdx"),
    "Frequently Asked Questions": Path("mdm/rollout/faq.mdx"),
    "Migrate your device from another MDM": Path("mdm/get-started/migrate-from-another-mdm.mdx"),
    "Remove an MDM manually from a device": Path("mdm/guides/remove-mdm-manually.mdx"),
    "Resolve enrollment issues": Path("mdm/guides/resolve-enrollment-issues.mdx"),
    "Set up licence provisioning": Path("saas/licence-provisioning.mdx"),
    "Zero-Touch Enrollment for Macs": Path("mdm/zero-touch/zero-touch-macs.mdx"),
    "Zero-Touch Enrollment for Windows": Path("mdm/zero-touch/zero-touch-windows.mdx"),
}

CUSTOM_ANCHORS = {
    "buy-apple-care-enterprise-guarantees__img-110__block-0014__2a943d9f.png": (
        "You will receive an email from Apple containing your enrollment number, "
        "which you can provide when placing your order."
    ),
    "employee-mdm-installation-guide__img-003__block-0040__2da43d9f.png": (
        "1. Open **System Settings** and go to **General \\> Device Management** "
        "(You can also use the search field in System Settings and search for Device Management.)"
    ),
    "employee-mdm-installation-guide__img-006__block-0050__2b843d9f.png": (
        "If you see an error that primo-enrollment.pkg is blocked:"
    ),
    "employee-mdm-installation-guide__img-007__block-0052__2b843d9f.png": (
        "You can unblock it in Settings > Privacy & Security > Security"
    ),
    "connect-your-apps__img-086__block-0005__27343d9f.png": (
        "If you are using Google Workspace, you can connect it in Identities & Access. "
        "It will automatically map all the applications for which your Google Workspace "
        "is used as a SSO connector."
    ),
    "connect-your-apps__img-089__block-0024__25443d9f.png": (
        "On-screen guidance is provided for each application to complete the setup."
    ),
    "device-orders-with-zero-touch__img-104__block-0016__eb022d41.png": (
        "8. In Primo, activate the toggle to finalize."
    ),
    "device-orders-with-zero-touch__img-105__block-0017__3ff17dd0.jpg": (
        "8. In Primo, activate the toggle to finalize."
    ),
    "device-orders-with-zero-touch__img-106__block-0018__19e5323d.png": (
        "8. In Primo, activate the toggle to finalize."
    ),
    "zero-touch-enrollment-for-macs__img-058__block-0072__1fb43d9f.png": (
        "2. Select country, language, and keyboard settings"
    ),
    "zero-touch-enrollment-for-macs__img-059__block-0075__1fb43d9f.png": (
        "4. The **Remote Management** screen appears"
    ),
    "zero-touch-enrollment-for-windows__img-024__block-0011__1b243d9f.png": (
        "The minimum license covering both features is **Enterprise Mobility + Security E3**"
    ),
    "zero-touch-enrollment-for-windows__img-025__block-0018__1b243d9f.png": (
        "4. Accept FleetDM terms and conditions"
    ),
    "zero-touch-enrollment-for-windows__img-026__block-0020__1b243d9f.png": (
        "5. Sign in with Microsoft credentials (+ 2FA if enabled)"
    ),
    "zero-touch-enrollment-for-windows__img-027__block-0022__1b243d9f.png": (
        "6. Set up a PIN code and fingerprint (if supported)"
    ),
    "zero-touch-enrollment-for-windows__img-028__block-0065__27743d9f.png": (
        "Enter your **Fleet** instance address (`https://{company}.mdm.getprimo.com`) and click **Save**"
    ),
    "zero-touch-enrollment-for-windows__img-029__block-0079__27743d9f.png": (
        "and click **Add permissions**"
    ),
}


@dataclass
class Entry:
    title: str
    file_name: str
    file_path: str
    page_id: str
    page_url: str
    block_id: str
    block_position: str
    heading_path: str
    previous_text: str
    next_text: str
    caption: str
    source_kind: str
    source_url: str
    mdx_target: Path | None = None


def normalize(value: str) -> str:
    value = value.replace("\\>", ">").replace("’", "'").replace("“", '"').replace("”", '"')
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = value.replace("…", " ")
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[`*_>#]", " ", value)
    value = re.sub(r"[^a-zA-Z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip().lower()


def parse_manifest() -> list[Entry]:
    text = MANIFEST_PATH.read_text(encoding="utf-8")
    pattern = re.compile(r"^### \d+\. (.+?)$([\s\S]*?)(?=^### \d+\. |\Z)", re.M)
    entries: list[Entry] = []
    for match in pattern.finditer(text):
        title = match.group(1)
        block = match.group(2)

        def get_bullet(label: str) -> str:
            bullet = re.search(rf"^- {re.escape(label)}: ?(.*)$", block, re.M)
            return bullet.group(1).strip() if bullet else ""

        entry = Entry(
            title=title,
            file_name=get_bullet("File").strip("`"),
            file_path=get_bullet("Path").strip("`"),
            page_id=get_bullet("Page ID").strip("`"),
            page_url=get_bullet("Page URL"),
            block_id=get_bullet("Block ID").strip("`"),
            block_position=get_bullet("Block position"),
            heading_path=get_bullet("Heading path").strip("`"),
            previous_text=get_bullet("Previous text").strip('"'),
            next_text=get_bullet("Next text").strip('"'),
            caption=get_bullet("Caption").strip('"'),
            source_kind=get_bullet("Source kind").strip("`"),
            source_url=get_bullet("Source URL"),
        )
        entry.mdx_target = TITLE_TO_DOC.get(entry.title)
        entries.append(entry)
    return entries


def alt_text(entry: Entry) -> str:
    label = entry.caption or entry.heading_path.split(" > ")[-1].strip() or entry.title
    label = label.replace("`", "").replace('"', "").strip()
    if label == "(root)":
        label = entry.title
    return f"Screenshot: {label}"


def line_anchor_candidates(entry: Entry) -> list[str]:
    candidates = []
    custom = CUSTOM_ANCHORS.get(entry.file_name)
    if custom:
        candidates.append(custom)
    if entry.previous_text:
        candidates.append(entry.previous_text)
    if entry.next_text:
        candidates.append(entry.next_text)
    if entry.heading_path:
        candidates.append(entry.heading_path.split(" > ")[-1])
    return [candidate for candidate in candidates if candidate and candidate != "(root)"]


def is_list_line(line: str) -> bool:
    return bool(re.match(r"^\s*(?:[-*+]|\d+\.)\s+", line))


def insertion_block(entry: Entry, anchor_line: str) -> list[str]:
    image_md = f"![{alt_text(entry)}](/images/notion-import/{entry.file_name})"
    if is_list_line(anchor_line):
        indent = re.match(r"^(\s*)", anchor_line).group(1) + "    "
        return [f"{indent}{image_md}", ""]
    return ["", image_md, ""]


def find_anchor_index(lines: list[str], start_index: int, entry: Entry) -> int:
    normalized_lines = [normalize(line) for line in lines]
    candidate_norms = [normalize(candidate) for candidate in line_anchor_candidates(entry)]
    candidate_norms = [candidate for candidate in candidate_norms if candidate]
    if not candidate_norms:
        return len(lines) - 1

    search_ranges = [range(start_index, len(lines)), range(0, start_index)]
    for search_range in search_ranges:
        for candidate in candidate_norms:
            for index in search_range:
                if candidate and candidate in normalized_lines[index]:
                    return index
    raise RuntimeError(f"No anchor found for {entry.file_name} in {entry.mdx_target}")


def inject_images(entries: list[Entry]) -> dict[Path, int]:
    grouped: dict[Path, list[Entry]] = {}
    for entry in entries:
        if entry.mdx_target is None:
            continue
        grouped.setdefault(entry.mdx_target, []).append(entry)

    injections: dict[Path, int] = {}
    for relative_path, doc_entries in grouped.items():
        doc_path = ROOT / relative_path
        lines = doc_path.read_text(encoding="utf-8").splitlines()
        cursor = 0
        injected_count = 0
        for entry in doc_entries:
            image_ref = f"/images/notion-import/{entry.file_name}"
            current_text = "\n".join(lines)
            if image_ref in current_text:
                continue
            anchor_index = find_anchor_index(lines, cursor, entry)
            block = insertion_block(entry, lines[anchor_index])
            insert_at = anchor_index + 1
            lines[insert_at:insert_at] = block
            cursor = insert_at + len(block)
            injected_count += 1

        updated_text = "\n".join(lines).replace("\n\n\n\n", "\n\n\n").rstrip() + "\n"
        doc_path.write_text(updated_text, encoding="utf-8")
        injections[relative_path] = injected_count
    return injections


def prune_assets(entries: list[Entry]) -> list[Entry]:
    kept_entries = [entry for entry in entries if entry.title in TITLE_TO_DOC]
    keep_files = {entry.file_name for entry in kept_entries}
    for path in IMPORT_DIR.iterdir():
        if path.name == MANIFEST_PATH.name:
            continue
        if path.is_file() and path.name not in keep_files:
            path.unlink()
    return kept_entries


def rewrite_manifest(entries: list[Entry], removed_count: int) -> None:
    lines = [
        "# Notion image import manifest",
        "",
        "- Scope: English screenshots kept and linked from the current MDX corpus",
        f"- Images kept: `{len(entries)}`",
        f"- Images removed: `{removed_count}`",
        "",
        "## Kept images",
        "",
    ]

    for index, entry in enumerate(entries, start=1):
        heading_path = entry.heading_path or "(root)"
        lines.extend(
            [
                f"### {index}. {entry.title}",
                "",
                f"- File: `{entry.file_name}`",
                f"- Path: `images/notion-import/{entry.file_name}`",
                f"- MDX target: `{entry.mdx_target}`",
                f"- Page ID: `{entry.page_id}`",
                f"- Page URL: {entry.page_url}",
                f"- Block ID: `{entry.block_id}`",
                f"- Block position: {entry.block_position}",
                f"- Heading path: `{heading_path}`",
                f'- Previous text: "{entry.previous_text}"',
                f'- Next text: "{entry.next_text}"',
                "",
            ]
        )

    MANIFEST_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    entries = parse_manifest()
    removed_count = len(entries) - sum(1 for entry in entries if entry.title in TITLE_TO_DOC)
    kept_entries = prune_assets(entries)
    injections = inject_images(kept_entries)
    rewrite_manifest(kept_entries, removed_count)

    total_injected = sum(injections.values())
    print(f"Injected {total_injected} images across {len(injections)} MDX files.")
    for path, count in sorted(injections.items()):
        print(f"- {path}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
