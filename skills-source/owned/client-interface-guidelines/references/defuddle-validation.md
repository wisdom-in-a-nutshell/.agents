# Defuddle Coverage Validation

Date: 2026-02-26

## Inputs
- Source repo markdown: content/_index.md
- Defuddle output: defuddle parse https://clig.dev/ --md

## Size
- Source lines: 1242
- Source bytes: 72478
- Defuddle lines: 867
- Defuddle bytes: 70567

## Structural Coverage
- H2 headings: source=6, defuddle=5
- H3 headings: source=25, defuddle=25
- Bold rules: source=100, defuddle=100

## Observations
- Defuddle preserved all H3 sections and all bolded guideline rules.
- Defuddle missed the final Further reading H2 wrapper heading.
- Defuddle normalized non-breaking spaces in two headings.
- For complete archival fidelity, prefer direct source capture from the repository.
