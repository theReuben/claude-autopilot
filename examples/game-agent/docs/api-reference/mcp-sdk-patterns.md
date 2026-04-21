# MCP SDK Patterns — FastMCP (Python) & TypeScript SDK

---

## Python: FastMCP (Blender MCP Server)

### Installation
```bash
pip install fastmcp
```

### Server Skeleton

```python
from mcp.server.fastmcp import FastMCP
import asyncio
import json
import socket

mcp = FastMCP("blender-mcp", version="0.1.0")

# Global connection to Blender addon
_blender_socket: socket.socket | None = None

BLENDER_HOST = "127.0.0.1"
BLENDER_PORT = 9876
SOCKET_TIMEOUT = 30.0

async def connect_to_blender():
    """Connect to the Blender addon's TCP socket server."""
    global _blender_socket
    if _blender_socket:
        return
    _blender_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _blender_socket.settimeout(SOCKET_TIMEOUT)
    _blender_socket.connect((BLENDER_HOST, BLENDER_PORT))

async def send_to_blender(command: dict) -> dict:
    """Send a JSON command to Blender and wait for the response."""
    global _blender_socket
    if not _blender_socket:
        await connect_to_blender()
    
    try:
        # Send command
        data = json.dumps(command).encode('utf-8')
        length = len(data)
        _blender_socket.sendall(length.to_bytes(4, 'big') + data)
        
        # Receive response (length-prefixed)
        length_bytes = _blender_socket.recv(4)
        if not length_bytes:
            raise ConnectionError("Blender disconnected")
        length = int.from_bytes(length_bytes, 'big')
        
        response_data = b""
        while len(response_data) < length:
            chunk = _blender_socket.recv(min(4096, length - len(response_data)))
            if not chunk:
                raise ConnectionError("Blender disconnected during response")
            response_data += chunk
        
        return json.loads(response_data.decode('utf-8'))
    except (ConnectionError, socket.timeout, OSError) as e:
        _blender_socket = None  # Force reconnect next time
        return {"status": "error", "message": f"Blender connection failed: {str(e)}"}


# Tool registration
@mcp.tool()
async def get_scene_info() -> dict:
    """Get information about all objects in the current Blender scene."""
    return await send_to_blender({"type": "get_scene_info", "params": {}})


@mcp.tool()
async def create_primitive(
    shape: str,
    name: str = "Object",
    location: list[float] = [0, 0, 0],
    size: float = 1.0,
    segments: int = 32
) -> dict:
    """Create a primitive mesh object in Blender.
    
    Args:
        shape: Type of primitive — cube, sphere, cylinder, cone, plane, torus, ico_sphere
        name: Name for the new object
        location: [x, y, z] position in world space
        size: Size/radius of the primitive
        segments: Number of segments (for spheres, cylinders, etc.)
    """
    return await send_to_blender({
        "type": "create_primitive",
        "params": {
            "shape": shape,
            "name": name,
            "location": location,
            "size": size,
            "segments": segments,
        }
    })


# Resource registration (for exposing data Claude can read)
@mcp.resource("blender://scene")
async def scene_resource() -> str:
    """Current Blender scene state."""
    result = await send_to_blender({"type": "get_scene_info", "params": {}})
    return json.dumps(result, indent=2)


# Run server
if __name__ == "__main__":
    mcp.run(transport="stdio")  # stdio for Claude Code, sse for web clients
```

### Tool Parameter Types
```python
# FastMCP infers JSON Schema from Python type hints:
str        → "type": "string"
int        → "type": "integer"
float      → "type": "number"
bool       → "type": "boolean"
list[str]  → "type": "array", "items": {"type": "string"}
list[float]→ "type": "array", "items": {"type": "number"}
dict       → "type": "object"

# Optional parameters use defaults:
def my_tool(required_param: str, optional_param: float = 1.0) -> dict:
    ...

# Enum-like constraints: use Literal
from typing import Literal
def my_tool(mode: Literal["add", "subtract", "multiply"]) -> dict:
    ...
```

---

## TypeScript: MCP SDK (Unity MCP Server)

### Installation
```bash
npm init -y
npm install @modelcontextprotocol/sdk
npm install ws                    # WebSocket client to Unity
npm install uuid                  # Request correlation
npm install -D typescript @types/node @types/ws
```

### tsconfig.json
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "Node16",
    "moduleResolution": "Node16",
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "declaration": true
  },
  "include": ["src/**/*"]
}
```

### package.json (relevant parts)
```json
{
  "type": "module",
  "scripts": {
    "build": "tsc",
    "start": "node dist/index.js"
  },
  "bin": {
    "unity-mcp": "dist/index.js"
  }
}
```

### Server Skeleton (src/index.ts)

```typescript
#!/usr/bin/env node
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { UnityBridge } from "./bridge.js";

const server = new McpServer({
  name: "unity-mcp",
  version: "0.1.0",
});

const bridge = new UnityBridge("ws://localhost:8090/mcp");

// Register a tool
server.tool(
  "get_scene_hierarchy",
  "Get the full hierarchy of GameObjects in the active Unity scene",
  {},  // No parameters
  async () => {
    const result = await bridge.sendCommand("scene", "get_hierarchy", {});
    return {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
    };
  }
);

// Tool with parameters (using Zod schemas)
server.tool(
  "create_gameobject",
  "Create a new GameObject in the Unity scene",
  {
    name: z.string().describe("Name of the GameObject"),
    primitive: z.enum(["none", "cube", "sphere", "capsule", "cylinder", "plane", "quad"])
      .optional()
      .default("none")
      .describe("Primitive mesh type, or 'none' for empty GameObject"),
    position: z.object({
      x: z.number().default(0),
      y: z.number().default(0),
      z: z.number().default(0),
    }).optional().describe("World position"),
    parent: z.string().optional().describe("Path to parent GameObject in hierarchy"),
  },
  async ({ name, primitive, position, parent }) => {
    const result = await bridge.sendCommand("gameobject", "create", {
      name, primitive, position, parent,
    });
    return {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
    };
  }
);

// Tool that creates a script file
server.tool(
  "create_script",
  "Create a C# script in the Unity project",
  {
    className: z.string().describe("Name of the C# class"),
    folder: z.string().default("Scripts").describe("Folder under Assets/"),
    code: z.string().describe("Full C# source code"),
  },
  async ({ className, folder, code }) => {
    const result = await bridge.sendCommand("script", "create", {
      className, folder, code,
    });
    return {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
    };
  }
);

// Resource (readable data)
server.resource(
  "unity://project-info",
  "unity://project-info",
  async (uri) => ({
    contents: [{
      uri: uri.href,
      mimeType: "application/json",
      text: JSON.stringify(await bridge.sendCommand("project", "get_info", {}), null, 2),
    }],
  })
);

// Start server
async function main() {
  await bridge.connect();
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Unity MCP server running on stdio");
}

main().catch(console.error);
```

### WebSocket Bridge (src/bridge.ts)

```typescript
import WebSocket from "ws";
import { v4 as uuidv4 } from "uuid";

interface PendingRequest {
  resolve: (value: any) => void;
  reject: (reason: any) => void;
  timeout: NodeJS.Timeout;
}

export class UnityBridge {
  private ws: WebSocket | null = null;
  private url: string;
  private pending = new Map<string, PendingRequest>();
  private reconnectInterval = 3000;
  private commandTimeout = 30000;

  constructor(url: string) {
    this.url = url;
  }

  async connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.url);

      this.ws.on("open", () => {
        console.error(`Connected to Unity at ${this.url}`);
        resolve();
      });

      this.ws.on("message", (data: WebSocket.Data) => {
        try {
          const response = JSON.parse(data.toString());
          const pending = this.pending.get(response.id);
          if (pending) {
            clearTimeout(pending.timeout);
            this.pending.delete(response.id);
            if (response.success) {
              pending.resolve(response.data);
            } else {
              pending.reject(new Error(response.error || "Unknown Unity error"));
            }
          }
        } catch (e) {
          console.error("Failed to parse Unity response:", e);
        }
      });

      this.ws.on("close", () => {
        console.error("Unity connection closed, attempting reconnect...");
        this.ws = null;
        // Reject all pending requests
        for (const [id, pending] of this.pending) {
          clearTimeout(pending.timeout);
          pending.reject(new Error("Connection closed"));
        }
        this.pending.clear();
        // Auto-reconnect
        setTimeout(() => this.connect().catch(() => {}), this.reconnectInterval);
      });

      this.ws.on("error", (err) => {
        console.error("Unity WebSocket error:", err.message);
        if (this.ws?.readyState !== WebSocket.OPEN) {
          reject(err);
        }
      });
    });
  }

  async sendCommand(category: string, command: string, params: any): Promise<any> {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error("Not connected to Unity. Is the Unity Editor open with the MCP plugin?");
    }

    const id = uuidv4();
    const request = { id, category, command, params };

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`Unity command timed out after ${this.commandTimeout}ms: ${category}.${command}`));
      }, this.commandTimeout);

      this.pending.set(id, { resolve, reject, timeout });
      this.ws!.send(JSON.stringify(request));
    });
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
```

### Zod Schema Patterns (for tool parameters)
```typescript
import { z } from "zod";

// Reusable schemas
const Vector3Schema = z.object({
  x: z.number().default(0),
  y: z.number().default(0),
  z: z.number().default(0),
}).describe("3D vector");

const ColorSchema = z.object({
  r: z.number().min(0).max(1).default(1),
  g: z.number().min(0).max(1).default(1),
  b: z.number().min(0).max(1).default(1),
  a: z.number().min(0).max(1).default(1),
}).describe("RGBA color (0-1 range)");

const TransformSchema = z.object({
  position: Vector3Schema.optional(),
  rotation: Vector3Schema.optional().describe("Euler angles in degrees"),
  scale: Vector3Schema.optional(),
});

// Use in tool definitions
server.tool(
  "set_transform",
  "Set the transform of a GameObject",
  {
    target: z.string().describe("GameObject name or hierarchy path"),
    position: Vector3Schema.optional(),
    rotation: Vector3Schema.optional().describe("Euler angles in degrees"),
    scale: Vector3Schema.optional(),
    space: z.enum(["world", "local"]).default("world"),
  },
  async (params) => { ... }
);
```
