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

## Terminology

- Use `employee` for managed people and `team member` for internal operators
- Use `device` for laptops, desktops, and smartphones unless a page is platform-specific
- Keep these product terms untranslated across locales: `Primo`, `MDM`, `SaaS`, `API`, `Fleet`, `zero-touch`, `AppleCare`, `SEPA`
- Prefer `dashboard` for the product surface and `Help Center` for the documentation experience
- Use `onboarding` and `offboarding` rather than ad hoc alternatives

## Style preferences

- Use active voice and second person ("you")
- Keep sentences concise — one idea per sentence
- Use sentence case for headings
- Bold for UI elements: Click **Settings**
- Code formatting for file names, commands, paths, and code references
- Keep navigation labels short and noun-based
- Preserve product names, API object names, and setting labels exactly as they appear in the UI
- When translating, keep links, paths, MDX components, and code blocks unchanged

## Content boundaries

- Document public Primo workflows for device management, procurement, employee lifecycle, SaaS, and developer setup
- Do not document internal admin tooling, support-only playbooks, or unreleased features unless they are already exposed in the product
- Keep API reference descriptions sourced from the OpenAPI spec; do not rewrite generated endpoint content manually in localized pages

## Maintenance note

- Review and customize this file as Primo terminology, product scope, and localization rules evolve
