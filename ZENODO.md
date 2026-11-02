# Archiving cat-list on Zenodo

Zenodo gives the tool a permanent **DOI**, so it can be cited in reports, grant
applications and papers. This guide lists what to enter in each field of the
Zenodo upload form (<https://zenodo.org/uploads/new>).

You can also connect a **GitHub** repository to Zenodo: every GitHub release is
then archived automatically, and Zenodo fills the form from `.zenodo.json` in
this folder. (This works with GitHub only, not GitLab.)

---

## 1. Files

| Field | What to enter |
|---|---|
| **Files** | Upload `cat-list.zip` (the full source: `app.py`, `templates/`, `tests/`, `README.md`, `CITATION.cff`, `requirements.txt`, `Procfile`, `LICENSE`). The `LICENSE` file (GPL v3) is included. |

## 2. Basic information

| Field | What to enter |
|---|---|
| **Digital Object Identifier** | Reserved DOI: `10.5281/zenodo.23886791` (already added to `CITATION.cff`, the README, the footer and the About page). |
| **Resource type** | Software |
| **Title** | `cat-list – Category → List: a Toolforge tool listing category pages with their Wikidata items` |
| **Publication date** | `2026-11-02` (or the day you publish) |
| **Creators** | **Name:** Karingamadathil, Manoj · **Type:** Person · **ORCID:** `0000-0003-3885-6595` · **Affiliation:** Wikimedia Biodiversity Taskforce · **Role:** leave empty (creators need no role). Typing the ORCID iD fills in the name automatically. |
| **Description** | Paste the text in *Description* below. |
| **Licenses** | GNU General Public License v3.0 or later (search "GPL" and pick *GNU General Public License v3.0 or later*). |
| **Copyright** | `© 2026 Manoj Karingamadathil` (optional) |

### Description

> **cat-list** is a Wikimedia Toolforge tool that takes a category on any Wikimedia wiki and lists its pages. It can follow subcategories to a chosen depth (0–6) and shows, for every page, its Wikidata item, the categories it was found in, its depth and its parent categories. Optional Wikidata details include the label and description in the wiki's language, instance of (P31) and the number of sitelinks.
>
> Filters highlight pages without a Wikidata item and items missing a label or description, with a one-click link to create new items. Results export as CSV, TSV, JSON, a wikitext table or a plain QID list, and can be opened in PetScan. The tool uses only the public MediaWiki Action API and Wikidata API.
>
> It was created for the needs of the Wikimedia Biodiversity Taskforce's ongoing projects, such as building lists of the plants of Kerala, Tamil Nadu and Odisha with valid taxonomy on Wikidata, and is useful for edit-a-thons, photo campaigns and WikiProjects.
>
> Live tool: https://cat-list.toolforge.org

## 3. Recommended information

| Field | What to enter |
|---|---|
| **Contributors** | Leave empty, or add people who helped test (Type: Person, Role: e.g. *Other* or *Project member*). |
| **Keywords and subjects** | Wikimedia · Wikipedia · Wikidata · Toolforge · categories · knowledge gaps · biodiversity · open data · Malayalam Wikipedia |
| **Languages** | English |
| **Dates** | Optional. *Created* – `2026-11-02` – "First release". |
| **Version** | `1.0.0` |
| **Publisher** | Zenodo (default) |

## 4. Software

Shown when the resource type is Software.

| Field | What to enter |
|---|---|
| **Repository URL** | Your Git repository, e.g. `https://gitlab.wikimedia.org/toolforge-repos/cat-list` or the GitHub URL |
| **Programming language** | Python (add HTML and JavaScript if you like) |
| **Development status** | Active |

## 5. Related works

| Relation | Identifier | Scheme | Resource type |
|---|---|---|---|
| Is supplement to | `https://cat-list.toolforge.org` | URL | Software |
| Is part of | `https://meta.wikimedia.org/wiki/Wikimedia_Biodiversity_Taskforce` | URL | Other |
| Is supplement to | Repository URL (same as above) | URL | Software |
| Is documented by | Tool's page on Meta-Wiki or mediawiki.org, if you create one | URL | Publication / Other |

## 6. Communities (optional)

Submit the record to a Zenodo community so it can be found with related work,
e.g. a **Wikimedia** community or the Taskforce's own community if you create one
on Zenodo.

## 7. Funding and access

| Field | What to enter |
|---|---|
| **Funding** | Leave empty unless a grant paid for the work. |
| **Visibility / access** | Public · Files: Public |

---

## After publishing

1. Check that the DOI resolves: https://doi.org/10.5281/zenodo.23886791
2. For each new version, open the record and click **New version** instead of
   creating a new upload. Zenodo then keeps one "concept DOI" for all versions
   plus a DOI for each release.
3. Optionally add the DOI to the tool's Wikidata item (property *DOI*, P356) and to
   its entry in Toolhub (<https://toolhub.wikimedia.org>).
