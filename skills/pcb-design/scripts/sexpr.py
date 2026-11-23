"""Minimal S-expression parser for KiCad files (.kicad_sch, .kicad_pcb).

Returns nested Python lists; atoms are strings (quoted strings keep no quotes).
"""
import re

_TOKEN = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))', re.S)


def parse(text):
    stack, cur = [], []
    pos, n = 0, len(text)
    while pos < n:
        m = _TOKEN.match(text, pos)
        if not m:
            if text[pos:].strip() == "":
                break
            raise ValueError(f"parse error at {pos}")
        pos = m.end()
        if m.group(1):
            stack.append(cur)
            cur = []
        elif m.group(2):
            done = cur
            cur = stack.pop()
            cur.append(done)
        elif m.group(3) is not None:
            s = m.group(3)
            if "\\" in s:
                s = re.sub(r'\\(.)', lambda e: {"n": "\n", "t": "\t"}.get(e.group(1), e.group(1)), s)
            cur.append(s)
        else:
            cur.append(m.group(4))
    return cur[0] if len(cur) == 1 else cur


def load(path):
    with open(path, encoding="utf-8") as f:
        return parse(f.read())


def children(node, tag):
    return [c for c in node if isinstance(c, list) and c and c[0] == tag]


def child(node, tag):
    for c in node:
        if isinstance(c, list) and c and c[0] == tag:
            return c
    return None


def walk(node, tag):
    """Yield all descendants with the given tag."""
    if isinstance(node, list):
        if node and node[0] == tag:
            yield node
        for c in node:
            if isinstance(c, list):
                yield from walk(c, tag)


def at(node):
    a = child(node, "at")
    if not a:
        return None
    vals = [float(v) for v in a[1:] if _isnum(v)]
    while len(vals) < 3:
        vals.append(0.0)
    return tuple(vals[:3])


def _isnum(v):
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False
