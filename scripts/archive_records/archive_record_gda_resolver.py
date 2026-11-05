"""Resolve supported Monasterium fonds references through the Bavarian catalog."""

from html.parser import HTMLParser
import re
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener

from archive_record_gda_bayern import RecordFields, fetch, field_values, iso_date

SEARCH_URL = "https://www.gda.bayern.de/gvl/search.jsf"


class SearchForm(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.select = None
        self.fields = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form" and attrs.get("id") == "searchForm":
            self.active = True
        if not self.active:
            return
        if tag == "input" and attrs.get("name") and attrs.get("type") not in ("checkbox", "radio", "submit", "button"):
            self.fields[attrs["name"]] = attrs.get("value", "")
        if tag == "select":
            self.select = attrs.get("name")
        if tag == "option" and self.select and ("selected" in attrs or self.select not in self.fields):
            self.fields[self.select] = attrs.get("value", "")

    def handle_endtag(self, tag):
        if tag == "form":
            self.active = False
        if tag == "select":
            self.select = None


class SearchResult(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.in_summary = False
        self.summary = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id") == "searchResultSummary":
            self.in_summary = True
        if tag == "a" and re.fullmatch(r"searchEntry:\d+:docForm:searchDocumentLink", attrs.get("id", "")):
            self.links.append(attrs.get("href", ""))

    def handle_data(self, data):
        if self.in_summary:
            self.summary += data

    def handle_endtag(self, tag):
        if tag == "div" and self.in_summary:
            self.in_summary = False


def resolve(archive, fonds, identifier, date):
    # These Monasterium fonds IDs encode the monastery name followed by its order.
    match = re.fullmatch(r"([A-Z][a-z]+)(?:OSB|OCist|CanReg)", fonds)
    if not re.fullmatch(r"DE-(StA[A-Za-z]+|BayHStA)", archive) or not match or not re.fullmatch(r"\d+", identifier) or not re.fullmatch(r"\d{8}", date):
        return None
    archive_code = archive[3:]
    monastery = match.group(1)
    opener = build_opener(HTTPCookieProcessor())
    headers = {"User-Agent": "Rosenberg research downloader/1.0"}
    with opener.open(Request(SEARCH_URL, headers=headers), timeout=60) as response:
        form = SearchForm()
        form.feed(response.read().decode("utf-8", "replace"))
    if "jakarta.faces.ViewState" not in form.fields:
        raise ValueError("Bavarian catalog search form is unavailable")
    form.fields.update({
        "searchForm": "searchForm",
        "searchForm:searchTerm_input": f'"{monastery} Urkunden {identifier}"',
        "searchForm:valuesRecordPerpage": "100",
        "jakarta.faces.partial.ajax": "true",
        "jakarta.faces.behavior.event": "action",
        "jakarta.faces.partial.event": "click",
        "jakarta.faces.source": "searchForm:searchButton",
        "jakarta.faces.partial.execute": "searchForm",
        "jakarta.faces.partial.render": "pagingTopForm docResultPanel docsMessagePanel pagingTopFormBottom searchResultHeader toolsBarForm",
        "searchForm:searchButton": "searchForm:searchButton",
    })
    with opener.open(Request(SEARCH_URL, data=urlencode(form.fields).encode(), headers={**headers, "Faces-Request": "partial/ajax"}), timeout=60) as response:
        result = SearchResult()
        payload = response.read().decode("utf-8", "replace")
        for fragment in re.findall(r"<!\[CDATA\[(.*?)(?:\]\]>|\Z)", payload, re.S):
            result.feed(fragment)
    if not re.search(r"\b1\s+Datensatz gefunden\b", result.summary) or len(result.links) != 1:
        return None
    candidate = urljoin(SEARCH_URL, result.links[0]).split("#", 1)[0]
    parsed = urlsplit(candidate)
    if parsed.hostname != "www.gda.bayern.de" or not parsed.path.startswith("/gvl/"):
        return None
    fields = RecordFields()
    fields.feed(fetch(candidate))
    citations = list(dict.fromkeys(field_values(fields, "Bestellsignatur")))
    dates = list(dict.fromkeys(field_values(fields, "Laufzeit")))
    expected = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    if len(citations) != 1 or len(dates) != 1:
        return None
    citation = " ".join(citations[0].split())
    if not re.match(rf"^{re.escape(archive_code)},", citation, re.I) or not re.search(rf"\b{re.escape(monastery)}\s+Urkunden\s+{re.escape(identifier)}$", citation, re.I):
        return None
    if iso_date(dates[0]) != expected:
        return None
    return candidate
