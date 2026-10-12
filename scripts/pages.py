"""Build one page per language from the bilingual template site/index.html.

English is served at / and Chinese at /zh/ (x-default is English), so search engines index each
language at its own address. In the template, an element whose class list contains "zh" or "en"
exists in that language only, and alt / aria-label / title texts written as "中文 / English" are split.

Usage: python3 scripts/pages.py <site dir>
  reads <site>/index.html (the template), writes <site>/index.html (en) and <site>/zh/index.html (zh)
"""
import re
import sys
from html import escape
from html.parser import HTMLParser
from pathlib import Path

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
CJK = re.compile(r"[　-鿿＀-￯]")
SPLIT_ATTRS = ("alt", "aria-label", "title")
URL_ATTRS = ("href", "src")
ABSOLUTE = ("#", "/", "http:", "https:", "mailto:", "data:")
HTML_LANG = {"en": "en", "zh": "zh-CN"}
# the language switch on each page: where it goes, that page's hreflang and language, its label
SWITCH = {"en": ("zh/", "zh-CN", "zh", "切换到中文"), "zh": ("../", "en", "en", "Switch to English")}


def localize(text, lang):
    left, sep, right = text.partition(" / ")
    if sep and CJK.search(left) and not CJK.search(right):
        return left if lang == "zh" else right
    return text


def set_attr(raw, name, value):
    """Set an attribute on a raw start tag, keeping everything else (including SVG casing) as written."""
    pattern = re.compile(r'(\s%s=")[^"]*(")' % re.escape(name))
    value = escape(value, quote=True)
    if pattern.search(raw):
        return pattern.sub(lambda m: m.group(1) + value + m.group(2), raw, count=1)
    end = len(raw) - (2 if raw.endswith("/>") else 1)
    return f'{raw[:end].rstrip()} {name}="{value}"{raw[end:]}'


def remove_attr(raw, name):
    return re.sub(r'\s%s="[^"]*"' % re.escape(name), "", raw, count=1)


class Page(HTMLParser):
    def __init__(self, lang):
        super().__init__(convert_charrefs=False)
        self.lang = lang
        self.other = "zh" if lang == "en" else "en"
        self.prefix = "../" if lang == "zh" else ""
        self.out = []
        self.skip = 0  # depth inside an element that belongs to the other language
        self.trim = False  # drop the newline left behind by a removed element

    def emit(self, text):
        if self.trim and text.startswith("\n"):
            text = text[1:]
        self.trim = False
        self.out.append(text)

    def removed(self):
        self.trim = not self.out or self.out[-1].endswith("\n")

    def rewrite(self, tag, attrs):
        raw = self.get_starttag_text()
        values = dict(attrs)
        classes = (values.get("class") or "").split()
        if self.lang in classes:
            rest = " ".join(c for c in classes if c != self.lang)
            raw = set_attr(raw, "class", rest) if rest else remove_attr(raw, "class")
        for name in SPLIT_ATTRS:
            if values.get(name):
                text = localize(values[name], self.lang)
                if text != values[name]:
                    raw = set_attr(raw, name, text)
        if tag == "html":
            raw = set_attr(set_attr(raw, "lang", HTML_LANG[self.lang]), "data-lang", self.lang)
            if self.prefix:
                raw = set_attr(raw, "data-base", self.prefix)
        elif values.get("id") == "lang":
            href, hreflang, target, label = SWITCH[self.lang]
            for name, value in (("href", href), ("hreflang", hreflang), ("data-lang", target), ("aria-label", label)):
                raw = set_attr(raw, name, value)
            return raw
        if self.prefix:
            for name in URL_ATTRS:
                url = values.get(name)
                if url and not url.startswith(ABSOLUTE):
                    raw = set_attr(raw, name, self.prefix + url)
        return raw

    def handle_starttag(self, tag, attrs):
        if self.skip:
            if tag not in VOID:
                self.skip += 1
            return
        if self.other in (dict(attrs).get("class") or "").split():
            if tag in VOID:
                self.removed()
            else:
                self.skip = 1
            return
        self.emit(self.rewrite(tag, attrs))

    def handle_startendtag(self, tag, attrs):
        if self.skip:
            return
        if self.other in (dict(attrs).get("class") or "").split():
            self.removed()
            return
        self.emit(self.rewrite(tag, attrs))

    def handle_endtag(self, tag):
        if self.skip:
            if tag not in VOID:
                self.skip -= 1
                if not self.skip:
                    self.removed()
            return
        self.emit(f"</{tag}>")

    def handle_data(self, data):
        if not self.skip:
            self.emit(data)

    def handle_entityref(self, name):
        if not self.skip:
            self.emit(f"&{name};")

    def handle_charref(self, name):
        if not self.skip:
            self.emit(f"&#{name};")

    def handle_comment(self, data):
        if not self.skip:
            self.emit(f"<!--{data}-->")

    def handle_decl(self, decl):
        self.emit(f"<!{decl}>")


def render(template, lang):
    page = Page(lang)
    page.feed(template)
    page.close()
    return "".join(page.out)


def build_pages(site):
    site = Path(site)
    template = (site / "index.html").read_text(encoding="utf-8")
    (site / "zh").mkdir(exist_ok=True)
    (site / "zh" / "index.html").write_text(render(template, "zh"), encoding="utf-8")
    (site / "index.html").write_text(render(template, "en"), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    build_pages(sys.argv[1])
