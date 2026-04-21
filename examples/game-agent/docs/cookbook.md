# Cookbook — Known Issues & Solutions

Add every non-obvious bug fix, API quirk, or workaround here as you discover it.
Future sessions read this before debugging to avoid re-solving known problems.

---

## Blender

### bpy.ops "context is incorrect" error
**Problem:** Most `bpy.ops.*` functions fail with "RuntimeError: Operator bpy.ops.X.poll() failed, context is incorrect" when called from a script or addon.
**Solution:** Use `bpy.context.temp_override()` to provide the correct context:
```python
window = bpy.context.window_manager.windows[0]
area = [a for a in window.screen.areas if a.type == 'VIEW_3D'][0]
region = [r for r in area.regions if r.type == 'WINDOW'][0]
with bpy.context.temp_override(window=window, area=area, region=region):
    bpy.ops.mesh.primitive_cube_add()
```
**Better solution:** Prefer `bpy.data.*` direct manipulation over `bpy.ops.*` whenever possible. It's faster, has no context requirements, and is more reliable in headless mode.

### bpy calls from non-main thread crash Blender
**Problem:** Calling any bpy function from the TCP socket listener thread causes segfaults or undefined behavior.
**Solution:** The addon uses `bpy.app.timers.register()` to create a polling function that runs on the main thread. The socket listener puts commands into a thread-safe queue, and the timer callback processes them.
```python
import queue
command_queue = queue.Queue()

def process_queue():
    try:
        while not command_queue.empty():
            cmd, response_callback = command_queue.get_nowait()
            result = execute_command(cmd)
            response_callback(result)
    except Exception as e:
        print(f"Error processing command: {e}")
    return 0.05  # Run every 50ms

bpy.app.timers.register(process_queue)
```

### FBX export scale issues
**Problem:** Models appear 100x too large or too small in Unity.
**Solution:** Use EXACTLY these settings:
- `global_scale=1.0`
- `apply_unit_scale=True`
- `apply_scale_options='FBX_SCALE_ALL'`
And in Unity ModelImporter: `useFileScale=true`, `globalScale=1`.

### FBX leaf bones
**Problem:** Unity shows extra bones at the end of each chain (LeafBone_End).
**Solution:** Set `add_leaf_bones=False` in the FBX export call.

### Materials don't transfer via FBX
**Problem:** Exported FBX shows default material in Unity despite having materials in Blender.
**Solution:** Materials can't reliably transfer via FBX. Instead:
1. Bake procedural textures to image files in Blender
2. Export textures as separate files alongside FBX (`path_mode='COPY'`, `embed_textures=False`)
3. In Unity, create URP materials and assign textures manually (or via MCP tool)

### Headless mode rendering
**Problem:** `bpy.ops.render.render()` fails or produces black images in `--background` mode.
**Solution:** Set render engine explicitly and configure output:
```python
bpy.context.scene.render.engine = 'CYCLES'  # or 'BLENDER_EEVEE_NEXT'
bpy.context.scene.render.resolution_x = 512
bpy.context.scene.render.resolution_y = 512
bpy.context.scene.render.filepath = "/path/to/output.png"
bpy.ops.render.render(write_still=True)
```
Note: EEVEE may not work in background mode on some systems. Cycles always works.

### Socket partial reads
**Problem:** Large JSON responses from Blender are truncated or split across multiple recv() calls.
**Solution:** Use length-prefixed messages. Send 4 bytes (big-endian uint32) with the message length, then the JSON payload. On receive, read exactly that many bytes.

---

## Unity

### WebSocket breaks on domain reload
**Problem:** Entering Play Mode with domain reload enabled destroys all static state, including the WebSocket server.
**Solution:** Either:
1. Disable domain reload: Edit > Project Settings > Editor > Enter Play Mode Settings > Reload Domain = OFF
2. Or implement reconnection: use `[InitializeOnLoad]` to restart the server after domain reload, and have the Node.js client auto-reconnect with a retry loop.

### ModelImporter changes don't apply
**Problem:** You set properties on ModelImporter but the model doesn't change.
**Solution:** MUST call `importer.SaveAndReimport()` after changing settings. `AssetDatabase.Refresh()` alone is not enough for import settings.

### Script compilation is async
**Problem:** After writing a .cs file and calling `AssetDatabase.Refresh()`, trying to use `System.Type.GetType("MyNewClass")` returns null.
**Solution:** Compilation happens asynchronously. You must wait:
```csharp
CompilationPipeline.compilationFinished += (obj) => {
    // NOW the type is available
    var type = AppDomain.CurrentDomain.GetAssemblies()
        .SelectMany(a => a.GetTypes())
        .FirstOrDefault(t => t.Name == "MyNewClass");
};
```
For MCP tools, return a response indicating compilation started, and provide a separate `get_compilation_status` tool.

### PrefabUtility requires scene object
**Problem:** `PrefabUtility.SaveAsPrefabAsset(go, path)` fails if `go` isn't in the scene.
**Solution:** Always create the GameObject in the scene first, then save as prefab. If you want a prefab-only asset (no scene instance), destroy the scene instance after saving:
```csharp
var prefab = PrefabUtility.SaveAsPrefabAsset(go, path);
Object.DestroyImmediate(go);
```

### SerializedProperty field names
**Problem:** `SerializedObject.FindProperty("mass")` returns null for a Rigidbody.
**Solution:** Internal serialized field names often start with `m_` prefix: `FindProperty("m_Mass")`. To discover the correct name, iterate all properties:
```csharp
var so = new SerializedObject(component);
var iter = so.GetIterator();
iter.Next(true);
do { Debug.Log(iter.propertyPath); } while (iter.Next(false));
```

### DestroyImmediate vs Destroy
**Problem:** `Object.Destroy()` doesn't work in Editor scripts.
**Solution:** In Editor code (non-play-mode), always use `Object.DestroyImmediate()`. `Destroy()` only works at runtime.

### AddComponent by string
**Problem:** `go.AddComponent("MyScript")` is obsolete and unreliable.
**Solution:** Use reflection to find the type, then add by type:
```csharp
var type = TypeCache.GetTypesDerivedFrom<Component>()
    .FirstOrDefault(t => t.Name == typeName);
if (type != null) go.AddComponent(type);
```

### URP shader property names
**Problem:** URP Lit shader uses different property names than Standard shader.
**Solution:** Key URP Lit properties:
- `_BaseColor` (not `_Color`)
- `_BaseMap` (not `_MainTex`)
- `_BumpMap` (normal map)
- `_BumpScale` (normal strength)
- `_Metallic`, `_Smoothness`
- `_MetallicGlossMap`
- `_EmissionColor`, `_EmissionMap`
- `_Surface` (0=Opaque, 1=Transparent)
- `_Cull` (0=Off, 1=Front, 2=Back)

### WebSocket library: websocket-sharp quirks
**Problem:** websocket-sharp's `OnMessage` callback runs on a background thread.
**Solution:** Never call Unity APIs from `OnMessage`. Always queue the message for main-thread processing via `EditorApplication.update`.

---

## MCP Protocol

### stdio transport buffering
**Problem:** MCP server using stdio doesn't receive messages or output is delayed.
**Solution:** Ensure stdout is unbuffered. In Python: `sys.stdout.reconfigure(line_buffering=False)` or let FastMCP handle it. In Node.js: this is typically handled by the SDK.

### Tool response format
**Problem:** Claude doesn't see tool results.
**Solution:** Tool handlers MUST return `{ content: [{ type: "text", text: "..." }] }`. The text field should be a JSON string of the result, not a raw object.

---

## Integration (Blender → Unity Pipeline)

### Bone orientation mismatch
**Problem:** Character is oriented wrong or animations are rotated 90° in Unity.
**Solution:** In Blender, ensure the armature's forward axis is -Y (Blender convention) before export. The FBX export with `axis_forward='-Z', axis_up='Y'` handles the conversion. If still wrong, check that `apply_scale_options='FBX_SCALE_ALL'` is set.

### Multiple animation clips from one FBX
**Problem:** Unity imports all animations as a single clip.
**Solution:** Either:
1. Export each animation as a separate FBX file (`Character@Walk.fbx`, `Character@Run.fbx`)
2. Or use NLA strips in Blender and configure the ModelImporter's clip ranges in Unity

### Texture path issues
**Problem:** Unity can't find textures after FBX import.
**Solution:** Export textures to the same directory as the FBX, or to a `Textures/` subfolder next to it. In ModelImporter, set `materialLocation = InPrefab` and use `AssetDatabase.FindAssets` to locate texture files by name.

---

*Add new entries above this line. Date and context help future sessions.*
