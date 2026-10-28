import difflib

class ASTPatcher:
    """Applies patches, extracts unified diffs, and validates Python syntax."""

    @staticmethod
    def generate_diff(original_code: str, patched_code: str, filename: str = "target.py") -> str:
        orig_lines = original_code.splitlines(keepends=True)
        patched_lines = patched_code.splitlines(keepends=True)
        diff = difflib.unified_diff(
            orig_lines,
            patched_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
            lineterm=""
        )
        return "".join(diff)

    @staticmethod
    def validate_syntax(code: str) -> bool:
        try:
            compile(code, "<string>", "exec")
            return True
        except SyntaxError:
            return False
