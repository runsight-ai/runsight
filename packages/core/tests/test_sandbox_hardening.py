"""
Tests for RUN-224: Harden CodeBlock sandbox against introspection bypass.

These tests verify that the AST validator catches bypass vectors that
circumvent the current blocked-builtins / blocked-modules lists.

Bypass-blocking tests are expected to FAIL until the validator is hardened.
Legitimate-code tests should PASS already.
"""

import textwrap

import pytest
from runsight_core import CodeBlock

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _code(body: str) -> str:
    """Wrap a code body in a ``def main(data)`` function."""
    return textwrap.dedent(body)


# ===========================================================================
# SECTION 1 — Legitimate code that MUST keep working
# ===========================================================================


class TestLegitimateCodeStillWorks:
    """These tests should PASS both before and after hardening."""

    def test_math_operations(self):
        code = _code("""\
            import math

            def main(data):
                return {"pi": math.pi, "sqrt": math.sqrt(16)}
        """)
        block = CodeBlock("legit_math", code)
        assert block.code == code

    def test_json_operations(self):
        code = _code("""\
            import json

            def main(data):
                payload = json.dumps({"key": "value"})
                return json.loads(payload)
        """)
        block = CodeBlock("legit_json", code)
        assert block.code == code

    def test_datetime_operations(self):
        code = _code("""\
            import datetime

            def main(data):
                now = datetime.datetime.now()
                return {"year": now.year}
        """)
        block = CodeBlock("legit_datetime", code)
        assert block.code == code

    def test_re_operations(self):
        code = _code("""\
            import re

            def main(data):
                match = re.match(r"^hello", "hello world")
                return {"matched": match is not None}
        """)
        block = CodeBlock("legit_re", code)
        assert block.code == code

    def test_collections_operations(self):
        code = _code("""\
            import collections

            def main(data):
                c = collections.Counter([1, 2, 2, 3, 3, 3])
                return dict(c)
        """)
        block = CodeBlock("legit_collections", code)
        assert block.code == code

    def test_safe_builtins_len_str_int(self):
        code = _code("""\
            def main(data):
                items = [1, 2, 3]
                return {"length": len(items), "first_str": str(items[0]), "total": int(sum(items))}
        """)
        block = CodeBlock("legit_builtins", code)
        assert block.code == code

    def test_safe_builtins_list_dict_tuple(self):
        code = _code("""\
            def main(data):
                a = list(range(5))
                b = dict(x=1, y=2)
                c = tuple(a)
                return {"list": a, "dict": b, "tuple_len": len(c)}
        """)
        block = CodeBlock("legit_containers", code)
        assert block.code == code

    def test_class_definition(self):
        code = _code("""\
            class Helper:
                def greet(self, name):
                    return f"Hello, {name}"

            def main(data):
                h = Helper()
                return {"msg": h.greet("world")}
        """)
        block = CodeBlock("legit_class", code)
        assert block.code == code

    def test_function_definition(self):
        code = _code("""\
            def add(a, b):
                return a + b

            def main(data):
                return {"sum": add(3, 4)}
        """)
        block = CodeBlock("legit_func", code)
        assert block.code == code

    def test_list_comprehension(self):
        code = _code("""\
            def main(data):
                squares = [x ** 2 for x in range(10)]
                return {"squares": squares}
        """)
        block = CodeBlock("legit_comprehension", code)
        assert block.code == code

    def test_hashlib_and_base64(self):
        code = _code("""\
            import hashlib
            import base64

            def main(data):
                h = hashlib.sha256(b"hello").hexdigest()
                b = base64.b64encode(b"hello").decode()
                return {"hash": h, "b64": b}
        """)
        block = CodeBlock("legit_hashlib", code)
        assert block.code == code

    def test_normal_attribute_access(self):
        """Normal (non-dunder) attribute access must remain allowed."""
        code = _code("""\
            import json

            def main(data):
                result = {"items": [1, 2, 3]}
                encoded = json.dumps(result)
                return json.loads(encoded)
        """)
        block = CodeBlock("legit_attr", code)
        assert block.code == code


# ===========================================================================
# SECTION 2 — Dunder attribute access (AC: block __class__, __bases__,
#              __subclasses__, __globals__, __builtins__, __dict__)
# ===========================================================================


class TestBlockDunderAttributes:
    """AST validator must reject code that accesses dangerous dunder attrs."""

    def test_dunder_class(self):
        code = _code("""\
            def main(data):
                return str(().__class__)
        """)
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_dunder_bases(self):
        code = _code("""\
            def main(data):
                return str(().__class__.__bases__)
        """)
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_dunder_subclasses(self):
        code = _code("""\
            def main(data):
                cls = ().__class__.__bases__[0]
                return str(cls.__subclasses__())
        """)
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_dunder_globals(self):
        code = _code("""\
            def main(data):
                return str(main.__globals__)
        """)
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_dunder_builtins(self):
        code = _code("""\
            def main(data):
                return str(main.__builtins__)
        """)
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_dunder_dict(self):
        code = _code("""\
            class Foo:
                secret = 42

            def main(data):
                return str(Foo.__dict__)
        """)
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)


# ===========================================================================
# SECTION 3 — Blocked modules (AC: builtins, types, ctypes, code, _thread)
# ===========================================================================


class TestBlockedModules:
    """AST validator must reject imports of newly blocked modules.

    These modules are passed via ``allowed_imports`` so the allowlist check
    does NOT reject them first.  Only the BLOCKED_MODULES gate should catch
    them — which won't happen until the Green implementation adds these
    modules to that set.
    """

    def test_import_builtins(self):
        code = _code("""\
            import builtins

            def main(data):
                return {}
        """)
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code, allowed_imports=["builtins"])

    def test_import_types(self):
        code = _code("""\
            import types

            def main(data):
                return {}
        """)
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code, allowed_imports=["types"])

    def test_import_ctypes(self):
        code = _code("""\
            import ctypes

            def main(data):
                return {}
        """)
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code, allowed_imports=["ctypes"])

    def test_import_code(self):
        code = _code("""\
            import code

            def main(data):
                return {}
        """)
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code, allowed_imports=["code"])

    def test_import_thread(self):
        code = _code("""\
            import _thread

            def main(data):
                return {}
        """)
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code, allowed_imports=["_thread"])

    def test_from_builtins_import(self):
        code = _code("""\
            from builtins import __import__

            def main(data):
                return {}
        """)
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code, allowed_imports=["builtins"])

    def test_from_types_import(self):
        code = _code("""\
            from types import CodeType

            def main(data):
                return {}
        """)
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code, allowed_imports=["types"])

    def test_from_ctypes_import(self):
        code = _code("""\
            from ctypes import cdll

            def main(data):
                return {}
        """)
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code, allowed_imports=["ctypes"])


# ===========================================================================
# SECTION 4 — Blocked builtins (AC: getattr, setattr, delattr, type, vars, dir)
# ===========================================================================


class TestBlockedBuiltins:
    """AST validator must reject calls to newly blocked builtins."""

    def test_getattr_call(self):
        code = _code("""\
            def main(data):
                return getattr(data, "keys")
        """)
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_setattr_call(self):
        code = _code("""\
            class Obj:
                pass

            def main(data):
                o = Obj()
                setattr(o, "x", 1)
                return {}
        """)
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_delattr_call(self):
        code = _code("""\
            class Obj:
                x = 1

            def main(data):
                o = Obj()
                delattr(o, "x")
                return {}
        """)
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_type_call(self):
        code = _code("""\
            def main(data):
                return str(type(data))
        """)
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_vars_call(self):
        code = _code("""\
            def main(data):
                return vars(data)
        """)
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_dir_call(self):
        code = _code("""\
            def main(data):
                return dir(data)
        """)
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)


# ===========================================================================
# SECTION 5 — Combined bypass vectors from the ticket
# ===========================================================================


class TestCombinedBypassVectors:
    """End-to-end bypass scenarios from the ticket description."""

    def test_introspection_chain(self):
        """Bypass vector 1: introspection chain via dunder attributes."""
        code = _code("""\
            def main(data):
                cls = ().__class__.__bases__[0].__subclasses__()
                for c in cls:
                    if 'os' in str(c):
                        return str(c)
                return "not found"
        """)
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_getattr_builtins_bypass(self):
        """Bypass vector 2: getattr() to reach hidden attributes."""
        code = _code("""\
            def main(data):
                fn = getattr(data, 'secret')
                return fn
        """)
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_type_constructor_bypass(self):
        """Bypass vector 3: type() three-arg form to create classes dynamically."""
        code = _code("""\
            def main(data):
                Evil = type('Evil', (object,), {'run': lambda self: 'pwned'})
                return str(Evil)
        """)
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_getattr_on_module(self):
        """getattr on an allowed module to reach blocked functionality."""
        code = _code("""\
            import json

            def main(data):
                loader = getattr(json, "loads")
                return loader('{"key": "value"}')
        """)
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_dunder_class_to_reach_object(self):
        """Use __class__ on a string to reach the object hierarchy."""
        code = _code("""\
            def main(data):
                obj_class = "".__class__.__bases__[0]
                return str(obj_class)
        """)
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_type_dynamic_class_creation(self):
        """Use type() three-arg form to dynamically create classes."""
        code = _code("""\
            def main(data):
                MyClass = type('MyClass', (object,), {'x': 1})
                return str(MyClass)
        """)
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_vars_to_inspect_module(self):
        """Use vars() on an allowed module to inspect its internals."""
        code = _code("""\
            import json

            def main(data):
                return list(vars(json).keys())
        """)
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_dir_to_discover_attributes(self):
        """Use dir() to discover attributes on an object."""
        code = _code("""\
            import json

            def main(data):
                return dir(json)
        """)
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_dunder_dict_class_internals(self):
        """Access __dict__ to read class internals."""
        code = _code("""\
            def main(data):
                return list(int.__dict__.keys())
        """)
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_chained_dunder_to_globals(self):
        """Chain dunders to reach __globals__ from a function."""
        code = _code("""\
            def helper():
                pass

            def main(data):
                g = helper.__globals__
                return list(g.keys())
        """)
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)


# ===========================================================================
# SECTION 6 — Existing blocked features still blocked
# ===========================================================================


class TestExistingBlocksStillWork:
    """Sanity: the pre-existing blocks must continue to work."""

    def test_import_os_still_blocked(self):
        code = "import os\ndef main(data): return {}"
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_eval_still_blocked(self):
        code = "x = eval('1')\ndef main(data): return {}"
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_exec_still_blocked(self):
        code = "exec('pass')\ndef main(data): return {}"
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_open_still_blocked(self):
        code = "f = open('x')\ndef main(data): return {}"
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)

    def test_dunder_import_still_blocked(self):
        code = "__import__('os')\ndef main(data): return {}"
        with pytest.raises(ValueError, match="not allowed"):
            CodeBlock("x", code)
