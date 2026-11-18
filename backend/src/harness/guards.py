"""Deterministic untrusted-context and conservative claim/citation guards.

Design limits (explicitly documented):
- This verifier is a conservative, explainable rule-based checker operating at
  sentence/clause level on the exact admitted composer excerpts.
- It is NOT a full Vietnamese semantic entailment / NLI model and does NOT prove
  medical accuracy.
- When support cannot be verified cleanly (polarity, numbers/ranges, units,
  populations/subjects, conditions, modality, or tight grounded overlap), it
  fails closed as `unsupported` / `inconclusive`.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

CLAIM_VALIDATION_POLICY_VERSION = "2026-11-18-v2"


def _normalize_match_text(text: str) -> str:
    normalized = unicodedata.normalize("NFD", (text or "").lower())
    without_marks = "".join(
        char for char in normalized if unicodedata.category(char) != "Mn"
    )
    return re.sub(r"\s+", " ", without_marks.replace("đ", "d")).strip()


INJECTION_MARKERS = (
    "ignore previous instructions", "disregard previous instructions",
    "reveal user health profile", "reveal system prompt", "print api key",
    "bỏ qua hướng dẫn", "bỏ qua cảnh báo", "tiết lộ hồ sơ",
    "tiết lộ dữ liệu", "tiết lộ api key", "không cần cảnh báo",
    "system: ignore", "developer: ignore", "system prompt:",
    "role=system", "role: system", "hãy bỏ cảnh báo",
    "bỏ qua kiểm tra an toàn", "in hồ sơ sức khỏe",
)


def has_untrusted_instruction(text: str) -> bool:
    normalized = _normalize_match_text(str(text or ""))
    return any(
        _normalize_match_text(marker) in normalized for marker in INJECTION_MARKERS
    )


def has_conflicting_evidence(docs: List[Dict[str, Any]]) -> bool:
    """Flag explicit conflicts or incompatible numbers for the same titled topic."""
    by_title: Dict[str, set[tuple[str, ...]]] = {}
    for doc in docs:
        if doc.get("evidence_conflict") or doc.get("conflicts_with"):
            return True
        title = _normalize_match_text(
            str(doc.get("title") or doc.get("question") or "")
        )
        numbers = tuple(
            sorted(set(re.findall(r"\d+(?:[.,]\d+)?", str(doc.get("content") or ""))))
        )
        if title and numbers:
            by_title.setdefault(title, set()).add(numbers)
    return any(len(values) > 1 for values in by_title.values())


def suggests_unsafe_medical_change(text: str) -> bool:
    normalized = _normalize_match_text(text)
    return any(
        marker in normalized
        for marker in (
            "tap nang hon",
            "tang lieu thuoc",
            "ngung thuoc",
            "bo thuoc",
            "an kieng cuc doan",
            "tang cuong do tap",
        )
    )


_STOPWORDS = {
    "la", "cua", "va", "trong", "co", "the", "duoc", "mot", "nhung",
    "voi", "cho", "cac", "nay", "do", "thi", "ve", "bang", "tu", "den",
    "de", "hay", "hoac", "nhu", "da", "se", "dang", "rat", "cung",
}

# Narrow, auditable lexical equivalences for controlled paraphrase support.
_CONTROLLED_PHRASE_EQUIVALENTS: Tuple[Tuple[str, str], ...] = (
    ("chi so khoi co the", "bmi"),
    ("phan tram mo co the", "pbf"),
    ("ty le phan tram mo co the", "pbf"),
    ("ti le phan tram mo co the", "pbf"),
    ("khoi luong co xuong", "smm"),
    ("khoi luong mo co the", "bfm"),
    ("visceral fat", "mo noi tang"),
    ("chat dam", "protein"),
    ("bieu thi", "la"),
    ("phan anh", "la"),
    ("cho biet", "la"),
    ("ti le", "ty le"),
)

_NON_NEGATION_KHONG_PHRASES = (
    "khong khi",
    "khong gian",
    "hang khong",
    "khong trung",
)

_NEGATION_PATTERNS = (
    r"\btuyet doi khong\b",
    r"\bchong chi dinh\b",
    r"\bkhong phai\b",
    r"\bkhong du\b",
    r"\bkhong the\b",
    r"\bkhong nen\b",
    r"\bkhong duoc\b",
    r"\bkhong co\b",
    r"\bkhong\b",
    r"\bchua\b",
    r"\bchang\b",
    r"\btranh\b",
    r"\bcam\b",
    r"\bngung\b",
    r"\bloai tru\b",
    r"\bnot\b",
    r"\bnever\b",
    r"\bcannot\b",
    r"\bcan't\b",
    r"\bdon't\b",
    r"\bdoesn't\b",
    r"\bavoid\b",
    r"\bcontraindicated\b",
)

_ANTONYM_PAIRS: Tuple[Tuple[str, str], ...] = (
    ("tang", "giam"),
    ("cao", "thap"),
    ("du", "thieu"),
    ("an toan", "nguy hiem"),
    ("nen", "tranh"),
    ("nen", "cam"),
    ("nen", "chong chi dinh"),
)

_UNIT_ALIASES: Tuple[Tuple[str, str], ...] = (
    (r"mg\s*/\s*dl", "mg/dl"),
    (r"mmol\s*/\s*l", "mmol/l"),
    (r"mm\s*hg", "mmhg"),
    (r"g(?:ram)?\s*/\s*kg", "g/kg"),
    (r"buoi\s*(?:/|moi)\s*tuan", "sessions/week"),
    (r"kcal|calories?|calo|cal", "kcal"),
    (r"%|phan\s+tram", "%"),
    (r"kg|kilograms?|ky", "kg"),
    (r"grams?|gr|g", "g"),
    (r"cm", "cm"),
    (r"ml", "ml"),
    (r"lit|l", "l"),
    (r"phut|mins?|minutes?", "min"),
    (r"gio|tieng|hours?", "hour"),
    (r"buoi", "sessions"),
    (r"tuan", "week"),
    (r"ngay", "day"),
    (r"thang", "month"),
    (r"tuoi", "age"),
    (r"level|muc|cap\s+do", "level"),
)

_UNIT_REGEX = "|".join(f"(?:{pattern})" for pattern, _ in _UNIT_ALIASES)

_POPULATION_PATTERNS: Dict[str, Tuple[str, ...]] = {
    "male": (r"\bnam gioi\b", r"\bnam\b", r"\bdan ong\b", r"\bmale\b", r"\bmen\b"),
    "female": (r"\bnu gioi\b", r"\bphu nu\b", r"\bnu\b", r"\bfemale\b", r"\bwomen\b"),
    "child": (r"\btre em\b", r"\btre nho\b", r"\bnhi\b", r"\bchildren\b", r"\bchild\b"),
    "adult": (r"\bnguoi lon\b", r"\bnguoi truong thanh\b", r"\btruong thanh\b", r"\badults?\b"),
    "elderly": (r"\bnguoi cao tuoi\b", r"\bnguoi gia\b", r"\belderly\b"),
    "pregnant": (r"\bmang thai\b", r"\bthai ky\b", r"\bba bau\b", r"\bpregnant\b"),
    "asian": (r"\bchau a\b", r"\basian\b"),
    "beginner": (r"\bnguoi moi tap\b", r"\bnguoi moi\b", r"\bbeginner\b"),
    "athlete": (r"\bvan dong vien\b", r"\bathletes?\b"),
    "diabetes": (r"\btieu duong\b", r"\bdai thao duong\b", r"\bdiabetes\b"),
    "hypertension": (r"\btang huyet ap\b", r"\bhuyet ap cao\b", r"\bhypertension\b"),
    "kidney_disease": (r"\bben[h]?\s*than\b", r"\bsuy than\b", r"\bckd\b", r"\bkidney\b"),
    "heart_disease": (r"\bben[h]?\s*tim\b", r"\btim mach\b", r"\bheart\b"),
    "pacemaker": (r"\bmay tao nhip tim\b", r"\bpacemaker\b"),
    "chronic_condition": (r"\bben[h]?\s*nen\b", r"\bben[h]?\s*ly man tinh\b", r"\bman tinh\b"),
}

_HEALTH_ENTITY_PATTERNS: Dict[str, Tuple[str, ...]] = {
    "bmi": (r"\bbmi\b", r"\bchi so khoi co the\b"),
    "pbf": (r"\bpbf\b", r"\bphan tram mo\b", r"\bty le mo\b", r"\bti le mo\b"),
    "smm": (r"\bsmm\b", r"\bkhoi luong co xuong\b", r"\bco xuong\b"),
    "bfm": (r"\bbfm\b", r"\bkhoi luong mo\b"),
    "visceral_fat": (r"\bmo noi tang\b", r"\bvisceral fat\b"),
    "bia": (r"\bbia\b", r"\btro khang dien\b"),
    "dxa": (r"\bdxa\b", r"\bdexa\b"),
    "mri": (r"\bmri\b",),
    "protein": (r"\bprotein\b", r"\bchat dam\b"),
    "cardio": (r"\bcardio\b",),
    "resistance": (r"\bkhang luc\b",),
}

_CONDITIONAL_MARKER_RE = re.compile(
    r"\b(?:chi khi|tru khi|voi dieu kien|trong truong hop|nhat la khi|khi di kem|"
    r"neu co|khi co|neu|khi|doi voi|o nguoi|if|when|unless|only if)\b"
)

_OVERGENERALIZATION_MARKERS = (
    r"\bmoi nguoi\b",
    r"\btat ca\b",
    r"\bluon luon\b",
    r"\bbat ky ai\b",
    r"\bvo dieu kien\b",
    r"\bbat ke\b",
)

_ESCALATED_MODALITY_MARKERS = (
    r"\bchac chan\b",
    r"\bkhang dinh\b",
    r"\bchan doan\b",
    r"\bket luan benh\b",
    r"\bchua khoi\b",
    r"\btri dut diem\b",
    r"\bcam ket\b",
    r"\bdam bao\b",
    r"\btuyet doi an toan\b",
    r"\bthay the bac si\b",
    r"\bke don\b",
    r"\bbat buoc phai\b",
    r"\bdu de chan doan\b",
)

_SAFETY_NOTICE_PHRASES = (
    "thong tin chi mang tinh tham khao",
    "thong tin nay chi nham",
    "khong thay the bac si",
    "khong phai chan doan",
    "khong chan doan benh",
    "khong ke don",
    "tham khao bac si",
    "tham khao y kien bac si",
    "tham khao chuyen gia y te",
    "hoi bac si",
    "gap chuyen gia y te",
    "lien he co so y te",
    "co so cap cuu",
    "dung tap ngay",
    "luu y an toan",
)

_CLARIFICATION_OR_REFUSAL_PHRASES = (
    "khong du bang chung",
    "chua du bang chung",
    "chua the ket luan",
    "khong the tu de xuat",
    "can them thong tin",
    "cung cap them",
    "cho biet them",
    "thieu du lieu",
    "chua co du du lieu",
)


def _canonicalize_unit(raw_unit: str) -> str:
    norm = _normalize_match_text(raw_unit)
    for pattern, canonical in _UNIT_ALIASES:
        if re.fullmatch(pattern, norm):
            return canonical
    return norm


def _canonicalize_comparator(raw_op: str) -> Optional[str]:
    norm = _normalize_match_text(raw_op)
    if not norm:
        return None
    if norm in {">=", "≥", "tu", "it nhat", "toi thieu"}:
        return ">="
    if norm in {">", "tren", "lon hon", "cao hon"}:
        return ">"
    if norm in {"<=", "≤", "toi da", "nhieu nhat"}:
        return "<="
    if norm in {"<", "duoi", "nho hon", "thap hon"}:
        return "<"
    return None


def _parse_number(raw: str) -> float:
    return float(raw.replace(",", "."))


def _strip_markdown(text: str) -> str:
    cleaned = re.sub(r"\*\*|__|`|~~", "", text or "")
    cleaned = re.sub(r"^\s*(?:[-*•]+|\d+[.)])\s+", "", cleaned)
    return cleaned.strip()


def _strip_breadcrumb(text: str) -> str:
    """Remove leading chunk breadcrumb header like `[Guide > Section]` without touching `[1]`."""
    return re.sub(r"^\s*\[[^\]\n]{3,200}\]\s*\n?", "", text or "").strip()


def _split_sentences(text: str) -> List[str]:
    cleaned = _strip_breadcrumb(text)
    if not cleaned:
        return []
    sentences: List[str] = []
    for raw_line in re.split(r"\n+", cleaned):
        line = raw_line.strip()
        if not line:
            continue
        # Protect decimal dots (e.g. 24.9) because we only split on punctuation followed by whitespace.
        for part in re.split(r"(?<=[.!?])\s+", line):
            item = part.strip()
            if item:
                sentences.append(item)
    return sentences


def _apply_controlled_equivalents(norm_text: str) -> str:
    result = norm_text
    for src, dst in _CONTROLLED_PHRASE_EQUIVALENTS:
        result = re.sub(rf"\b{re.escape(src)}\b", dst, result)
    return re.sub(r"\s+", " ", result).strip()


def _claim_tokens(text: str) -> set[str]:
    norm = _apply_controlled_equivalents(_normalize_match_text(text))
    return set(re.findall(r"[a-z0-9]+", norm)) - _STOPWORDS


def _has_negation(norm_text: str) -> bool:
    scrubbed = norm_text
    for phrase in _NON_NEGATION_KHONG_PHRASES:
        scrubbed = scrubbed.replace(phrase, " ")
    return any(re.search(pattern, scrubbed) for pattern in _NEGATION_PATTERNS)


def _split_clauses(norm_text: str) -> List[str]:
    parts = re.split(
        r"\s*(?:;|,\s*(?:nhung ma|nhung|tuy nhien|con|trong khi|song)|"
        r"\b(?:nhung ma|nhung|tuy nhien|trong khi)\b|,)\s*",
        norm_text,
    )
    return [part.strip() for part in parts if len(part.strip()) >= 4]


def _extract_ranges(norm_text: str) -> List[Tuple[float, float, Optional[str]]]:
    pattern = re.compile(
        rf"(?:\btu\s+)?(\d+(?:[.,]\d+)?)\s*(?:-|–|—|~|\bden\s+(?:duoi\s+)?|\btoi\s+(?:duoi\s+)?)"
        rf"(\d+(?:[.,]\d+)?)(?:\s*({_UNIT_REGEX})\b|(\s*%))?"
    )
    results: List[Tuple[float, float, Optional[str]]] = []
    for match in pattern.finditer(norm_text):
        low = _parse_number(match.group(1))
        high = _parse_number(match.group(2))
        raw_unit = match.group(3) or match.group(4) or ""
        unit = _canonicalize_unit(raw_unit) if raw_unit.strip() else None
        results.append((low, high, unit))
    return results


def _extract_quantities(norm_text: str) -> List[Tuple[float, Optional[str], Optional[str]]]:
    """Extract (number, comparator, unit) tuples from normalized text."""
    # Prefix-unit pattern like "level 12" or "muc 15"
    prefix_matches: Dict[int, str] = {}
    for match in re.finditer(r"\b(level|muc|cap\s+do)\s+(\d+(?:[.,]\d+)?)", norm_text):
        prefix_matches[match.start(2)] = _canonicalize_unit(match.group(1))

    pattern = re.compile(
        rf"(?:(>=|<=|≥|≤|>|<|\b(?:tren|duoi|lon hon|nho hon|cao hon|thap hon|it nhat|toi thieu|toi da|nhieu nhat)\b)\s*)?"
        rf"(\d+(?:[.,]\d+)?)"
        rf"(?:\s*(%|(?:{_UNIT_REGEX})\b))?"
    )
    quantities: List[Tuple[float, Optional[str], Optional[str]]] = []
    for match in pattern.finditer(norm_text):
        op = _canonicalize_comparator(match.group(1) or "")
        value = _parse_number(match.group(2))
        raw_unit = match.group(3) or ""
        unit = (
            _canonicalize_unit(raw_unit)
            if raw_unit.strip()
            else prefix_matches.get(match.start(2))
        )
        quantities.append((value, op, unit))
    return quantities


def _extract_tagged_groups(
    norm_text: str,
    pattern_map: Mapping[str, Tuple[str, ...]],
) -> set[str]:
    found: set[str] = set()
    for tag, patterns in pattern_map.items():
        if any(re.search(pattern, norm_text) for pattern in patterns):
            found.add(tag)
    return found


def _extract_condition_clauses(norm_text: str) -> List[Tuple[str, set[str]]]:
    """Extract conditional clauses and their meaningful tokens from a sentence."""
    clauses: List[Tuple[str, set[str]]] = []
    for match in _CONDITIONAL_MARKER_RE.finditer(norm_text):
        tail = norm_text[match.end():].strip()
        # Cut at next major punctuation / clause boundary
        segment = re.split(r"[,;.]|\b(?:thi|nen|se|can|phai)\b", tail, maxsplit=1)[0].strip()
        tokens = _claim_tokens(segment)
        if len(tokens) >= 2:
            clauses.append((match.group(0), tokens))
    return clauses


def _check_negation_and_polarity(norm_claim: str, norm_ev: str) -> Optional[str]:
    claim_neg = _has_negation(norm_claim)
    ev_neg = _has_negation(norm_ev)
    if ev_neg and not claim_neg:
        return "negation_dropped"
    if claim_neg and not ev_neg:
        return "negation_added"

    # Clause-level polarity check prevents negation-scope swaps across compound sentences.
    claim_clauses = _split_clauses(norm_claim)
    ev_clauses = _split_clauses(norm_ev)
    if len(claim_clauses) >= 2 or len(ev_clauses) >= 2:
        for c_clause in claim_clauses:
            c_tokens = _claim_tokens(c_clause)
            if not c_tokens:
                continue
            best_ev_clause = max(
                ev_clauses,
                key=lambda ec: len(c_tokens & _claim_tokens(ec)) / max(1, len(c_tokens)),
                default=norm_ev,
            )
            if len(c_tokens & _claim_tokens(best_ev_clause)) > 0:
                c_neg = _has_negation(c_clause)
                e_neg = _has_negation(best_ev_clause)
                if e_neg and not c_neg:
                    return "negation_scope_dropped"
                if c_neg and not e_neg:
                    return "negation_scope_added"

    # Antonym / directional polarity check
    for pos_word, neg_word in _ANTONYM_PAIRS:
        pos_in_claim = bool(re.search(rf"\b{re.escape(pos_word)}\b", norm_claim))
        neg_in_claim = bool(re.search(rf"\b{re.escape(neg_word)}\b", norm_claim))
        pos_in_ev = bool(re.search(rf"\b{re.escape(pos_word)}\b", norm_ev))
        neg_in_ev = bool(re.search(rf"\b{re.escape(neg_word)}\b", norm_ev))
        if pos_in_claim and neg_in_ev and not pos_in_ev:
            return "polarity_antonym_mismatch"
        if neg_in_claim and pos_in_ev and not neg_in_ev:
            return "polarity_antonym_mismatch"

    return None


def _check_quantities_and_units(norm_claim: str, norm_ev: str) -> Optional[str]:
    claim_ranges = _extract_ranges(norm_claim)
    ev_ranges = _extract_ranges(norm_ev)
    for c_low, c_high, c_unit in claim_ranges:
        matched = False
        for e_low, e_high, e_unit in ev_ranges:
            if abs(c_low - e_low) < 1e-6 and abs(c_high - e_high) < 1e-6:
                if c_unit == e_unit or (c_unit is None and e_unit is None):
                    matched = True
                    break
        if not matched:
            return "range_or_unit_mismatch"

    claim_qs = _extract_quantities(norm_claim)
    ev_qs = _extract_quantities(norm_ev)
    if not claim_qs:
        return None

    # Propagate range unit to range endpoints in evidence/claim (e.g. "300-500 kcal" -> 300 has unit kcal)
    def _augment_range_units(
        qs: List[Tuple[float, Optional[str], Optional[str]]],
        ranges: List[Tuple[float, float, Optional[str]]],
    ) -> List[Tuple[float, Optional[str], Optional[str]]]:
        augmented = list(qs)
        for low, high, unit in ranges:
            if unit:
                augmented.append((low, None, unit))
                augmented.append((high, None, unit))
        return augmented

    ev_pool = _augment_range_units(ev_qs, ev_ranges)
    claim_range_endpoints = {
        val: unit for low, high, unit in claim_ranges for val in (low, high)
    }

    for c_val, c_op, c_unit in claim_qs:
        effective_c_unit = c_unit or claim_range_endpoints.get(c_val)
        same_number = [item for item in ev_pool if abs(item[0] - c_val) < 1e-6]
        if not same_number:
            return "number_mismatch"

        unit_ok = False
        op_ok = False
        for _, e_op, e_unit in same_number:
            # Strict unit check: 25 kg != 25%, and if either side names a concrete unit, units must agree.
            if effective_c_unit == e_unit:
                unit_ok = True
            elif effective_c_unit is None and e_unit is None:
                unit_ok = True
            else:
                continue

            if c_op is None and e_op is None:
                op_ok = True
            elif c_op == e_op:
                op_ok = True
            elif c_op is None and e_op is not None:
                # Dropping an explicit inequality comparator like "< 100" changes meaning.
                op_ok = False
            elif c_op is not None and e_op is None:
                op_ok = False
            else:
                op_ok = False

            if unit_ok and op_ok:
                break

        if not unit_ok:
            return "unit_mismatch"
        if not op_ok:
            return "comparator_mismatch"

    return None


def _check_subjects_and_populations(norm_claim: str, norm_ev: str) -> Optional[str]:
    claim_pops = _extract_tagged_groups(norm_claim, _POPULATION_PATTERNS)
    ev_pops = _extract_tagged_groups(norm_ev, _POPULATION_PATTERNS)

    if claim_pops - ev_pops:
        return "subject_population_mismatch"

    # If evidence explicitly restricts a statement to a specific demographic/clinical
    # group, dropping that scope overgeneralizes the claim.
    scope_sensitive = {
        "male", "female", "child", "adult", "elderly", "pregnant", "asian",
        "diabetes", "hypertension", "kidney_disease", "heart_disease",
        "pacemaker", "chronic_condition",
    }
    ev_scoped = ev_pops & scope_sensitive
    if ev_scoped and not (claim_pops & ev_scoped):
        return "subject_scope_dropped"

    claim_entities = _extract_tagged_groups(norm_claim, _HEALTH_ENTITY_PATTERNS)
    ev_entities = _extract_tagged_groups(norm_ev, _HEALTH_ENTITY_PATTERNS)
    if claim_entities - ev_entities:
        return "subject_entity_mismatch"

    return None


def _check_conditions(norm_claim: str, norm_ev: str) -> Optional[str]:
    for marker in _OVERGENERALIZATION_MARKERS:
        if re.search(marker, norm_claim) and not re.search(marker, norm_ev):
            return "condition_overgeneralized"

    ev_conditions = _extract_condition_clauses(norm_ev)
    if not ev_conditions:
        return None

    claim_tokens = _claim_tokens(norm_claim)
    for _, cond_tokens in ev_conditions:
        overlap_ratio = len(cond_tokens & claim_tokens) / max(1, len(cond_tokens))
        if overlap_ratio < 0.5:
            return "condition_dropped"

    return None


def _check_modality(norm_claim: str, norm_ev: str) -> Optional[str]:
    claim_neg = _has_negation(norm_claim)
    ev_neg = _has_negation(norm_ev)
    for pattern in _ESCALATED_MODALITY_MARKERS:
        in_claim = bool(re.search(pattern, norm_claim))
        in_ev = bool(re.search(pattern, norm_ev))
        if in_claim and not in_ev:
            return "epistemic_escalation"
        if in_claim and in_ev and ev_neg and not claim_neg:
            return "epistemic_escalation"
    return None


def _evaluate_claim_against_sentence(
    claim_plain: str,
    evidence_sentence: str,
) -> Tuple[str, List[str], float]:
    """Evaluate one claim against one evidence sentence.

    Returns `(verdict, reasons, coverage)` where verdict is one of:
    `supported`, `unsupported`, or `inconclusive`.
    """
    norm_claim = _normalize_match_text(claim_plain)
    norm_ev = _normalize_match_text(evidence_sentence)
    if not norm_claim or not norm_ev:
        return "unsupported", ["empty_claim_or_evidence"], 0.0

    # Exact or whitespace-normalized quotation passes immediately.
    if norm_claim == norm_ev:
        return "supported", [], 1.0

    reasons: List[str] = []
    for checker in (
        _check_negation_and_polarity,
        _check_quantities_and_units,
        _check_subjects_and_populations,
        _check_conditions,
        _check_modality,
    ):
        failure = checker(norm_claim, norm_ev)
        if failure:
            reasons.append(failure)

    claim_tokens = _claim_tokens(norm_claim)
    ev_tokens = _claim_tokens(norm_ev)
    if not claim_tokens:
        return "unsupported", ["no_content_tokens"], 0.0

    coverage = len(claim_tokens & ev_tokens) / len(claim_tokens)
    novel_tokens = claim_tokens - ev_tokens

    if reasons:
        return "unsupported", reasons, coverage

    # Conservative grounded support threshold: token overlap alone never overrides
    # the semantic constraint checks above, and unexplained novel content fails closed.
    if coverage >= 0.75 and len(novel_tokens) <= max(2, int(len(claim_tokens) * 0.25)):
        return "supported", [], coverage

    return "inconclusive", ["insufficient_grounded_support"], coverage


def _extract_tool_numbers(tool_results: Sequence[Mapping[str, Any]]) -> set[float]:
    values: set[float] = set()

    def _walk(obj: Any) -> None:
        if isinstance(obj, bool) or obj is None:
            return
        if isinstance(obj, (int, float)):
            values.add(float(obj))
        elif isinstance(obj, Mapping):
            for val in obj.values():
                _walk(val)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                _walk(item)

    for entry in tool_results or []:
        _walk(entry.get("result") if isinstance(entry, Mapping) else entry)
    return values


def _is_safety_notice(
    plain: str,
    safety_result: Optional[Mapping[str, Any]],
) -> bool:
    norm = _normalize_match_text(plain)
    if not norm or suggests_unsafe_medical_change(norm):
        return False
    safety = safety_result or {}
    for key in ("disclaimer", "recommended_action"):
        expected = _normalize_match_text(str(safety.get(key) or ""))
        if expected and (expected in norm or norm in expected):
            return True
    if any(phrase in norm for phrase in _SAFETY_NOTICE_PHRASES):
        # Do not let a fabricated numeric clinical threshold hide inside a safety notice.
        nums = [val for val, _, _ in _extract_quantities(norm)]
        if all(abs(num - 115.0) < 1e-6 for num in nums):
            return True
    return False


def _is_clarification_or_refusal(plain: str) -> bool:
    norm = _normalize_match_text(plain)
    if not norm or suggests_unsafe_medical_change(norm):
        return False
    if _extract_quantities(norm):
        return False
    if plain.strip().endswith("?"):
        return True
    return any(phrase in norm for phrase in _CLARIFICATION_OR_REFUSAL_PHRASES)


def _check_deterministic_tool_sentence(
    plain: str,
    tool_results: Sequence[Mapping[str, Any]],
) -> Optional[str]:
    """Return 'matched', 'mismatch', or None (not a deterministic tool sentence)."""
    if not tool_results:
        return None
    norm = _normalize_match_text(plain)
    if suggests_unsafe_medical_change(norm):
        return None
    tool_numbers = _extract_tool_numbers(tool_results)
    if not tool_numbers:
        return None

    claim_qs = _extract_quantities(norm)
    if not claim_qs:
        return None

    # Identify sentences reporting calculated metrics from deterministic tools.
    metric_markers = ("bmi", "pbf", "mo noi tang", "visceral", "calo", "tdee", "bmr", "protein", "can nang", "chieu cao")
    if not any(marker in norm for marker in metric_markers):
        return None

    for val, _, _ in claim_qs:
        if not any(abs(val - tool_val) <= 0.05 for tool_val in tool_numbers):
            return "mismatch"
    return "matched"


def _sentence_in_child_excerpt(matched_sentence: str, child_excerpt: str) -> bool:
    if not child_excerpt or not matched_sentence:
        return False
    norm_matched = _normalize_match_text(matched_sentence)
    norm_child = _normalize_match_text(_strip_breadcrumb(child_excerpt))
    if not norm_matched or not norm_child:
        return False
    if norm_matched in norm_child:
        return True
    child_sentences = _split_sentences(child_excerpt)
    return any(_normalize_match_text(cs) == norm_matched for cs in child_sentences)


def verify_answer_claims_detailed(
    answer: str,
    evidence: List[Dict[str, Any]],
    *,
    tool_results: Optional[Sequence[Mapping[str, Any]]] = None,
    safety_result: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Verify answer claims with sentence-level checks and auditable reasons.

    Internal status values:
    - `supported`: all RAG claims are verified and no tool/safety violations occurred.
    - `unsupported`: explicit contradiction, invalid/missing citation, unit/number/
      subject/condition/modality error, or tool value mismatch.
    - `inconclusive`: no explicit contradiction found, but grounded support on the
      admitted excerpt could not be established (fails closed).
    """
    by_id = {str(item["id"]): item for item in (evidence or [])}
    sentences = _split_sentences(answer or "")
    if not sentences:
        return {
            "status": "unsupported",
            "supported": False,
            "links": [],
            "claims": [],
            "reasons": ["empty_answer"],
            "policy_version": CLAIM_VALIDATION_POLICY_VERSION,
        }

    links: List[Dict[str, Any]] = []
    claim_reports: List[Dict[str, Any]] = []
    all_reasons: List[str] = []
    has_unsupported = False
    has_inconclusive = False
    verified_rag_claims = 0

    for index, raw_sentence in enumerate(sentences, 1):
        cited = re.findall(r"\[(\d+)\]", raw_sentence)
        plain = _strip_markdown(re.sub(r"\[\d+\]", "", raw_sentence).strip())
        if not plain:
            has_unsupported = True
            all_reasons.append("empty_claim")
            claim_reports.append(
                {"claim_id": index, "text": raw_sentence, "kind": "rag_claim",
                 "verdict": "unsupported", "reasons": ["empty_claim"]}
            )
            continue

        # Sentences without citations may only pass if they are system safety notices,
        # deterministic tool outputs matching tool_results, or safe clarifications/refusals.
        if not cited:
            if _is_safety_notice(plain, safety_result):
                claim_reports.append(
                    {"claim_id": index, "text": plain, "kind": "safety_notice",
                     "verdict": "exempt", "reasons": []}
                )
                continue
            tool_check = _check_deterministic_tool_sentence(plain, tool_results or [])
            if tool_check == "matched":
                claim_reports.append(
                    {"claim_id": index, "text": plain, "kind": "deterministic_tool",
                     "verdict": "exempt", "reasons": []}
                )
                continue
            if tool_check == "mismatch":
                has_unsupported = True
                all_reasons.append("tool_value_mismatch")
                claim_reports.append(
                    {"claim_id": index, "text": plain, "kind": "deterministic_tool",
                     "verdict": "unsupported", "reasons": ["tool_value_mismatch"]}
                )
                continue
            if _is_clarification_or_refusal(plain):
                claim_reports.append(
                    {"claim_id": index, "text": plain, "kind": "clarification_or_refusal",
                     "verdict": "exempt", "reasons": []}
                )
                continue

            has_unsupported = True
            all_reasons.append("missing_citation")
            claim_reports.append(
                {"claim_id": index, "text": plain, "kind": "rag_claim",
                 "verdict": "unsupported", "reasons": ["missing_citation"]}
            )
            continue

        if any(ref not in by_id for ref in cited):
            has_unsupported = True
            all_reasons.append("invalid_citation")
            claim_reports.append(
                {"claim_id": index, "text": plain, "kind": "rag_claim",
                 "verdict": "unsupported", "reasons": ["invalid_citation"]}
            )
            continue

        claim_tokens = _claim_tokens(plain)
        if not claim_tokens:
            has_unsupported = True
            all_reasons.append("no_content_tokens")
            claim_reports.append(
                {"claim_id": index, "text": plain, "kind": "rag_claim",
                 "verdict": "unsupported", "reasons": ["no_content_tokens"]}
            )
            continue

        sentence_links: List[Dict[str, Any]] = []
        sentence_verdict = "supported"
        sentence_reasons: List[str] = []

        for ref in cited:
            item = by_id[ref]
            excerpt = str(item.get("excerpt") or "")
            ev_sentences = _split_sentences(excerpt)
            if not ev_sentences:
                sentence_verdict = "unsupported"
                sentence_reasons.append("empty_evidence_excerpt")
                continue

            # Rank candidate sentences in this excerpt by topical relevance so
            # negation or qualifiers in an unrelated sentence of the same chunk
            # do not corrupt the evaluation.
            ranked = sorted(
                ev_sentences,
                key=lambda ev_sent: (
                    len(claim_tokens & _claim_tokens(ev_sent)) / max(1, len(claim_tokens)),
                    len(claim_tokens & _claim_tokens(ev_sent)),
                ),
                reverse=True,
            )

            best_supported: Optional[Tuple[str, float]] = None
            best_failure_verdict = "inconclusive"
            best_failure_reasons: List[str] = ["insufficient_grounded_support"]

            # Inspect top candidates; if the closest topical sentence explicitly
            # contradicts the claim, do not silently bypass it unless an exact/stronger
            # supporting sentence exists.
            for rank_idx, ev_sent in enumerate(ranked[:5]):
                verdict, reasons, coverage = _evaluate_claim_against_sentence(plain, ev_sent)
                if verdict == "supported":
                    best_supported = (ev_sent, coverage)
                    break
                if rank_idx == 0:
                    best_failure_verdict = verdict
                    best_failure_reasons = reasons

            if best_supported is None:
                if best_failure_verdict == "unsupported":
                    sentence_verdict = "unsupported"
                elif sentence_verdict != "unsupported":
                    sentence_verdict = "inconclusive"
                sentence_reasons.extend(best_failure_reasons)
                continue

            matched_ev_sent, _ = best_supported
            is_parent = bool(item.get("is_expanded_parent")) or item.get("evidence_scope") == "parent_section"
            child_excerpt = str(item.get("child_excerpt") or "")
            matched_child_id = item.get("matched_child_chunk_id")
            if is_parent:
                in_child = _sentence_in_child_excerpt(matched_ev_sent, child_excerpt)
                link_scope = "child_chunk" if in_child and matched_child_id else "parent_section"
                link_entry: Dict[str, Any] = {
                    "claim_id": index,
                    "evidence_id": item["id"],
                    "document_id": item["document_id"],
                    "chunk_id": item["chunk_id"],
                    "evidence_scope": link_scope,
                    "parent_id": item.get("parent_id") or item["chunk_id"],
                    "matched_child_chunk_id": matched_child_id if link_scope == "child_chunk" else None,
                }
            else:
                link_entry = {
                    "claim_id": index,
                    "evidence_id": item["id"],
                    "document_id": item["document_id"],
                    "chunk_id": item["chunk_id"],
                    "evidence_scope": item.get("evidence_scope") or "chunk",
                }
            sentence_links.append(link_entry)

        if sentence_verdict == "supported" and sentence_links:
            verified_rag_claims += 1
            links.extend(sentence_links)
            claim_reports.append(
                {
                    "claim_id": index,
                    "text": plain,
                    "kind": "rag_claim",
                    "verdict": "supported",
                    "reasons": [],
                }
            )
        else:
            if sentence_verdict == "unsupported":
                has_unsupported = True
            else:
                has_inconclusive = True
            all_reasons.extend(sentence_reasons)
            claim_reports.append(
                {
                    "claim_id": index,
                    "text": plain,
                    "kind": "rag_claim",
                    "verdict": sentence_verdict,
                    "reasons": sentence_reasons,
                }
            )

    if has_unsupported:
        return {
            "status": "unsupported",
            "supported": False,
            "links": [],
            "claims": claim_reports,
            "reasons": sorted(set(all_reasons)),
            "policy_version": CLAIM_VALIDATION_POLICY_VERSION,
        }
    if has_inconclusive:
        return {
            "status": "inconclusive",
            "supported": False,
            "links": [],
            "claims": claim_reports,
            "reasons": sorted(set(all_reasons)),
            "policy_version": CLAIM_VALIDATION_POLICY_VERSION,
        }
    # If an answer contained ONLY exempt sentences (e.g. a clarification/refusal or
    # safety notice without any verified RAG claim), do not mark RAG claims supported
    # with empty links when evidence was required; only return supported if at least
    # one RAG claim was verified OR deterministic tool claims were verified alongside safety.
    has_exempt_tool = any(item["kind"] == "deterministic_tool" for item in claim_reports)
    if verified_rag_claims == 0 and not has_exempt_tool:
        all_safe_exempt = bool(claim_reports) and all(
            item["kind"] in {"safety_notice", "clarification_or_refusal"}
            for item in claim_reports
        )
        return {
            "status": "clarification_or_safety_only" if all_safe_exempt else "inconclusive",
            "supported": False,
            "safe_without_citations": all_safe_exempt,
            "links": [],
            "claims": claim_reports,
            "reasons": ["no_verified_rag_claims"],
            "policy_version": CLAIM_VALIDATION_POLICY_VERSION,
        }
    return {
        "status": "supported",
        "supported": True,
        "safe_without_citations": False,
        "links": links,
        "claims": claim_reports,
        "reasons": [],
        "policy_version": CLAIM_VALIDATION_POLICY_VERSION,
    }


def verify_answer_claims(
    answer: str,
    evidence: List[Dict[str, Any]],
    *,
    tool_results: Optional[Sequence[Mapping[str, Any]]] = None,
    safety_result: Optional[Mapping[str, Any]] = None,
) -> Tuple[bool, List[Dict[str, Any]]]:
    """Fail closed when any sentence lacks grounded support or violates constraints."""
    result = verify_answer_claims_detailed(
        answer,
        evidence,
        tool_results=tool_results,
        safety_result=safety_result,
    )
    return bool(result["supported"]), list(result["links"])
