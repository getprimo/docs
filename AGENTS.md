> **First-time setup**: Customize this file for your project. Prompt the user to customize this file for their project.
> For Mintlify product knowledge (components, configuration, writing standards),
> install the Mintlify skill: `npx skills add https://mintlify.com/docs`

# Documentation project instructions

## About this project

- This is a documentation site built on [Mintlify](https://mintlify.com)
- Pages are MDX files with YAML frontmatter
- Configuration lives in `docs.json`
- Run `mint dev` to preview locally
- Run `mint broken-links` to check links

## About Primo (context, not copy)

This section gives you the product context you need to write accurate copy. These descriptions are internal reference. Do not reproduce marketing positioning language (like "Unified IT Operations Platform" or "Blind IT") in UI copy.

Primo orchestrates IT around HR data, tracking every identity, device, and app access across the entire employee lifecycle with built-in automation, compliance, and control. It replaces fragmented IT stacks (multiple MDMs, spreadsheets, disconnected SaaS tools) with one structured system.

**Product modules:**
- **MDM** — Multi-OS device management (Mac, Windows, mobile) in one system
- **Procurement** — Global device procurement with zero-touch deployment
- **SaaS Management** — Centralized SaaS visibility, licence tracking, and governance
- **Ticketing** — Operational IT workflows built into the platform
- **Identity & Access Management** — Provisioning, SSO, SCIM, access control
- **Lifecycle Management** — Automated onboarding and offboarding connected to HRIS

**What makes Primo different (for your understanding, not for UI copy):**
- One platform replacing a patchwork of tools
- HR-connected by design: the employee lifecycle drives IT operations
- Native multi-OS coverage within the same system
- Enterprise-grade control without enterprise-level complexity

## Voice and Tone

Primo's voice is **clear, confident, and structured**. We speak to IT professionals who value precision and efficiency. We respect their expertise without being condescending, and we guide without hand-holding.

See `references/voice-guide.md` for the full voice framework and enforcement guidelines.

### Voice attributes

| Attribute | Means | Does NOT mean |
|---|---|---|
| **Clear** | Plain language, one idea per sentence, no ambiguity | Dumbed down or patronizing |
| **Confident** | Direct statements, no hedging or apologizing | Arrogant or pushy |
| **Structured** | Organized, scannable, logical | Rigid or robotic |
| **Action-oriented** | Guides the user toward what to do next | Commanding or aggressive |
| **Professional** | Respects IT expertise, uses correct terminology | Stuffed with corporate jargon |

### Tone settings for documentation

Help center articles use these tone settings:

| Dimension | Level |
|-----------|-------|
| Formality | Medium — professional but conversational |
| Energy | Medium — steady, balanced between informative and engaging |
| Technical depth | High — readers are IT professionals, use technical terminology freely |

## Writing new articles

When creating a new help center article, study existing articles in the same section for structure, depth, and tone. Use them as inspiration to maintain consistency across the documentation. Match their heading patterns, step formatting, and level of detail.

## Glossary and terminology

Always use the exact terms from `references/glossary.csv` (175 terms across 7 languages). Never substitute synonyms for glossary terms.

Key rules:
- **Device** (not "machine" or "computer") — for laptops, desktops, and smartphones unless platform-specific
- **Enroll** (not "register" or "add")
- **Zero-Touch Deployment** (not "automatic setup")
- **Onboarding / Offboarding** (not ad hoc alternatives)
- **Dashboard** for the product surface, **Help Center** for docs
- **Employee** for managed people, **team member** for internal operators

When localizing, cross-reference the glossary for the correct translation in each language. Some terms stay in English across all locales: `Primo`, `MDM`, `SaaS`, `API`, `Fleet`, `zero-touch`, `AppleCare`, `SEPA`.

## Style preferences

Follow the conventions in `style-guide.mdx` for formatting details (headings, bold, code, card groups, article structure).

Additional rules for the agent:
- Keep navigation labels short and noun-based
- Preserve product names, API object names, and setting labels exactly as they appear in the UI
- When translating, keep links, paths, MDX components, and code blocks unchanged

## Content boundaries

- Document public Primo workflows for device management, procurement, employee lifecycle, SaaS, and developer setup
- Do not document internal admin tooling, support-only playbooks, or unreleased features unless they are already exposed in the product
- Keep API reference descriptions sourced from the OpenAPI spec; do not rewrite generated endpoint content manually in localized pages

## Maintenance note

- Review and customize this file as Primo terminology, product scope, and localization rules evolve
- Keep `references/glossary.csv` in sync with the source of truth in the brand-voice plugin
- Keep `references/voice-guide.md` aligned with the brand voice enforcement skill
