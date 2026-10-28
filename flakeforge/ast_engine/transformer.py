import libcst as cst
from typing import Union

class AwaitScheduleInjector(cst.CSTTransformer):
    """libcst transformer inserting `await __flake_yield__(coro_name, line_no)`

    before and around async yield points, ensuring deterministic interleaving.
    """

    def __init__(self):
        super().__init__()
        self.current_coro = "module"
        self.injected_count = 0

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        if node.asynchronous is not None:
            self.current_coro = node.name.value
        return True

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        if original_node.asynchronous is not None:
            self.current_coro = "module"
        return updated_node

    def leave_Await(
        self, original_node: cst.Await, updated_node: cst.Await
    ) -> Union[cst.Await, cst.BaseExpression]:
        # Avoid double-wrapping existing flake hooks
        if isinstance(original_node.expression, cst.Call):
            call_func = original_node.expression.func
            if isinstance(call_func, cst.Name) and call_func.value == "__flake_yield__":
                return updated_node

        self.injected_count += 1
        return updated_node

    def leave_SimpleStatementLine(
        self, original_node: cst.SimpleStatementLine, updated_node: cst.SimpleStatementLine
    ) -> Union[cst.SimpleStatementLine, cst.FlattenSentinel[cst.SimpleStatementLine]]:
        has_await = False
        for stmt in original_node.body:
            if isinstance(stmt, cst.Expr) and isinstance(stmt.value, cst.Await):
                # Don't hook an existing __flake_yield__
                if isinstance(stmt.value.expression, cst.Call):
                    fn = stmt.value.expression.func
                    if isinstance(fn, cst.Name) and fn.value == "__flake_yield__":
                        continue
                has_await = True
                break

        if not has_await or self.current_coro == "module":
            return updated_node

        yield_call = cst.Expr(
            value=cst.Await(
                expression=cst.Call(
                    func=cst.Name("__flake_yield__"),
                    args=[
                        cst.Arg(cst.SimpleString(f'"{self.current_coro}"')),
                        cst.Arg(cst.Integer("0")),
                    ]
                )
            )
        )
        self.injected_count += 1
        return cst.FlattenSentinel([
            cst.SimpleStatementLine(body=[yield_call]),
            updated_node
        ])

def instrument_code(source_code: str) -> str:
    """Parses source code with libcst, prepends runtime import and injects yield hooks."""
    tree = cst.parse_module(source_code)
    transformer = AwaitScheduleInjector()
    transformed_tree = tree.visit(transformer)

    import_stmt = "from flakeforge.scheduler.hooks import __flake_yield__\n"
    instrumented = transformed_tree.code
    if "__flake_yield__" not in source_code:
        instrumented = import_stmt + instrumented

    return instrumented
