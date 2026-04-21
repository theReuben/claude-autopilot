"""
Blender MCP Tool Template
=========================
Copy this file and rename for each new tool category.
File: mcp-servers/blender-mcp/tools/{category_name}.py

Each tool:
1. Is decorated with @mcp.tool()
2. Is async and returns dict
3. Sends a JSON command to the Blender addon via send_to_blender()
4. Returns {"success": True/False, "data": {...}, "error": "..."}
"""

from mcp.server.fastmcp import FastMCP


def register_tools(mcp: FastMCP, send_to_blender):
    """Register all tools in this category with the MCP server.
    
    Args:
        mcp: The FastMCP server instance
        send_to_blender: async function that sends commands to Blender addon
    """

    @mcp.tool()
    async def tool_name(
        required_param: str,
        optional_param: float = 1.0,
        optional_list: list[float] = [0, 0, 0],
    ) -> dict:
        """One-line description of what this tool does.
        
        Detailed description if needed. Explain what the tool creates,
        modifies, or returns.
        
        Args:
            required_param: What this parameter controls
            optional_param: What this controls (default: 1.0)
            optional_list: [x, y, z] description (default: origin)
        """
        response = await send_to_blender({
            "type": "tool_name",
            "params": {
                "required_param": required_param,
                "optional_param": optional_param,
                "optional_list": optional_list,
            }
        })
        
        if response.get("status") == "error":
            return {
                "success": False,
                "error": response.get("message", "Unknown error"),
                "data": None,
            }
        
        return {
            "success": True,
            "data": response.get("result", {}),
            "error": None,
        }

    # Add more tools in this category below...
