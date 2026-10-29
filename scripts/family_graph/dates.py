"""Inclusive calendar-day intervals, sharing the fact validator's semantics."""

from datetime import date, timedelta
from validate_facts import date_bounds, inherited_date_bounds


def death_interval(mention):
    fact = mention.assertion.original
    if fact['type'] == 'death':
        if 'diedOn' in fact:
            return date_bounds(fact['diedOn'])
        return date.min, date_bounds(fact['diedBefore'])[0] - timedelta(days=1)
    if mention.deceased:
        return date.min, mention.assertion.bounds[1]
    return None


def compatible_deaths(mentions):
    intervals = [interval for mention in mentions if (interval := death_interval(mention))]
    return not intervals or max(start for start, _ in intervals) <= min(end for _, end in intervals)


def near(left, right, years=10):
    return max(left[0], right[0]).toordinal() - min(left[1], right[1]).toordinal() <= years * 366
