# SEO SERP Analysis & On-Page Intelligence

Streamlit tool that extracts top SERP pages and turns them into actionable SEO insights.

## Features
- Keyword-wise SERP extraction (top 10 URLs)
- Body-only on-page parsing (`<main>`, `<article>`, or largest text block)
- Meta extraction (title/description)
- Structure extraction (H1, H2-H6, paragraphs)
- Metrics (word count, H2 count, avg paragraph length)
- Link analysis (internal vs external links)
- Entity and repeated-term extraction
- SERP pattern classification (Listicle / Guide / Landing page / Blog)
- Common topic clustering from repeated H2s
- Table view + grouped insights + CSV export

## Run
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Notes
- SERP source uses DuckDuckGo HTML endpoint (no API key required).
- Location/language/device/domain inputs are included in UI and surfaced in output context.
- Some websites block scraping, so per-keyword URL counts may be lower than 10.
