"""
cat-list – list the pages in a category (optionally its subcategories,
to a chosen depth) together with their Wikidata items, parent categories
and Wikidata labels/descriptions. Works on every Wikimedia wiki through the
MediaWiki Action API, so no replica database credentials are needed.

Run locally:   flask --app app run
Toolforge:     see README.md
"""
import csv
import io
import json
import os
import re
import threading
import time
from collections import OrderedDict, deque
from urllib.parse import quote, urlencode

import requests
from flask import Flask, Response, jsonify, render_template, request

TOOL_NAME = os.environ.get("TOOL_NAME", "cat-list")
VERSION = "1.0.0"
DOI = "10.5281/zenodo.23886791"
USER_AGENT = (
    f"{TOOL_NAME}/{VERSION} (https://{TOOL_NAME}.toolforge.org; "
    f"tools.{TOOL_NAME}@toolforge.org) python-requests/{requests.__version__}"
)

MAX_DEPTH = 6
MAX_CATEGORIES = 3000
MAX_PAGES = 20000
MAX_WIKIDATA = 5000        # items enriched with labels/descriptions/P31
CACHE_TTL = 600            # seconds
CACHE_SIZE = 64

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
app.json.ensure_ascii = False

@app.context_processor
def tool_meta():
    return {"version": VERSION, "doi": DOI}


SESSION = requests.Session()
SESSION.headers["User-Agent"] = USER_AGENT


class ToolError(Exception):
    pass


# --------------------------------------------------------------------------
# Wiki name handling (also guards against requests to arbitrary hosts)
# --------------------------------------------------------------------------
PROJECTS = ("wikipedia", "wiktionary", "wikisource", "wikiquote", "wikibooks",
            "wikinews", "wikiversity", "wikivoyage")
WIKI_RE = re.compile(
    r"^(?:[a-z0-9-]+\.(?:" + "|".join(PROJECTS) + r")"
    r"|(?:commons|meta|species|incubator|outreach|wikimania)\.wikimedia"
    r"|www\.wikidata|www\.mediawiki|www\.wikifunctions)\.org$"
)
SPECIAL_DB = {
    "commonswiki": "commons.wikimedia.org",
    "metawiki": "meta.wikimedia.org",
    "specieswiki": "species.wikimedia.org",
    "wikidatawiki": "www.wikidata.org",
    "mediawikiwiki": "www.mediawiki.org",
    "incubatorwiki": "incubator.wikimedia.org",
    "outreachwiki": "outreach.wikimedia.org",
}
DB_SUFFIX = {"wiki": "wikipedia", "wiktionary": "wiktionary",
             "wikisource": "wikisource", "wikiquote": "wikiquote",
             "wikibooks": "wikibooks", "wikinews": "wikinews",
             "wikiversity": "wikiversity", "wikivoyage": "wikivoyage"}


def normalize_wiki(raw):
    """Accept 'ml', 'mlwiki', 'ml.wikipedia.org' or a full URL."""
    s = (raw or "").strip().lower()
    s = re.sub(r"^https?://", "", s).split("/")[0]
    if not s:
        raise ToolError("Please enter a wiki, e.g. ml.wikipedia.org or mlwiki.")
    if s in SPECIAL_DB:
        s = SPECIAL_DB[s]
    elif "." not in s:
        for suffix in sorted(DB_SUFFIX, key=len, reverse=True):
            if s.endswith(suffix) and len(s) > len(suffix):
                s = f"{s[:-len(suffix)].replace('_', '-')}.{DB_SUFFIX[suffix]}.org"
                break
        else:
            s = f"{s}.wikipedia.org"          # plain language code
    elif s.count(".") == 1:                   # e.g. "ml.wikipedia"
        s += ".org"
    if not WIKI_RE.match(s):
        raise ToolError(f"'{raw}' is not a recognised Wikimedia wiki.")
    return s


# --------------------------------------------------------------------------
# API helpers
# --------------------------------------------------------------------------
def api(host, params):
    params = {**params, "format": "json", "formatversion": "2", "maxlag": "5"}
    for attempt in range(5):
        try:
            r = SESSION.get(f"https://{host}/w/api.php", params=params, timeout=60)
        except requests.RequestException as e:
            if attempt == 4:
                raise ToolError(f"Could not reach {host}: {e}")
            time.sleep(2 * (attempt + 1))
            continue
        if r.status_code in (429, 503):
            time.sleep(int(r.headers.get("Retry-After", 5)))
            continue
        try:
            data = r.json()
        except ValueError:
            raise ToolError(f"{host} returned an invalid response (HTTP {r.status_code}).")
        err = data.get("error")
        if err:
            if err.get("code") == "maxlag":
                time.sleep(int(r.headers.get("Retry-After", 5)))
                continue
            raise ToolError(f"{host}: {err.get('info', err.get('code'))}")
        return data
    raise ToolError(f"{host} is busy, please try again later.")


def api_iter(host, params):
    cont = {}
    while True:
        data = api(host, {**params, **cont})
        yield data
        if "continue" not in data:
            return
        cont = data["continue"]


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


# --------------------------------------------------------------------------
# Small TTL cache
# --------------------------------------------------------------------------
_cache, _cache_lock = OrderedDict(), threading.Lock()


def cached(key, fn):
    now = time.time()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < CACHE_TTL:
            _cache.move_to_end(key)
            return hit[1]
    value = fn()
    with _cache_lock:
        _cache[key] = (now, value)
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    return value


# --------------------------------------------------------------------------
# Site info
# --------------------------------------------------------------------------
def siteinfo(host):
    def load():
        d = api(host, {"action": "query", "meta": "siteinfo",
                       "siprop": "general|namespaces|namespacealiases"})["query"]
        g = d["general"]
        cat_names = {"category"}
        ns14 = next(n for n in d["namespaces"].values() if n["id"] == 14)
        cat_names.add(ns14["name"].lower())
        cat_names.add(ns14.get("canonical", "Category").lower())
        for a in d.get("namespacealiases", []):
            if a["id"] == 14:
                cat_names.add(a["alias"].lower())
        ns_names = {n["id"]: (n["name"] or "(Main)") for n in d["namespaces"].values()}
        return {"host": host, "dbname": g["wikiid"], "lang": g["lang"],
                "sitename": g["sitename"], "cat_prefixes": cat_names,
                "ns_names": ns_names, "articlepath": g["articlepath"]}
    return cached(("siteinfo", host), load)


def strip_cat_prefix(raw, si):
    name = raw.strip().replace("_", " ")
    if ":" in name:
        prefix, rest = name.split(":", 1)
        if prefix.strip().lower() in si["cat_prefixes"]:
            name = rest
    name = name.strip()
    if not name:
        raise ToolError("Please enter a category name.")
    return name


def page_url(si, title):
    return f"https://{si['host']}" + si["articlepath"].replace(
        "$1", quote(title.replace(" ", "_"), safe="/:()',"))


# --------------------------------------------------------------------------
# Category scan
# --------------------------------------------------------------------------
def scan(host, category, depth, namespaces, want_parents, include_hidden):
    """namespaces: set of ints, or None for all namespaces."""
    si = siteinfo(host)
    name = strip_cat_prefix(category, si)
    d = api(host, {"action": "query", "titles": f"Category:{name}",
                   "prop": "pageprops|categoryinfo", "ppprop": "wikibase_item"})
    root = d["query"]["pages"][0]
    if root.get("missing") or root.get("invalid"):
        raise ToolError(f"Category:{name} does not exist on {host}.")
    root_title = root["title"]

    cats = OrderedDict()
    cats[root_title] = {"title": root_title, "depth": 0, "parent": None,
                        "qid": (root.get("pageprops") or {}).get("wikibase_item"),
                        "pages": 0, "subcats": 0}
    pages = OrderedDict()
    queue = deque([root_title])
    warnings = []

    def ns_param(include_subcats):
        if namespaces is None:
            return None
        ns = set(namespaces) | ({14} if include_subcats else set())
        return "|".join(str(n) for n in sorted(ns))

    while queue:
        ctitle = queue.popleft()
        cinfo = cats[ctitle]
        recurse = cinfo["depth"] < depth
        params = {"action": "query", "generator": "categorymembers",
                  "gcmtitle": ctitle, "gcmlimit": "max",
                  "prop": "pageprops", "ppprop": "wikibase_item|disambiguation"}
        nsp = ns_param(recurse)
        if nsp:
            params["gcmnamespace"] = nsp
        if want_parents:
            params["prop"] = "pageprops|categories"
            params["cllimit"] = "max"
            if not include_hidden:
                params["clshow"] = "!hidden"

        merged = OrderedDict()
        for resp in api_iter(host, params):
            for m in resp.get("query", {}).get("pages", []):
                e = merged.setdefault(m["pageid"], {
                    "title": m["title"], "ns": m["ns"], "qid": None,
                    "disambig": False, "parent_cats": []})
                pp = m.get("pageprops") or {}
                if "wikibase_item" in pp:
                    e["qid"] = pp["wikibase_item"]
                if "disambiguation" in pp:
                    e["disambig"] = True
                for c in m.get("categories", []):
                    if c["title"] not in e["parent_cats"]:
                        e["parent_cats"].append(c["title"])

        for pid, e in merged.items():
            if e["ns"] == 14:
                cinfo["subcats"] += 1
                if recurse and e["title"] not in cats:
                    if len(cats) >= MAX_CATEGORIES:
                        if not any("categories" in w for w in warnings):
                            warnings.append(f"Stopped after {MAX_CATEGORIES} categories.")
                    else:
                        cats[e["title"]] = {"title": e["title"], "depth": cinfo["depth"] + 1,
                                            "parent": ctitle, "qid": e["qid"],
                                            "pages": 0, "subcats": 0}
                        queue.append(e["title"])
            if namespaces is None or e["ns"] in namespaces:
                cinfo["pages"] += 1
                if pid in pages:
                    pages[pid]["found_in"].append(ctitle)
                elif len(pages) < MAX_PAGES:
                    pages[pid] = {"pageid": pid, **e, "depth": cinfo["depth"],
                                  "found_in": [ctitle]}
                elif not any("pages" in w for w in warnings):
                    warnings.append(f"Stopped after {MAX_PAGES} pages.")
        if len(pages) >= MAX_PAGES:
            break

    return {"site": si, "root": root_title, "categories": list(cats.values()),
            "pages": list(pages.values()), "warnings": warnings}


# --------------------------------------------------------------------------
# Wikidata enrichment
# --------------------------------------------------------------------------
def wikidata_info(qids, lang):
    langs = [lang] + (["en"] if lang != "en" else [])
    out, p31_ids = {}, set()
    for batch in chunks(qids, 50):
        d = api("www.wikidata.org", {"action": "wbgetentities", "ids": "|".join(batch),
                                     "props": "labels|descriptions|claims|sitelinks",
                                     "languages": "|".join(langs)})
        for qid, ent in d.get("entities", {}).items():
            if "missing" in ent:
                out[qid] = {"missing": True}
                continue
            p31 = []
            for c in ent.get("claims", {}).get("P31", []):
                v = c.get("mainsnak", {}).get("datavalue", {}).get("value", {})
                if isinstance(v, dict) and v.get("id"):
                    p31.append(v["id"])
            p31_ids.update(p31)
            lab, desc = ent.get("labels", {}), ent.get("descriptions", {})
            out[qid] = {
                "label": lab.get(lang, {}).get("value", ""),
                "description": desc.get(lang, {}).get("value", ""),
                "label_en": lab.get("en", {}).get("value", ""),
                "description_en": desc.get("en", {}).get("value", ""),
                "p31": p31,
                "sitelinks": len(ent.get("sitelinks", {})),
            }
    p31_labels = {}
    for batch in chunks(sorted(p31_ids), 50):
        d = api("www.wikidata.org", {"action": "wbgetentities", "ids": "|".join(batch),
                                     "props": "labels", "languages": "|".join(langs),
                                     "languagefallback": "1"})
        for qid, ent in d.get("entities", {}).items():
            labs = ent.get("labels", {})
            p31_labels[qid] = (labs.get(lang) or labs.get("en") or {}).get("value", qid)
    for info in out.values():
        if "p31" in info:
            info["p31"] = [{"id": q, "label": p31_labels.get(q, q)} for q in info["p31"]]
    return out


# --------------------------------------------------------------------------
# Request handling
# --------------------------------------------------------------------------
FILTERS = {
    "all": "All pages",
    "with": "Only pages with a Wikidata item",
    "without": "Only pages without a Wikidata item",
    "nolabel": "Item has no label in the wiki's language",
    "nodesc": "Item has no description in the wiki's language",
}
FORMATS = ("html", "json", "csv", "tsv", "wikitext", "qids")


def parse_namespaces(raw):
    raw = (raw or "0").strip()
    if raw in ("*", "all"):
        return None
    try:
        return {int(x) for x in re.split(r"[,|\s]+", raw) if x != ""} or {0}
    except ValueError:
        raise ToolError("Namespaces must be numbers separated by commas, or * for all.")


def read_options(args):
    try:
        depth = max(0, min(MAX_DEPTH, int(args.get("depth", 0) or 0)))
    except ValueError:
        depth = 0
    flt = args.get("filter", "all")
    fmt = args.get("format", "html")
    return {
        "wiki": args.get("wiki", "").strip(),
        "category": args.get("category", "").strip(),
        "depth": depth,
        "ns": args.get("ns", "0").strip() or "0",
        "parents": args.get("parents") == "1",
        "hidden": args.get("hidden") == "1",
        "wd": args.get("wd") == "1",
        "filter": flt if flt in FILTERS else "all",
        "format": fmt if fmt in FORMATS else "html",
    }


def run(opts):
    host = normalize_wiki(opts["wiki"])
    namespaces = parse_namespaces(opts["ns"])
    key = ("scan", host, opts["category"], opts["depth"],
           None if namespaces is None else tuple(sorted(namespaces)),
           opts["parents"], opts["hidden"])
    res = cached(key, lambda: scan(host, opts["category"], opts["depth"], namespaces,
                                   opts["parents"], opts["hidden"]))
    si = res["site"]
    wd = {}
    need_wd = opts["wd"] or opts["filter"] in ("nolabel", "nodesc")
    if need_wd:
        qids = sorted({p["qid"] for p in res["pages"] if p["qid"]})
        if len(qids) > MAX_WIKIDATA:
            res["warnings"].append(f"Wikidata details fetched for the first {MAX_WIKIDATA} items only.")
            qids = qids[:MAX_WIKIDATA]
        wd = cached(("wd", si["lang"], tuple(qids)), lambda: wikidata_info(qids, si["lang"]))

    rows = []
    for p in res["pages"]:
        info = wd.get(p["qid"], {}) if p["qid"] else {}
        f = opts["filter"]
        if f == "with" and not p["qid"]:
            continue
        if f == "without" and p["qid"]:
            continue
        if f == "nolabel" and (not p["qid"] or p["qid"] not in wd or info.get("label")):
            continue
        if f == "nodesc" and (not p["qid"] or p["qid"] not in wd or info.get("description")):
            continue
        rows.append({
            **p,
            "url": page_url(si, p["title"]),
            "ns_name": si["ns_names"].get(p["ns"], str(p["ns"])),
            "wd": info,
            "new_item_url": None if p["qid"] else
                "https://www.wikidata.org/wiki/Special:NewItem?" + urlencode(
                    {"site": si["dbname"], "page": p["title"], "lang": si["lang"],
                     "label": re.sub(r"\s*\(.*\)$", "", p["title"].split(":", 1)[-1]
                                     if p["ns"] else p["title"])}),
        })

    with_item = sum(1 for p in res["pages"] if p["qid"])
    stats = {"total": len(res["pages"]), "with": with_item,
             "without": len(res["pages"]) - with_item,
             "categories": len(res["categories"]), "shown": len(rows)}
    return {"host": host, "site": si, "root": res["root"], "rows": rows,
            "categories": res["categories"], "stats": stats,
            "warnings": res["warnings"], "wd_loaded": need_wd,
            "petscan": petscan_url(host, res["root"], opts["depth"], namespaces)}


def petscan_url(host, root, depth, namespaces):
    sub, project = host.split(".")[0], host.split(".")[1]
    if project == "wikimedia" or host == "www.wikidata.org":
        lang, project = sub, "wikimedia" if project == "wikimedia" else "wikidata"
    else:
        lang = sub
    params = [("language", lang), ("project", project),
              ("categories", root.split(":", 1)[1]), ("depth", depth),
              ("wikidata_item", "any"), ("interface_language", "en"), ("doit", "")]
    for n in sorted(namespaces) if namespaces is not None else []:
        params.append((f"ns[{n}]", "1"))
    return "https://petscan.wmcloud.org/?" + urlencode(params)


# --------------------------------------------------------------------------
# Exports
# --------------------------------------------------------------------------
COLUMNS = ["title", "namespace", "pageid", "qid", "depth", "found_in",
           "parent_categories", "label", "description", "label_en",
           "description_en", "instance_of", "sitelinks", "disambiguation", "url"]


def flat(row):
    w = row["wd"]
    return {
        "title": row["title"], "namespace": row["ns"], "pageid": row["pageid"],
        "qid": row["qid"] or "", "depth": row["depth"],
        "found_in": " | ".join(row["found_in"]),
        "parent_categories": " | ".join(row["parent_cats"]),
        "label": w.get("label", ""), "description": w.get("description", ""),
        "label_en": w.get("label_en", ""), "description_en": w.get("description_en", ""),
        "instance_of": " | ".join(f"{p['id']} ({p['label']})" for p in w.get("p31", [])),
        "sitelinks": w.get("sitelinks", ""), "disambiguation": int(row["disambig"]),
        "url": row["url"],
    }


def export(result, fmt, opts):
    base = re.sub(r"[^\w\-]+", "_", result["root"].split(":", 1)[-1])[:60] or "category"
    if fmt == "json":
        return jsonify({"wiki": result["host"], "category": result["root"],
                        "depth": opts["depth"], "stats": result["stats"],
                        "warnings": result["warnings"], "categories": result["categories"],
                        "pages": [flat(r) for r in result["rows"]]})
    if fmt in ("csv", "tsv"):
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=COLUMNS,
                           delimiter="," if fmt == "csv" else "\t")
        w.writeheader()
        for r in result["rows"]:
            w.writerow(flat(r))
        mime = "text/csv" if fmt == "csv" else "text/tab-separated-values"
        return Response("\ufeff" + buf.getvalue(), mimetype=f"{mime}; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{base}.{fmt}"'})
    if fmt == "qids":
        body = "\n".join(r["qid"] for r in result["rows"] if r["qid"])
        return Response(body, mimetype="text/plain; charset=utf-8")
    if fmt == "wikitext":
        lines = ['{| class="wikitable sortable"',
                 "! # !! Page !! Wikidata !! Label !! Description !! Found in"]
        for i, r in enumerate(result["rows"], 1):
            w = r["wd"]
            title = f":{r['title']}" if r["ns"] in (6, 14) else r["title"]
            q = f"[[d:{r['qid']}|{r['qid']}]]" if r["qid"] else "–"
            found = ", ".join(f"[[:{c}]]" for c in r["found_in"])
            lines += ["|-", f"| {i} || [[{title}]] || {q} || {w.get('label', '')} || "
                            f"{w.get('description', '')} || {found}"]
        lines.append("|}")
        return Response("\n".join(lines), mimetype="text/plain; charset=utf-8")


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.route("/")
def index():
    opts = read_options(request.args)
    ctx = {"opts": opts, "filters": FILTERS, "max_depth": MAX_DEPTH,
           "result": None, "error": None, "query": request.query_string.decode()}
    if opts["wiki"] and opts["category"]:
        try:
            result = run(opts)
            if opts["format"] != "html":
                return export(result, opts["format"], opts)
            ctx["result"] = result
        except ToolError as e:
            if opts["format"] == "json":
                return jsonify({"error": str(e)}), 400
            ctx["error"] = str(e)
    return render_template("index.html", **ctx)


@app.route("/api")
def api_route():
    args = request.args.to_dict()
    args["format"] = "json"
    opts = read_options(args)
    if not (opts["wiki"] and opts["category"]):
        return jsonify({"error": "Parameters 'wiki' and 'category' are required.",
                        "parameters": ["wiki", "category", "depth", "ns", "parents",
                                       "hidden", "wd", "filter"]}), 400
    try:
        return export(run(opts), "json", opts)
    except ToolError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/healthz")
def healthz():
    return "ok"


@app.template_filter("export_link")
def export_link(query, fmt):
    parts = [p for p in query.split("&") if p and not p.startswith("format=")]
    return "?" + "&".join(parts + [f"format={fmt}"])


if __name__ == "__main__":
    app.run(debug=True)
