import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

try:
    import pymupdf  # newer PyMuPDF
except ImportError:
    import fitz as pymupdf
import yaml

from agents.llm import call_json
from agents.utils import load_prompt, save_json

DATA_DIR = Path("data")
STOP = set("the a an and or of to in for is are on with at by from as it this that be your you we our".split())


def tokenize(text):
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP]


def ingest(chunk_size=900, overlap=150):
    chunks = []
    for f in sorted(DATA_DIR.glob("*")):
        if f.suffix.lower() == ".pdf":
            doc = pymupdf.open(f)
            pages = [(i + 1, p.get_text()) for i, p in enumerate(doc)]
        elif f.suffix.lower() in (".txt", ".md"):
            pages = [(1, f.read_text(encoding="utf-8"))]
        else:
            continue
        for pno, text in pages:
            text = re.sub(r"\s+", " ", text).strip()
            step = chunk_size - overlap
            for n, i in enumerate(range(0, max(len(text), 1), step), start=1):
                piece = text[i:i + chunk_size].strip()
                if len(piece) > 40:
                    chunks.append({"id": f"{f.name}:p{pno}:c{n}", "file": f.name,
                                   "page": pno, "text": piece})
    return chunks


def retrieve(query, chunks, k=6):
    n = len(chunks)
    toks = [tokenize(c["text"]) for c in chunks]
    df = Counter()
    for t in toks:
        df.update(set(t))
    q = set(tokenize(query))
    scored = []
    for c, t in zip(chunks, toks):
        tf = Counter(t)
        score = sum(tf[w] * math.log(1 + n / (1 + df[w])) for w in q if w in tf)
        scored.append((score, c))
    scored.sort(key=lambda x: -x[0])
    return [c for s, c in scored[:k] if s > 0]


def norm(s):
    return re.sub(r"\s+", " ", s).lower().strip()


def run(brief, out_path="outputs/facts.json"):
    chunks = ingest()
    if not chunks:
        raise SystemExit("No text found in data/. Add the brochure/fact sheet first.")
    queries = [brief["topic"]] + [str(x) for x in brief.get("must_include", [])]
    picked = {}
    for q in queries:
        for c in retrieve(q, chunks):
            picked[c["id"]] = c
    context = list(picked.values())[:14]
    ctx_text = "\n\n".join(f"[{c['id']}]\n{c['text']}" for c in context)
    by_id = {c["id"]: c for c in context}
    user = f"BRIEF:\n{json.dumps(brief, ensure_ascii=False)}\n\nSOURCE CHUNKS:\n{ctx_text}"

    facts, rejected = [], []
    for attempt in range(3):
        res = call_json("researcher", "researcher_v1", load_prompt("researcher_v1.txt"),
                        user, output_path=out_path)
        facts, rejected = [], []
        for f in res.get("facts", []):
            sid = str(f.get("source_id", "")).strip().strip("[]").strip()
            quote = f.get("quote") or f.get("evidence") or f.get("text") or ""
            c = by_id.get(sid)
            if c and quote and norm(quote) in norm(c["text"]):
                facts.append({"claim": f.get("claim", ""), "source": c["file"],
                              "page": c["page"], "source_id": c["id"], "quote": quote})
            else:
                rejected.append(f)  # quote not found in source -> possible hallucination
        if len(facts) >= 3:
            break
        user += ("\nYour previous answer had facts without a valid word-for-word quote. "
                 "Every fact needs claim, source_id and an exact quote copied from the chunk.")
    save_json({"facts": facts, "rejected": rejected}, out_path)
    return facts


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as f:
        brief = yaml.safe_load(f)
    facts = run(brief)
    print(f"{len(facts)} verified facts saved to outputs/facts.json")
    for f in facts:
        print("-", f["claim"], "|", f["source"], "p", f["page"])