# Blender Python API (bpy) Reference — Game Asset Pipeline

This is a task-focused reference. It covers the bpy functions we actually use,
with working code for each. Consult this instead of searching external docs.

---

## Table of Contents
1. Scene & Object Basics
2. Mesh Creation (Primitives)
3. Mesh Creation (Custom Geometry)
4. Modifiers
5. Transforms
6. Materials & Shader Nodes
7. UV Mapping
8. Texture Baking
9. Rigging & Armatures
10. Animation & Keyframes
11. Shape Keys (Blend Shapes)
12. FBX Export (Unity-compatible)
13. glTF Export
14. Scene Inspection
15. Selection & Deletion
16. Headless / Background Mode
17. Common Context Overrides

---

## 1. Scene & Object Basics

```python
import bpy
import math

# Get active scene
scene = bpy.context.scene

# Get all objects
for obj in bpy.data.objects:
    print(obj.name, obj.type)  # MESH, ARMATURE, CAMERA, LIGHT, EMPTY, CURVE

# Get active object
obj = bpy.context.active_object

# Get selected objects
selected = bpy.context.selected_objects

# Set active object
bpy.context.view_layer.objects.active = obj

# Get object by name
obj = bpy.data.objects.get("Cube")  # Returns None if not found

# New empty scene
bpy.ops.scene.new(type='EMPTY')

# Delete everything in scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
```

## 2. Mesh Creation (Primitives)

```python
# Cube
bpy.ops.mesh.primitive_cube_add(
    size=2.0,                        # Edge length
    location=(0, 0, 0),
    rotation=(0, 0, 0),
    scale=(1, 1, 1)
)
cube = bpy.context.active_object

# UV Sphere
bpy.ops.mesh.primitive_uv_sphere_add(
    radius=1.0,
    segments=32,                      # Longitude divisions
    ring_count=16,                    # Latitude divisions
    location=(0, 0, 0)
)

# Ico Sphere (lower poly)
bpy.ops.mesh.primitive_ico_sphere_add(
    radius=1.0,
    subdivisions=2,                   # 2 = 80 faces, 3 = 320, 4 = 1280
    location=(0, 0, 0)
)

# Cylinder
bpy.ops.mesh.primitive_cylinder_add(
    radius=1.0,
    depth=2.0,
    vertices=32,                      # Circle resolution
    location=(0, 0, 0)
)

# Cone
bpy.ops.mesh.primitive_cone_add(
    radius1=1.0,                      # Base radius
    radius2=0.0,                      # Top radius (0 = point)
    depth=2.0,
    vertices=32,
    location=(0, 0, 0)
)

# Plane
bpy.ops.mesh.primitive_plane_add(
    size=2.0,
    location=(0, 0, 0)
)

# Torus
bpy.ops.mesh.primitive_torus_add(
    major_radius=1.0,
    minor_radius=0.25,
    major_segments=48,
    minor_segments=12,
    location=(0, 0, 0)
)

# Grid (subdivided plane)
bpy.ops.mesh.primitive_grid_add(
    x_subdivisions=10,
    y_subdivisions=10,
    size=2.0,
    location=(0, 0, 0)
)
```

## 3. Mesh Creation (Custom Geometry)

```python
import bmesh

# Method 1: Direct mesh data
mesh = bpy.data.meshes.new("CustomMesh")
obj = bpy.data.objects.new("CustomObject", mesh)
bpy.context.collection.objects.link(obj)

vertices = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
edges = []
faces = [(0, 1, 2, 3)]
mesh.from_pydata(vertices, edges, faces)
mesh.update()

# Method 2: BMesh (more powerful, supports edit operations)
bm = bmesh.new()
v1 = bm.verts.new((0, 0, 0))
v2 = bm.verts.new((1, 0, 0))
v3 = bm.verts.new((1, 1, 0))
v4 = bm.verts.new((0, 1, 0))
bm.faces.new((v1, v2, v3, v4))
bm.to_mesh(mesh)
bm.free()

# Method 3: BMesh from existing mesh
obj = bpy.context.active_object
bm = bmesh.new()
bm.from_mesh(obj.data)
# ... operations ...
bm.to_mesh(obj.data)
bm.free()
obj.data.update()
```

## 4. Modifiers

```python
obj = bpy.context.active_object

# Subdivision Surface
mod = obj.modifiers.new(name="Subsurf", type='SUBSURF')
mod.levels = 2              # Viewport
mod.render_levels = 3        # Render

# Mirror
mod = obj.modifiers.new(name="Mirror", type='MIRROR')
mod.use_axis = (True, False, False)  # Mirror on X
mod.use_clip = True

# Array
mod = obj.modifiers.new(name="Array", type='ARRAY')
mod.count = 5
mod.relative_offset_displace = (1.0, 0.0, 0.0)

# Bevel
mod = obj.modifiers.new(name="Bevel", type='BEVEL')
mod.width = 0.02
mod.segments = 3
mod.limit_method = 'ANGLE'
mod.angle_limit = math.radians(30)

# Decimate (for LOD generation)
mod = obj.modifiers.new(name="Decimate", type='DECIMATE')
mod.decimate_type = 'COLLAPSE'  # or 'UNSUBDIV', 'DISSOLVE'
mod.ratio = 0.5                  # Keep 50% of faces

# Solidify (give thickness to flat surfaces)
mod = obj.modifiers.new(name="Solidify", type='SOLIDIFY')
mod.thickness = 0.1

# Boolean
mod = obj.modifiers.new(name="Boolean", type='BOOLEAN')
mod.operation = 'DIFFERENCE'     # or 'UNION', 'INTERSECT'
mod.object = bpy.data.objects["CutterObject"]

# Smooth
mod = obj.modifiers.new(name="Smooth", type='SMOOTH')
mod.factor = 0.5
mod.iterations = 5

# Apply a modifier (makes it permanent)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.modifier_apply(modifier="Subsurf")

# Apply all modifiers
for mod in obj.modifiers:
    bpy.ops.object.modifier_apply(modifier=mod.name)
```

## 5. Transforms

```python
obj = bpy.data.objects["MyObject"]

# Position
obj.location = (1.0, 2.0, 3.0)
obj.location.x = 5.0

# Rotation (Euler, in radians)
obj.rotation_euler = (0, 0, math.radians(45))
obj.rotation_mode = 'XYZ'  # or 'QUATERNION'

# Rotation (Quaternion)
obj.rotation_mode = 'QUATERNION'
obj.rotation_quaternion = (1, 0, 0, 0)  # w, x, y, z

# Scale
obj.scale = (2.0, 2.0, 2.0)

# Apply transforms (reset to identity, bake into mesh)
bpy.context.view_layer.objects.active = obj
obj.select_set(True)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# Parent
child.parent = parent_obj
child.matrix_parent_inverse = parent_obj.matrix_world.inverted()

# Unparent
child.parent = None

# Duplicate
bpy.context.view_layer.objects.active = obj
obj.select_set(True)
bpy.ops.object.duplicate(linked=False)
duplicate = bpy.context.active_object

# Duplicate via data copy (faster, no ops context needed)
new_obj = obj.copy()
new_obj.data = obj.data.copy()  # Deep copy mesh data
new_obj.name = "Duplicate"
bpy.context.collection.objects.link(new_obj)
```

## 6. Materials & Shader Nodes

```python
# Create PBR material
mat = bpy.data.materials.new(name="MAT_MyMaterial")
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links

# Get Principled BSDF (exists by default)
principled = nodes.get("Principled BSDF")

# Set PBR properties
principled.inputs["Base Color"].default_value = (0.8, 0.2, 0.1, 1.0)  # RGBA
principled.inputs["Roughness"].default_value = 0.5
principled.inputs["Metallic"].default_value = 0.0
principled.inputs["IOR"].default_value = 1.45
principled.inputs["Alpha"].default_value = 1.0

# Emission
principled.inputs["Emission Color"].default_value = (1, 1, 1, 1)
principled.inputs["Emission Strength"].default_value = 2.0

# Add image texture
tex_node = nodes.new(type='ShaderNodeTexImage')
tex_node.location = (-400, 300)
img = bpy.data.images.load("/path/to/texture.png")
tex_node.image = img
links.new(tex_node.outputs["Color"], principled.inputs["Base Color"])

# Add normal map
normal_map = nodes.new(type='ShaderNodeNormalMap')
normal_map.location = (-200, -200)
normal_tex = nodes.new(type='ShaderNodeTexImage')
normal_tex.location = (-500, -200)
normal_tex.image = bpy.data.images.load("/path/to/normal.png")
normal_tex.image.colorspace_settings.name = 'Non-Color'
links.new(normal_tex.outputs["Color"], normal_map.inputs["Color"])
links.new(normal_map.outputs["Normal"], principled.inputs["Normal"])

# Procedural: Noise texture
noise = nodes.new(type='ShaderNodeTexNoise')
noise.inputs["Scale"].default_value = 5.0
noise.inputs["Detail"].default_value = 2.0
noise.location = (-400, 0)

# Procedural: Voronoi
voronoi = nodes.new(type='ShaderNodeTexVoronoi')
voronoi.inputs["Scale"].default_value = 10.0

# Procedural: Color ramp (for mapping values to colors)
ramp = nodes.new(type='ShaderNodeValToRGB')
ramp.color_ramp.elements[0].color = (0.1, 0.05, 0.02, 1)
ramp.color_ramp.elements[1].color = (0.4, 0.3, 0.2, 1)

# Mix shader
mix = nodes.new(type='ShaderNodeMixShader')

# Assign material to object
obj = bpy.data.objects["MyObject"]
if obj.data.materials:
    obj.data.materials[0] = mat      # Replace first slot
else:
    obj.data.materials.append(mat)   # Add new slot

# Assign material to specific faces (requires edit mode via bmesh)
```

## 7. UV Mapping

```python
obj = bpy.context.active_object
bpy.context.view_layer.objects.active = obj
obj.select_set(True)

# Smart UV Project (best general-purpose auto unwrap)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(
    angle_limit=math.radians(66),
    island_margin=0.02,
    area_weight=0.0,
    correct_aspect=True
)
bpy.ops.object.mode_set(mode='OBJECT')

# Cube Projection
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.cube_project(cube_size=1.0)
bpy.ops.object.mode_set(mode='OBJECT')

# Cylinder Projection
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.cylinder_project(direction='VIEW_ON_EQUATOR')
bpy.ops.object.mode_set(mode='OBJECT')

# Sphere Projection
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.sphere_project()
bpy.ops.object.mode_set(mode='OBJECT')

# Unwrap (requires seams to be marked first)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=0.02)
bpy.ops.object.mode_set(mode='OBJECT')

# Mark seams (via bmesh for programmatic control)
import bmesh
bm = bmesh.new()
bm.from_mesh(obj.data)
for edge in bm.edges:
    # Example: mark edges above certain angle as seams
    if edge.calc_face_angle(0) > math.radians(60):
        edge.seam = True
bm.to_mesh(obj.data)
bm.free()
```

## 8. Texture Baking

```python
# Bake procedural material to image texture
obj = bpy.context.active_object

# Create target image
img = bpy.data.images.new("BakedTexture", width=1024, height=1024)

# Add image texture node to material (set as active for bake target)
mat = obj.data.materials[0]
nodes = mat.node_tree.nodes
img_node = nodes.new(type='ShaderNodeTexImage')
img_node.image = img
img_node.select = True
nodes.active = img_node

# Must have UV map
# Bake settings
bpy.context.scene.render.engine = 'CYCLES'  # Baking requires Cycles
bpy.context.scene.cycles.bake_type = 'DIFFUSE'  # or 'NORMAL', 'ROUGHNESS', 'EMIT', 'COMBINED'
bpy.context.scene.cycles.samples = 128

# For diffuse color only (no lighting contribution)
bpy.context.scene.render.bake.use_pass_direct = False
bpy.context.scene.render.bake.use_pass_indirect = False
bpy.context.scene.render.bake.use_pass_color = True

# Bake
bpy.ops.object.bake(type='DIFFUSE')

# Save
img.filepath_raw = "/path/to/BakedTexture.png"
img.file_format = 'PNG'
img.save()
```

## 9. Rigging & Armatures

```python
# Create armature
bpy.ops.object.armature_add(location=(0, 0, 0))
armature_obj = bpy.context.active_object
armature_obj.name = "Armature"
armature = armature_obj.data

# Add bones in edit mode
bpy.ops.object.mode_set(mode='EDIT')
edit_bones = armature.edit_bones

# The default bone
root = edit_bones[0]
root.name = "Root"
root.head = (0, 0, 0)
root.tail = (0, 0, 0.5)

# Add child bone
spine = edit_bones.new("Spine")
spine.head = (0, 0, 0.5)
spine.tail = (0, 0, 1.0)
spine.parent = root

# Add more bones
chest = edit_bones.new("Chest")
chest.head = (0, 0, 1.0)
chest.tail = (0, 0, 1.5)
chest.parent = spine

# Left arm chain
upper_arm_l = edit_bones.new("UpperArm.L")
upper_arm_l.head = (0.2, 0, 1.4)
upper_arm_l.tail = (0.6, 0, 1.4)
upper_arm_l.parent = chest

bpy.ops.object.mode_set(mode='OBJECT')

# Parent mesh to armature with automatic weights
mesh_obj = bpy.data.objects["MyCharacter"]
mesh_obj.select_set(True)
armature_obj.select_set(True)
bpy.context.view_layer.objects.active = armature_obj
bpy.ops.object.parent_set(type='ARMATURE_AUTO')

# Manual vertex group assignment
vg = mesh_obj.vertex_groups.new(name="Spine")
vg.add([0, 1, 2, 3], 1.0, 'REPLACE')  # vertex indices, weight, mode
```

## 10. Animation & Keyframes

```python
obj = bpy.data.objects["MyObject"]
scene = bpy.context.scene

# Set frame range
scene.frame_start = 1
scene.frame_end = 60
scene.render.fps = 30

# Insert keyframes
obj.location = (0, 0, 0)
obj.keyframe_insert(data_path="location", frame=1)

obj.location = (5, 0, 0)
obj.keyframe_insert(data_path="location", frame=30)

obj.location = (0, 0, 0)
obj.keyframe_insert(data_path="location", frame=60)

# Rotation keyframes
obj.rotation_euler = (0, 0, 0)
obj.keyframe_insert(data_path="rotation_euler", frame=1)

obj.rotation_euler = (0, 0, math.radians(360))
obj.keyframe_insert(data_path="rotation_euler", frame=60)

# Armature bone animation (pose mode)
armature_obj = bpy.data.objects["Armature"]
bpy.context.view_layer.objects.active = armature_obj
bpy.ops.object.mode_set(mode='POSE')

bone = armature_obj.pose.bones["Spine"]
bone.rotation_euler = (math.radians(15), 0, 0)
bone.keyframe_insert(data_path="rotation_euler", frame=1)

bone.rotation_euler = (math.radians(-15), 0, 0)
bone.keyframe_insert(data_path="rotation_euler", frame=30)

bpy.ops.object.mode_set(mode='OBJECT')

# NLA strips (for exporting separate animation clips)
armature_obj = bpy.data.objects["Armature"]
action = armature_obj.animation_data.action
track = armature_obj.animation_data.nla_tracks.new()
track.name = "Walk"
strip = track.strips.new(action.name, int(action.frame_range[0]), action)

# Set interpolation on all keyframes
if obj.animation_data and obj.animation_data.action:
    for fcurve in obj.animation_data.action.fcurves:
        for kp in fcurve.keyframe_points:
            kp.interpolation = 'LINEAR'  # or 'BEZIER', 'CONSTANT'
```

## 11. Shape Keys (Blend Shapes / Morph Targets)

```python
obj = bpy.data.objects["MyCharacter"]

# Add basis shape key (reference shape — must be first)
obj.shape_key_add(name="Basis", from_mix=False)

# Add morph target
sk = obj.shape_key_add(name="Smile", from_mix=False)
# Modify vertices in the shape key
for i, vert in enumerate(sk.data):
    if i in mouth_vertex_indices:  # your list of mouth vertices
        vert.co.z += 0.1  # Move up

# Set shape key value (0.0 = basis, 1.0 = fully morphed)
obj.data.shape_keys.key_blocks["Smile"].value = 0.5

# Animate shape key
obj.data.shape_keys.key_blocks["Smile"].value = 0.0
obj.data.shape_keys.key_blocks["Smile"].keyframe_insert("value", frame=1)

obj.data.shape_keys.key_blocks["Smile"].value = 1.0
obj.data.shape_keys.key_blocks["Smile"].keyframe_insert("value", frame=30)
```

## 12. FBX Export (Unity-Compatible)

```python
# ALWAYS USE THESE SETTINGS FOR UNITY
bpy.ops.export_scene.fbx(
    filepath="/path/to/exports/models/Character_Hero.fbx",
    use_selection=True,           # Only export selected objects
    global_scale=1.0,
    apply_unit_scale=True,
    apply_scale_options='FBX_SCALE_ALL',
    axis_forward='-Z',
    axis_up='Y',
    use_mesh_modifiers=True,      # Apply modifiers before export
    mesh_smooth_type='FACE',
    use_subsurf=False,
    use_mesh_edges=False,
    use_tspace=True,              # Export tangent space (needed for normal maps)
    use_custom_props=False,
    add_leaf_bones=False,         # IMPORTANT: Unity doesn't need leaf bones
    primary_bone_axis='Y',
    secondary_bone_axis='X',
    use_armature_deform_only=True,
    armature_nodetype='NULL',
    bake_anim=True,
    bake_anim_use_all_bones=True,
    bake_anim_use_nla_strips=False,
    bake_anim_use_all_actions=False,
    bake_anim_force_startend_keying=True,
    bake_anim_step=1.0,
    bake_anim_simplify_factor=1.0,
    path_mode='COPY',            # Copy textures alongside FBX
    embed_textures=False,         # Keep textures as separate files
    batch_mode='OFF',
)

# Export animation only (no mesh)
bpy.ops.export_scene.fbx(
    filepath="/path/to/exports/animations/Hero@Walk.fbx",
    use_selection=True,
    global_scale=1.0,
    apply_unit_scale=True,
    apply_scale_options='FBX_SCALE_ALL',
    axis_forward='-Z',
    axis_up='Y',
    object_types={'ARMATURE'},    # Only armature, no mesh
    add_leaf_bones=False,
    bake_anim=True,
    bake_anim_use_all_bones=True,
)
```

## 13. glTF Export

```python
bpy.ops.export_scene.gltf(
    filepath="/path/to/export.glb",
    export_format='GLB',          # or 'GLTF_SEPARATE', 'GLTF_EMBEDDED'
    use_selection=True,
    export_apply=True,            # Apply modifiers
    export_animations=True,
    export_draco_mesh_compression_enable=True,
    export_draco_mesh_compression_level=6,
    export_materials='EXPORT',
    export_colors=True,
    export_normals=True,
    export_tangents=True,
    export_yup=True,              # Unity uses Y-up
)
```

## 14. Scene Inspection

```python
# Get all objects with details
for obj in bpy.data.objects:
    info = {
        "name": obj.name,
        "type": obj.type,
        "location": list(obj.location),
        "rotation": [math.degrees(r) for r in obj.rotation_euler],
        "scale": list(obj.scale),
        "visible": obj.visible_get(),
        "parent": obj.parent.name if obj.parent else None,
    }
    if obj.type == 'MESH':
        mesh = obj.data
        info["vertices"] = len(mesh.vertices)
        info["faces"] = len(mesh.polygons)
        info["triangles"] = sum(len(p.vertices) - 2 for p in mesh.polygons)
        info["materials"] = [m.name for m in obj.data.materials if m]
        info["has_uv"] = len(mesh.uv_layers) > 0
        info["uv_layers"] = [uv.name for uv in mesh.uv_layers]
        # Bounding box
        info["bounds"] = {
            "min": [min(v.co[i] for v in mesh.vertices) for i in range(3)],
            "max": [max(v.co[i] for v in mesh.vertices) for i in range(3)],
        }

# Check mesh validity
def validate_mesh(obj):
    issues = []
    mesh = obj.data
    tri_count = sum(len(p.vertices) - 2 for p in mesh.polygons)
    if tri_count > 15000:
        issues.append(f"High triangle count: {tri_count}")
    if len(mesh.uv_layers) == 0:
        issues.append("No UV map")
    if len(obj.data.materials) == 0:
        issues.append("No materials assigned")
    if len(obj.data.materials) > 3:
        issues.append(f"Too many material slots: {len(obj.data.materials)}")
    # Check for non-manifold edges
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(mesh)
    non_manifold = [e for e in bm.edges if not e.is_manifold]
    if non_manifold:
        issues.append(f"Non-manifold edges: {len(non_manifold)}")
    bm.free()
    return issues
```

## 15. Selection & Deletion

```python
# Select by name
obj = bpy.data.objects.get("Cube")
if obj:
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

# Select all
bpy.ops.object.select_all(action='SELECT')

# Deselect all
bpy.ops.object.select_all(action='DESELECT')

# Select by type
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        obj.select_set(True)

# Select by name pattern
import fnmatch
for obj in bpy.data.objects:
    if fnmatch.fnmatch(obj.name, "Enemy_*"):
        obj.select_set(True)

# Delete selected
bpy.ops.object.delete()

# Delete specific object (no context needed)
bpy.data.objects.remove(obj, do_unlink=True)

# Delete all mesh data (cleanup orphans)
for mesh in bpy.data.meshes:
    if mesh.users == 0:
        bpy.data.meshes.remove(mesh)
```

## 16. Headless / Background Mode

```bash
# Run Blender in background with a script
blender --background --python my_script.py

# Run with a specific .blend file
blender myfile.blend --background --python my_script.py

# With arguments after --
blender --background --python my_script.py -- --my-arg value
```

```python
# In the script, get custom arguments
import sys
argv = sys.argv
argv = argv[argv.index("--") + 1:]  # Everything after --
```

## 17. Common Context Overrides

```python
# When bpy.ops complains about wrong context, use temp_override (Blender 3.2+)
# Find the right area/region
def get_3d_view_context():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        return window, area, region
    return None, None, None

window, area, region = get_3d_view_context()
if area:
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.mesh.primitive_cube_add()

# Alternative: prefer bpy.data over bpy.ops when possible
# bpy.data operations don't need context at all
mesh = bpy.data.meshes.new("Cube")
obj = bpy.data.objects.new("Cube", mesh)
bpy.context.collection.objects.link(obj)
# Build mesh data directly...
```

---

## Performance Budget Defaults

| Asset Type | Max Triangles | Max Materials | Max Bones | Max Texture Size |
|---|---|---|---|---|
| Player Character | 10,000–15,000 | 2–3 | 50 | 2048×2048 |
| NPC / Enemy | 5,000–10,000 | 2 | 40 | 1024×1024 |
| Large Prop | 2,000–5,000 | 2 | 0 | 1024×1024 |
| Small Prop | 200–1,000 | 1 | 0 | 512×512 |
| Environment Piece | 1,000–10,000 | 2 | 0 | 2048×2048 |
| UI Element | 4–100 | 1 | 0 | 512×512 |
