"""Pattern management tools for FL Studio.

Provides full pattern lifecycle control: create, list, select, rename, clone,
duplicate, clear, set length, and move patterns.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastmcp import FastMCP


def register_pattern_tools(mcp: FastMCP) -> None:
    """Register pattern tools with the MCP server."""
    from fl_studio_mcp.utils.connection import get_connection

    @mcp.tool()
    def fl_get_pattern_count() -> dict:
        """Get the number of patterns in the project and the active pattern index.

        Returns:
            dict with 'count', 'max', and 'active' (index of the active pattern).
        """
        conn = get_connection()
        result = conn.send_command("patterns.count")

        if not result.get("success", False) and "error" in result:
            return {"error": result["error"]}

        return {
            "count": result.get("count", 0),
            "max": result.get("max", 999),
            "active": result.get("active", 0),
        }

    @mcp.tool()
    def fl_list_patterns() -> list[dict]:
        """List all patterns in the project with their names, lengths, and colors.

        Returns a list of pattern dictionaries:
            - index: Pattern index
            - name: Pattern name
            - length_beats: Length in beats (may be None)
            - color: Hex color (may be None)
            - is_active: Whether this is the currently active pattern
        """
        conn = get_connection()
        result = conn.send_command("patterns.list")

        if not result.get("success", False) and "error" in result:
            return [{"error": result["error"]}]

        return result.get("patterns", [])

    @mcp.tool()
    def fl_get_pattern(index: int = -1) -> dict:
        """Get detailed information about a pattern.

        Args:
            index: Pattern index. If -1, uses the currently active pattern.

        Returns:
            dict with 'index', 'name', 'length_beats', 'color', 'is_active'
        """
        conn = get_connection()
        result = conn.send_command("patterns.get", {"index": index})

        if not result.get("success", False) and "error" in result:
            return {"error": result["error"]}

        return result

    @mcp.tool()
    def fl_create_pattern(name: str = "") -> dict:
        """Create a new pattern and make it active.

        Creates a new empty pattern at the first free slot and sets it as the
        active pattern. Optionally names it.

        Args:
            name: Optional name for the new pattern

        Returns:
            dict with 'index' and 'name' of the created pattern
        """
        conn = get_connection()
        result = conn.send_command("patterns.create", {"name": name})

        if not result.get("success", False) and "error" in result:
            return {"error": result["error"]}

        return {
            "index": result.get("index", 0),
            "name": result.get("name", ""),
        }

    @mcp.tool()
    def fl_select_pattern(index: int) -> dict:
        """Select a pattern as the active pattern.

        Args:
            index: Pattern index to select

        Returns:
            dict with 'index', 'name', 'active' of the selected pattern
        """
        conn = get_connection()
        result = conn.send_command("patterns.select", {"index": index})

        if not result.get("success", False) and "error" in result:
            return {"error": result["error"]}

        return {
            "index": result.get("index", index),
            "name": result.get("name", ""),
            "active": result.get("active", -1),
        }

    @mcp.tool()
    def fl_rename_pattern(name: str, index: int = -1) -> dict:
        """Rename a pattern.

        Args:
            name: New name for the pattern
            index: Pattern index. If -1, renames the active pattern.

        Returns:
            dict with 'index' and 'name'
        """
        conn = get_connection()
        result = conn.send_command("patterns.rename", {"index": index, "name": name})

        if not result.get("success", False) and "error" in result:
            return {"error": result["error"]}

        return {
            "index": result.get("index", index),
            "name": result.get("name", name),
        }

    @mcp.tool()
    def fl_clone_pattern(index: int = -1) -> dict:
        """Clone a pattern (creates a copy of it).

        Args:
            index: Pattern index to clone. If -1, clones the active pattern.

        Returns:
            dict with 'index' and 'name' of the new cloned pattern
        """
        conn = get_connection()
        result = conn.send_command("patterns.clone", {"index": index})

        if not result.get("success", False) and "error" in result:
            return {"error": result["error"]}

        return {
            "index": result.get("index", 0),
            "name": result.get("name", ""),
        }

    @mcp.tool()
    def fl_clear_pattern(index: int = -1) -> dict:
        """Clear all data (notes, automation) from a pattern.

        Args:
            index: Pattern index to clear. If -1, clears the active pattern.

        Returns:
            dict with 'index' and 'cleared': True
        """
        conn = get_connection()
        result = conn.send_command("patterns.clear", {"index": index})

        if not result.get("success", False) and "error" in result:
            return {"error": result["error"]}

        return {"index": result.get("index", index), "cleared": True}

    @mcp.tool()
    def fl_set_pattern_length(length: int, index: int = -1) -> dict:
        """Set the length of a pattern in beats.

        Args:
            length: New pattern length in beats (e.g. 4 = one bar of 4/4, 16 = 4 bars)
            index: Pattern index. If -1, uses the active pattern.

        Returns:
            dict with 'index' and 'length_beats'
        """
        conn = get_connection()
        result = conn.send_command("patterns.setLength", {
            "index": index,
            "length": length,
        })

        if not result.get("success", False) and "error" in result:
            return {"error": result["error"]}

        return {
            "index": result.get("index", index),
            "length_beats": result.get("length_beats", length),
        }
