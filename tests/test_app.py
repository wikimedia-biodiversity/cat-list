import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A

SITE = {"query": {"general": {"wikiid": "mlwiki", "lang": "ml", "sitename": "വിക്കിപീഡിയ", "articlepath": "/wiki/$1"},
        "namespaces": {"0": {"id": 0, "name": ""}, "14": {"id": 14, "name": "വർഗ്ഗം", "canonical": "Category"}},
        "namespacealiases": []}}
MEMBERS = {
 "വർഗ്ഗം:തെയ്യങ്ങൾ": [
   {"pageid": 1, "ns": 0, "title": "ഗുളികൻ", "pageprops": {"wikibase_item": "Q1"}, "categories": [{"title": "വർഗ്ഗം:തെയ്യങ്ങൾ"}]},
   {"pageid": 2, "ns": 0, "title": "കതിവനൂർ വീരൻ", "categories": [{"title": "വർഗ്ഗം:തെയ്യങ്ങൾ"}]},
   {"pageid": 10, "ns": 14, "title": "വർഗ്ഗം:അമ്മദൈവങ്ങൾ", "pageprops": {"wikibase_item": "Q9"}}],
 "വർഗ്ഗം:അമ്മദൈവങ്ങൾ": [
   {"pageid": 3, "ns": 0, "title": "മുച്ചിലോട്ട് ഭഗവതി", "pageprops": {"wikibase_item": "Q2"}},
   {"pageid": 1, "ns": 0, "title": "ഗുളികൻ", "pageprops": {"wikibase_item": "Q1"}},
   {"pageid": 99, "ns": 14, "title": "വർഗ്ഗം:തെയ്യങ്ങൾ"}]}  # loop back to root

def fake_api(host, p):
    if p.get("meta") == "siteinfo": return SITE
    if p.get("titles"): return {"query": {"pages": [{"title": "വർഗ്ഗം:തെയ്യങ്ങൾ", "pageprops": {"wikibase_item": "Q100"}}]}}
    if p.get("generator") == "categorymembers":
        pages = MEMBERS[p["gcmtitle"]]
        # simulate prop continuation: split first page's categories into a second response
        if "continue" not in p and len(pages) > 1:
            return {"query": {"pages": [dict(x, categories=[]) for x in pages]}, "continue": {"clcontinue": "x", "continue": "||"}}
        return {"query": {"pages": [{k: v for k, v in x.items() if k in ("pageid", "ns", "title", "categories")} for x in pages]}}
    if p.get("action") == "wbgetentities":
        ents = {"Q1": {"labels": {"ml": {"value": "ഗുളികൻ"}, "en": {"value": "Gulikan"}}, "descriptions": {"en": {"value": "Theyyam"}},
                       "claims": {"P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}]}, "sitelinks": {"mlwiki": {}, "enwiki": {}}},
                "Q2": {"labels": {"en": {"value": "Muchilot Bhagavathi"}}, "descriptions": {}, "claims": {}, "sitelinks": {}},
                "Q5": {"labels": {"ml": {"value": "തെയ്യം"}}}}
        return {"entities": {q: ents[q] for q in p["ids"].split("|")}}
    raise AssertionError(p)

A.api = fake_api
c = A.app.test_client()

def test_normalize():
    assert A.normalize_wiki("ml") == "ml.wikipedia.org"
    assert A.normalize_wiki("mlwiki") == "ml.wikipedia.org"
    assert A.normalize_wiki("mlwikisource") == "ml.wikisource.org"
    assert A.normalize_wiki("commonswiki") == "commons.wikimedia.org"
    assert A.normalize_wiki("https://kn.wikipedia.org/wiki/X") == "kn.wikipedia.org"
    assert A.normalize_wiki("zh_min_nanwiki") == "zh-min-nan.wikipedia.org"
    for bad in ("evil.com", "ml.wikipedia.org.evil.com", "a.b.c.d"):
        try: A.normalize_wiki(bad); assert False, bad
        except A.ToolError: pass

def test_scan_json():
    j = c.get("/api?wiki=ml&category=Category:തെയ്യങ്ങൾ&depth=2&parents=1&wd=1").get_json()
    assert j["stats"] == {"total": 3, "with": 2, "without": 1, "categories": 2, "shown": 3}, j["stats"]
    g = {p["title"]: p for p in j["pages"]}
    assert g["ഗുളികൻ"]["found_in"] == "വർഗ്ഗം:തെയ്യങ്ങൾ | വർഗ്ഗം:അമ്മദൈവങ്ങൾ"
    assert g["ഗുളികൻ"]["parent_categories"] == "വർഗ്ഗം:തെയ്യങ്ങൾ"
    assert g["ഗുളികൻ"]["instance_of"] == "Q5 (തെയ്യം)"
    assert g["മുച്ചിലോട്ട് ഭഗവതി"]["depth"] == 1 and g["മുച്ചിലോട്ട് ഭഗവതി"]["label"] == ""

def test_filters_and_exports():
    base = "/?wiki=mlwiki&category=തെയ്യങ്ങൾ&depth=1&wd=1&parents=1"
    assert c.get(base + "&filter=nolabel&format=qids").get_data(as_text=True) == "Q2"
    assert "കതിവനൂർ" in c.get(base + "&filter=without&format=csv").get_data(as_text=True)
    assert "[[d:Q1|Q1]]" in c.get(base + "&format=wikitext").get_data(as_text=True)
    h = c.get(base).get_data(as_text=True)
    assert "Special:NewItem" in h and "petscan.wmcloud.org" in h and "Category tree" in h
    assert c.get("/?wiki=evil.com&category=x").status_code == 200

if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"): f(); print("ok", n)
