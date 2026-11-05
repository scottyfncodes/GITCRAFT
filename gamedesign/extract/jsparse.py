"""A tolerant, read-only reader for the data that games keep in JavaScript / TypeScript source.

DESIGNCRAFT never runs a game's code. This module tokenises a source file and parses the literal values
of its top-level declarations (`export const MISSIONS: MissionDef[] = [ ... ]`), plus builder-style calls
whose arguments are literals (`b.person('mara', 'Mara Okonjo', ...)`). Anything that is not a literal is
kept as a marker instead of being guessed:

  {"$ref": "HQ_T"}                 an identifier or member expression (resolved later when it names a literal)
  {"$call": "P", "args": [...]}   a call; its literal arguments are kept
  {"$expr": "<raw text>"}          arithmetic, arrow functions, anything else (numeric arithmetic is folded)
  {"$spread": <value>}             ...spread inside an array or object

Every object and array that came from source carries "_L": its 1-based line number, so every fact found
later can cite file:line."""
import re

PUNCT3 = ("...", "===", "!==", "**=", "<<=", ">>=", "&&=", "||=", "??=", ">>>")
PUNCT2 = ("=>", "==", "!=", "<=", ">=", "&&", "||", "??", "?.", "++", "--", "+=", "-=", "*=", "/=", "**", "<<", ">>")
ID_START = re.compile(r"[A-Za-z_$]")
ID_CHAR = re.compile(r"[A-Za-z0-9_$]")
NUM_RE = re.compile(r"0[xX][0-9a-fA-F_]+|0[bB][01_]+|0[oO][0-7_]+|(?:\d[\d_]*\.?[\d_]*|\.\d[\d_]*)(?:[eE][+-]?\d+)?n?")


class Tok:
    __slots__ = ("k", "v", "line", "pos", "end")

    def __init__(self, k, v, line, pos, end):
        self.k, self.v, self.line, self.pos, self.end = k, v, line, pos, end

    def __repr__(self): return f"{self.k}:{self.v!r}@{self.line}"


def tokenize(src):
    """kinds: id, num, str, tmpl, punct, regex. Comments are dropped; doc comments are kept separately."""
    toks, i, n, line = [], 0, len(src), 1
    docs = {}   # line of the token that follows a /** doc */ comment -> text
    pending_doc = None
    prev_sig = None
    while i < n:
        c = src[i]
        if c == "\n": line += 1; i += 1; continue
        if c in " \t\r﻿": i += 1; continue
        if src.startswith("//", i):
            j = src.find("\n", i); i = n if j < 0 else j; continue
        if src.startswith("/*", i):
            j = src.find("*/", i + 2); j = n if j < 0 else j + 2
            body = src[i:j]
            if body.startswith("/**"):
                pending_doc = re.sub(r"^\s*\*\s?", "", body[3:-2], flags=re.M).strip()
            line += body.count("\n"); i = j; continue
        start, sline = i, line
        if ID_START.match(c):
            j = i + 1
            while j < n and ID_CHAR.match(src[j]): j += 1
            t = Tok("id", src[i:j], sline, start, j); i = j
        elif c.isdigit() or (c == "." and i + 1 < n and src[i + 1].isdigit()):
            m = NUM_RE.match(src, i)
            j = m.end() if m and m.end() > i else i + 1
            t = Tok("num", src[i:j], sline, start, j); i = j
        elif c in "'\"":
            j, buf = i + 1, []
            while j < n and src[j] != c:
                if src[j] == "\\" and j + 1 < n:
                    e = src[j + 1]
                    buf.append({"n": "\n", "t": "\t", "r": "", "0": "\0"}.get(e, e)); j += 2; continue
                if src[j] == "\n": line += 1
                buf.append(src[j]); j += 1
            t = Tok("str", "".join(buf), sline, start, j + 1); i = j + 1
        elif c == "`":
            j, depth, buf = i + 1, 0, []
            while j < n:
                ch = src[j]
                if ch == "\\" and j + 1 < n: buf.append(src[j + 1]); j += 2; continue
                if ch == "\n": line += 1
                if depth == 0 and ch == "`": break
                if src.startswith("${", j): depth += 1; buf.append("${"); j += 2; continue
                if depth and ch == "{": depth += 1
                if depth and ch == "}": depth -= 1
                buf.append(ch); j += 1
            t = Tok("tmpl", "".join(buf), sline, start, j + 1); i = j + 1
        elif c == "/" and _regex_allowed(prev_sig):
            j, cls = i + 1, False
            while j < n and src[j] != "\n":
                ch = src[j]
                if ch == "\\": j += 2; continue
                if ch == "[": cls = True
                elif ch == "]": cls = False
                elif ch == "/" and not cls: break
                j += 1
            j += 1
            while j < n and ID_CHAR.match(src[j]): j += 1
            t = Tok("regex", src[i:j], sline, start, j); i = j
        else:
            for p in PUNCT3 + PUNCT2:
                if src.startswith(p, i):
                    t = Tok("punct", p, sline, start, i + len(p)); i += len(p); break
            else:
                t = Tok("punct", c, sline, start, i + 1); i += 1
        if pending_doc is not None:
            docs[len(toks)] = pending_doc; pending_doc = None
        toks.append(t); prev_sig = t
    return toks, docs


def _regex_allowed(prev):
    if prev is None: return True
    if prev.k in ("num", "str", "tmpl", "regex"): return False
    if prev.k == "id": return prev.v in ("return", "typeof", "case", "do", "else", "in", "of", "new", "delete", "void", "throw", "yield", "await")
    return prev.v not in (")", "]", "}")


class Fail(Exception):
    pass


BIN_PREC = {"??": 1, "||": 2, "&&": 3, "|": 4, "^": 5, "&": 6, "==": 7, "!=": 7, "===": 7, "!==": 7,
            "<": 8, ">": 8, "<=": 8, ">=": 8, "instanceof": 8, "in": 8, "<<": 9, ">>": 9, ">>>": 9,
            "+": 10, "-": 10, "*": 11, "/": 11, "%": 11, "**": 12}


class Parser:
    def __init__(self, src):
        self.src = src
        self.t, self.docs = tokenize(src)
        self.i = 0

    # ------------------------------------------------------------------ helpers
    def peek(self, o=0):
        j = self.i + o
        return self.t[j] if j < len(self.t) else None

    def at(self, v, o=0):
        p = self.peek(o); return p is not None and p.v == v and p.k in ("punct", "id")

    def eat(self, v):
        if not self.at(v): raise Fail(f"expected {v!r} at line {self.peek().line if self.peek() else 'EOF'}")
        self.i += 1

    def skip_balanced(self, stops=(",", ";", ")", "]", "}")):
        """Skip an expression we will not parse, to the next stop token at depth 0."""
        depth, start = 0, self.i
        while self.i < len(self.t):
            tk = self.t[self.i]
            if tk.k == "punct":
                if tk.v in "([{": depth += 1
                elif tk.v in ")]}":
                    if depth == 0: break
                    depth -= 1
                elif depth == 0 and tk.v in stops: break
            self.i += 1
        if self.i == start: self.i += 1
        a = self.t[start].pos; b = self.t[self.i - 1].end
        return self.src[a:b]

    def skip_type(self, stops):
        """Skip a type annotation up to a stop token at depth 0 (tracks <> as well)."""
        depth = 0
        while self.i < len(self.t):
            tk = self.t[self.i]
            if tk.k == "punct":
                if tk.v in "([{<": depth += 1
                elif tk.v in ")]}>":
                    if depth == 0 and tk.v != ">": return
                    depth = max(0, depth - 1)
                elif tk.v == "=>": pass
                elif depth == 0 and tk.v in stops: return
            self.i += 1

    # ------------------------------------------------------------------ values
    def value(self):
        start = self.i
        try:
            v = self.expr(0)
        except Fail:
            self.i = start
            return {"$expr": self.skip_balanced()[:200]}
        # TypeScript postfix: `as const`, `as Foo`, `satisfies Foo`, non-null `!`
        while self.peek() and self.peek().k == "id" and self.peek().v in ("as", "satisfies"):
            self.i += 1; self.skip_type((",", ";", ")", "]", "}"))
        return v

    def expr(self, min_prec):
        left = self.unary()
        while True:
            p = self.peek()
            if p is None: break
            if p.v == "?" and p.k == "punct" and min_prec == 0:
                self.i += 1; a = self.expr(0); self.eat(":"); b = self.expr(0)
                left = {"$expr": "conditional", "options": [a, b]}; continue
            op = p.v if p.k in ("punct", "id") else None
            prec = BIN_PREC.get(op)
            if prec is None or prec < min_prec: break
            if p.k == "id" and op not in ("instanceof", "in"): break
            self.i += 1
            right = self.expr(prec + 1)
            left = _fold(op, left, right)
        return left

    def unary(self):
        p = self.peek()
        if p is None: raise Fail("EOF")
        if p.k == "punct" and p.v in ("-", "+", "!", "~"):
            self.i += 1; v = self.unary()
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                return -v if p.v == "-" else v if p.v == "+" else ~int(v) if p.v == "~" else (not v)
            if p.v == "!" and isinstance(v, bool): return not v
            return {"$expr": p.v + _raw(v)}
        if p.k == "id" and p.v in ("typeof", "void", "await", "new"):
            self.i += 1; v = self.unary(); return {"$expr": p.v + " " + _raw(v)}
        return self.postfix(self.primary())

    def postfix(self, v):
        while True:
            p = self.peek()
            if p is None: return v
            if p.v in (".", "?.") and p.k == "punct":
                self.i += 1
                nx = self.peek()
                if nx is not None and nx.k == "id":
                    self.i += 1
                    v = {"$ref": _raw(v) + "." + nx.v} if isinstance(v, dict) and "$ref" in v else {"$expr": _raw(v) + "." + nx.v}
                    continue
                if nx is not None and nx.v in ("(", "["): continue
                raise Fail("member")
            if p.v == "(" and p.k == "punct":
                line = p.line; self.i += 1; args = []
                while not self.at(")"):
                    if self.at("..."): self.i += 1; args.append({"$spread": self.value()})
                    else: args.append(self.value())
                    if self.at(","): self.i += 1
                    elif not self.at(")"): raise Fail("call args")
                self.eat(")")
                v = {"$call": _raw(v), "args": args, "_L": line}
                continue
            if p.v == "[" and p.k == "punct":
                self.i += 1; k = self.value(); self.eat("]")
                v = {"$expr": f"{_raw(v)}[{_raw(k)}]"}; continue
            if p.v == "!" and p.k == "punct" and not (self.peek(1) and self.peek(1).v == "="):
                self.i += 1; continue
            if p.k == "tmpl":   # tagged template
                self.i += 1; v = {"$expr": _raw(v) + "`" + p.v + "`"}; continue
            return v

    def primary(self):
        p = self.peek()
        if p.k == "num":
            self.i += 1; return _num(p.v)
        if p.k == "str":
            self.i += 1; return p.v
        if p.k == "tmpl":
            self.i += 1; return p.v
        if p.k == "regex":
            self.i += 1; return {"$expr": p.v}
        if p.k == "punct":
            if p.v == "[": return self.array()
            if p.v == "{": return self.obj()
            if p.v == "(":
                # arrow function or parenthesised expression
                j = self._match(self.i)
                if j is not None and j + 1 < len(self.t) and self.t[j + 1].v in ("=>", ":"):
                    return self._skip_fn()
                self.i += 1; v = self.value(); self.eat(")"); return v
            if p.v == "<":   # generic arrow  <T,>(x) => ...
                return self._skip_fn()
        if p.k == "id":
            if p.v in ("true", "false"): self.i += 1; return p.v == "true"
            if p.v in ("null", "undefined"): self.i += 1; return None
            if p.v in ("function", "class", "async"): return self._skip_fn()
            nx = self.peek(1)
            if nx is not None and nx.v == "=>": return self._skip_fn()
            self.i += 1; return {"$ref": p.v}
        raise Fail(f"unexpected {p}")

    def _match(self, j):
        depth = 0
        while j < len(self.t):
            v = self.t[j].v if self.t[j].k == "punct" else None
            if v in ("(", "[", "{"): depth += 1
            elif v in (")", "]", "}"):
                depth -= 1
                if depth == 0: return j
            j += 1
        return None

    def _skip_fn(self):
        raw = self.skip_balanced()
        return {"$expr": "fn " + raw[:120]}

    def array(self):
        line = self.peek().line; self.eat("[")
        out = []
        while not self.at("]"):
            if self.peek() is None: raise Fail("EOF in array")
            if self.at(","): self.i += 1; out.append(None); continue
            if self.at("..."): self.i += 1; out.append({"$spread": self.value()})
            else: out.append(self.value())
            if self.at(","): self.i += 1
            elif not self.at("]"):
                self.skip_balanced((",",))
                if self.at(","): self.i += 1
        self.eat("]")
        return _Arr(out, line)

    def obj(self):
        line = self.peek().line; self.eat("{")
        out = {"_L": line}
        doc_idx = None
        while not self.at("}"):
            p = self.peek()
            if p is None: raise Fail("EOF in object")
            if self.at("..."):
                self.i += 1; out.setdefault("$spreads", []).append(self.value())
            else:
                doc_idx = self.i
                if p.k in ("id", "str", "num"): key = p.v; self.i += 1
                elif p.v == "[":
                    self.i += 1; key = "[" + _raw(self.value()) + "]"; self.eat("]")
                else: raise Fail(f"object key {p}")
                if p.k == "id" and key in ("get", "set", "async") and self.peek() and self.peek().k in ("id", "str"):
                    key = self.peek().v; self.i += 1
                if self.at("?"): self.i += 1
                if self.at(":"):
                    self.i += 1; out[key] = self.value()
                elif self.at("("):   # method
                    self.skip_balanced((",",)); out[key] = {"$expr": "method"}
                else:                   # shorthand  { id, name }
                    out[key] = {"$ref": key}
                if doc_idx in self.docs: out.setdefault("_doc", {})[key] = self.docs[doc_idx]
            if self.at(","): self.i += 1
            elif not self.at("}"):
                self.skip_balanced((",",))
                if self.at(","): self.i += 1
        self.eat("}")
        return out


class _Arr(list):
    """A list that remembers its source line."""
    def __init__(self, items, line):
        super().__init__(items); self.line = line


def _num(s):
    s = s.replace("_", "").rstrip("n")
    try:
        if s[:2].lower() == "0x": return int(s, 16)
        if s[:2].lower() == "0b": return int(s, 2)
        if s[:2].lower() == "0o": return int(s, 8)
        f = float(s)
        return int(f) if f.is_integer() and "." not in s and "e" not in s.lower() else f
    except ValueError:
        return {"$expr": s}


def _raw(v):
    if isinstance(v, dict):
        for k in ("$ref", "$expr", "$call"):
            if k in v: return str(v[k])
        return "{…}"
    if isinstance(v, list): return "[…]"
    return repr(v)


def _fold(op, a, b):
    num = lambda x: isinstance(x, (int, float)) and not isinstance(x, bool)
    if num(a) and num(b):
        try:
            r = {"+": a + b, "-": a - b, "*": a * b, "/": a / b if b else None, "%": a % b if b else None, "**": a ** b}.get(op)
            if r is not None:
                return int(r) if isinstance(r, float) and r.is_integer() and op != "/" else r
        except Exception: pass
    if op == "+" and isinstance(a, str) and isinstance(b, str): return a + b
    if op in ("??", "||") : return a if a is not None else b
    return {"$expr": f"{_raw(a)} {op} {_raw(b)}"}


# ---------------------------------------------------------------------- declarations
DECL_KW = ("const", "let", "var")
BUILDER_MIN_ARGS = 2


def parse_module(src):
    """-> {"decls": {name: {"value", "line", "exported", "doc", "type"}}, "calls": [...], "imports": {local: source}}"""
    p = Parser(src)
    t = p.t
    decls, calls, imports = {}, [], {}
    depth = 0
    n = len(t)
    while p.i < n:
        tk = t[p.i]
        if tk.k == "punct":
            if tk.v in "{([": depth += 1
            elif tk.v in "})]": depth = max(0, depth - 1)
            p.i += 1; continue
        if tk.k == "id" and tk.v == "import" and depth == 0:
            j = p.i + 1; names = []
            while j < n and not (t[j].k == "str"):
                if t[j].k == "id" and t[j].v not in ("type", "as", "from", "import"): names.append(t[j].v)
                j += 1
            if j < n:
                for nm in names: imports[nm] = t[j].v
            p.i = j + 1; continue
        if tk.k == "id" and tk.v in DECL_KW and depth <= 1 and p.i + 1 < n and t[p.i + 1].k == "id":
            exported = p.i > 0 and t[p.i - 1].v == "export"
            decl_at = p.i - 1 if exported else p.i
            name_tok = t[p.i + 1]; p.i += 2
            typ = None
            if p.at(":"):
                p.i += 1; ts = p.i; p.skip_type(("=", ";", ","))
                typ = src[t[ts].pos:t[p.i - 1].end] if p.i > ts else None
            if p.at("="):
                p.i += 1; vstart = p.i
                try:
                    v = p.value()
                except Exception:
                    p.i = vstart; v = {"$expr": p.skip_balanced((";",))[:200]}
                doc = p.docs.get(decl_at) or None
                decls[name_tok.v] = {"value": v, "line": name_tok.line, "exported": exported, "doc": doc, "type": typ, "depth": depth}
            continue
        # builder-style call: recv.method('id', ...) as a statement
        if tk.k == "id" and p.i + 3 < n and t[p.i + 1].v == "." and t[p.i + 2].k == "id" and t[p.i + 3].v == "(" \
                and (p.i == 0 or t[p.i - 1].v in (";", "{", "}", ")")) and depth >= 0:
            save = p.i
            try:
                meth = t[p.i + 2].v; line = t[p.i + 2].line; p.i += 3
                c = p.postfix({"$ref": tk.v + "." + meth})
                if isinstance(c, dict) and "$call" in c and len(c["args"]) >= BUILDER_MIN_ARGS and isinstance(c["args"][0], str):
                    calls.append({"recv": tk.v, "method": meth, "args": c["args"], "line": line})
            except Exception:
                p.i = save + 1
            continue
        p.i += 1
    return {"decls": decls, "calls": calls, "imports": imports}


def plain(v, depth=0):
    """Convert parsed values to JSON-safe data: _Arr -> list (line kept as first-class '_L' only for objects)."""
    if depth > 40: return None
    if isinstance(v, _Arr): return [plain(x, depth + 1) for x in v]
    if isinstance(v, list): return [plain(x, depth + 1) for x in v]
    if isinstance(v, dict): return {k: plain(x, depth + 1) for k, x in v.items()}
    return v


def line_of(v):
    if isinstance(v, _Arr): return v.line
    if isinstance(v, dict): return v.get("_L")
    return None
