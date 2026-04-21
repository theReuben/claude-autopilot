# Architecture Decision Records

Claude: when you make a significant technical decision, record it here.
Before making a new decision, check if a related ADR already exists.
Do NOT contradict previous ADRs without explicitly superseding them.

Format:
```
## ADR-NNN: Title
**Date:** YYYY-MM-DD
**Status:** accepted | superseded by ADR-XXX
**Context:** Why this decision was needed
**Decision:** What was decided
**Consequences:** What this means for the codebase
```

---

## ADR-001: WebSocket for Unity Communication
**Date:** 2026-04-20
**Status:** accepted
**Context:** Need a way for the Node.js MCP server to communicate with the Unity Editor plugin. Evaluated WebSocket, Unity's official MCP package, CLI batch mode, and file-based communication.
**Decision:** Use WebSocket (websocket-sharp on C# side, ws on Node.js side) on localhost:8090. Unity's official MCP package (com.unity.ai.assistant) is the backup migration target once it exits pre-release.
**Consequences:** Two-process architecture (Node.js + Unity). Must handle domain reload disconnections. Must marshal all Unity API calls to the main thread.

## ADR-002: TCP Socket for Blender Communication
**Date:** 2026-04-20
**Status:** accepted
**Context:** Blender's Python environment is embedded and can't directly host an MCP server. Need a bridge.
**Decision:** Blender addon runs a TCP socket server on localhost:9876. MCP server connects as a client. Length-prefixed JSON messages (4-byte big-endian + payload).
**Consequences:** All bpy calls must be queued to main thread via bpy.app.timers. Socket listener runs in a daemon thread.

## ADR-003: Separate FBX Files for Textures
**Date:** 2026-04-20
**Status:** accepted
**Context:** FBX can embed textures or reference external files. Unity needs to create URP materials separately.
**Decision:** Export textures as separate PNG/TGA files alongside FBX. Never embed textures. Use path_mode='COPY', embed_textures=False.
**Consequences:** Blender MCP must export textures to exports/textures/. Unity MCP must handle material creation separately after model import. Asset naming convention: {Model}_Albedo.png, {Model}_Normal.png.

## ADR-004: URP as Default Render Pipeline
**Date:** 2026-04-20
**Status:** accepted
**Context:** Unity supports Built-in, URP, and HDRP render pipelines.
**Decision:** Use Universal Render Pipeline (URP). It has the widest platform support and is sufficient for indie games.
**Consequences:** All material creation uses URP shader property names (_BaseColor, _BaseMap, etc.). Post-processing uses URP Volume system. Shader property names documented in docs/api-reference/unity-editor-api-reference.md.

## ADR-005: JSON Command Protocol
**Date:** 2026-04-20
**Status:** accepted
**Context:** Need a consistent message format for both bridges (Blender TCP and Unity WebSocket).
**Decision:** All commands use: `{ "id": "uuid", "category": "...", "command": "...", "params": {...} }`. All responses use: `{ "id": "matching-uuid", "success": bool, "data": {...}, "error": "..." }`. Blender uses a slightly simpler format (no category, uses "type" instead) — documented in CLAUDE.md.
**Consequences:** Both bridges can be tested with the same harness. Response correlation via UUID. Errors always include a human-readable message.

## ADR-006: One Handler Class Per Category
**Date:** 2026-04-20
**Status:** accepted
**Context:** Unity plugin needs to handle 50+ different commands. Single file would be unmanageable.
**Decision:** One C# class per category (SceneHandler, GameObjectHandler, etc.), each implementing ICommandHandler. CommandRouter discovers handlers via reflection.
**Consequences:** Adding a new tool category = adding a new .cs file. Claude only needs to read one handler file at a time, saving context tokens. Category names must match between TypeScript tool definitions and C# handlers.
