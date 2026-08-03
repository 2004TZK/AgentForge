"""Calculator Tool：安全算术表达式求值（AST 白名单，禁止 eval）。"""
import ast
import operator

_ALLOWED_NODES = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant)
_ALLOWED_BIN_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
}
_ALLOWED_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def evaluate(expression: str) -> float:
    """求值算术表达式，如 '2 + 3 * 4'。非法表达式抛 ValueError。"""
    try:
        tree = ast.parse(expression, mode="eval")
        return _eval_node(tree.body)
    except (SyntaxError, ValueError, ZeroDivisionError, TypeError, OverflowError) as exc:
        raise ValueError(f"无法计算的表达式: {expression}") from exc


def _eval_node(node) -> float:
    if not isinstance(node, _ALLOWED_NODES):
        raise ValueError(f"表达式包含不支持的语法: {type(node).__name__}")
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("仅支持数值常量")
    if isinstance(node, ast.BinOp):
        op = _ALLOWED_BIN_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"不支持的操作符: {type(node.op).__name__}")
        return op(_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp):
        op = _ALLOWED_UNARY_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"不支持的操作符: {type(node.op).__name__}")
        return op(_eval_node(node.operand))
    raise ValueError("不支持的表达式结构")


SCHEMA = {
    "name": "calculator",
    "description": "计算算术表达式，输入如 '2 + 3 * 4'，返回数值结果。",
    "parameters": {"expression": {"type": "string", "description": "算术表达式"}},
}
