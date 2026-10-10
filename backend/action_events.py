"""Instrument observable Playwright actions without serializing their input values."""

from __future__ import annotations

import ast


MARKER = "__OUTSKILL_ACTION__:"
METHOD_ACTIONS = {
    "goto": "navigate", "click": "click", "fill": "fill", "press": "press",
    "check": "check", "uncheck": "check", "select_option": "select_option",
    "screenshot": "screenshot", "wait_for": "expect", "to_be_visible": "expect",
    "to_have_text": "expect", "to_contain_text": "expect", "to_have_url": "expect",
}


class _ActionTransformer(ast.NodeTransformer):
    def visit_Call(self, node: ast.Call) -> ast.AST:
        node = self.generic_visit(node)
        action = None
        if isinstance(node.func, ast.Attribute):
            action = METHOD_ACTIONS.get(node.func.attr)
        elif isinstance(node.func, ast.Name) and node.func.id == "expect":
            action = "expect"
        if not action or any(isinstance(child, ast.Await) for child in ast.walk(node)):
            return node
        wrapper = ast.Call(
            func=ast.Name(id="_outskill_record_action", ctx=ast.Load()),
            args=[ast.Constant(value=action), ast.Lambda(
                args=ast.arguments(posonlyargs=[], args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
                body=node,
            )],
            keywords=[],
        )
        return ast.copy_location(wrapper, node)


def insert_after_future_imports(header: str, script: str) -> str:
    """Place injected helpers after the module docstring and future imports."""
    body = ast.parse(script).body
    last_line = 0
    for index, node in enumerate(body):
        is_docstring = (
            index == 0 and isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
        )
        if is_docstring or isinstance(node, ast.ImportFrom) and node.module == "__future__":
            last_line = node.end_lineno or last_line
        else:
            break
    lines = script.splitlines(keepends=True)
    prefix = "".join(lines[:last_line])
    suffix = "".join(lines[last_line:])
    if prefix and not prefix.endswith("\n"):
        prefix += "\n"
    return prefix + header + "\n" + suffix


def instrument_script(script: str) -> str:
    tree = _ActionTransformer().visit(ast.parse(script))
    ast.fix_missing_locations(tree)
    header = '''import json as _outskill_json
def _outskill_record_action(action, call):
    print("__OUTSKILL_ACTION__:" + _outskill_json.dumps({"action":action,"phase":"started"}, separators=(",", ":")), flush=True)
    try:
        result = call()
    except Exception:
        print("__OUTSKILL_ACTION__:" + _outskill_json.dumps({"action":action,"phase":"failed"}, separators=(",", ":")), flush=True)
        raise
    print("__OUTSKILL_ACTION__:" + _outskill_json.dumps({"action":action,"phase":"finished"}, separators=(",", ":")), flush=True)
    return result
'''
    return insert_after_future_imports(header, ast.unparse(tree) + "\n")
