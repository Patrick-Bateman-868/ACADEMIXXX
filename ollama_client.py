"""
Ollama client for Gold Students Club.
Handles AI scraping and personalized recommendations.
"""
import json
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:7b"
OLLAMA_TIMEOUT = 60  # reduced from 90 for faster failure recovery

VALID_CATEGORIES = {
    "Engineering", "Science", "Arts", "Business", "Research",
    "Calligraphy", "Design", "Music", "Sports", "Social", "Other"
}


# ============================================
# Core Ollama communication
# ============================================

def is_ollama_available() -> bool:
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def call_ollama(prompt: str, system: str = None) -> str | None:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }
    if system:
        payload["system"] = system
    try:
        r = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=OLLAMA_TIMEOUT
        )
        r.raise_for_status()
        return r.json().get("response", "").strip()
    except Exception as e:
        print(f"[Ollama] Error: {e}")
        return None


def _extract_json(text: str) -> dict | None:
    """Extract JSON from model response, handle markdown code blocks."""
    if not text:
        return None
    # Strip markdown code fences
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try to find JSON object inside text
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


def call_ollama_json(prompt: str, system: str = None) -> dict | None:
    """Call Ollama and parse JSON response. Retries once if invalid."""
    response = call_ollama(prompt, system)
    result = _extract_json(response)
    if result is not None:
        return result
    # Retry with explicit instruction
    retry_prompt = prompt + "\n\nIMPORTANT: Your previous response was not valid JSON. Respond ONLY with a valid JSON object, no markdown, no explanation."
    response2 = call_ollama(retry_prompt, system)
    return _extract_json(response2)


# ============================================
# Scraping
# ============================================

SCRAPE_SYSTEM = (
    "You are a data extraction assistant. Extract competition and opportunity information "
    "from web page text. Always respond with valid JSON only — no markdown, no explanation. "
    "The content may be in any language (Russian, English, Kazakh, etc). "
    "Extract the information and respond with field values in the same language as the content."
)

SCRAPE_PROMPT_TEMPLATE = """Extract competition/opportunity details from the web page content below.

EXAMPLE INPUT:
"International Engineering Olympiad 2025. Open to students aged 18-25. Submit your project by June 15, 2025. Apply at https://example.com/register. Covers robotics, AI, and embedded systems."

EXAMPLE OUTPUT:
{{"title": "International Engineering Olympiad 2025", "description": "An international competition covering robotics, AI, and embedded systems for university students.", "requirements": "Students aged 18–25", "category": "Engineering", "deadline": "15.06.2025", "registration_link": "https://example.com/register"}}

---

Now extract these fields from the content:
- title: name of the competition or opportunity (string)
- description: what it is about, max 3 sentences (string)
- requirements: who can apply / eligibility criteria (string, or null if not found)
- category: choose ONE from this list:
    Engineering (техника, IT, программирование, робототехника)
    Science (наука, исследования, физика, химия, биология)
    Arts (искусство, творчество, живопись, фотография)
    Business (бизнес, стартап, предпринимательство, экономика)
    Research (научная работа, гранты, академические исследования)
    Calligraphy (каллиграфия, почерк, шрифт)
    Design (дизайн, UI/UX, графика, архитектура)
    Music (музыка, вокал, инструменты, конкурс исполнителей)
    Sports (спорт, физкультура, соревнования)
    Social (волонтёрство, социальные проекты, НКО)
    Other (всё остальное)
- deadline: application deadline as text, e.g. "31.05.2025", "31 May 2025", "до 30 мая", "May 30" (string, or null if not found)
  Look for phrases like: "deadline", "срок подачи", "до", "дедлайн", "подать до", "apply by", "closes on"
- registration_link: full URL to apply or register (string starting with http/https, or null if not found)

Respond ONLY with this JSON structure:
{{
  "title": "...",
  "description": "...",
  "requirements": "...",
  "category": "...",
  "deadline": "...",
  "registration_link": "..."
}}

Web page content:
{content}"""


def _strip_html(html: str) -> str:
    """Strip HTML to plain text. Prioritizes semantic content tags."""
    soup = BeautifulSoup(html, "html.parser")
    # Remove script/style noise
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    # Prioritize semantic content containers
    for tag_name in ("main", "article", "section"):
        node = soup.find(tag_name)
        if node:
            text = re.sub(r"\s+", " ", node.get_text(" ", strip=True))
            if len(text) > 300:
                return text[:2000]
    # Fallback: entire body
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    return text[:2000]


def scrape_url(url: str) -> dict | None:
    """Fetch URL, strip HTML, send to Ollama, return extracted dict or None."""
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        content = _strip_html(r.text)
    except Exception as e:
        print(f"[Scraper] Failed to fetch {url}: {e}")
        return None

    prompt = SCRAPE_PROMPT_TEMPLATE.format(content=content)
    data = call_ollama_json(prompt, SCRAPE_SYSTEM)
    if not data:
        print(f"[Scraper] No JSON from Ollama for {url}")
        return None
    if not data.get("title"):
        print(f"[Scraper] Missing title in response for {url}")
        return None
    return data


def run_scraping_job(db, Opportunity, ScrapingTarget) -> dict:
    """
    Run scraping for all active ScrapingTarget entries.
    Returns {"created": N, "skipped": N, "errors": [...]}.
    Must be called inside a Flask app context.
    Pass db, Opportunity, ScrapingTarget explicitly to avoid circular imports.
    """
    targets = ScrapingTarget.query.filter_by(is_active=True).all()
    created, skipped, errors = 0, 0, []

    for target in targets:
        try:
            data = scrape_url(target.url)
            if not data:
                errors.append(f"{target.name}: Ollama не вернул данные")
                continue

            title = data.get("title", "").strip()
            if not title:
                errors.append(f"{target.name}: нет названия")
                continue

            # Deduplication by title
            if Opportunity.query.filter_by(title=title).first():
                skipped += 1
                continue

            # Validate category against whitelist
            category = data.get("category", "").strip()
            if category not in VALID_CATEGORIES:
                category = "Other"

            reg_link = data.get("registration_link") or None
            # Validate registration_link
            if reg_link and not reg_link.startswith(("http://", "https://")):
                reg_link = None

            op = Opportunity(
                title=title,
                description=data.get("description") or None,
                requirements=data.get("requirements") or None,
                category=category,
                deadline=data.get("deadline") or None,
                registration_link=reg_link,
                source=target.name,
                verified=False,
                ai_scraped=True,
            )
            db.session.add(op)
            target.last_scraped = datetime.utcnow()
            # Commit immediately after each target — keeps write-lock duration minimal
            db.session.commit()
            created += 1

        except Exception as e:
            # Always rollback on error so session stays clean for next iteration
            db.session.rollback()
            errors.append(f"{target.name}: {str(e)}")

    return {"created": created, "skipped": skipped, "errors": errors}


# ============================================
# Recommendations
# ============================================

RECOMMEND_SYSTEM = (
    "You are a student opportunity recommender. "
    "Given a student profile and a list of opportunities, select the most relevant ones. "
    "Respond ONLY with valid JSON — no markdown, no explanation."
)

RECOMMEND_PROMPT_TEMPLATE = """Student profile:
- Skills: {skills}
- Goals: {goals}
- Interests: {interests}

Available opportunities (format: id | title | category):
{opportunities_list}

Select up to 6 opportunities most relevant to this student.
Respond ONLY with this JSON:
{{
  "recommendations": [
    {{"id": <number>, "score": <0.0-1.0>, "explanation": "<1 sentence why>"}},
    ...
  ]
}}"""


def get_recommendations_for_user(user, db, Opportunity, Recommendation, force_refresh: bool = False):
    """
    Returns list of (Opportunity, explanation) tuples for the user.
    Uses DB cache (24h TTL). Returns [] if profile is empty or Ollama unavailable.
    Pass db, Opportunity, Recommendation explicitly to avoid circular imports.
    """
    from datetime import timedelta

    # If profile is empty — no point calling Ollama
    profile_text = " ".join(filter(None, [user.skills, user.goals, user.interests]))
    if not profile_text.strip():
        return []

    # Check cache
    if not force_refresh:
        cached = Recommendation.query.filter_by(user_id=user.id).first()
        if cached:
            age = datetime.utcnow() - cached.created_at
            if age < timedelta(hours=24):
                recs = (
                    Recommendation.query
                    .filter_by(user_id=user.id)
                    .order_by(Recommendation.score.desc())
                    .all()
                )
                result = []
                for rec in recs:
                    op = Opportunity.query.get(rec.opportunity_id)
                    if op and op.verified:
                        result.append((op, rec.explanation))
                if result:
                    return result

    if not is_ollama_available():
        return None  # Signal: Ollama unavailable (different from empty profile)

    # Build list of verified opportunities (max 30)
    opportunities = (
        Opportunity.query
        .filter_by(verified=True)
        .order_by(Opportunity.created_at.desc())
        .limit(30)
        .all()
    )
    if not opportunities:
        return []

    opp_lines = "\n".join(
        f"{op.id} | {op.title} | {op.category or 'Other'}"
        for op in opportunities
    )
    prompt = RECOMMEND_PROMPT_TEMPLATE.format(
        skills=user.skills or "не указаны",
        goals=user.goals or "не указаны",
        interests=user.interests or "не указаны",
        opportunities_list=opp_lines,
    )

    data = call_ollama_json(prompt, RECOMMEND_SYSTEM)
    if not data or "recommendations" not in data:
        return []

    # Clear old cache
    Recommendation.query.filter_by(user_id=user.id).delete()

    result = []
    op_map = {op.id: op for op in opportunities}
    now = datetime.utcnow()

    for item in data["recommendations"]:
        try:
            op_id = int(item["id"])
            score = float(item.get("score", 0.5))
            explanation = str(item.get("explanation", ""))
        except (KeyError, ValueError, TypeError):
            continue
        op = op_map.get(op_id)
        if not op:
            continue
        rec = Recommendation(
            user_id=user.id,
            opportunity_id=op_id,
            score=score,
            explanation=explanation,
            created_at=now,
        )
        db.session.add(rec)
        result.append((op, explanation))

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[Recommendations] DB error: {e}")

    return result
