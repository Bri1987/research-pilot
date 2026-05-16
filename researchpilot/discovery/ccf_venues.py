from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from typing import Any


CCF_DIRECTORY_SOURCE_URL = "https://www.ccf.org.cn/Academic_Evaluation/By_category/"
CCF_SOURCE_VERSION = "CCF 7th directory, released 2026-03-31; local seed curated from CCF pages"


@dataclass(frozen=True)
class VenueSeed:
    acronym: str
    name: str
    ccf_rank: str
    ccf_field: str
    kind: str
    domains: tuple[str, ...]
    aliases: tuple[str, ...] = ()
    homepage: str = ""
    proceedings_url: str = ""
    ccf_source_url: str = CCF_DIRECTORY_SOURCE_URL
    openreview_id_template: str | None = None
    openalex_terms: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source_version"] = CCF_SOURCE_VERSION
        return data


AI_SOURCE_URL = "https://www.ccf.org.cn/Academic_Evaluation/AI/"
SE_PL_SOURCE_URL = "https://www.ccf.org.cn/Academic_Evaluation/TCSE_SS_PDL/"
THEORY_SOURCE_URL = "https://www.ccf.org.cn/Academic_Evaluation/TCS/"
CROSS_SOURCE_URL = "https://www.ccf.org.cn/Academic_Evaluation/Cross_Compre_Emerging/"


VENUES: tuple[VenueSeed, ...] = (
    VenueSeed(
        acronym="NeurIPS",
        aliases=("NIPS",),
        name="Conference on Neural Information Processing Systems",
        ccf_rank="A",
        ccf_field="人工智能",
        kind="conference",
        domains=("ai", "machine_learning", "llm"),
        homepage="https://neurips.cc/",
        proceedings_url="https://papers.nips.cc/",
        ccf_source_url=AI_SOURCE_URL,
        openreview_id_template="NeurIPS.cc/{year}/Conference",
        openalex_terms=("NeurIPS", "Neural Information Processing Systems"),
    ),
    VenueSeed(
        acronym="ICML",
        name="International Conference on Machine Learning",
        ccf_rank="A",
        ccf_field="人工智能",
        kind="conference",
        domains=("ai", "machine_learning", "llm"),
        homepage="https://icml.cc/",
        proceedings_url="https://proceedings.mlr.press/",
        ccf_source_url=AI_SOURCE_URL,
        openreview_id_template="ICML.cc/{year}/Conference",
        openalex_terms=("ICML", "International Conference on Machine Learning"),
    ),
    VenueSeed(
        acronym="ICLR",
        name="International Conference on Learning Representations",
        ccf_rank="A",
        ccf_field="人工智能",
        kind="conference",
        domains=("ai", "machine_learning", "llm"),
        homepage="https://iclr.cc/",
        proceedings_url="https://openreview.net/group?id=ICLR.cc",
        ccf_source_url=CCF_DIRECTORY_SOURCE_URL,
        openreview_id_template="ICLR.cc/{year}/Conference",
        openalex_terms=("ICLR", "International Conference on Learning Representations"),
    ),
    VenueSeed(
        acronym="AAAI",
        name="AAAI Conference on Artificial Intelligence",
        ccf_rank="A",
        ccf_field="人工智能",
        kind="conference",
        domains=("ai", "machine_learning", "llm"),
        homepage="https://aaai.org/conference/aaai/",
        proceedings_url="https://ojs.aaai.org/index.php/AAAI",
        ccf_source_url=AI_SOURCE_URL,
        openalex_terms=("AAAI Conference on Artificial Intelligence", "AAAI"),
    ),
    VenueSeed(
        acronym="IJCAI",
        name="International Joint Conference on Artificial Intelligence",
        ccf_rank="B",
        ccf_field="人工智能",
        kind="conference",
        domains=("ai", "machine_learning"),
        homepage="https://www.ijcai.org/",
        proceedings_url="https://www.ijcai.org/proceedings/",
        ccf_source_url=AI_SOURCE_URL,
        openalex_terms=("IJCAI", "International Joint Conference on Artificial Intelligence"),
    ),
    VenueSeed(
        acronym="ACL",
        name="Annual Meeting of the Association for Computational Linguistics",
        ccf_rank="A",
        ccf_field="人工智能",
        kind="conference",
        domains=("ai", "nlp", "llm"),
        homepage="https://www.aclweb.org/",
        proceedings_url="https://aclanthology.org/events/acl-2026/",
        ccf_source_url=AI_SOURCE_URL,
        openalex_terms=("ACL", "Annual Meeting of the Association for Computational Linguistics"),
    ),
    VenueSeed(
        acronym="EMNLP",
        name="Conference on Empirical Methods in Natural Language Processing",
        ccf_rank="B",
        ccf_field="人工智能",
        kind="conference",
        domains=("ai", "nlp", "llm"),
        homepage="https://2026.emnlp.org/",
        proceedings_url="https://aclanthology.org/events/emnlp-2025/",
        ccf_source_url=AI_SOURCE_URL,
        openalex_terms=("EMNLP", "Empirical Methods in Natural Language Processing"),
    ),
    VenueSeed(
        acronym="CVPR",
        name="IEEE/CVF Computer Vision and Pattern Recognition Conference",
        ccf_rank="A",
        ccf_field="人工智能",
        kind="conference",
        domains=("ai", "computer_vision"),
        homepage="https://cvpr.thecvf.com/",
        proceedings_url="https://openaccess.thecvf.com/",
        ccf_source_url=AI_SOURCE_URL,
        openalex_terms=("CVPR", "Computer Vision and Pattern Recognition"),
    ),
    VenueSeed(
        acronym="ICCV",
        name="International Conference on Computer Vision",
        ccf_rank="A",
        ccf_field="人工智能",
        kind="conference",
        domains=("ai", "computer_vision"),
        homepage="https://iccv.thecvf.com/",
        proceedings_url="https://openaccess.thecvf.com/",
        ccf_source_url=AI_SOURCE_URL,
        openalex_terms=("ICCV", "International Conference on Computer Vision"),
    ),
    VenueSeed(
        acronym="KDD",
        name="ACM SIGKDD Conference on Knowledge Discovery and Data Mining",
        ccf_rank="A",
        ccf_field="数据库/数据挖掘/内容检索",
        kind="conference",
        domains=("ai", "data_mining"),
        homepage="https://kdd.org/",
        proceedings_url="https://dl.acm.org/conference/kdd",
        openalex_terms=("KDD", "Knowledge Discovery and Data Mining"),
    ),
    VenueSeed(
        acronym="JMLR",
        name="Journal of Machine Learning Research",
        ccf_rank="A",
        ccf_field="人工智能",
        kind="journal",
        domains=("ai", "machine_learning", "llm"),
        homepage="https://www.jmlr.org/",
        proceedings_url="https://www.jmlr.org/papers/",
        ccf_source_url=AI_SOURCE_URL,
        openalex_terms=("Journal of Machine Learning Research", "JMLR"),
    ),
    VenueSeed(
        acronym="TPAMI",
        name="IEEE Transactions on Pattern Analysis and Machine Intelligence",
        ccf_rank="A",
        ccf_field="人工智能",
        kind="journal",
        domains=("ai", "computer_vision", "machine_learning"),
        homepage="https://www.computer.org/csdl/journal/tp",
        ccf_source_url=AI_SOURCE_URL,
        openalex_terms=("IEEE Transactions on Pattern Analysis and Machine Intelligence", "TPAMI"),
    ),
    VenueSeed(
        acronym="PLDI",
        name="ACM SIGPLAN Conference on Programming Language Design and Implementation",
        ccf_rank="A",
        ccf_field="软件工程/系统软件/程序设计语言",
        kind="conference",
        domains=("formal_methods", "programming_languages", "software_engineering"),
        homepage="https://pldi.sigplan.org/",
        proceedings_url="https://dl.acm.org/conference/pldi",
        ccf_source_url=SE_PL_SOURCE_URL,
        openalex_terms=("PLDI", "Programming Language Design and Implementation"),
    ),
    VenueSeed(
        acronym="POPL",
        name="ACM SIGPLAN-SIGACT Symposium on Principles of Programming Languages",
        ccf_rank="A",
        ccf_field="软件工程/系统软件/程序设计语言",
        kind="conference",
        domains=("formal_methods", "programming_languages", "theory"),
        homepage="https://popl.sigplan.org/",
        proceedings_url="https://dl.acm.org/conference/popl",
        ccf_source_url=SE_PL_SOURCE_URL,
        openalex_terms=("POPL", "Principles of Programming Languages"),
    ),
    VenueSeed(
        acronym="OOPSLA",
        name="Object-Oriented Programming, Systems, Languages, and Applications",
        ccf_rank="A",
        ccf_field="软件工程/系统软件/程序设计语言",
        kind="conference",
        domains=("formal_methods", "programming_languages", "software_engineering"),
        homepage="https://2026.splashcon.org/track/splash-2026-oopsla",
        proceedings_url="https://dl.acm.org/conference/oopsla",
        ccf_source_url=SE_PL_SOURCE_URL,
        openalex_terms=("OOPSLA", "Object-Oriented Programming Systems Languages and Applications"),
    ),
    VenueSeed(
        acronym="FM",
        name="International Symposium on Formal Methods",
        ccf_rank="A",
        ccf_field="软件工程/系统软件/程序设计语言",
        kind="conference",
        domains=("formal_methods", "software_engineering"),
        homepage="https://formalmethods.org/",
        proceedings_url="https://dblp.org/db/conf/fm/",
        ccf_source_url=SE_PL_SOURCE_URL,
        openalex_terms=("International Symposium on Formal Methods", "Formal Methods"),
    ),
    VenueSeed(
        acronym="ICSE",
        name="International Conference on Software Engineering",
        ccf_rank="A",
        ccf_field="软件工程/系统软件/程序设计语言",
        kind="conference",
        domains=("software_engineering", "formal_methods"),
        homepage="https://conf.researchr.org/series/icse",
        proceedings_url="https://dl.acm.org/conference/icse",
        ccf_source_url=SE_PL_SOURCE_URL,
        openalex_terms=("ICSE", "International Conference on Software Engineering"),
    ),
    VenueSeed(
        acronym="FSE",
        name="ACM International Conference on the Foundations of Software Engineering",
        ccf_rank="A",
        ccf_field="软件工程/系统软件/程序设计语言",
        kind="conference",
        domains=("software_engineering", "formal_methods"),
        homepage="https://conf.researchr.org/series/fse",
        proceedings_url="https://dl.acm.org/conference/sigsoft",
        ccf_source_url=SE_PL_SOURCE_URL,
        openalex_terms=("FSE", "Foundations of Software Engineering"),
    ),
    VenueSeed(
        acronym="ASE",
        name="International Conference on Automated Software Engineering",
        ccf_rank="A",
        ccf_field="软件工程/系统软件/程序设计语言",
        kind="conference",
        domains=("software_engineering", "formal_methods"),
        homepage="https://conf.researchr.org/series/ase",
        proceedings_url="https://dl.acm.org/conference/kbse",
        ccf_source_url=SE_PL_SOURCE_URL,
        openalex_terms=("ASE", "Automated Software Engineering"),
    ),
    VenueSeed(
        acronym="ISSTA",
        name="International Symposium on Software Testing and Analysis",
        ccf_rank="A",
        ccf_field="软件工程/系统软件/程序设计语言",
        kind="conference",
        domains=("software_engineering", "formal_methods"),
        homepage="https://conf.researchr.org/series/issta",
        proceedings_url="https://dl.acm.org/conference/issta",
        ccf_source_url=SE_PL_SOURCE_URL,
        openalex_terms=("ISSTA", "Software Testing and Analysis"),
    ),
    VenueSeed(
        acronym="CAV",
        name="International Conference on Computer Aided Verification",
        ccf_rank="A",
        ccf_field="计算机科学理论",
        kind="conference",
        domains=("formal_methods", "theory"),
        homepage="https://i-cav.org/",
        proceedings_url="https://dblp.org/db/conf/cav/",
        ccf_source_url=THEORY_SOURCE_URL,
        openalex_terms=("CAV", "Computer Aided Verification"),
    ),
    VenueSeed(
        acronym="LICS",
        name="ACM/IEEE Symposium on Logic in Computer Science",
        ccf_rank="A",
        ccf_field="计算机科学理论",
        kind="conference",
        domains=("formal_methods", "theory"),
        homepage="https://lics.siglog.org/",
        proceedings_url="https://dblp.org/db/conf/lics/",
        ccf_source_url=THEORY_SOURCE_URL,
        openalex_terms=("LICS", "Logic in Computer Science"),
    ),
    VenueSeed(
        acronym="CADE",
        aliases=("IJCAR",),
        name="International Conference on Automated Deduction / International Joint Conference on Automated Reasoning",
        ccf_rank="B",
        ccf_field="计算机科学理论",
        kind="conference",
        domains=("formal_methods", "theory"),
        homepage="https://www.cadeinc.org/",
        proceedings_url="https://dblp.org/db/conf/cade/",
        ccf_source_url=THEORY_SOURCE_URL,
        openalex_terms=("CADE", "Automated Deduction", "Automated Reasoning", "IJCAR"),
    ),
    VenueSeed(
        acronym="TACAS",
        name="Tools and Algorithms for the Construction and Analysis of Systems",
        ccf_rank="B",
        ccf_field="软件工程/系统软件/程序设计语言",
        kind="conference",
        domains=("formal_methods", "software_engineering"),
        homepage="https://etaps.org/",
        proceedings_url="https://dblp.org/db/conf/tacas/",
        ccf_source_url=SE_PL_SOURCE_URL,
        openalex_terms=("TACAS", "Tools and Algorithms for the Construction and Analysis of Systems"),
    ),
    VenueSeed(
        acronym="FMCAD",
        name="Formal Methods in Computer-Aided Design",
        ccf_rank="B",
        ccf_field="软件工程/系统软件/程序设计语言",
        kind="conference",
        domains=("formal_methods", "hardware_verification"),
        homepage="https://fmcad.org/",
        proceedings_url="https://dblp.org/db/conf/fmcad/",
        ccf_source_url=SE_PL_SOURCE_URL,
        openalex_terms=("FMCAD", "Formal Methods in Computer-Aided Design"),
    ),
    VenueSeed(
        acronym="TOPLAS",
        name="ACM Transactions on Programming Languages and Systems",
        ccf_rank="A",
        ccf_field="软件工程/系统软件/程序设计语言",
        kind="journal",
        domains=("formal_methods", "programming_languages"),
        homepage="https://dl.acm.org/journal/toplas",
        ccf_source_url=SE_PL_SOURCE_URL,
        openalex_terms=("ACM Transactions on Programming Languages and Systems", "TOPLAS"),
    ),
    VenueSeed(
        acronym="PACMPL",
        aliases=("PACM PL",),
        name="Proceedings of the ACM on Programming Languages",
        ccf_rank="C",
        ccf_field="软件工程/系统软件/程序设计语言",
        kind="journal",
        domains=("formal_methods", "programming_languages"),
        homepage="https://dl.acm.org/journal/pacmpl",
        ccf_source_url=SE_PL_SOURCE_URL,
        openalex_terms=("Proceedings of the ACM on Programming Languages", "PACMPL"),
    ),
    VenueSeed(
        acronym="TSE",
        name="IEEE Transactions on Software Engineering",
        ccf_rank="A",
        ccf_field="软件工程/系统软件/程序设计语言",
        kind="journal",
        domains=("software_engineering", "formal_methods"),
        homepage="https://www.computer.org/csdl/journal/ts",
        ccf_source_url=SE_PL_SOURCE_URL,
        openalex_terms=("IEEE Transactions on Software Engineering", "TSE"),
    ),
    VenueSeed(
        acronym="TOSEM",
        name="ACM Transactions on Software Engineering and Methodology",
        ccf_rank="A",
        ccf_field="软件工程/系统软件/程序设计语言",
        kind="journal",
        domains=("software_engineering", "formal_methods"),
        homepage="https://dl.acm.org/journal/tosem",
        ccf_source_url=SE_PL_SOURCE_URL,
        openalex_terms=("ACM Transactions on Software Engineering and Methodology", "TOSEM"),
    ),
    VenueSeed(
        acronym="WWW",
        name="International World Wide Web Conference",
        ccf_rank="A",
        ccf_field="交叉/综合/新兴",
        kind="conference",
        domains=("ai", "web", "data_mining"),
        homepage="https://www2026.thewebconf.org/",
        proceedings_url="https://dl.acm.org/conference/www",
        ccf_source_url=CROSS_SOURCE_URL,
        openalex_terms=("The Web Conference", "WWW", "World Wide Web Conference"),
    ),
)


DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ai": (
        "ai",
        "artificial intelligence",
        "machine learning",
        "deep learning",
        "neural",
        "large language model",
        "llm",
        "foundation model",
        "agent",
        "reinforcement learning",
        "人工智能",
        "机器学习",
        "深度学习",
        "大模型",
        "语言模型",
        "智能体",
    ),
    "formal_methods": (
        "formal",
        "verification",
        "formal verification",
        "theorem proving",
        "proof assistant",
        "model checking",
        "program verification",
        "program analysis",
        "static analysis",
        "smt",
        "solver",
        "specification",
        "correctness",
        "formal semantics",
        "program semantics",
        "形式化",
        "形式化验证",
        "定理证明",
        "模型检测",
        "程序验证",
        "程序分析",
        "静态分析",
        "形式语义",
        "程序语义",
        "规约",
    ),
    "programming_languages": (
        "programming language",
        "compiler",
        "type system",
        "formal semantics",
        "operational semantics",
        "program synthesis",
        "程序语言",
        "编译器",
        "类型系统",
        "程序合成",
    ),
    "software_engineering": (
        "software engineering",
        "software testing",
        "program repair",
        "bug",
        "fuzzing",
        "requirements",
        "软件工程",
        "软件测试",
        "程序修复",
    ),
    "nlp": ("nlp", "natural language", "language model", "text", "自然语言"),
    "computer_vision": ("vision", "image", "video", "multimodal", "视觉", "图像", "多模态"),
    "data_mining": ("data mining", "knowledge discovery", "recommendation", "数据挖掘", "推荐"),
}


DOMAIN_EXPANSION_TERMS: dict[str, tuple[str, ...]] = {
    "ai": ("large language models", "LLM", "foundation models", "neural methods"),
    "formal_methods": ("formal verification", "theorem proving", "model checking", "program verification"),
    "programming_languages": ("programming languages", "program synthesis", "type systems"),
    "software_engineering": ("software engineering", "software testing", "program analysis"),
    "nlp": ("natural language processing", "language models"),
    "computer_vision": ("computer vision", "multimodal learning"),
    "data_mining": ("data mining", "knowledge discovery"),
}

AI_VENUE_PRIORITY = {
    "NeurIPS": 0,
    "ICML": 1,
    "ICLR": 2,
    "AAAI": 3,
    "ACL": 4,
    "CVPR": 5,
    "ICCV": 6,
    "IJCAI": 7,
}


def infer_domains(topic: str, explicit_domains: list[str] | None = None) -> list[str]:
    domains: list[str] = []
    for domain in explicit_domains or []:
        normalized = str(domain).strip().lower().replace("-", "_").replace(" ", "_")
        if normalized and normalized not in domains:
            domains.append(normalized)

    topic_lower = str(topic or "").lower()
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(keyword.lower() in topic_lower for keyword in keywords):
            if domain not in domains:
                domains.append(domain)

    if "formal_methods" in domains and "programming_languages" not in domains:
        domains.append("programming_languages")
    if "formal_methods" in domains and "software_engineering" not in domains:
        domains.append("software_engineering")
    if "llm" in topic_lower and "ai" not in domains:
        domains.append("ai")
    if not domains:
        domains.append("ai")
    return domains


def build_topic_keywords(topic: str, domains: list[str], explicit_keywords: list[str] | None = None) -> list[str]:
    keywords: list[str] = []
    for keyword in explicit_keywords or []:
        text = str(keyword).strip()
        if text and text.lower() not in {item.lower() for item in keywords}:
            keywords.append(text)

    topic_text = str(topic or "").strip()
    if topic_text:
        keywords.append(topic_text)

    for domain in domains:
        for term in DOMAIN_EXPANSION_TERMS.get(domain, ()):
            if term.lower() not in {item.lower() for item in keywords}:
                keywords.append(term)

    return keywords[:12]


def venue_tokens(venue: VenueSeed) -> set[str]:
    values = [venue.acronym, venue.name, *venue.aliases, *venue.openalex_terms]
    return {value.lower() for value in values if value}


def venue_by_acronym(acronym: str) -> VenueSeed | None:
    normalized = str(acronym or "").strip().lower()
    for venue in VENUES:
        if venue.acronym.lower() == normalized:
            return venue
        if normalized in {alias.lower() for alias in venue.aliases}:
            return venue
    return None


def rank_weight(rank: str) -> int:
    return {"A": 30, "B": 18, "C": 8}.get(str(rank).upper(), 0)


def select_venues(
    topic: str,
    domains: list[str],
    requested_venues: list[str] | None = None,
    include_journals: bool = True,
    max_venues: int = 12,
) -> list[VenueSeed]:
    requested: list[VenueSeed] = []
    for item in requested_venues or []:
        venue = venue_by_acronym(item)
        if venue is not None and venue not in requested:
            requested.append(venue)

    domain_set = set(domains)
    topic_lower = str(topic or "").lower()
    scored: list[tuple[int, str, VenueSeed]] = []
    for venue in VENUES:
        if venue.kind == "journal" and not include_journals:
            continue
        score = rank_weight(venue.ccf_rank)
        overlap = domain_set.intersection(venue.domains)
        score += len(overlap) * 25
        if any(token in topic_lower for token in venue_tokens(venue)):
            score += 40
        if "ai" in domain_set and "formal_methods" in domain_set:
            if "ai" in venue.domains:
                score += 8
            if "formal_methods" in venue.domains:
                score += 8
        if score <= 0:
            continue
        scored.append((score, venue.acronym, venue))

    scored.sort(
        key=lambda item: (
            -item[0],
            AI_VENUE_PRIORITY.get(item[2].acronym, 999) if "ai" in domain_set and "ai" in item[2].domains else 999,
            item[1],
        )
    )
    selected: list[VenueSeed] = []
    for venue in requested:
        selected.append(venue)

    quota = 3 if {"ai", "formal_methods"}.issubset(domain_set) else 2
    for domain in domains:
        domain_candidates = [
            venue
            for venue in VENUES
            if domain in venue.domains and (include_journals or venue.kind != "journal")
        ]
        if domain == "ai":
            domain_candidates.sort(
                key=lambda venue: (
                    -rank_weight(venue.ccf_rank),
                    AI_VENUE_PRIORITY.get(venue.acronym, 999),
                    venue.acronym,
                )
            )
        else:
            domain_candidates.sort(key=lambda venue: (-rank_weight(venue.ccf_rank), venue.acronym))
        added = 0
        for venue in domain_candidates:
            if venue not in selected:
                selected.append(venue)
                added += 1
            if added >= quota or len(selected) >= max_venues:
                break
        if len(selected) >= max_venues:
            break

    for _, _, venue in scored:
        if venue not in selected:
            selected.append(venue)
        if len(selected) >= max_venues:
            break

    return selected[:max_venues]


def scholar_followup_urls(topic: str, keywords: list[str], venues: list[VenueSeed], max_urls: int = 8) -> list[dict[str, str]]:
    from urllib.parse import quote_plus

    urls: list[dict[str, str]] = []
    base_terms: list[str] = []
    for term in [str(topic or "").strip(), *keywords[:4]]:
        if term and term.lower() not in {item.lower() for item in base_terms}:
            base_terms.append(term)
    base_query = " ".join(term for term in base_terms if term)
    for venue in venues[:max_urls]:
        query = f'{base_query} "{venue.acronym}" OR "{venue.name}"'
        urls.append(
            {
                "venue": venue.acronym,
                "url": f"https://scholar.google.com/scholar?q={quote_plus(query)}",
            }
        )
    return urls
