# Translation workflow

The documentation uses Mintlify's native multilingual navigation in `docs.json`.

English is the source of truth. Update English content first, then sync translations.

## Locales

- Source: `en`
- Targets: `fr`, `de`, `es`, `it`
- Deferred: `ca`

## Local development

Run a full sync with the built-in Google fallback:

```bash
python3 scripts/i18n_sync.py --engine google
```

Run a targeted sync for specific source files:

```bash
python3 scripts/i18n_sync.py --engine google --files index.mdx employees/connect-hris.mdx
```

Run with DeepL when `DEEPL_API_KEY` is available:

```bash
DEEPL_API_KEY=... python3 scripts/i18n_sync.py --engine deepl
```

## Automation strategy

- Preferred path: Mintlify + Locadex managed translations
- Repo fallback: `.github/workflows/i18n-sync.yml`
- Delivery model: translation updates are proposed through pull requests only

## Guardrails

- Keep these terms unchanged across locales: `Primo`, `MDM`, `SaaS`, `API`, `Fleet`, `zero-touch`, `AppleCare`, `SEPA`
- Preserve MDX syntax, code fences, URLs, image paths, and product names
- Review generated translations before merge, especially complex MDX pages and API-adjacent content

## Freshness tracking

`i18n/translation-manifest.json` stores the source hash used to generate each localized file. If an English source changes, rerun the sync and review the resulting pull request.
