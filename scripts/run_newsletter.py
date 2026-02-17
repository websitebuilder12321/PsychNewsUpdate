#!/usr/bin/env python3
"""
Psych Research Daily — PubMed Data Fetcher & HTML Builder

Uses ONLY Python standard library (no pip install needed).
Fetches from PubMed E-utilities API and FDA RSS feeds,
saves raw article data as JSON, and generates a styled HTML newsletter.

When run standalone (double-click), generates a basic newsletter.
When run via the Cowork skill, Claude interprets the articles
and writes proper synopses before building the HTML.
"""

import urllib.request
import urllib.parse
import urllib.error
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import os
import subprocess
import html as html_module
import ssl
import sys
import time
import traceback

# ─── Configuration ───────────────────────────────────────────────────────────
OUTPUT_DIR = os.environ.get("PRD_OUTPUT_DIR", os.path.expanduser("~/Desktop/PsychResearchDaily"))
PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
FDA_FEED_URL = "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/drugs/rss.xml"
LOOKBACK_DAYS = 3

# Allow unverified SSL for systems with outdated certificates
try:
    _ssl_ctx = ssl.create_default_context()
except Exception:
    _ssl_ctx = ssl._create_unverified_context()

SEARCH_QUERIES = [
    '("psychiatry"[MeSH] OR "mental disorders"[MeSH]) AND ("therapy"[Subheading] OR "drug therapy"[Subheading])',
    '("psychotropic drugs"[MeSH] OR "antidepressive agents"[MeSH] OR "antipsychotic agents"[MeSH] OR "anti-anxiety agents"[MeSH] OR "lithium"[MeSH]) AND ("clinical trial"[pt] OR "randomized controlled trial"[pt])',
    '("depressive disorder, major"[MeSH] OR "bipolar disorder"[MeSH] OR "schizophrenia"[MeSH] OR "anxiety disorders"[MeSH] OR "stress disorders, post-traumatic"[MeSH] OR "attention deficit disorder with hyperactivity"[MeSH])',
    '("psychiatry"[MeSH] OR "mental disorders"[MeSH]) AND ("meta-analysis"[pt] OR "systematic review"[pt] OR "practice guideline"[pt])',
    '("psychiatry"[MeSH] OR "mental disorders"[MeSH]) AND "case reports"[pt]',
    '(esketamine OR psilocybin OR brexanolone OR zuranolone OR "dextromethorphan bupropion" OR cariprazine OR lumateperone)',
    '("mental disorders"[MeSH] OR "psychiatry"[MeSH]) AND ("exercise"[MeSH] OR "diet"[MeSH] OR "sleep"[MeSH] OR "mindfulness"[MeSH] OR "yoga"[MeSH] OR "lifestyle"[tiab] OR "microbiome"[tiab])',
]

CME_KEYWORDS = [
    "clinical trial", "randomized", "meta-analysis", "systematic review",
    "practice guideline", "treatment", "efficacy", "safety", "dosing",
    "pharmacotherapy", "evidence-based", "fda", "approval",
]

# ── Three sub-categories replacing the old single "psychopharm" bucket ──
CURRENT_MEDS_KEYWORDS = [
    "pharmacotherapy", "antidepressant", "antipsychotic", "anxiolytic",
    "mood stabilizer", "ssri", "snri", "dosing", "drug interaction",
    "pharmacokinetic", "psychotropic", "medication", "lithium",
    "buprenorphine", "naltrexone", "clozapine", "lamotrigine", "valproate",
    "aripiprazole", "quetiapine", "olanzapine", "risperidone", "venlafaxine",
    "sertraline", "fluoxetine", "duloxetine", "bupropion", "mirtazapine",
    "trazodone", "lisdexamfetamine", "methylphenidate", "amphetamine",
    "atomoxetine", "guanfacine", "brexpiprazole", "genesight",
    "pharmacogenomic", "side effect", "adverse event", "tolerability",
    "drug safety", "label change", "dose adjustment", "therapeutic drug monitoring",
    "polypharmacy", "switching", "augmentation", "prescribing",
]

NOVEL_TREATMENTS_KEYWORDS = [
    "psilocybin", "esketamine", "spravato", "ketamine", "zuranolone",
    "brexanolone", "dextromethorphan", "auvelity", "cariprazine",
    "lumateperone", "novel mechanism", "novel compound", "pipeline",
    "investigational", "phase 2", "phase 3", "phase ii", "phase iii",
    "breakthrough therapy", "psychedelic", "mdma", "lsd", "ayahuasca",
    "tms", "transcranial magnetic", "tdcs", "transcranial direct current",
    "deep brain stimulation", "vagus nerve", "electroconvulsive",
    "digital therapeutic", "neuroplasticity", "glutamate", "gaba modulator",
    "neurosteroid", "kappa opioid", "muscarinic", "trace amine",
    "new drug application", "first-in-class",
]

LIFESTYLE_KEYWORDS = [
    "exercise", "physical activity", "aerobic", "yoga", "meditation",
    "mindfulness", "sleep hygiene", "sleep intervention", "circadian",
    "nutrition", "diet", "mediterranean diet", "omega-3", "gut-brain",
    "microbiome", "probiotic", "social support", "social isolation",
    "psychosocial", "behavioral activation", "lifestyle intervention",
    "lifestyle modification", "complementary", "integrative medicine",
    "nature therapy", "green space", "light therapy", "bright light",
    "chronotherapy", "acupuncture", "stress reduction", "relaxation",
    "cognitive behavioral", "self-care", "wellness", "prevention",
]

# ── Disorder-based tagging (articles can match multiple disorders) ──
DISORDER_TAGS = [
    ("depression", [
        "depression", "depressive", "major depressive", "mdd", "dysthymia",
        "persistent depressive", "treatment-resistant depression", "trd",
        "antidepressant", "ssri", "snri", "suicid", "melanchol",
        "anhedonia", "electroconvulsive", "ketamine", "esketamine",
        "zuranolone", "brexanolone", "postpartum depression",
    ]),
    ("anxiety", [
        "anxiety", "anxious", "generalized anxiety", "gad", "panic disorder",
        "panic attack", "social anxiety", "social phobia", "agoraphobia",
        "specific phobia", "separation anxiety", "anxiolytic",
        "benzodiazepine", "buspirone", "worry", "fear",
    ]),
    ("adhd", [
        "adhd", "attention deficit", "attention-deficit", "hyperactivity",
        "inattention", "inattentive", "impulsivity", "executive function",
        "methylphenidate", "amphetamine", "lisdexamfetamine", "atomoxetine",
        "guanfacine", "stimulant", "adderall", "ritalin", "vyvanse",
        "concerta", "centanafadine",
    ]),
    ("ptsd", [
        "ptsd", "post-traumatic", "posttraumatic", "trauma", "traumatic stress",
        "combat veteran", "sexual assault", "mdma", "prolonged exposure",
        "emdr", "eye movement desensitization", "nightmare", "flashback",
        "hyperarousal", "moral injury", "complex ptsd",
    ]),
    ("bipolar", [
        "bipolar", "mania", "manic", "hypomania", "hypomanic", "mood stabiliz",
        "lithium", "lamotrigine", "valproate", "valproic", "carbamazepine",
        "bipolar depression", "cyclothymi", "rapid cycling", "mixed episode",
        "cariprazine", "lumateperone", "lurasidone",
    ]),
    ("schizophrenia", [
        "schizophren", "psychosis", "psychotic", "antipsychotic", "delusion",
        "hallucination", "negative symptoms", "positive symptoms", "clozapine",
        "olanzapine", "risperidone", "aripiprazole", "quetiapine", "paliperidone",
        "first episode psychosis", "schizoaffective", "thought disorder",
        "caplyta", "cobenfy", "muscarinic",
    ]),
    ("ocd", [
        "obsessive-compulsive", "obsessive compulsive", "ocd", "obsession",
        "compulsion", "intrusive thought", "hoarding", "body dysmorphic",
        "trichotillomania", "hair pulling", "skin picking", "excoriation",
        "exposure and response prevention", "erp", "serotonin reuptake",
    ]),
]


# ═══════════════════════════════════════════════════════════════════════════════
# HTTP helpers using stdlib only
# ═══════════════════════════════════════════════════════════════════════════════

def http_get(url, params=None, timeout=20):
    """Simple HTTP GET using urllib (no requests library needed)."""
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "PsychResearchDaily/1.0"})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx)
        return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        print(f"    HTTP error {e.code} for {url[:80]}")
        return None
    except Exception as e:
        print(f"    Request failed: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# PubMed Fetching
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_pubmed_ids(query, max_results=20):
    """Search PubMed and return PMIDs."""
    date_from = (datetime.now() - timedelta(days=LOOKBACK_DAYS)).strftime("%Y/%m/%d")
    date_to = datetime.now().strftime("%Y/%m/%d")
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "sort": "date",
        "datetype": "edat",
        "mindate": date_from,
        "maxdate": date_to,
        "retmode": "json",
    }
    body = http_get(f"{PUBMED_BASE}/esearch.fcgi", params)
    if not body:
        return []
    try:
        data = json.loads(body)
        return data.get("esearchresult", {}).get("idlist", [])
    except json.JSONDecodeError:
        return []


def fetch_pubmed_details(pmids):
    """Fetch article details for PMIDs."""
    if not pmids:
        return []
    articles = []
    for i in range(0, len(pmids), 50):
        batch = pmids[i:i + 50]
        params = {"db": "pubmed", "id": ",".join(batch), "retmode": "xml"}
        body = http_get(f"{PUBMED_BASE}/efetch.fcgi", params, timeout=30)
        if body:
            articles.extend(parse_pubmed_xml(body))
        time.sleep(0.4)
    return articles


def parse_pubmed_xml(xml_text):
    """Parse PubMed XML into article dicts with raw abstract text."""
    articles = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    for pa in root.findall(".//PubmedArticle"):
        try:
            mc = pa.find(".//MedlineCitation")
            art = mc.find(".//Article")

            te = art.find(".//ArticleTitle")
            title = "".join(te.itertext()).strip() if te is not None else "Untitled"

            # Get the full raw abstract text
            abstract_raw = ""
            ae = art.find(".//Abstract")
            if ae is not None:
                raw_parts = []
                for at in ae.findall(".//AbstractText"):
                    label = (at.get("Label") or "").strip()
                    text = "".join(at.itertext()).strip()
                    if label:
                        raw_parts.append(f"{label}: {text}")
                    else:
                        raw_parts.append(text)
                abstract_raw = " ".join(raw_parts)
            abstract = abstract_raw or "Abstract not available."

            authors = []
            al = art.find(".//AuthorList")
            if al is not None:
                for a in al.findall(".//Author"):
                    ln = a.find("LastName")
                    fn = a.find("ForeName")
                    if ln is not None:
                        name = ln.text
                        if fn is not None:
                            name += f" {fn.text[0]}"
                        authors.append(name)
            author_str = ", ".join(authors[:5])
            if len(authors) > 5:
                author_str += " et al."

            je = art.find(".//Journal/Title")
            journal = je.text if je is not None else "Unknown Journal"

            pd_elem = art.find(".//Journal/JournalIssue/PubDate")
            date_parts = []
            if pd_elem is not None:
                for tag in ("Year", "Month", "Day"):
                    el = pd_elem.find(tag)
                    if el is not None:
                        date_parts.append(el.text)
            date_str = " ".join(date_parts)

            pe = mc.find(".//PMID")
            pmid = pe.text if pe is not None else ""
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""

            pub_types = [pt.text.lower() for pt in art.findall(".//PublicationTypeList/PublicationType") if pt.text]

            all_text = f"{title} {abstract}".lower()
            is_cme = any(kw in all_text or kw in " ".join(pub_types) for kw in CME_KEYWORDS)

            # Categorize
            if "case reports" in pub_types:
                category, art_type = "case_studies", "case report"
            elif any(t in pub_types for t in ("practice guideline", "guideline")):
                category, art_type = "guidelines", "guideline"
            elif any(kw in all_text for kw in LIFESTYLE_KEYWORDS):
                category = "lifestyle"
                art_type = "clinical trial" if any("clinical trial" in t for t in pub_types) else "review"
            elif any(kw in all_text for kw in NOVEL_TREATMENTS_KEYWORDS):
                category = "novel_treatments"
                art_type = "clinical trial" if any("clinical trial" in t for t in pub_types) else "review"
            elif any(kw in all_text for kw in CURRENT_MEDS_KEYWORDS):
                category = "current_meds"
                art_type = "clinical trial" if any("clinical trial" in t for t in pub_types) else "review"
            elif "meta-analysis" in pub_types:
                category, art_type = "top_stories", "meta-analysis"
            elif "systematic review" in pub_types:
                category, art_type = "top_stories", "systematic review"
            elif any("clinical trial" in t or "randomized controlled trial" in t for t in pub_types):
                category, art_type = "top_stories", "clinical trial"
            else:
                category, art_type = "new_research", "other"

            # Tag with relevant disorders
            disorders = []
            for disorder_id, disorder_kws in DISORDER_TAGS:
                if any(kw in all_text for kw in disorder_kws):
                    disorders.append(disorder_id)

            articles.append({
                "title": title, "authors": author_str, "journal": journal,
                "date": date_str, "pmid": pmid, "url": url,
                "abstract": abstract,
                "type": art_type, "is_cme": is_cme,
                "category": category, "disorders": disorders,
            })
        except Exception:
            continue
    return articles


def fetch_fda_alerts():
    """Fetch psychiatry-relevant FDA alerts."""
    psych_kw = [
        "antidepressant", "antipsychotic", "anxiolytic", "psychiatr",
        "mental health", "ssri", "snri", "bipolar", "schizophren",
        "depression", "anxiety", "adhd", "stimulant", "benzodiazepine",
        "ketamine", "esketamine", "psychotropic", "suicid", "serotonin",
    ]
    alerts = []
    body = http_get(FDA_FEED_URL, timeout=15)
    if not body:
        return []
    try:
        root = ET.fromstring(body)
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            desc = (item.findtext("description") or "").strip()
            link = (item.findtext("link") or "").strip()
            if any(kw in f"{title} {desc}".lower() for kw in psych_kw):
                alerts.append({"title": title, "description": desc[:400], "url": link})
    except ET.ParseError:
        pass
    return alerts[:5]


# ═══════════════════════════════════════════════════════════════════════════════
# HTML Generation
# ═══════════════════════════════════════════════════════════════════════════════

def esc(s):
    return html_module.escape(str(s))


def render_article(a):
    badges = []
    if a.get("is_cme"):
        badges.append('<span class="badge badge-cme">CME</span>')
    t = a.get("type", "")
    if "trial" in t:
        badges.append('<span class="badge badge-trial">Clinical Trial</span>')
    if "review" in t or "meta" in t:
        badges.append('<span class="badge badge-review">Review</span>')
    if "guideline" in t:
        badges.append('<span class="badge badge-guideline">Guideline</span>')
    if "case" in t:
        badges.append('<span class="badge badge-case">Case Report</span>')

    h = f'''<div class="article-card">
  <div class="article-title"><a href="{esc(a.get('url',''))}">{esc(a['title'])}</a></div>
  <div class="article-meta">
    <span class="journal-name">{esc(a.get('journal',''))}</span>
    &bull; {esc(a.get('date',''))} &bull; {esc(a.get('authors',''))} {' '.join(badges)}
  </div>'''

    # Use AI-written synopsis if available, otherwise show abstract snippet
    if a.get("synopsis"):
        h += f'\n  <div class="article-summary">{esc(a["synopsis"])}</div>'
    elif a.get("abstract") and a["abstract"] != "Abstract not available.":
        # Fallback: first 2 sentences of abstract (standalone mode only)
        sentences = a["abstract"].split(". ")
        snippet = ". ".join(sentences[:2]).strip()
        if snippet and not snippet.endswith("."):
            snippet += "."
        if len(snippet) > 400:
            snippet = snippet[:400].rsplit(". ", 1)[0] + "."
        h += f'\n  <div class="article-summary">{esc(snippet)}</div>'

    if a.get("implications"):
        h += f'\n  <div class="clinical-impl"><strong>Implications for practice:</strong> {esc(a["implications"])}</div>'

    if a.get("url"):
        h += f'\n  <a class="article-link" href="{esc(a["url"])}">Read full article &rarr;</a>'
    h += "\n</div>"
    return h


def render_section(sid, icon, title, articles):
    h = f'''<div class="section" id="{sid}">
  <div class="section-header">
    <span class="section-icon">{icon}</span>
    <span class="section-title">{title}</span>
  </div>'''
    if not articles:
        h += '\n  <p class="empty-section">No articles in this category today.</p>'
    else:
        for a in articles:
            h += "\n" + render_article(a)
    h += "\n</div>\n"
    return h


def build_html(categories, fda_alerts, date_str, ai_mode=False, all_articles=None):
    ts = list(categories.get("top_stories", []))
    nr = list(categories.get("new_research", []))
    cm = list(categories.get("current_meds", []))
    nt = list(categories.get("novel_treatments", []))
    lf = list(categories.get("lifestyle", []))
    gl = list(categories.get("guidelines", []))
    cs = list(categories.get("case_studies", []))
    qr = list(categories.get("quick_reads", []))

    if not ts and nr:
        ts = nr[:3]; nr = nr[3:]
    if len(nr) > 8:
        qr.extend(nr[8:]); nr = nr[:8]
    if len(cm) > 6:
        qr.extend(cm[6:]); cm = cm[:6]
    if len(nt) > 6:
        qr.extend(nt[6:]); nt = nt[:6]
    if len(lf) > 6:
        qr.extend(lf[6:]); lf = lf[:6]

    # Build disorder-based sections from ALL articles
    all_arts = all_articles or []
    for sec in (ts, nr, cm, nt, lf, gl, cs, qr):
        for a in sec:
            if a not in all_arts:
                all_arts.append(a)

    disorder_display = [
        ("depression", "Depression"),
        ("anxiety", "Anxiety"),
        ("adhd", "ADHD"),
        ("ptsd", "PTSD"),
        ("bipolar", "Bipolar"),
        ("schizophrenia", "Schizophrenia"),
        ("ocd", "OCD"),
    ]
    disorder_buckets = {}
    for did, _ in disorder_display:
        disorder_buckets[did] = [a for a in all_arts if did in a.get("disorders", [])]

    # Build disorder nav bar HTML
    disorder_nav = ""
    for did, dlabel in disorder_display:
        count = len(disorder_buckets[did])
        disorder_nav += f'<a href="#disorder-{did}" class="disorder-pill">{dlabel} <span class="disorder-count">{count}</span></a>\n'

    # Build disorder sections HTML
    disorder_sections = ""
    for did, dlabel in disorder_display:
        arts = disorder_buckets[did]
        disorder_sections += render_section(f"disorder-{did}", "", dlabel, arts)

    fda_html = ""
    if fda_alerts:
        for a in fda_alerts:
            fda_html += f'''<div class="fda-alert"><div class="fda-alert-title"><a href="{esc(a.get("url",""))}">{esc(a["title"])}</a></div><div class="fda-alert-desc">{esc(a["description"])}</div></div>\n'''
    else:
        fda_html = '<p class="empty-section">No psychiatry-relevant FDA alerts today.</p>'

    qr_html = ""
    if qr:
        for a in qr:
            cme = ' <span class="badge badge-cme">CME</span>' if a.get("is_cme") else ""
            qr_html += f'''<div class="quick-read">&bull; <a href="{esc(a.get('url',''))}">{esc(a['title'])}</a>{cme}<br><span class="journal-name">{esc(a.get('journal',''))}</span></div>\n'''
    else:
        qr_html = '<p class="empty-section">No additional articles today.</p>'

    total = len(ts) + len(nr) + len(cm) + len(nt) + len(lf) + len(gl) + len(cs) + len(qr)
    mode_note = "" if ai_mode else '<div style="background:#fef3c7;padding:12px 20px;border-radius:8px;margin-bottom:20px;text-align:center;color:#92400e;font-size:.9em">Basic mode — For AI-interpreted synopses, run via Cowork skill</div>'

    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Psych Research Daily — {esc(date_str)}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;background:#f5f5f7;color:#1d1d1f;line-height:1.6}}
.header{{background:linear-gradient(135deg,#1a365d 0%,#2d5a8e 50%,#3a7ec2 100%);color:#fff;padding:40px 0 10px;text-align:center;border-bottom:4px solid #f0b429}}
.header h1{{font-size:2.2em;font-weight:700;letter-spacing:-.5px;margin-bottom:8px}}
.header .subtitle{{font-size:1.05em;opacity:.85}}
.header .date{{font-size:.9em;opacity:.7;margin-top:6px}}
.disorder-nav{{display:flex;flex-wrap:wrap;justify-content:center;gap:10px;padding:18px 20px 20px;background:linear-gradient(135deg,#1a365d 0%,#2d5a8e 50%,#3a7ec2 100%)}}
.disorder-pill{{display:inline-flex;align-items:center;gap:6px;padding:8px 18px;background:rgba(255,255,255,0.15);color:#fff;border-radius:20px;text-decoration:none;font-size:.92em;font-weight:600;transition:background .2s;backdrop-filter:blur(4px)}}
.disorder-pill:hover{{background:rgba(255,255,255,0.3)}}
.disorder-count{{background:rgba(255,255,255,0.25);padding:1px 8px;border-radius:10px;font-size:.8em;font-weight:700}}
.container{{max-width:820px;margin:0 auto;padding:30px 20px}}
.toc{{background:#fff;border-radius:12px;padding:24px 30px;margin-bottom:30px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.toc h2{{font-size:1.1em;color:#6b7280;text-transform:uppercase;letter-spacing:1px;margin-bottom:14px}}
.toc ul{{list-style:none;display:grid;grid-template-columns:1fr 1fr;gap:8px}}
.toc a{{color:#2d5a8e;text-decoration:none;font-weight:500;font-size:.95em}}
.toc a:hover{{text-decoration:underline}}
.section{{background:#fff;border-radius:12px;padding:28px 30px;margin-bottom:24px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.section-header{{display:flex;align-items:center;gap:10px;margin-bottom:22px;padding-bottom:12px;border-bottom:2px solid #e5e7eb}}
.section-icon{{font-size:1.4em}}
.section-title{{font-size:1.3em;font-weight:700;color:#1a365d}}
.article-card{{padding:18px 0;border-bottom:1px solid #f0f0f0}}
.article-card:last-child{{border-bottom:none;padding-bottom:0}}
.article-title{{font-size:1.05em;font-weight:600;color:#1d1d1f;margin-bottom:6px;line-height:1.4}}
.article-title a{{color:#1d1d1f;text-decoration:none}}
.article-title a:hover{{color:#2d5a8e;text-decoration:underline}}
.article-meta{{font-size:.85em;color:#6b7280;margin-bottom:10px;display:flex;flex-wrap:wrap;gap:6px;align-items:center}}
.journal-name{{font-style:italic;color:#4b5563}}
.badge{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:.75em;font-weight:600;text-transform:uppercase;letter-spacing:.5px}}
.badge-cme{{background:#fef3c7;color:#92400e}}
.badge-trial{{background:#dbeafe;color:#1e40af}}
.badge-review{{background:#ede9fe;color:#5b21b6}}
.badge-guideline{{background:#d1fae5;color:#065f46}}
.badge-case{{background:#fce7f3;color:#9d174d}}
.article-summary{{font-size:.93em;color:#374151;line-height:1.65;margin-top:8px}}
.clinical-impl{{font-size:.9em;color:#065f46;background:#ecfdf5;padding:10px 14px;border-radius:6px;margin-top:8px;border-left:3px solid #10b981;line-height:1.6}}
.clinical-impl strong{{color:#047857;font-weight:600}}
.article-link{{display:inline-block;margin-top:8px;color:#2d5a8e;text-decoration:none;font-size:.88em;font-weight:500}}
.article-link:hover{{text-decoration:underline}}
.fda-alert{{padding:14px 18px;background:#fff7ed;border-left:4px solid #f59e0b;border-radius:0 8px 8px 0;margin-bottom:12px}}
.fda-alert:last-child{{margin-bottom:0}}
.fda-alert-title{{font-weight:600;color:#92400e;font-size:.95em;margin-bottom:4px}}
.fda-alert-title a{{color:#92400e;text-decoration:none}}
.fda-alert-desc{{font-size:.88em;color:#78350f}}
.quick-read{{padding:10px 0;border-bottom:1px solid #f0f0f0}}
.quick-read:last-child{{border-bottom:none}}
.quick-read a{{color:#1d1d1f;text-decoration:none;font-size:.93em}}
.quick-read a:hover{{color:#2d5a8e;text-decoration:underline}}
.quick-read .journal-name{{font-size:.82em}}
.empty-section{{color:#9ca3af;font-style:italic;font-size:.93em;padding:10px 0}}
.footer{{text-align:center;padding:30px;color:#9ca3af;font-size:.85em}}
.footer a{{color:#6b7280}}
.stats{{background:#eef2ff;border-radius:10px;padding:16px 24px;margin-bottom:24px;text-align:center;font-size:.95em;color:#4338ca}}
@media(max-width:600px){{.disorder-nav{{gap:6px;padding:12px 10px}}.disorder-pill{{padding:6px 12px;font-size:.82em}}.toc ul{{grid-template-columns:1fr}}.header h1{{font-size:1.6em}}.container{{padding:16px 12px}}.section{{padding:20px 16px}}}}
</style></head><body>
<div class="header">
  <h1>Psych Research Daily</h1>
  <div class="subtitle">Curated Psychiatric Research &amp; Clinical Updates</div>
  <div class="date">{esc(date_str)} &mdash; Generated for Jacob Krasner, PA-C</div>
</div>
<div class="disorder-nav">
  {disorder_nav}
</div>
<div class="container">
  {mode_note}
  <div class="stats">{total} articles found &bull; {sum(1 for sec in (ts,nr,cm,nt,lf,gl,cs,qr) for a in sec if a.get('is_cme'))} CME-relevant &bull; {len(fda_alerts)} FDA alerts</div>
  <div class="toc"><h2>In This Issue</h2><ul>
    <li><a href="#disorder-depression">Depression</a></li>
    <li><a href="#disorder-anxiety">Anxiety</a></li>
    <li><a href="#disorder-adhd">ADHD</a></li>
    <li><a href="#disorder-ptsd">PTSD</a></li>
    <li><a href="#disorder-bipolar">Bipolar</a></li>
    <li><a href="#disorder-schizophrenia">Schizophrenia</a></li>
    <li><a href="#disorder-ocd">OCD</a></li>
    <li><a href="#current-meds">&#128138; Current Meds ({len(cm)})</a></li>
    <li><a href="#novel-treatments">&#129514; Novel Treatments ({len(nt)})</a></li>
    <li><a href="#lifestyle">&#127793; Lifestyle ({len(lf)})</a></li>
    <li><a href="#fda-watch">&#9888; FDA Watch ({len(fda_alerts)})</a></li>
    <li><a href="#guidelines">&#128203; Guidelines ({len(gl)})</a></li>
  </ul></div>
{disorder_sections}
{render_section("current-meds","&#128138;","Current Medication Updates",cm)}
{render_section("novel-treatments","&#129514;","Novel Mechanisms &amp; Treatments",nt)}
{render_section("lifestyle","&#127793;","Lifestyle Approaches",lf)}
<div class="section" id="fda-watch">
  <div class="section-header"><span class="section-icon">&#9888;</span><span class="section-title">FDA Watch</span></div>
{fda_html}</div>
{render_section("guidelines","&#128203;","Guidelines &amp; Policy",gl)}
{render_section("case-studies","&#128269;","Case Studies",cs)}
<div class="section" id="quick-reads">
  <div class="section-header"><span class="section-icon">&#9889;</span><span class="section-title">Quick Reads</span></div>
{qr_html}</div>
<div class="footer">
  <p>Psych Research Daily &mdash; Generated {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
  <p>Sources: <a href="https://pubmed.ncbi.nlm.nih.gov/">PubMed/MEDLINE</a> &bull;
     <a href="https://www.fda.gov/drugs/drug-safety-and-availability">FDA MedWatch</a> &bull;
     <a href="https://psychiatry.org/">APA</a></p>
  <p style="margin-top:8px;font-size:.9em">Articles flagged <span class="badge badge-cme">CME</span> may be relevant for continuing education.</p>
</div>
</div></body></html>"""



# ═══════════════════════════════════════════════════════════════════════════════
# Main — Fetch data, save JSON, build HTML
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_all_data():
    """Fetch articles from PubMed and FDA. Returns (articles, fda_alerts)."""
    print("[1/3] Searching PubMed...")
    all_pmids = set()
    for i, q in enumerate(SEARCH_QUERIES, 1):
        ids = fetch_pubmed_ids(q, max_results=15)
        print(f"    Query {i}/{len(SEARCH_QUERIES)}: {len(ids)} results")
        all_pmids.update(ids)
        time.sleep(0.4)
    print(f"    Total unique PMIDs: {len(all_pmids)}")

    print("\n[2/3] Fetching article details...")
    articles = fetch_pubmed_details(list(all_pmids))
    seen = set()
    unique = []
    for a in articles:
        if a["pmid"] not in seen:
            seen.add(a["pmid"])
            unique.append(a)
    articles = unique
    print(f"    Retrieved {len(articles)} unique articles")

    print("\n[3/3] Checking FDA alerts...")
    fda_alerts = fetch_fda_alerts()
    print(f"    Found {len(fda_alerts)} psychiatry-relevant alerts")

    return articles, fda_alerts


def enrich_articles_with_ai(raw_json_path, enriched_json_path):
    """Call the Anthropic API to generate synopses and clinical implications for each article."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set. Skipping AI enrichment.")
        return False

    with open(raw_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    articles = data.get("articles", [])
    if not articles:
        print("No articles to enrich.")
        return False

    print(f"\nEnriching {len(articles)} articles with AI synopses...")

    # Process articles in batches of 10 to keep prompt size manageable
    BATCH_SIZE = 10
    enriched_count = 0

    for batch_start in range(0, len(articles), BATCH_SIZE):
        batch = articles[batch_start:batch_start + BATCH_SIZE]
        batch_num = (batch_start // BATCH_SIZE) + 1
        total_batches = (len(articles) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"  Batch {batch_num}/{total_batches} ({len(batch)} articles)...")

        # Build the prompt with article data
        articles_text = ""
        for i, a in enumerate(batch):
            abstract_preview = (a.get("abstract") or "Abstract not available.")[:1500]
            articles_text += f"""
--- ARTICLE {i + 1} ---
Title: {a['title']}
Journal: {a.get('journal', 'Unknown')}
Type: {a.get('type', 'other')}
Abstract: {abstract_preview}
"""

        prompt = f"""You are a psychiatric research analyst writing for practicing clinicians (psychiatrists, psychiatric PAs, and NPs). For each article below, write:

1. **synopsis**: A concise 2-3 sentence plain-language summary of the study's key findings and methodology. Focus on what was studied, key results, and effect sizes when available. Write for a clinical audience — assume familiarity with psychiatric terminology.

2. **implications**: A single sentence starting with a practical takeaway for clinical practice. What should a prescriber or clinician consider based on this study?

Return ONLY valid JSON — an array of objects, one per article, in the same order. Each object must have exactly two keys: "synopsis" and "implications". No markdown, no extra text.

{articles_text}

Return JSON array:"""

        # Call Anthropic Messages API using stdlib
        request_body = json.dumps({
            "model": "claude-sonnet-4-5-20250514",
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=request_body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )

        try:
            resp = urllib.request.urlopen(req, timeout=120, context=_ssl_ctx)
            resp_body = json.loads(resp.read().decode("utf-8"))
            ai_text = resp_body["content"][0]["text"].strip()

            # Parse the JSON response — handle possible markdown wrapping
            if ai_text.startswith("```"):
                ai_text = ai_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            batch_results = json.loads(ai_text)

            # Apply synopses back to articles
            for i, result in enumerate(batch_results):
                if i < len(batch):
                    idx = batch_start + i
                    articles[idx]["synopsis"] = result.get("synopsis", "")
                    articles[idx]["implications"] = result.get("implications", "")
                    enriched_count += 1

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            print(f"    API error {e.code}: {error_body[:200]}")
            continue
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"    Failed to parse AI response: {e}")
            continue
        except Exception as e:
            print(f"    Enrichment failed for batch: {e}")
            continue

        # Rate limit: pause between batches
        if batch_start + BATCH_SIZE < len(articles):
            time.sleep(1)

    print(f"  Enriched {enriched_count}/{len(articles)} articles.")

    # Save enriched data
    data["articles"] = articles
    data["ai_mode"] = True
    with open(enriched_json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Saved: {enriched_json_path}")
    return True


def save_raw_json(articles, fda_alerts, path):
    """Save raw article data as JSON for the Cowork skill to process."""
    data = {
        "fetched_at": datetime.now().isoformat(),
        "date": datetime.now().strftime("%A, %B %d, %Y"),
        "articles": articles,
        "fda_alerts": fda_alerts,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"    Raw data saved: {path}")
    return data


def build_and_save_html(articles, fda_alerts, date_str, ai_mode=False):
    """Bucket articles and build the HTML newsletter."""
    categories = {
        "top_stories": [], "new_research": [],
        "current_meds": [], "novel_treatments": [], "lifestyle": [],
        "guidelines": [], "case_studies": [], "quick_reads": [],
    }
    for a in articles:
        cat = a.get("category", "new_research")
        categories.setdefault(cat, []).append(a)

    html_content = build_html(categories, fda_alerts, date_str, ai_mode=ai_mode, all_articles=articles)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    fname = f"PsychResearchDaily_{datetime.now().strftime('%Y-%m-%d')}.html"
    fpath = os.path.join(OUTPUT_DIR, fname)

    with open(fpath, "w", encoding="utf-8") as f:
        f.write(html_content)
    latest = os.path.join(OUTPUT_DIR, "latest.html")
    with open(latest, "w", encoding="utf-8") as f:
        f.write(html_content)

    return fpath


def main():
    """Standalone mode: fetch, save JSON, build basic HTML, open in Safari."""
    try:
        print()
        print("=" * 55)
        print("   Psych Research Daily — Generating Newsletter")
        print("=" * 55)
        print()

        date_str = datetime.now().strftime("%A, %B %d, %Y")

        articles, fda_alerts = fetch_all_data()

        # Save raw data as JSON (for Cowork skill to pick up)
        json_path = os.path.join(OUTPUT_DIR, "raw_articles.json")
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        save_raw_json(articles, fda_alerts, json_path)

        # Build and save basic HTML
        print("\nBuilding newsletter...")
        fpath = build_and_save_html(articles, fda_alerts, date_str, ai_mode=False)
        print(f"    Saved: {fpath}")

        # Open in Safari
        print("    Opening in Safari...")
        result = subprocess.run(
            ["open", "-a", "Safari", fpath],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            subprocess.run(["open", fpath], capture_output=True, text=True)

        cme_count = sum(1 for a in articles if a.get("is_cme"))
        print()
        print("=" * 55)
        print(f"   Done! {len(articles)} articles | {cme_count} CME-relevant")
        print(f"   {len(fda_alerts)} FDA alerts")
        print(f"   File: {fpath}")
        print("=" * 55)
        print()
        return True

    except Exception as e:
        print()
        print("!" * 55)
        print(f"   ERROR: {e}")
        print()
        traceback.print_exc()
        print()
        print("!" * 55)
        return False


if __name__ == "__main__":
    # Check for --fetch-only mode (used by Cowork skill)
    if "--fetch-only" in sys.argv:
        print("Fetching data only (Cowork skill mode)...")
        articles, fda_alerts = fetch_all_data()
        json_path = os.path.join(OUTPUT_DIR, "raw_articles.json")
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        save_raw_json(articles, fda_alerts, json_path)
        print(f"Data saved to {json_path}")
        sys.exit(0)

    # Check for --enrich mode (call Anthropic API to add synopses)
    if "--enrich" in sys.argv:
        print("Enriching articles with AI synopses...")
        raw_path = os.path.join(OUTPUT_DIR, "raw_articles.json")
        enriched_path = os.path.join(OUTPUT_DIR, "enriched_articles.json")
        if not os.path.exists(raw_path):
            print(f"ERROR: {raw_path} not found. Run --fetch-only first.")
            sys.exit(1)
        success = enrich_articles_with_ai(raw_path, enriched_path)
        sys.exit(0 if success else 1)

    # Check for --build-from-json mode (used after Cowork enrichment)
    if "--build-from-json" in sys.argv:
        json_path = os.path.join(OUTPUT_DIR, "enriched_articles.json")
        if not os.path.exists(json_path):
            json_path = os.path.join(OUTPUT_DIR, "raw_articles.json")
        print(f"Building HTML from {json_path}...")
        with open(json_path, "r") as f:
            data = json.load(f)
        date_str = data.get("date", datetime.now().strftime("%A, %B %d, %Y"))
        fpath = build_and_save_html(
            data["articles"], data.get("fda_alerts", []),
            date_str, ai_mode=data.get("ai_mode", False)
        )
        print(f"Saved: {fpath}")
        # Open in Safari if on macOS (skip on CI/Linux)
        if sys.platform == "darwin":
            subprocess.run(["open", "-a", "Safari", fpath], capture_output=True, text=True)
        sys.exit(0)

    # Default: full standalone mode
    success = main()
    if not success:
    input("\nPress Enter to close this window...")
    sys.exit(1)
