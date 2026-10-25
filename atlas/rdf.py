"""RDF terms and a reader for Turtle and N-Triples files, copied from judaicalink-data (src/jl/rdf.py, decision 0018).

The framework reads RDF itself, with the standard library: QLever normalises literal values when it indexes
(xsd:integer becomes xsd:int, xsd:float is rounded to a decimal, dateTime loses its microseconds, WKT points
are reformatted; measured with QLever 0.6.0 on 2026-10-11), so it cannot give the triples of a file as they
are. The reader keeps every term as written; the canonical form (canonical.py) normalises only what RDF 1.1
says is equal (xsd:string, the case of language tags).

Terms: IRI and BNode are str subclasses (the IRI without angle brackets, the label without "_:"); Literal
is a named tuple (value, datatype, lang).
"""

import codecs
import gzip
import re
import tarfile
from typing import NamedTuple
from urllib.parse import urljoin

RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
XSD = "http://www.w3.org/2001/XMLSchema#"
RDF_TYPE = RDF + "type"
XSD_STRING = XSD + "string"


class IRI(str):
    __slots__ = ()


class BNode(str):
    __slots__ = ()


class Literal(NamedTuple):
    value: str
    datatype: str | None = None   # an IRI string; None for simple and language-tagged literals
    lang: str | None = None


class ParseError(Exception):
    def __init__(self, msg, source=None, line=None):
        self.msg, self.source, self.line = msg, source, line
        where = f"{source}" + (f", line {line}" if line else "") if source else ""
        super().__init__(f"{where}: {msg}" if where else msg)


# --- N-Triples terms ------------------------------------------------------------------------------

_IRI_ESC = {c: f"\\u{c:04X}" for c in list(range(0x21)) + [ord(x) for x in '<>"{}|^`\\']}
_STR_ESC = {c: f"\\u{c:04X}" for c in list(range(0x20)) + [0x7F]}
_STR_ESC.update({ord("\\"): "\\\\", ord('"'): '\\"', ord("\n"): "\\n", ord("\r"): "\\r", ord("\t"): "\\t",
                 ord("\b"): "\\b", ord("\f"): "\\f"})


def nt_iri(iri):
    return "<" + iri.translate(_IRI_ESC) + ">"


def nt_string(s):
    return '"' + s.translate(_STR_ESC) + '"'


def nt(term, canonical=False):
    """A term in N-Triples syntax. canonical: drop xsd:string, lower-case language tags (RDF 1.1 equality)."""
    if isinstance(term, Literal):
        s = nt_string(term.value)
        if term.lang:
            return s + "@" + (term.lang.lower() if canonical else term.lang)
        if term.datatype and not (canonical and term.datatype == XSD_STRING):
            return s + "^^" + nt_iri(term.datatype)
        return s
    if isinstance(term, BNode):
        return "_:" + term
    return nt_iri(term)


def nt_line(s, p, o, canonical=False):
    return f"{nt(s, canonical)} {nt(p, canonical)} {nt(o, canonical)} ."


# --- opening files --------------------------------------------------------------------------------

def rdf_format(name):
    """'nt' or 'turtle' from a file name (".gz" ignored), or None."""
    n = name[:-3] if name.endswith(".gz") else name
    if n.endswith(".nt"):
        return "nt"
    if n.endswith((".ttl", ".n3")):
        return "turtle"
    return None


def is_tar_gz(path):
    """Some legacy dumps named *.ttl.gz are tar archives (ustar header at byte 257)."""
    try:
        with gzip.open(path, "rb") as f:
            return f.read(512)[257:262] == b"ustar"
    except (OSError, EOFError):
        return False


def open_members(path):
    """Yield (name, binary stream) for the RDF content of a file: plain, gzipped, or a gzipped tar archive."""
    path = str(path)
    if path.endswith(".gz"):
        if is_tar_gz(path):
            with tarfile.open(path, "r:gz") as t:
                for m in t.getmembers():
                    if m.isfile():
                        yield m.name, t.extractfile(m)
            return
        with gzip.open(path, "rb") as f:
            yield path, f
        return
    with open(path, "rb") as f:
        yield path, f


def read_triples(path, report=None):
    """All triples of an RDF file (N-Triples or Turtle by name; tar members by their own names).

    report (a dict) collects what the reader met: members, rdf_star (statements left out).
    """
    report = report if report is not None else {}
    report.setdefault("members", [])
    report.setdefault("rdf_star", 0)
    fmt_file = rdf_format(str(path))
    for name, stream in open_members(path):
        fmt = rdf_format(name) or fmt_file
        if fmt is None:
            raise ParseError("not an N-Triples or Turtle file", name)
        report["members"].append(name)
        text = codecs.getreader("utf-8")(stream, errors="strict")
        if fmt == "nt":
            yield from parse_ntriples(text, name)
        else:
            yield from TurtleParser(text, name, report).triples()


# --- N-Triples ------------------------------------------------------------------------------------

_UCHAR = re.compile(r"\\u([0-9A-Fa-f]{4})|\\U([0-9A-Fa-f]{8})")
_ECHAR = {"t": "\t", "b": "\b", "n": "\n", "r": "\r", "f": "\f", '"': '"', "'": "'", "\\": "\\"}
_STR_UNESC = re.compile(r"\\(?:u([0-9A-Fa-f]{4})|U([0-9A-Fa-f]{8})|(.))", re.S)


def unescape_iri(s):
    if "\\" not in s:
        return s
    return _UCHAR.sub(lambda m: chr(int(m.group(1) or m.group(2), 16)), s)


def unescape_string(s, source=None, line=None):
    if "\\" not in s:
        return s

    def rep(m):
        if m.group(3) is not None:
            c = _ECHAR.get(m.group(3))
            if c is None:
                raise ParseError(f"invalid escape \\{m.group(3)}", source, line)
            return c
        return chr(int(m.group(1) or m.group(2), 16))
    out = _STR_UNESC.sub(rep, s)
    if _SURROGATE.search(out):   # \u escapes of UTF-16 surrogates (not N-Triples, but written e.g. by VIAF)
        out = out.encode("utf-16", "surrogatepass").decode("utf-16", "replace")
    return out


_SURROGATE = re.compile("[\ud800-\udfff]")


_NT_IRI = r'<([^\x00-\x20<>"{}|^`\\]*(?:\\[uU][0-9A-Fa-f]+[^\x00-\x20<>"{}|^`\\]*)*)>'
_NT_BNODE = r"_:([A-Za-z0-9_\u00C0-\U000EFFFF](?:[A-Za-z0-9_.\-\u00B7-\U000EFFFF]*[A-Za-z0-9_\-\u00B7-\U000EFFFF])?)"
_NT_LINE = re.compile(
    r"[ \t]*(?:" + _NT_IRI + "|" + _NT_BNODE + r")[ \t]+" + _NT_IRI + r"[ \t]+(?:" + _NT_IRI + "|" + _NT_BNODE +
    r'|"((?:[^"\\\n\r]|\\.)*)"(?:@([a-zA-Z]+(?:-[a-zA-Z0-9]+)*)|\^\^' + _NT_IRI + r")?)[ \t]*\.[ \t]*(?:#.*)?$")
_NT_SKIP = re.compile(r"[ \t]*(?:#.*)?$")


def parse_ntriples(text, source=None):
    for n, line in enumerate(text, 1):
        line = line.rstrip("\r\n")
        m = _NT_LINE.match(line)
        if m is None:
            if _NT_SKIP.match(line):
                continue
            raise ParseError("not an N-Triples statement", source, n)
        si, sb, p, oi, ob, lex, lang, dt = m.groups()
        s = IRI(unescape_iri(si)) if si is not None else BNode(sb)
        if oi is not None:
            o = IRI(unescape_iri(oi))
        elif ob is not None:
            o = BNode(ob)
        else:
            o = Literal(unescape_string(lex, source, n), IRI(unescape_iri(dt)) if dt else None, lang)
        yield s, IRI(unescape_iri(p)), o


# --- Turtle ---------------------------------------------------------------------------------------

_PN_CHARS_BASE = r"A-Za-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D" \
                 r"\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\U00010000-\U000EFFFF"
_PN_CHARS_U = _PN_CHARS_BASE + "_"
_PN_CHARS = _PN_CHARS_U + r"\-0-9\u00B7\u0300-\u036F\u203F-\u2040"
_PLX = r"%[0-9A-Fa-f]{2}|\\[_~.\-!$&'()*+,;=/?#@%]"
PN_PREFIX = f"[{_PN_CHARS_BASE}](?:[{_PN_CHARS}.]*[{_PN_CHARS}])?"
PN_LOCAL = f"(?:[{_PN_CHARS_U}:0-9]|{_PLX})(?:(?:[{_PN_CHARS}.:]|{_PLX})*(?:[{_PN_CHARS}:]|{_PLX}))?"

_TOKENS = re.compile("|".join([
    r"(?P<ws>(?:[ \t\r\n]|#[^\n]*)+)",
    r"(?P<iri><[^\x00-\x20<>\"{}|^`\\]*(?:\\[uU][0-9A-Fa-f]+[^\x00-\x20<>\"{}|^`\\]*)*>)",
    r'(?P<lstr>"""(?:[^"\\]|\\.|"(?!""))*"""|' r"'''(?:[^'\\]|\\.|'(?!''))*''')",
    r'(?P<str>"(?:[^"\\\n\r]|\\.)*"|' r"'(?:[^'\\\n\r]|\\.)*')",
    r"(?P<dtmark>\^\^)",
    r"(?P<at>@[a-zA-Z]+(?:-[a-zA-Z0-9]+)*)",
    r"(?P<double>[+-]?(?:[0-9]+\.[0-9]*[eE][+-]?[0-9]+|\.[0-9]+[eE][+-]?[0-9]+|[0-9]+[eE][+-]?[0-9]+))",
    r"(?P<decimal>[+-]?[0-9]*\.[0-9]+)",
    r"(?P<integer>[+-]?[0-9]+)",
    f"(?P<pname>(?:{PN_PREFIX})?:(?:{PN_LOCAL})?)",
    f"(?P<bnode>_:[{_PN_CHARS_U}0-9](?:[{_PN_CHARS}.]*[{_PN_CHARS}])?)",
    r"(?P<star><<|>>|\{\||\|\})",
    r"(?P<word>[A-Za-z]+)",
    r"(?P<punct>[.;,\[\]()])",
]), re.S)

_NUMERIC = {"integer": XSD + "integer", "decimal": XSD + "decimal", "double": XSD + "double"}
_PLX_UNESC = re.compile(r"\\([_~.\-!$&'()*+,;=/?#@%])")


class TurtleParser:
    """A Turtle 1.1 reader that streams its input. RDF-star statements are left out and counted (they occur
    in legacy dumps and are not RDF 1.1); blank nodes keep their labels, anonymous ones are labelled anon<n>."""

    TOKENS = _TOKENS
    CHUNK = 1 << 20
    MARGIN = 4096

    def __init__(self, text, source=None, report=None):
        self.text, self.source = text, source
        self.report = report if report is not None else {}
        self.report.setdefault("rdf_star", 0)
        self.buf, self.pos, self.eof, self.line = "", 0, False, 1
        self.prefixes, self.base = {}, ""
        self.anon = 0
        self.peeked = None
        self.out = []

    # tokens
    def fill(self):
        chunk = self.text.read(self.CHUNK)
        if not chunk:
            self.eof = True
            return False
        self.buf = self.buf[self.pos:] + chunk
        self.pos = 0
        return True

    def next_token(self):
        if self.peeked is not None:
            t, self.peeked = self.peeked, None
            return t
        while True:
            if not self.eof and len(self.buf) - self.pos < 16 * self.MARGIN:
                self.fill()
            m = self.TOKENS.match(self.buf, self.pos)
            # A token near the end of the buffer may be cut (e.g. "1." of "1.5"), and a long literal that does
            # not fit would be read as the empty string '""': read more and match again.
            if m is None or not self.eof and (m.end() > len(self.buf) - self.MARGIN or (
                    m.lastgroup == "str" and self.buf.startswith(('"""', "'''"), self.pos))):
                if not self.eof and self.fill():
                    continue
                if self.pos >= len(self.buf):
                    return ("eof", None)
                if m is None:
                    raise ParseError(f"unexpected text {self.buf[self.pos:self.pos + 40]!r}", self.source, self.line)
            kind, value = m.lastgroup, m.group()
            self.pos = m.end()
            self.line += value.count("\n")
            if kind == "ws":
                continue
            return (kind, value)

    def peek(self):
        if self.peeked is None:
            self.peeked = self.next_token()
        return self.peeked

    def error(self, msg):
        raise ParseError(msg, self.source, self.line)

    def expect(self, value):
        t = self.next_token()
        if t[1] != value:
            self.error(f"expected {value!r}, found {t[1]!r}")

    # terms
    def iri(self, raw):
        v = unescape_iri(raw[1:-1])
        if self.base and not re.match(r"[A-Za-z][A-Za-z0-9+.\-]*:", v):
            v = urljoin(self.base, v)
        return IRI(v)

    def pname(self, raw):
        prefix, _, local = raw.partition(":")
        if prefix not in self.prefixes:
            self.error(f"undeclared prefix {prefix!r}")
        return IRI(self.prefixes[prefix] + _PLX_UNESC.sub(r"\1", local))

    def string(self, kind, raw):
        body = raw[3:-3] if kind == "lstr" else raw[1:-1]
        return unescape_string(body, self.source, self.line)

    def term(self, t, position):
        kind, v = t
        if kind == "iri":
            return self.iri(v)
        if kind == "pname":
            return self.pname(v)
        if kind == "bnode":
            return BNode(v[2:])
        if kind == "word" and v == "a" and position == "predicate":
            return IRI(RDF_TYPE)
        if position == "object":
            if kind in ("str", "lstr"):
                value = self.string(kind, v)
                k2, v2 = self.peek()
                if k2 == "at":
                    self.next_token()
                    return Literal(value, None, v2[1:])
                if k2 == "dtmark":
                    self.next_token()
                    dt = self.next_token()
                    if dt[0] not in ("iri", "pname"):
                        self.error("expected a datatype IRI")
                    return Literal(value, self.term(dt, "datatype"), None)
                return Literal(value)
            if kind in _NUMERIC:
                return Literal(v, IRI(_NUMERIC[kind]))
            if kind == "word" and v in ("true", "false"):
                return Literal(v, IRI(XSD + "boolean"))
        self.error(f"unexpected {v!r} as {position}")

    def new_bnode(self):
        self.anon += 1
        return BNode(f"anon{self.anon}")

    # grammar
    def triples(self):
        while True:
            t = self.next_token()
            if t[0] == "eof":
                break
            self.statement(t)
            if self.out:
                yield from self.out
                self.out = []

    def statement(self, t):
        kind, v = t
        if kind == "at" and v in ("@prefix", "@base"):
            self.directive(v[1:])
            self.expect(".")
            return
        if kind == "word" and v.lower() in ("prefix", "base"):
            self.directive(v.lower())
            return
        if kind == "star" and v == "<<":
            self.skip_statement()
            self.report["rdf_star"] += 1
            return
        if kind == "punct" and v == "[":
            s = self.blank_node_property_list()
            if self.peek()[1] != ".":
                self.predicate_object_list(s)
        elif kind == "punct" and v == "(":
            s = self.collection()
            self.predicate_object_list(s)
        else:
            if kind not in ("iri", "pname", "bnode"):
                self.error(f"unexpected {v!r} at the start of a statement")
            s = self.term(t, "subject")
            self.predicate_object_list(s)
        self.expect(".")

    def directive(self, which):
        if which == "prefix":
            k, v = self.next_token()
            if k != "pname" or not v.endswith(":"):
                self.error("expected a prefix name")
            k2, v2 = self.next_token()
            if k2 != "iri":
                self.error("expected an IRI")
            self.prefixes[v[:-1]] = self.iri(v2)
        else:
            k, v = self.next_token()
            if k != "iri":
                self.error("expected an IRI")
            self.base = self.iri(v)

    def skip_statement(self):
        depth = 1
        while True:
            k, v = self.next_token()
            if k == "eof":
                self.error("end of file inside an RDF-star statement")
            if v == "<<":
                depth += 1
            elif v == ">>":
                depth -= 1
            elif v == "." and depth == 0 and k == "punct":
                return

    def predicate_object_list(self, s):
        while True:
            t = self.next_token()
            if t[0] not in ("iri", "pname") and t != ("word", "a"):
                self.error(f"expected a predicate, found {t[1]!r}")
            p = self.term(t, "predicate")
            while True:
                self.out.append((s, p, self.object()))
                if self.peek()[1] == "{|":
                    self.error("RDF-star annotations are not supported")
                if self.peek()[1] != ",":
                    break
                self.next_token()
            # one or more ';', possibly followed by the end of the list
            if self.peek()[1] != ";":
                return
            while self.peek()[1] == ";":
                self.next_token()
            if self.peek()[1] in (".", "]") or self.peek()[0] == "eof":
                return

    def object(self):
        t = self.next_token()
        if t == ("punct", "["):
            return self.blank_node_property_list()
        if t == ("punct", "("):
            return self.collection()
        if t == ("star", "<<"):
            self.error("RDF-star quoted triples are not supported")
        return self.term(t, "object")

    def blank_node_property_list(self):
        b = self.new_bnode()
        if self.peek()[1] == "]":
            self.next_token()
            return b
        self.predicate_object_list(b)
        self.expect("]")
        return b

    def collection(self):
        items = []
        while self.peek()[1] != ")":
            items.append(self.object())
        self.next_token()
        if not items:
            return IRI(RDF + "nil")
        head = node = self.new_bnode()
        for i, item in enumerate(items):
            self.out.append((node, IRI(RDF + "first"), item))
            nxt = self.new_bnode() if i + 1 < len(items) else IRI(RDF + "nil")
            self.out.append((node, IRI(RDF + "rest"), nxt))
            node = nxt
        return head
