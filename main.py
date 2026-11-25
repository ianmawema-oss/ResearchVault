import asyncio, json, os, re, sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE = Path(__file__).parent
DB_PATH = os.getenv("DATABASE_PATH", str(BASE / "researchvault.db"))
HEADERS = {"User-Agent": "ResearchVault/0.1 (academic discovery MVP; contact: admin@example.com)"}

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS saved_papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doi TEXT UNIQUE,
            title TEXT NOT NULL,
            authors TEXT,
            year INTEGER,
            journal TEXT,
            url TEXT,
            saved_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="ResearchVault API", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")

def clean_doi(value):
    if not value:
        return None
    value = value.strip()
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value, flags=re.I)
    return value or None

def normalise(title, authors=None, year=None, journal=None, doi=None, abstract=None, url=None, source=None, oa_url=None):
    return {
        "title": (title or "Untitled publication").strip(),
        "authors": authors or [],
        "year": year,
        "journal": journal,
        "doi": clean_doi(doi),
        "abstract": abstract,
        "url": url or (f"https://doi.org/{clean_doi(doi)}" if doi else None),
        "source": source,
        "open_access_url": oa_url,
        "verification_status": "metadata found; independent field checks pending"
    }

async def search_openalex(client, q, from_year, to_year, limit):
    params = {"search": q, "per-page": min(limit, 50), "sort": "relevance_score:desc"}
    if from_year or to_year:
        lo, hi = from_year or 1900, to_year or 2100
        params["filter"] = f"publication_year:{lo}-{hi}"
    r = await client.get("https://api.openalex.org/works", params=params)
    r.raise_for_status()
    data = r.json()
    out = []
    for w in data.get("results", []):
        authors = [a.get("author", {}).get("display_name") for a in w.get("authorships", [])[:12]]
        loc = w.get("best_oa_location") or {}
        source = loc.get("source") or {}
        out.append(normalise(
            w.get("title"), authors, w.get("publication_year"),
            source.get("display_name"), w.get("doi"),
            None, w.get("doi") or w.get("id"), "OpenAlex",
            loc.get("landing_page_url") or loc.get("pdf_url")
        ))
    return out

async def search_crossref(client, q, from_year, to_year, limit):
    params = {"query.bibliographic": q, "rows": min(limit, 50), "select": "DOI,title,author,published,container-title,URL,type"}
    filters = []
    if from_year: filters.append(f"from-pub-date:{from_year}-01-01")
    if to_year: filters.append(f"until-pub-date:{to_year}-12-31")
    if filters: params["filter"] = ",".join(filters)
    r = await client.get("https://api.crossref.org/works", params=params)
    r.raise_for_status()
    items = r.json().get("message", {}).get("items", [])
    out = []
    for w in items:
        date = w.get("published", {}).get("date-parts", [[None]])[0]
        authors = [(" ".join(x for x in [a.get("given"), a.get("family")] if x)) for a in w.get("author", [])[:12]]
        out.append(normalise(
            (w.get("title") or [None])[0], authors, date[0] if date else None,
            (w.get("container-title") or [None])[0], w.get("DOI"),
            None, w.get("URL"), "Crossref", None
        ))
    return out

async def search_europepmc(client, q, from_year, to_year, limit):
    query = q
    if from_year: query += f" AND FIRST_PDATE:[{from_year}-01-01 TO "
    if from_year and to_year: query += f"{to_year}-12-31]"
    elif from_year: query += "3000-12-31]"
    elif to_year: query += f" AND FIRST_PDATE:[1900-01-01 TO {to_year}-12-31]"
    params = {"query": query, "format": "json", "pageSize": min(limit, 50), "resultType": "core"}
    r = await client.get("https://www.ebi.ac.uk/europepmc/webservices/rest/search", params=params)
    r.raise_for_status()
    out = []
    for w in r.json().get("resultList", {}).get("result", []):
        authors = [a.get("fullName") for a in w.get("authorList", {}).get("author", [])[:12]]
        pmcid = w.get("pmcid")
        oa = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/" if pmcid else None
        out.append(normalise(
            w.get("title"), authors, int(w["firstPublicationDate"][:4]) if w.get("firstPublicationDate", "")[:4].isdigit() else None,
            w.get("journalTitle"), w.get("doi"), w.get("abstractText"),
            f"https://europepmc.org/article/MED/{w.get('pmid')}" if w.get("pmid") else (f"https://europepmc.org/article/PMC/{pmcid}" if pmcid else None),
            "Europe PMC", oa
        ))
    return out

@app.get("/")
def home():
    return FileResponse(BASE / "static" / "index.html")

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "ResearchVault API", "version": "0.1.0"}

@app.get("/api/search")
async def search(
    q: str = Query(..., min_length=3, max_length=300),
    from_year: Optional[int] = None,
    to_year: Optional[int] = None,
    limit: int = Query(20, ge=1, le=50)
):
    if from_year and to_year and from_year > to_year:
        raise HTTPException(400, "from_year must be less than or equal to to_year")
    timeout = httpx.Timeout(18.0, connect=8.0)
    async with httpx.AsyncClient(timeout=timeout, headers=HEADERS) as client:
        tasks = [
            search_openalex(client, q, from_year, to_year, limit),
            search_crossref(client, q, from_year, to_year, limit),
            search_europepmc(client, q, from_year, to_year, limit)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    papers, errors = [], []
    for name, result in zip(["OpenAlex", "Crossref", "Europe PMC"], results):
        if isinstance(result, Exception):
            errors.append({"source": name, "message": str(result)[:250]})
        else:
            papers.extend(result)
    # Deduplicate primarily by DOI, then by normalised title.
    unique, seen = [], set()
    for p in papers:
        key = ("doi:" + p["doi"].lower()) if p.get("doi") else ("title:" + re.sub(r"\W+", "", p["title"].lower()))
        if key in seen: continue
        seen.add(key)
        unique.append(p)
    unique.sort(key=lambda p: (p.get("year") or 0), reverse=True)
    return {"query": q, "count": len(unique), "results": unique[:limit], "source_errors": errors,
            "notice": "Search coverage depends on source indexing. A record found is not a judgement of scientific quality."}

@app.get("/api/verify")
async def verify(doi: str):
    doi = clean_doi(doi)
    if not doi or not re.match(r"^10\.\d{4,9}/\S+$", doi):
        raise HTTPException(400, "Please provide a syntactically valid DOI.")
    async with httpx.AsyncClient(timeout=12.0, headers=HEADERS) as client:
        try:
            r = await client.get(f"https://api.crossref.org/works/{doi}")
            if r.status_code == 404:
                return {"doi": doi, "status": "not_found_in_crossref", "message": "No Crossref record found. This alone does not prove the work is fabricated."}
            r.raise_for_status()
            m = r.json().get("message", {})
            title = (m.get("title") or [None])[0]
            return {
                "doi": doi, "status": "record_found",
                "title": title, "authors": [(" ".join(x for x in [a.get("given"), a.get("family")] if x)) for a in m.get("author", [])],
                "journal": (m.get("container-title") or [None])[0],
                "year": (m.get("published", {}).get("date-parts") or [[None]])[0][0],
                "publisher": m.get("publisher"),
                "source": "Crossref",
                "limitation": "This verifies a Crossref metadata record, not the scientific validity, peer-review quality or current retraction status of the work."
            }
        except httpx.HTTPError as e:
            raise HTTPException(502, f"Crossref lookup failed: {str(e)[:180]}")

class SavePaper(BaseModel):
    doi: Optional[str] = None
    title: str = Field(min_length=1, max_length=1000)
    authors: list[str] = []
    year: Optional[int] = None
    journal: Optional[str] = None
    url: Optional[str] = None

@app.post("/api/saved")
def save_paper(p: SavePaper):
    doi = clean_doi(p.doi)
    with db() as con:
        if doi:
            con.execute("""INSERT INTO saved_papers(doi,title,authors,year,journal,url)
            VALUES(?,?,?,?,?,?) ON CONFLICT(doi) DO UPDATE SET title=excluded.title""",
            (doi, p.title, json.dumps(p.authors), p.year, p.journal, p.url))
        else:
            con.execute("INSERT INTO saved_papers(title,authors,year,journal,url) VALUES(?,?,?,?,?)",
            (p.title, json.dumps(p.authors), p.year, p.journal, p.url))
    return {"saved": True}

@app.get("/api/saved")
def list_saved():
    with db() as con:
        rows = con.execute("SELECT * FROM saved_papers ORDER BY saved_at DESC").fetchall()
    return [dict(r) for r in rows]

@app.delete("/api/saved/{paper_id}")
def delete_saved(paper_id: int):
    with db() as con:
        cur = con.execute("DELETE FROM saved_papers WHERE id=?", (paper_id,))
        if cur.rowcount == 0: raise HTTPException(404, "Saved publication not found")
    return {"deleted": True}
