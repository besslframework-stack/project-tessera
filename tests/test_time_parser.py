"""Tests for natural language time parser."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.time_parser import DateRange, parse_time_expression, strip_time_expression

# Fix "now" for deterministic tests
NOW = datetime(2026, 3, 16, 14, 30, 0)


class TestEnglishPatterns:
    def test_today(self):
        r = parse_time_expression("what happened today", NOW)
        assert r == DateRange("2026-03-16", "2026-03-16")

    def test_yesterday(self):
        r = parse_time_expression("yesterday's decisions", NOW)
        assert r == DateRange("2026-03-15", "2026-03-15")

    def test_day_before_yesterday(self):
        r = parse_time_expression("day before yesterday", NOW)
        assert r == DateRange("2026-03-14", "2026-03-14")

    def test_n_days_ago(self):
        r = parse_time_expression("3 days ago", NOW)
        assert r == DateRange("2026-03-13", "2026-03-13")

    def test_last_n_days(self):
        r = parse_time_expression("last 7 days", NOW)
        assert r == DateRange("2026-03-09", "2026-03-16")

    def test_this_week(self):
        # March 16 2026 is Monday
        r = parse_time_expression("this week", NOW)
        assert r == DateRange("2026-03-16", "2026-03-16")

    def test_last_week(self):
        r = parse_time_expression("last week", NOW)
        assert r == DateRange("2026-03-09", "2026-03-15")

    def test_this_month(self):
        r = parse_time_expression("this month", NOW)
        assert r == DateRange("2026-03-01", "2026-03-16")

    def test_last_month(self):
        r = parse_time_expression("last month", NOW)
        assert r == DateRange("2026-02-01", "2026-02-28")

    def test_2_weeks_ago(self):
        r = parse_time_expression("2 weeks ago", NOW)
        assert r is not None
        assert r.start < "2026-03-10"

    def test_in_january(self):
        r = parse_time_expression("in January", NOW)
        assert r == DateRange("2026-01-01", "2026-01-31")

    def test_in_february(self):
        r = parse_time_expression("in February", NOW)
        assert r == DateRange("2026-02-01", "2026-02-28")


class TestKoreanPatterns:
    def test_오늘(self):
        r = parse_time_expression("오늘 뭐 했지", NOW)
        assert r == DateRange("2026-03-16", "2026-03-16")

    def test_어제(self):
        r = parse_time_expression("어제 결정한 거", NOW)
        assert r == DateRange("2026-03-15", "2026-03-15")

    def test_그저께(self):
        r = parse_time_expression("그저께 얘기", NOW)
        assert r == DateRange("2026-03-14", "2026-03-14")

    def test_n일전(self):
        r = parse_time_expression("5일 전에 한 거", NOW)
        assert r == DateRange("2026-03-11", "2026-03-11")

    def test_최근_n일(self):
        r = parse_time_expression("최근 3일", NOW)
        assert r == DateRange("2026-03-13", "2026-03-16")

    def test_이번주(self):
        r = parse_time_expression("이번 주 결정", NOW)
        assert r is not None

    def test_지난주(self):
        r = parse_time_expression("지난주에 뭐 했지", NOW)
        assert r is not None
        assert r.end < "2026-03-16"

    def test_이번달(self):
        r = parse_time_expression("이번 달 작업", NOW)
        assert r == DateRange("2026-03-01", "2026-03-16")

    def test_지난달(self):
        r = parse_time_expression("지난달 결정", NOW)
        assert r == DateRange("2026-02-01", "2026-02-28")

    def test_3월(self):
        r = parse_time_expression("3월에 한 거", NOW)
        assert r == DateRange("2026-03-01", "2026-03-31")

    def test_3월초(self):
        r = parse_time_expression("3월 초", NOW)
        assert r == DateRange("2026-03-01", "2026-03-10")

    def test_3월말(self):
        r = parse_time_expression("3월 말", NOW)
        assert r == DateRange("2026-03-21", "2026-03-31")

    def test_3월중(self):
        r = parse_time_expression("3월 중", NOW)
        assert r == DateRange("2026-03-11", "2026-03-20")

    def test_2주전(self):
        r = parse_time_expression("2주 전 결정", NOW)
        assert r is not None

    def test_1개월전(self):
        r = parse_time_expression("1개월 전", NOW)
        assert r is not None
        assert r.start.startswith("2026-02")


class TestNoMatch:
    def test_no_time(self):
        assert parse_time_expression("database architecture") is None

    def test_empty(self):
        assert parse_time_expression("") is None


class TestStripTimeExpression:
    def test_strip_yesterday(self):
        result = strip_time_expression("yesterday's database decisions")
        assert "yesterday" not in result.lower()
        assert "database" in result

    def test_strip_korean(self):
        result = strip_time_expression("지난주에 결정한 DB 관련")
        assert "지난" not in result
        assert "DB" in result

    def test_strip_month(self):
        result = strip_time_expression("3월 초에 한 API 작업")
        assert "3월" not in result
        assert "API" in result

    def test_no_time_unchanged(self):
        assert strip_time_expression("database stuff") == "database stuff"
