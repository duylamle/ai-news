"""Rule-based first-pass classification for entries.

Adds fields: types, topics, audiences, importance, relevance, tags, quality, source_org.

This is the deterministic part. Routine agent (Haiku) overrides for top-tier articles.

Usage:
    cat fetched.json | python scripts/classify.py --sources sources.json > classified.json
"""

import argparse
import io
import json
import re
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# Source ID prefix → org display name (for classification.source_org)
SOURCE_ORG_MAP = {
    "anthropic-news": "Anthropic",
    "openai-blog": "OpenAI",
    "deepmind-blog": "Google DeepMind",
    "mistral-news": "Mistral AI",
    "cohere-blog": "Cohere",
    "meta-fair": "Meta AI",
    "ms-research": "Microsoft Research",
    "together-ai": "Together AI",
    "huggingface-blog": "Hugging Face",
    "arxiv-cs-ai": "arXiv",
    "arxiv-cs-cl": "arXiv",
    "arxiv-cs-lg": "arXiv",
    "hf-daily-papers": "Hugging Face",
    "alphaxiv": "alphaXiv",
    "papers-with-code": "Papers with Code",
    "bair-blog": "Berkeley BAIR",
    "the-gradient": "The Gradient",
    "import-ai": "Import AI",
    "the-batch": "DeepLearning.AI",
    "mit-tech-review": "MIT Tech Review",
    "tldr-ai": "TLDR",
    "bens-bites": "Ben's Bites",
    "simon-willison": "Simon Willison",
    "sebastian-raschka": "Sebastian Raschka",
    "eugene-yan": "Eugene Yan",
    "hamel-husain": "Hamel Husain",
    "latent-space": "Latent Space",
    "addy-osmani": "Addy Osmani",
    "mitchell-hashimoto": "Mitchell Hashimoto",
    "karpathy-blog": "Andrej Karpathy",
    "pete-koomen": "Pete Koomen",
    "a16z-ai": "Andreessen Horowitz",
    "lenny-newsletter": "Lenny's Newsletter",
    "theory-vc": "Theory Ventures",
    "sequoia-ai": "Sequoia Capital",
    "lesswrong-ai": "LessWrong",
    "alignment-forum": "Alignment Forum",
    "fli-safety": "Future of Life Institute",
    "fpt-ai": "FPT.AI",
    "vinai": "VinAI",
    "good-ai-list": "Good AI List",
    "goon-nguyen": "Goon Nguyễn",
    "ml-mastery": "ML Mastery",
    "kdnuggets": "KDnuggets",
    "marktechpost": "MarkTechPost",
    "mit-news-ai": "MIT News",
    "bdtechtalks": "TechTalks",
    "one-useful-thing": "Ethan Mollick",
    "cerebras": "Cerebras",
    "aws-ml": "AWS",
    "apple-ml": "Apple ML",
    "google-research": "Google Research",
    "analytics-vidhya": "Analytics Vidhya",
    "nvidia-ai": "NVIDIA",
    "salesforce-ai": "Salesforce AI",
    "venturebeat-ai": "VentureBeat",
    "wired-ai": "Wired",
    "techcrunch-ai": "TechCrunch",
    "theverge-ai": "The Verge",
    "last-week-in-ai": "Last Week in AI",
    "neuron": "The Neuron",
    "langchain": "LangChain",
    "lex-fridman": "Lex Fridman",
}


# Unified TYPE taxonomy (replaces both old Quality + Type axes)
# Single dimension Lam filters on. 9 values, multi-label allowed.
#
# Priority order when multi-match:
#   1. Source-based (research-published / research-draft / newsletter) — deterministic
#   2. Content keyword (release / tutorial / essay / news) — multi-label
#   3. Fallback by source quality (company-blog / personal-blog) — single-label

TYPE_PATTERNS = {
    "release": [r"\b(introducing|announcing|launching|now available|generally available|releasing)\b",
                r"\b(claude|gpt|gemini|llama|mistral|opus|sonnet|haiku)[\s-]?\d",
                r"\b(beta|preview|public release|new feature|new model)\b"],
    "tutorial": [r"\b(how to|tutorial|guide|step-by-step|walkthrough|getting started|building a|build your own)\b"],
    "essay": [r"\b(thoughts on|reflections|why we|opinion|perspective|i think|my take)\b",
              r"\b(deep dive|long-form)\b"],
    "news": [r"\b(today|announces|unveiled|reports?|breaking|update)\b"],
}

# Source quality → fallback type (when no content keyword match)
QUALITY_TO_TYPE = {
    "peer-reviewed": "research-published",
    "preprint": "research-draft",
    "curated-newsletter": "newsletter",
    "lab-official": "company-blog",
    "corporate-blog": "company-blog",
    "personal-blog": "personal-blog",
    "vendor-blog": "company-blog",
    "aggregator": "newsletter",
    "community-forum": "personal-blog",
}

# Topic keywords
TOPIC_PATTERNS = {
    "llm": [r"\b(llm|large language model|gpt|claude|gemini|llama|mistral|opus|sonnet|haiku)\b"],
    "agents": [r"\b(agent|agentic|autonomous|workflow|tool[- ]use|multi[- ]agent)\b"],
    "multimodal": [r"\b(multimodal|vision|image|video|audio|voice|tts|asr|speech)\b"],
    "rag": [r"\b(rag|retrieval[- ]augmented|vector|embedding|semantic search)\b"],
    "fine-tuning": [r"\b(fine[- ]?tun|lora|peft|sft|rlhf|dpo|adapt|instruct[- ]?tun)\b"],
    "inference": [r"\b(inference|serving|latency|throughput|deploy|quantiz|distill)\b"],
    "evaluation": [r"\b(eval|benchmark|metric|measur|leaderboard|test set)\b"],
    "safety": [r"\b(safety|alignment|red[- ]?team|jailbreak|harm|bias|fairness)\b"],
    "reasoning": [r"\b(reason|chain[- ]of[- ]thought|cot|thinking|step[- ]by[- ]step|o1|o3)\b"],
    "coding-ai": [r"\b(code|coding|programming|developer|claude code|cursor|copilot|aider|devin)\b"],
    "infrastructure": [r"\b(gpu|tpu|cluster|training compute|h100|h200|datacenter|hardware)\b"],
    "data": [r"\b(dataset|synthetic data|data quality|annotation|labeling|crawl)\b"],
}

def find_matches(text: str, patterns: dict) -> list[str]:
    text_l = text.lower()
    out = []
    for label, pats in patterns.items():
        for p in pats:
            if re.search(p, text_l, re.IGNORECASE):
                out.append(label)
                break
    return out


def extract_tags(text: str, max_tags: int = 4) -> list[str]:
    text_l = text.lower()
    tag_keywords = [
        ("claude", r"\bclaude\b"),
        ("gpt", r"\bgpt\b"),
        ("gemini", r"\bgemini\b"),
        ("llama", r"\bllama\b"),
        ("mistral", r"\bmistral\b"),
        ("agents", r"\bagent"),
        ("rag", r"\brag\b"),
        ("fine-tuning", r"\bfine[- ]?tun"),
        ("safety", r"\b(safety|alignment)\b"),
        ("multimodal", r"\b(multimodal|vision)\b"),
        ("open-source", r"\bopen[- ]source\b"),
        ("benchmark", r"\bbenchmark\b"),
        ("tutorial", r"\btutorial\b"),
        ("paper", r"\bpaper\b"),
        ("reasoning", r"\breason"),
        ("coding-ai", r"\b(claude code|cursor|copilot|aider)\b"),
    ]
    out = []
    for tag, pat in tag_keywords:
        if re.search(pat, text_l):
            out.append(tag)
        if len(out) >= max_tags:
            break
    return out


def determine_importance(entry: dict, source_quality: str) -> str:
    """Agent never sets must-read — Lam stars manually.

    worth-reading: liên quan AI x product/engineering practical
    skim: academic theory thuần, math-heavy, infrastructure deep
    """
    text = f"{entry.get('title','')} {entry.get('excerpt','')}".lower()

    # Product / engineering practical signals → worth-reading
    practical_signals = [
        r"\b(claude code|cursor|copilot|aider|devin)\b",  # AI coding tools
        r"\b(agent|agentic|workflow|tool[- ]use|automation)\b",
        r"\b(rag|retrieval[- ]augmented|memory)\b",
        r"\b(introducing|announcing|releasing|launching|now available)\b",  # product launches
        r"\b(model release|new model|generally available)\b",
        r"\b(prompt|prompting|context window|token)\b",
        r"\b(use case|workflow|deploy|integration|api|sdk)\b",
        r"\b(productivity|developer experience|ux|ui)\b",
        r"\b(eval|evaluation|benchmark|metric)\b",
        r"\b(safety|alignment|red[- ]?team)\b",  # relevant for product safety
        r"\b(open[- ]source|llama|mistral|claude|gpt|gemini)\b",
    ]
    for pat in practical_signals:
        if re.search(pat, text, re.IGNORECASE):
            return "worth-reading"

    # Academic theory / math-heavy / infrastructure deep → skim
    theory_signals = [
        r"\b(theorem|lemma|proof|equation|gradient|hessian)\b",
        r"\b(architecture details|kernel|cuda|hbm|memory bandwidth)\b",
        r"\b(formal|formalization|mathematical|statistical)\b",
    ]
    for pat in theory_signals:
        if re.search(pat, text, re.IGNORECASE):
            return "skim"

    # Default: skim cho mọi thứ không match (an toàn — Lam tự đánh sao must-read)
    return "skim"


def detect_language(text: str) -> str:
    """Heuristic: detect Vietnamese vs English from diacritic density."""
    if not text:
        return "en"
    vn_chars = "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ"
    vn_chars_upper = vn_chars.upper()
    vn_count = sum(1 for c in text if c in vn_chars or c in vn_chars_upper)
    # >2% diacritic chars → Vietnamese
    if vn_count / max(len(text), 1) > 0.02:
        return "vi"
    return "en"


def classify_entry(entry: dict, source_meta: dict, source_id: str) -> dict:
    text = f"{entry.get('title','')} {entry.get('excerpt','')}"
    quality = source_meta.get("quality", "aggregator")

    # Build unified types (multi-label):
    # 1. Always include source-based type (research-published/draft/newsletter/company/personal-blog)
    # 2. Plus content keywords if matched
    types = []
    source_type = QUALITY_TO_TYPE.get(quality, "company-blog")
    types.append(source_type)

    content_types = find_matches(text, TYPE_PATTERNS)
    for t in content_types:
        if t not in types:
            types.append(t)

    topics = find_matches(text, TOPIC_PATTERNS)
    language = detect_language(text)

    return {
        **entry,
        "source_org": SOURCE_ORG_MAP.get(source_id, source_id),
        "source_name": source_meta.get("name", source_id),
        "types": types,
        "topics": topics,
        "language": language,
        "importance": determine_importance(entry, quality),
        "tags": extract_tags(text),
        "excerpt_vn": entry.get("excerpt_vn") or entry.get("excerpt", ""),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", default="sources.json")
    ap.add_argument("--input", help="JSON file (default: stdin)")
    args = ap.parse_args()

    sources = json.loads(Path(args.sources).read_text(encoding="utf-8")).get("sources", {})

    if args.input:
        entries = json.loads(Path(args.input).read_text(encoding="utf-8"))
    else:
        entries = json.loads(sys.stdin.read())

    classified = []
    for e in entries:
        sid = e.get("source")
        meta = sources.get(sid, {})
        classified.append(classify_entry(e, meta, sid))

    print(json.dumps(classified, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
