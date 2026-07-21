"""Document categorization utilities."""

from __future__ import annotations


def categorize(text: str, metadata: dict | None = None) -> tuple[str, list[str]]:
    """
    Return (document_type, tags).

    Supported document_type values:
    - invoice
    - receipt
    - unknown
    """

    haystack = (text or "").lower()
    title = ""
    if metadata:
        title = str(metadata.get("doc_type", "")).lower()

    tags: list[str] = []
    if "invoice" in haystack or "inv #" in haystack or "invoice" in title:
        tags.append("financial")
        tags.append("vendor")
        if "invoice" in haystack:
            return "invoice", tags
    if "receipt" in haystack or "receipt" in title:
        tags.append("reimbursements")
        tags.append("merchant")
        return "receipt", tags
    if "po" in haystack or "purchase" in haystack:
        tags.append("procurement")
        return "invoice", tags

    return "unknown", ["unclassified"]

