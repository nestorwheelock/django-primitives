"""Report formatting for layer violations."""

import json
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class Violation:
    """A layer boundary violation."""

    file_path: Path
    line_number: int
    import_module: str
    from_package: str
    to_package: str
    from_layer: str
    to_layer: str
    reason: str

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "file": str(self.file_path),
            "line": self.line_number,
            "import": self.import_module,
            "from_package": self.from_package,
            "to_package": self.to_package,
            "from_layer": self.from_layer,
            "to_layer": self.to_layer,
            "reason": self.reason,
        }


def format_text(violations: list[Violation], root_dir: Path | None = None) -> str:
    """Format violations as human-readable text.

    Args:
        violations: List of violations
        root_dir: Root directory for relative paths

    Returns:
        Formatted text report
    """
    if not violations:
        return "No layer violations found."

    lines = [
        f"Found {len(violations)} layer violation(s):",
        "",
    ]

    for v in violations:
        file_display = str(v.file_path)
        if root_dir:
            try:
                file_display = str(v.file_path.relative_to(root_dir))
            except ValueError:
                file_display = str(v.file_path)  # Keep absolute if not relative to root

        lines.append(f"  {file_display}:{v.line_number}")
        lines.append(f"    Import: {v.import_module}")
        lines.append(f"    From: {v.from_package} ({v.from_layer})")
        lines.append(f"    To: {v.to_package} ({v.to_layer})")
        lines.append(f"    Reason: {v.reason}")
        lines.append("")
        lines.append(f"    Fix: Move shared code to a lower layer, or add an explicit allow rule.")
        lines.append("")

    return "\n".join(lines)


def format_json(violations: list[Violation]) -> str:
    """Format violations as JSON.

    Args:
        violations: List of violations

    Returns:
        JSON string
    """
    return json.dumps(
        {
            "violations": [v.to_dict() for v in violations],
            "count": len(violations),
        },
        indent=2,
    )
