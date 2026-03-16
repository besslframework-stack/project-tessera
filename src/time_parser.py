"""Natural language time parser for memory queries.

Converts expressions like "yesterday", "last week", "지난주", "3월 초"
into (start_date, end_date) tuples for filtering.

No LLM needed -- regex + date arithmetic.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import NamedTuple


class DateRange(NamedTuple):
    start: str  # YYYY-MM-DD
    end: str    # YYYY-MM-DD


def parse_time_expression(text: str, now: datetime | None = None) -> DateRange | None:
    """Extract a time range from natural language text.

    Returns a DateRange if a time expression is found, None otherwise.

    Supports:
        English: today, yesterday, this week, last week, this month,
                 last month, N days ago, last N days, in January, etc.
        Korean: 오늘, 어제, 이번 주, 지난주, 이번 달, 지난달, N일 전, etc.
    """
    if not text:
        return None

    if now is None:
        now = datetime.now()

    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    text_lower = text.lower().strip()

    # --- English patterns ---

    # today / 오늘
    if re.search(r'\btoday\b|오늘', text_lower):
        return _range(today, today)

    # day before yesterday / 그제 / 그저께 (must come before "yesterday")
    if re.search(r'\bday before yesterday\b|그저께|그제', text_lower):
        d = today - timedelta(days=2)
        return _range(d, d)

    # yesterday / 어제
    if re.search(r'\byesterday\b|어제', text_lower):
        y = today - timedelta(days=1)
        return _range(y, y)

    # N days ago / N일 전
    m = re.search(r'(\d+)\s*(?:days?\s*ago|일\s*전)', text_lower)
    if m:
        d = today - timedelta(days=int(m.group(1)))
        return _range(d, d)

    # last N days / 최근 N일
    m = re.search(r'(?:last|past|recent)\s*(\d+)\s*days?|최근\s*(\d+)\s*일', text_lower)
    if m:
        n = int(m.group(1) or m.group(2))
        return _range(today - timedelta(days=n), today)

    # this week / 이번 주
    if re.search(r'\bthis week\b|이번\s*주', text_lower):
        start = today - timedelta(days=today.weekday())
        return _range(start, today)

    # last week / 지난주 / 지난 주
    if re.search(r'\blast week\b|지난\s*주', text_lower):
        end = today - timedelta(days=today.weekday() + 1)
        start = end - timedelta(days=6)
        return _range(start, end)

    # this month / 이번 달
    if re.search(r'\bthis month\b|이번\s*달', text_lower):
        start = today.replace(day=1)
        return _range(start, today)

    # last month / 지난달 / 지난 달
    if re.search(r'\blast month\b|지난\s*달', text_lower):
        first_this = today.replace(day=1)
        end = first_this - timedelta(days=1)
        start = end.replace(day=1)
        return _range(start, end)

    # N weeks ago / N주 전
    m = re.search(r'(\d+)\s*(?:weeks?\s*ago|주\s*전)', text_lower)
    if m:
        n = int(m.group(1))
        end = today - timedelta(weeks=n)
        start = end - timedelta(days=6)
        return _range(start, end)

    # N months ago / N달 전 / N개월 전
    m = re.search(r'(\d+)\s*(?:months?\s*ago|달\s*전|개월\s*전)', text_lower)
    if m:
        n = int(m.group(1))
        month = today.month - n
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        start = today.replace(year=year, month=month, day=1)
        if month == 12:
            end = today.replace(year=year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end = today.replace(year=year, month=month + 1, day=1) - timedelta(days=1)
        return _range(start, end)

    # "in January" / "in March" etc.
    month_names = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }
    for name, num in month_names.items():
        if re.search(rf'\bin {name}\b', text_lower):
            year = today.year if num <= today.month else today.year - 1
            start = datetime(year, num, 1)
            if num == 12:
                end = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                end = datetime(year, num + 1, 1) - timedelta(days=1)
            return _range(start, end)

    # Korean month: "3월", "3월 초", "3월 말"
    m = re.search(r'(\d{1,2})월(?:\s*(초|중|말))?', text_lower)
    if m:
        month_num = int(m.group(1))
        if 1 <= month_num <= 12:
            part = m.group(2)
            year = today.year if month_num <= today.month else today.year - 1
            if part == "초":
                start = datetime(year, month_num, 1)
                end = datetime(year, month_num, 10)
            elif part == "말":
                if month_num == 12:
                    last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
                else:
                    last_day = datetime(year, month_num + 1, 1) - timedelta(days=1)
                start = datetime(year, month_num, 21)
                end = last_day
            elif part == "중":
                start = datetime(year, month_num, 11)
                end = datetime(year, month_num, 20)
            else:
                start = datetime(year, month_num, 1)
                if month_num == 12:
                    end = datetime(year + 1, 1, 1) - timedelta(days=1)
                else:
                    end = datetime(year, month_num + 1, 1) - timedelta(days=1)
            return _range(start, end)

    return None


def strip_time_expression(text: str) -> str:
    """Remove the time expression from a query, leaving the rest for search."""
    patterns = [
        r'\btoday\b', r'\byesterday\b', r'\bday before yesterday\b',
        r'\d+\s*days?\s*ago', r'(?:last|past|recent)\s*\d+\s*days?',
        r'\bthis week\b', r'\blast week\b', r'\bthis month\b', r'\blast month\b',
        r'\d+\s*weeks?\s*ago', r'\d+\s*months?\s*ago',
        r'\bin (?:january|february|march|april|may|june|july|august|september|october|november|december)\b',
        r'오늘', r'어제', r'그저께', r'그제',
        r'\d+\s*일\s*전', r'최근\s*\d+\s*일',
        r'이번\s*주', r'지난\s*주', r'이번\s*달', r'지난\s*달',
        r'\d+\s*주\s*전', r'\d+\s*(?:달|개월)\s*전',
        r'\d{1,2}월(?:\s*(?:초|중|말))?',
    ]
    result = text
    for p in patterns:
        result = re.sub(p, '', result, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', result).strip()


def _range(start: datetime, end: datetime) -> DateRange:
    return DateRange(
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
    )
