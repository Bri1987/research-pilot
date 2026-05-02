from difflib import unified_diff


def make_unified_diff(
    old_text: str,
    new_text: str,
    old_label: str = "old",
    new_label: str = "new",
) -> str:
    old_lines = (old_text or "").splitlines(keepends=True)
    new_lines = (new_text or "").splitlines(keepends=True)

    diff_lines = unified_diff(
        old_lines,
        new_lines,
        fromfile=old_label,
        tofile=new_label,
        lineterm="",
    )
    return "\n".join(diff_lines)
