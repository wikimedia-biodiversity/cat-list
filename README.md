# cat-list – Category → List

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23886791.svg)](https://doi.org/10.5281/zenodo.23886791) · Version 1.0.0 · Licence: GPL-3.0

A Toolforge tool that takes a category on **any Wikimedia wiki** and lists its
pages.

Features

* Scan a category and its subcategories to a chosen **depth** (0–6), with loop protection.
* For every page: **Wikidata QID**, the scanned categories it was **found in**, its
  **depth**, and (optional) all its **parent categories** (hidden ones optional).
* Optional Wikidata details: **label and description** in the wiki's language (with
  English fallback shown when missing), **instance of (P31)**, number of **sitelinks**.
* Filters: all / with item / without item / item missing a label / item missing a description.
* "**+ create**" link on pages without an item (opens `Special:NewItem` with site and page filled in).
* **Category tree** view: each subcategory with its parent, depth, member counts and QID.
* Exports: **CSV, TSV, JSON, wikitext table, plain QID list** (paste into QuickStatements / PetScan).
* **Open in PetScan** link with the same category, depth and namespaces.
* JSON API: `/api?wiki=ml&category=തെയ്യങ്ങൾ&depth=1&wd=1&parents=1`
* No database credentials needed: uses the MediaWiki Action API and the Wikidata API
  (with `maxlag`, retries and a descriptive User-Agent), with a 10-minute cache.

## Parameters

| Parameter | Meaning | Default |
|---|---|---|
| `wiki` | `ml`, `mlwiki`, `ml.wikipedia.org`, `commonswiki`, `knwikisource`… | – |
| `category` | Name with or without prefix (`Category:`, `വർഗ്ഗം:` both work) | – |
| `depth` | Subcategory levels to scan, 0–6 | `0` |
| `ns` | Namespaces, comma-separated (`0`, `0,6`), or `*` for all | `0` |
| `parents` | `1` = list parent categories of each page | off |
| `hidden` | `1` = include hidden categories in parents | off |
| `wd` | `1` = fetch Wikidata label/description/P31/sitelinks | off |
| `filter` | `all`, `with`, `without`, `nolabel`, `nodesc` | `all` |
| `format` | `html`, `csv`, `tsv`, `json`, `wikitext`, `qids` | `html` |

Limits (edit at the top of `app.py`): 3,000 categories, 20,000 pages, Wikidata details for 5,000 items.

## Notes

* Very large scans (deep trees on big wikis) can take a minute or more; use PetScan
  for anything larger than the limits.
* Toolforge's privacy policy forbids loading resources from outside Wikimedia; the
  page has no external CSS, JS or fonts.
* Licence: GNU General Public License v3.0 or later (see `LICENSE`).

## Author

**Manoj Karingamadathil** – Open Knowledge activist and Citizen Scientist from India,
[Wikimedia Biodiversity Taskforce](https://meta.wikimedia.org/wiki/Wikimedia_Biodiversity_Taskforce)
ORCID: [0000-0003-3885-6595](https://orcid.org/0000-0003-3885-6595)

## How to cite

Karingamadathil, M. (2026). *cat-list – Category → List* (Version 1.0.0) [Computer software]. Zenodo. https://doi.org/10.5281/zenodo.23886791

Machine-readable citation: `CITATION.cff`.
