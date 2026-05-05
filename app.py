import re
import io
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from urllib.parse import urlparse, urljoin

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
STOPWORDS = {
    "the","and","for","with","that","this","from","you","your","are","was","were","can","will","into","about","how","what",
    "why","when","where","which","their","they","them","our","out","all","not","have","has","had","use","using","used",
    "more","best","top","guide","complete","vs","than","over","under","new","get","make","many","most","other","also"
}
ENTITY_HINTS = {"ai","nlp","api","gpt","chatgpt","hubspot","google","openai","semrush","ahrefs","wordpress"}


@dataclass
class PageMetrics:
    keyword: str
    rank: int
    url: str
    meta_title: str
    meta_description: str
    h1: str
    h2s: list
    word_count: int
    h2_count: int
    avg_paragraph_len: float
    internal_links: int
    external_links: int
    content_type: str
    entities: list
    terms: list


def fetch_serp_urls(keyword: str, top_n: int = 10):
    q = requests.utils.quote(keyword)
    url = f"https://html.duckduckgo.com/html/?q={q}"
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    urls = []
    for a in soup.select("a.result__a"):
        href = a.get("href")
        if href and href.startswith("http"):
            urls.append(href)
        if len(urls) >= top_n:
            break
    return urls


def visible_text(tag):
    if tag.name in {"script", "style", "noscript", "svg"}:
        return False
    if tag.get("aria-hidden") == "true":
        return False
    return True


def extract_main_area(soup: BeautifulSoup):
    for selector in ["main", "article", "[role='main']"]:
        node = soup.select_one(selector)
        if node:
            return node
    candidates = soup.find_all(["section", "div"], limit=150)
    if not candidates:
        return soup.body or soup
    best = max(candidates, key=lambda n: len(" ".join(n.stripped_strings)))
    return best


def clean_tokens(text: str):
    toks = re.findall(r"[A-Za-z][A-Za-z0-9\-\+\.]{1,}", text)
    return [t for t in toks if len(t) > 2]


def classify_content_type(title: str, h2s: list, word_count: int):
    t = (title or "").lower()
    if re.search(r"\b(top|best|\d+)\b", t):
        return "Listicle"
    if "guide" in t or "complete" in t or "how to" in t:
        return "Guide"
    if word_count < 900 and len(h2s) <= 2:
        return "Landing page"
    return "Blog"


def analyze_page(keyword: str, rank: int, url: str):
    try:
        res = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
        res.raise_for_status()
    except Exception:
        return None

    soup = BeautifulSoup(res.text, "html.parser")
    meta_title = (soup.title.text.strip() if soup.title else "")
    meta_desc_tag = soup.find("meta", attrs={"name": re.compile("description", re.I)})
    meta_description = meta_desc_tag.get("content", "").strip() if meta_desc_tag else ""

    body = extract_main_area(soup)

    for bad in body.select("header, footer, nav, aside"):
        bad.decompose()

    h1 = (body.find("h1").get_text(" ", strip=True) if body.find("h1") else "")
    h2s = [h.get_text(" ", strip=True) for h in body.find_all(re.compile("^h[2-6]$")) if h.get_text(strip=True)]
    paragraphs = [p.get_text(" ", strip=True) for p in body.find_all("p") if p.get_text(strip=True)]

    body_text = "\n".join(paragraphs + h2s + ([h1] if h1 else []))
    tokens = clean_tokens(body_text)
    word_count = len(tokens)
    avg_para_len = (sum(len(clean_tokens(p)) for p in paragraphs) / len(paragraphs)) if paragraphs else 0.0

    host = urlparse(url).netloc
    internal = external = 0
    for a in body.find_all("a", href=True):
        href = urljoin(url, a["href"])
        linked_host = urlparse(href).netloc
        if not linked_host:
            continue
        if linked_host == host:
            internal += 1
        else:
            external += 1

    cap_entities = [t for t in re.findall(r"\b[A-Z][a-zA-Z0-9\+\-]{2,}\b", body_text)]
    hint_entities = [t for t in tokens if t.lower() in ENTITY_HINTS]
    entity_counts = Counter([e.strip() for e in cap_entities + hint_entities if e.lower() not in STOPWORDS])

    term_counts = Counter([t.lower() for t in tokens if t.lower() not in STOPWORDS])
    content_type = classify_content_type(meta_title, h2s, word_count)

    return PageMetrics(
        keyword=keyword,
        rank=rank,
        url=url,
        meta_title=meta_title,
        meta_description=meta_description,
        h1=h1,
        h2s=h2s,
        word_count=word_count,
        h2_count=len(h2s),
        avg_paragraph_len=round(avg_para_len, 2),
        internal_links=internal,
        external_links=external,
        content_type=content_type,
        entities=[e for e, _ in entity_counts.most_common(10)],
        terms=[t for t, _ in term_counts.most_common(15)],
    )


def cluster_topics(h2_bank: list):
    norm = [re.sub(r"[^a-z0-9 ]", "", h.lower()).strip() for h in h2_bank]
    norm = [h for h in norm if h]
    c = Counter(norm)
    return c.most_common(12)


def run_keyword(keyword: str):
    urls = fetch_serp_urls(keyword)
    pages = []
    for i, u in enumerate(urls, 1):
        row = analyze_page(keyword, i, u)
        if row:
            pages.append(row)
    return pages


def pages_to_df(pages):
    rows = []
    for p in pages:
        d = asdict(p)
        d["h2s"] = " | ".join(p.h2s)
        d["entities"] = ", ".join(p.entities)
        d["terms"] = ", ".join(p.terms)
        rows.append(d)
    return pd.DataFrame(rows)


def render_summary(df):
    if df.empty:
        st.warning("No pages extracted.")
        return
    type_dist = df["content_type"].value_counts().to_dict()
    st.subheader("SERP Summary")
    st.write({
        "content_type_distribution": type_dist,
        "avg_word_count": round(df["word_count"].mean(), 1),
        "avg_h2_count": round(df["h2_count"].mean(), 1),
    })

    h2_bank = []
    for h2line in df["h2s"].fillna(""):
        h2_bank.extend([x.strip() for x in h2line.split("|") if x.strip()])
    st.subheader("Common Topics (repeated H2/themes)")
    st.table(pd.DataFrame(cluster_topics(h2_bank), columns=["topic", "frequency"]))

    ents = Counter()
    for e in df["entities"].fillna(""):
        ents.update([x.strip() for x in e.split(",") if x.strip()])
    st.subheader("Top Entities")
    st.table(pd.DataFrame(ents.most_common(15), columns=["entity", "count"]))


def main():
    st.set_page_config(page_title="SEO SERP Intelligence", layout="wide")
    st.title("SEO SERP Analysis & On-Page Intelligence")

    with st.sidebar:
        st.header("Input")
        keywords_text = st.text_area("Keywords (one per line)", height=160)
        csv = st.file_uploader("or upload CSV (column: keyword)", type=["csv"])
        domain_compare = st.text_input("Optional domain compare")
        location = st.text_input("Location", value="United States")
        language = st.selectbox("Language", ["en", "es", "de", "fr"], index=0)
        device = st.selectbox("Device", ["desktop", "mobile"], index=0)
        run = st.button("Run analysis", type="primary")

    st.caption(f"Settings: location={location}, language={language}, device={device}, compare_domain={domain_compare or 'N/A'}")

    keywords = []
    if keywords_text.strip():
        keywords.extend([k.strip() for k in keywords_text.splitlines() if k.strip()])
    if csv is not None:
        up = pd.read_csv(csv)
        if "keyword" in up.columns:
            keywords.extend(up["keyword"].dropna().astype(str).tolist())

    keywords = list(dict.fromkeys(keywords))

    if run:
        if not keywords:
            st.error("Please add at least one keyword.")
            return
        all_frames = []
        for kw in keywords:
            with st.spinner(f"Analyzing: {kw}"):
                pages = run_keyword(kw)
                df = pages_to_df(pages)
            st.header(f"Keyword: {kw}")
            render_summary(df)
            st.subheader("URL-level data")
            st.dataframe(df[["rank","url","meta_title","meta_description","h1","h2s","word_count","internal_links","external_links","content_type"]], use_container_width=True)
            all_frames.append(df)

        if all_frames:
            final = pd.concat(all_frames, ignore_index=True)
            st.download_button(
                "Export CSV",
                data=final.to_csv(index=False).encode("utf-8"),
                file_name="serp_intelligence_export.csv",
                mime="text/csv",
            )


if __name__ == "__main__":
    main()
