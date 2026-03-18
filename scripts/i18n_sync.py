#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


ROOT = Path(__file__).resolve().parent.parent
I18N_DIR = ROOT / "i18n"
MANIFEST_PATH = I18N_DIR / "translation-manifest.json"
GLOSSARY_PATH = I18N_DIR / "glossary.json"
SOURCE_LOCALE = "en"
SUPPORTED_LOCALES = ("fr", "de", "es", "it")
LOCALE_DIRS = {f"{locale}/" for locale in SUPPORTED_LOCALES}
FRONTMATTER_KEYS = {"title", "description", "sidebarTitle"}
ATTR_KEYS = (
    "title",
    "description",
    "tab",
    "group",
    "label",
    "summary",
    "caption",
    "subtitle",
    "placeholder",
    "aria-label",
    "alt",
)
JS_PROP_KEYS = (
    "label",
    "desc",
    "title",
    "description",
    "summary",
    "caption",
    "subtitle",
    "content",
)
INTERNAL_PATH_EXCLUSIONS = (
    "/images/",
    "/logo/",
    "/favicon",
    "/favicon.svg",
    "/references/",
)
SEGMENT_TOKEN = "ZXSEGBOUNDARY1CDA0C52"
PROTECT_TOKEN = "ZXPROTECT"


class TranslationError(RuntimeError):
    pass


def load_glossary() -> Dict[str, Dict[str, str]]:
    with GLOSSARY_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def is_source_path(path: Path) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    if not relative.endswith(".mdx"):
        return False
    return not any(relative.startswith(prefix) for prefix in LOCALE_DIRS)


def discover_source_files() -> List[Path]:
    files: List[Path] = []
    for path in ROOT.rglob("*.mdx"):
        if is_source_path(path):
            files.append(path)
    return sorted(files)


def split_frontmatter(text: str) -> Tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    end_index = text.find("\n---\n", 4)
    if end_index == -1:
        return "", text
    frontmatter = text[: end_index + 5]
    body = text[end_index + 5 :]
    return frontmatter, body


class Translator:
    def __init__(self, engine: str, glossary: Dict[str, Dict[str, str]], api_key: str | None = None) -> None:
        self.engine = engine
        self.api_key = api_key
        self.glossary = glossary
        self.cache: Dict[Tuple[str, str], str] = {}

    def translate_many(self, locale: str, texts: Iterable[str]) -> Dict[str, str]:
        pending: List[str] = []
        for text in texts:
            key = (locale, text)
            if key in self.cache:
                continue
            pending.append(text)

        if not pending:
            return {text: self.cache[(locale, text)] for text in texts}

        if self.engine == "copy":
            for text in pending:
                self.cache[(locale, text)] = text
        elif self.engine == "deepl":
            self._translate_many_deepl(locale, pending)
        else:
            self._translate_many_google(locale, pending)

        return {text: self.cache[(locale, text)] for text in texts}

    def _translate_many_deepl(self, locale: str, texts: List[str]) -> None:
        if not self.api_key:
            raise TranslationError("DEEPL_API_KEY is required when engine=deepl")

        endpoint = "https://api-free.deepl.com/v2/translate" if self.api_key.endswith(":fx") else "https://api.deepl.com/v2/translate"
        for chunk in chunked(texts, 25):
            protected = [protect_snippet(text, locale, self.glossary) for text in chunk]
            payload: List[Tuple[str, str]] = [
                ("auth_key", self.api_key),
                ("source_lang", SOURCE_LOCALE.upper()),
                ("target_lang", locale.upper()),
                ("preserve_formatting", "1"),
            ]
            for text, _restore in protected:
                payload.append(("text", text))

            body = urllib.parse.urlencode(payload).encode("utf-8")
            request = urllib.request.Request(endpoint, data=body, headers={"User-Agent": "Mozilla/5.0"})
            try:
                with urllib.request.urlopen(request) as response:
                    data = json.load(response)
            except urllib.error.HTTPError as exc:
                raise TranslationError(f"DeepL request failed: {exc}") from exc

            translations = data.get("translations", [])
            if len(translations) != len(chunk):
                raise TranslationError("DeepL response size mismatch")

            for original, protected_text, translation in zip(chunk, protected, translations):
                translated = restore_snippet(translation["text"], protected_text[1])
                self.cache[(locale, original)] = translated

    def _translate_many_google(self, locale: str, texts: List[str]) -> None:
        for chunk in chunked(texts, 20):
            protected = [protect_snippet(text, locale, self.glossary) for text in chunk]
            combined = f"\n{SEGMENT_TOKEN}\n".join(text for text, _restore in protected)
            translated = self._google_translate(locale, combined)
            split = translated.split(f"\n{SEGMENT_TOKEN}\n")
            if len(split) != len(chunk):
                split = [self._google_translate(locale, text) for text, _restore in protected]

            for original, protected_text, translated_text in zip(chunk, protected, split):
                self.cache[(locale, original)] = restore_snippet(translated_text, protected_text[1])

    def _google_translate(self, locale: str, text: str) -> str:
        params = [
            ("client", "gtx"),
            ("sl", SOURCE_LOCALE),
            ("tl", locale),
            ("dt", "t"),
            ("q", text),
        ]
        url = "https://translate.googleapis.com/translate_a/single?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(request) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise TranslationError(f"Google Translate request failed: {exc}") from exc

        return "".join(part[0] for part in payload[0])


class SegmentRegistry:
    def __init__(self) -> None:
        self.segment_by_text: Dict[str, str] = {}
        self.text_by_token: Dict[str, str] = {}
        self.counter = 0

    def register(self, text: str) -> str:
        normalized = text.strip("\n")
        if not contains_letters(normalized):
            return text
        token = self.segment_by_text.get(normalized)
        if token is None:
            token = f"@@I18N_SEG_{self.counter}@@"
            self.counter += 1
            self.segment_by_text[normalized] = token
            self.text_by_token[token] = normalized
        return token


def contains_letters(value: str) -> bool:
    return any(char.isalpha() for char in value)


def chunked(items: List[str], size: int) -> Iterable[List[str]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def protect_snippet(text: str, locale: str, glossary: Dict[str, Dict[str, str]]) -> Tuple[str, Dict[str, str]]:
    restore: Dict[str, str] = {}
    counter = 0

    def stash(value: str) -> str:
        nonlocal counter
        token = f"{PROTECT_TOKEN}{counter}ZX"
        counter += 1
        restore[token] = value
        return token

    safe = text
    safe = re.sub(r"`[^`]+`", lambda match: stash(match.group(0)), safe)
    safe = re.sub(r"https?://[^\s)>\"]+", lambda match: stash(match.group(0)), safe)
    safe = re.sub(r"mailto:[^\s)>\"]+", lambda match: stash(match.group(0)), safe)
    safe = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", lambda match: stash(match.group(0)), safe)
    safe = re.sub(r"(?<!\w)/(?:[A-Za-z0-9._~!$&'()*+,;=:@%/-]+)", lambda match: stash(match.group(0)), safe)
    safe = re.sub(r"[A-Za-z]:\\[A-Za-z0-9._\\-]+(?:\\[A-Za-z0-9._\\-]+)+", lambda match: stash(match.group(0)), safe)

    for source, translated in sorted(glossary.get(locale, {}).items(), key=lambda pair: len(pair[0]), reverse=True):
        pattern = re.escape(source)
        if source.isalnum():
            pattern = rf"\b{pattern}\b"
        safe = re.sub(pattern, lambda _match, value=translated: stash(value), safe)

    return safe, restore


def restore_snippet(text: str, restore: Dict[str, str]) -> str:
    restored = text
    for token, original in restore.items():
        restored = restored.replace(token, original)
    return restored


def translate_frontmatter(frontmatter: str, registry: SegmentRegistry) -> str:
    if not frontmatter:
        return frontmatter

    lines = frontmatter.splitlines(keepends=True)
    rendered: List[str] = []
    pattern = re.compile(r'^([A-Za-z0-9_-]+):\s*"(.+)"(\s*)$')

    for line in lines:
        match = pattern.match(line.rstrip("\n"))
        if not match or match.group(1) not in FRONTMATTER_KEYS:
            rendered.append(line)
            continue
        key, value, trailing = match.groups()
        rendered.append(f'{key}: "{registry.register(value)}"{trailing}\n')

    return "".join(rendered)


def transform_body(body: str, registry: SegmentRegistry) -> str:
    lines = body.splitlines(keepends=True)
    rendered: List[str] = []
    in_fence = False

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            rendered.append(line)
            continue
        if in_fence:
            rendered.append(line)
            continue
        if stripped.startswith("{/*") or stripped.startswith("*/}") or stripped.startswith("import "):
            rendered.append(line)
            continue

        transformed = line
        transformed = replace_regex(
            transformed,
            re.compile(r'(\b(?:' + "|".join(re.escape(key) for key in ATTR_KEYS) + r')\s*=\s*")([^"]+)(")'),
            registry,
        )
        transformed = replace_regex(
            transformed,
            re.compile(r'(\b(?:' + "|".join(re.escape(key) for key in JS_PROP_KEYS) + r')\s*:\s*")([^"]+)(")'),
            registry,
        )
        transformed = replace_inline_text_nodes(transformed, registry)
        transformed = replace_markdown_content(transformed, registry)
        rendered.append(transformed)

    return "".join(rendered)


def replace_regex(line: str, pattern: re.Pattern[str], registry: SegmentRegistry) -> str:
    def callback(match: re.Match[str]) -> str:
        value = match.group(2)
        return match.group(1) + registry.register(value) + match.group(3)

    return pattern.sub(callback, line)


def replace_inline_text_nodes(line: str, registry: SegmentRegistry) -> str:
    pattern = re.compile(r">(?!\s*<)([^<>{}]+?)<")

    def callback(match: re.Match[str]) -> str:
        value = match.group(1)
        if not contains_letters(value):
            return match.group(0)
        return ">" + registry.register(value) + "<"

    return pattern.sub(callback, line)


def replace_markdown_content(line: str, registry: SegmentRegistry) -> str:
    stripped = line.strip()
    if not stripped:
        return line
    if "{" in line or "}" in line:
        return line
    if re.match(r"^\s*[A-Za-z][A-Za-z0-9-]*\s*:", line):
        return line
    if re.search(r"\b[A-Za-z][A-Za-z0-9-]*\s*:\s*[\"'#0-9]", line) and line.rstrip().endswith(","):
        return line
    if stripped.startswith("<") or stripped.startswith("{") or stripped in {"}", "})", "));", "]);"}:
        return line

    if stripped.startswith("|"):
        cells = line.rstrip("\n").split("|")
        translated_cells = [translate_cell(cell, registry) for cell in cells]
        return "|".join(translated_cells) + ("\n" if line.endswith("\n") else "")

    marker = re.match(r"^(\s*(?:#{1,6}\s+|[-*+]\s+|\d+\.\s+|>\s+|-\s+\[[ xX]\]\s+)?)", line)
    prefix = marker.group(1) if marker else ""
    content = line[len(prefix) :].rstrip("\n")
    if not contains_letters(content):
        return line

    return prefix + registry.register(content) + ("\n" if line.endswith("\n") else "")


def translate_cell(cell: str, registry: SegmentRegistry) -> str:
    if re.fullmatch(r"\s*:?-{2,}:?\s*", cell or ""):
        return cell
    content = cell.strip()
    if not contains_letters(content):
        return cell
    leading = cell[: len(cell) - len(cell.lstrip())]
    trailing = cell[len(cell.rstrip()) :]
    return leading + registry.register(content) + trailing


def render_segments(template: str, translations: Dict[str, str]) -> str:
    rendered = template
    for token, text in translations.items():
        rendered = rendered.replace(token, text)
    return rendered


def prefix_internal_links(text: str, locale: str) -> str:
    def should_prefix(path: str) -> bool:
        if not path.startswith("/"):
            return False
        if path == "/":
            return True
        if any(path.startswith(f"/{known}/") for known in SUPPORTED_LOCALES):
            return False
        if any(path.startswith(prefix) for prefix in INTERNAL_PATH_EXCLUSIONS):
            return False
        if path.startswith("/favicon"):
            return False
        return True

    def rewrite(path: str) -> str:
        if path == "/":
            return f"/{locale}"
        return f"/{locale}{path}" if should_prefix(path) else path

    text = re.sub(r'href="(/[^"]*)"', lambda match: f'href="{rewrite(match.group(1))}"', text)
    text = re.sub(r'(\bhref\s*:\s*")(/[^"]*)(")', lambda match: match.group(1) + rewrite(match.group(2)) + match.group(3), text)
    text = re.sub(r'src="(/[^"]*)"', lambda match: f'src="{rewrite(match.group(1))}"', text)
    text = re.sub(r'(\]\()(/[^)]+)(\))', lambda match: match.group(1) + rewrite(match.group(2)) + match.group(3), text)
    return text


def build_manifest(entries: Dict[str, Dict[str, object]]) -> None:
    existing: Dict[str, object] = {}
    if MANIFEST_PATH.exists():
        with MANIFEST_PATH.open("r", encoding="utf-8") as handle:
            existing = json.load(handle)
    files = existing.get("files", {}) if isinstance(existing, dict) else {}
    files.update(entries)
    payload = {
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "sourceLocale": SOURCE_LOCALE,
        "locales": list(SUPPORTED_LOCALES),
        "files": files,
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def resolve_source_files(explicit_files: List[str] | None) -> List[Path]:
    if not explicit_files:
        return discover_source_files()

    resolved: List[Path] = []
    for item in explicit_files:
        path = (ROOT / item).resolve() if not os.path.isabs(item) else Path(item).resolve()
        if path.exists() and is_source_path(path):
            resolved.append(path)
    return sorted(set(resolved))


def translate_file(path: Path, translator: Translator, locale: str) -> Tuple[str, str]:
    source_text = path.read_text(encoding="utf-8")
    registry = SegmentRegistry()
    frontmatter, body = split_frontmatter(source_text)
    template = translate_frontmatter(frontmatter, registry) + transform_body(body, registry)
    translations_by_text = translator.translate_many(locale, registry.text_by_token.values())
    token_map = {token: translations_by_text[text] for token, text in registry.text_by_token.items()}
    translated = render_segments(template, token_map)
    leftovers = set(re.findall(r"@@I18N_SEG_\d+@@", translated))
    if leftovers:
        print(f"[i18n] warning: unresolved segments in {path.relative_to(ROOT)} ({len(leftovers)})", flush=True)
    translated = prefix_internal_links(translated, locale)
    return translated, sha256_text(source_text)


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize translated MDX content for Mintlify docs.")
    parser.add_argument("--engine", choices=["google", "deepl", "copy"], default="google")
    parser.add_argument("--locales", nargs="+", default=list(SUPPORTED_LOCALES))
    parser.add_argument("--files", nargs="*")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    invalid = [locale for locale in args.locales if locale not in SUPPORTED_LOCALES]
    if invalid:
        print(f"Unsupported locales: {', '.join(invalid)}", file=sys.stderr)
        return 1

    glossary = load_glossary()
    translator = Translator(args.engine, glossary, os.environ.get("DEEPL_API_KEY"))
    source_files = resolve_source_files(args.files)
    if not source_files:
        print("No source files selected.")
        return 0

    manifest_entries: Dict[str, Dict[str, object]] = {}
    for path in source_files:
        relative = path.relative_to(ROOT).as_posix()
        print(f"[i18n] source {relative}", flush=True)
        manifest_entries[relative] = {"sourceHash": sha256_text(path.read_text(encoding="utf-8")), "targets": {}}
        for locale in args.locales:
            print(f"[i18n]   -> {locale}", flush=True)
            translated, source_hash = translate_file(path, translator, locale)
            target = ROOT / locale / relative
            manifest_entries[relative]["targets"][locale] = {
                "path": f"{locale}/{relative}",
                "sourceHash": source_hash,
                "syncedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
            }
            if args.dry_run:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(translated, encoding="utf-8")

    if not args.dry_run:
        build_manifest(manifest_entries)

    print(f"Synchronized {len(source_files)} source files for {len(args.locales)} locales.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
