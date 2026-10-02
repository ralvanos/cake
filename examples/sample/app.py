"""Sample module scanned by cake."""


def normalize_email(value: str) -> str:
    """Trim and lowercase an email address."""
    return value.strip().lower()


def unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        key = item.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        ordered.append(key)
    return ordered


def chunk(items: list[str], size: int) -> list[list[str]]:
    if size <= 0:
        raise ValueError("size must be positive")
    pages: list[list[str]] = []
    page: list[str] = []
    for item in items:
        page.append(item)
        if len(page) == size:
            pages.append(page)
            page = []
    if page:
        pages.append(page)
    return pages


def cents(amount: float) -> int:
    # Money is stored as integer cents so totals stay exact.
    return int(round(amount * 100))


def format_total(cents_value: int) -> str:
    sign = "-" if cents_value < 0 else ""
    whole, part = divmod(abs(cents_value), 100)
    return f"{sign}${whole:,}.{part:02d}"
