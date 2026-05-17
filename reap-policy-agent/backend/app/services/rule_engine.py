from __future__ import annotations

import re
from decimal import Decimal

from app.schemas import (
    CompiledPolicy,
    CompiledRule,
    Employee,
    PredicateType,
    Receipt,
    Transaction,
    Vendor,
    Verdict,
)

# FX rates relative to USD (1 USD = N units of currency) — mirrors read_tools.py
_FX: dict[str, float] = {
    "USD": 1.0,
    "EUR": 0.92,
    "GBP": 0.79,
    "SGD": 1.35,
}

# Verdict severity ordering — higher index = higher priority
_SEVERITY = [Verdict.pass_through, Verdict.needs_judgment, Verdict.needs_evidence, Verdict.fail]


def _convert(amount: Decimal, from_ccy: str, to_ccy: str) -> Decimal:
    f = _FX.get(from_ccy.upper(), 1.0)
    t = _FX.get(to_ccy.upper(), 1.0)
    return Decimal(str(float(amount) / f * t))


def _worse(a: Verdict, b: Verdict) -> Verdict:
    try:
        return b if _SEVERITY.index(b) > _SEVERITY.index(a) else a
    except ValueError:
        return a


# ---------------------------------------------------------------------------
# applies_when gate
# ---------------------------------------------------------------------------

def _check_applies_when(
    rule: CompiledRule, txn: Transaction, employee: Employee | None
) -> bool:
    """Evaluate the rule's applies_when condition. Returns True if the rule applies.

    Handles amount-threshold patterns; defaults to True (conservative) for any
    condition we cannot evaluate (e.g., city-based constraints).
    """
    cond = rule.applies_when
    if cond is None:
        return True

    # "amount > N [CCY]" — parse and check
    m = re.search(r"amount\s*[>≥]\s*(\d+(?:\.\d+)?)\s*([A-Z]{3})?", cond, re.IGNORECASE)
    if m:
        threshold = Decimal(m.group(1))
        ccy = (m.group(2) or txn.currency).upper()
        amount_in_ccy = _convert(txn.amount, txn.currency, ccy)
        return amount_in_ccy > threshold

    # Unknown condition (e.g. city-based) — skip rather than over-fire.
    # The judgment agent handles context the rule engine cannot evaluate.
    return False


# ---------------------------------------------------------------------------
# Per-predicate evaluators
# Return: (fired, verdict, missing_evidence)
# ---------------------------------------------------------------------------

def _eval_amount_requires_receipt(
    rule: CompiledRule, txn: Transaction, receipt: Receipt | None
) -> tuple[bool, Verdict, list[str]]:
    threshold = Decimal(str(rule.parameters.get("threshold", 0)))
    ccy = rule.parameters.get("currency", txn.currency)
    amount = _convert(txn.amount, txn.currency, ccy)
    if amount <= threshold:
        return False, Verdict.pass_through, []
    if receipt is None:
        return True, Verdict.needs_evidence, ["receipt"]
    return False, Verdict.pass_through, []


def _eval_amount_cap(
    rule: CompiledRule, txn: Transaction
) -> tuple[bool, Verdict, list[str]]:
    cap = Decimal(str(rule.parameters.get("cap", 0)))
    ccy = rule.parameters.get("currency", txn.currency)
    amount = _convert(txn.amount, txn.currency, ccy)
    if amount > cap:
        return True, Verdict.fail, []
    return False, Verdict.pass_through, []


def _eval_vendor_blocklist(
    rule: CompiledRule, txn: Transaction, vendor: Vendor | None
) -> tuple[bool, Verdict, list[str]]:
    blocked = {v.lower() for v in rule.parameters.get("vendors", [])}
    if txn.merchant_name.lower() in blocked:
        return True, Verdict.fail, []
    if vendor and vendor.name.lower() in blocked:
        return True, Verdict.fail, []
    return False, Verdict.pass_through, []


def _eval_vendor_allowlist(
    rule: CompiledRule, txn: Transaction, vendor: Vendor | None
) -> tuple[bool, Verdict, list[str]]:
    allowed = {v.lower() for v in rule.parameters.get("vendors", [])}
    if not allowed:
        return False, Verdict.pass_through, []
    merchant_ok = txn.merchant_name.lower() in allowed
    vendor_ok = vendor is not None and vendor.name.lower() in allowed
    if not (merchant_ok or vendor_ok):
        return True, Verdict.fail, []
    return False, Verdict.pass_through, []


def _eval_mcc_ban(
    rule: CompiledRule, txn: Transaction
) -> tuple[bool, Verdict, list[str]]:
    banned = set(rule.parameters.get("mcc_codes", []))
    if txn.mcc_code in banned:
        return True, Verdict.fail, []
    return False, Verdict.pass_through, []


_HOTEL_CATEGORIES = {"hotels", "hotel", "lodging"}


def _eval_hotel_star_max(
    rule: CompiledRule, vendor: Vendor | None
) -> tuple[bool, Verdict, list[str]]:
    """Only fires for confirmed hotel vendors; routes to judgment when star rating is unknown."""
    max_stars = rule.parameters.get("max_stars", 5)
    # Require positive evidence this is a hotel — skip for unknown or non-hotel vendors.
    if vendor is None or vendor.category.lower() not in _HOTEL_CATEGORIES:
        return False, Verdict.pass_through, []
    # Vendor schema has no star_rating field — route to LLM to check booking details.
    star_rating = getattr(vendor, "star_rating", None)
    if star_rating is None:
        return True, Verdict.needs_judgment, []
    if float(star_rating) > float(max_stars):
        return True, Verdict.fail, []
    return False, Verdict.pass_through, []


def _eval_per_diem_cap(
    rule: CompiledRule, txn: Transaction, employee: Employee | None
) -> tuple[bool, Verdict, list[str]]:
    ccy = rule.parameters.get("currency", txn.currency)
    # country-specific rates take precedence over a flat cap
    rates: dict[str, float] = rule.parameters.get("rates", {})
    if rates and employee and employee.country in rates:
        cap = Decimal(str(rates[employee.country]))
    else:
        cap = Decimal(str(rule.parameters.get("cap", 0)))
    amount = _convert(txn.amount, txn.currency, ccy)
    if amount > cap:
        return True, Verdict.fail, []
    return False, Verdict.pass_through, []


def _category_tokens(text: str) -> set[str]:
    """Extract words (≥4 chars) and add simple singular forms for better matching."""
    words = re.findall(r"[a-z]{4,}", text.lower())
    stems = set(words)
    for w in words:
        if w.endswith("s"):
            stems.add(w[:-1])
    return stems


def _eval_category_pre_approval(
    rule: CompiledRule, txn: Transaction, vendor: Vendor | None
) -> tuple[bool, Verdict, list[str]]:
    categories = [c.lower() for c in rule.parameters.get("categories", [])]
    if not categories:
        return False, Verdict.pass_through, []
    vendor_cat = vendor.category.lower() if vendor else ""
    merchant = txn.merchant_name.lower()
    desc = (txn.description or "").lower()
    hay_tokens = _category_tokens(f"{vendor_cat} {merchant} {desc}")
    for cat in categories:
        if _category_tokens(cat) & hay_tokens:
            return True, Verdict.fail, []
    return False, Verdict.pass_through, []


def _eval_requires_attendee_note(
    rule: CompiledRule, txn: Transaction, receipt: Receipt | None
) -> tuple[bool, Verdict, list[str]]:
    threshold = Decimal(str(rule.parameters.get("threshold", 0)))
    ccy = rule.parameters.get("currency", txn.currency)
    if threshold > 0:
        amount = _convert(txn.amount, txn.currency, ccy)
        if amount <= threshold:
            return False, Verdict.pass_through, []
    has_attendees = receipt is not None and bool(receipt.attendees)
    if not has_attendees:
        return True, Verdict.needs_judgment, []
    return False, Verdict.pass_through, []


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_EVALUATORS = {
    PredicateType.amount_requires_receipt: lambda rule, txn, receipt, vendor, employee: _eval_amount_requires_receipt(rule, txn, receipt),
    PredicateType.amount_cap:              lambda rule, txn, receipt, vendor, employee: _eval_amount_cap(rule, txn),
    PredicateType.vendor_blocklist:        lambda rule, txn, receipt, vendor, employee: _eval_vendor_blocklist(rule, txn, vendor),
    PredicateType.vendor_allowlist:        lambda rule, txn, receipt, vendor, employee: _eval_vendor_allowlist(rule, txn, vendor),
    PredicateType.mcc_ban:                 lambda rule, txn, receipt, vendor, employee: _eval_mcc_ban(rule, txn),
    PredicateType.hotel_star_max:          lambda rule, txn, receipt, vendor, employee: _eval_hotel_star_max(rule, vendor),
    PredicateType.per_diem_cap:            lambda rule, txn, receipt, vendor, employee: _eval_per_diem_cap(rule, txn, employee),
    PredicateType.category_pre_approval:   lambda rule, txn, receipt, vendor, employee: _eval_category_pre_approval(rule, txn, vendor),
    PredicateType.requires_attendee_note:  lambda rule, txn, receipt, vendor, employee: _eval_requires_attendee_note(rule, txn, receipt),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate(
    transaction: Transaction,
    policy: CompiledPolicy,
    receipt: Receipt | None,
    vendor: Vendor | None,
    employee: Employee | None,
) -> tuple[Verdict, list[str], list[str]]:
    """Evaluate a transaction against all structured rules in the policy.

    Returns:
        verdict         — worst verdict across all fired rules
        rules_fired     — rule_ids of every rule that triggered
        missing_evidence — evidence types collected from needs_evidence rules
    """
    if not policy.structured_rules:
        return Verdict.abstain, [], []

    verdict = Verdict.pass_through
    rules_fired: list[str] = []
    missing_evidence: list[str] = []

    for rule in policy.structured_rules:
        if not _check_applies_when(rule, transaction, employee):
            continue

        evaluator = _EVALUATORS.get(rule.predicate)
        if evaluator is None:
            continue

        fired, rule_verdict, evidence = evaluator(rule, transaction, receipt, vendor, employee)
        if fired:
            rules_fired.append(rule.rule_id)
            verdict = _worse(verdict, rule_verdict)
            for e in evidence:
                if e not in missing_evidence:
                    missing_evidence.append(e)

    return verdict, rules_fired, missing_evidence
