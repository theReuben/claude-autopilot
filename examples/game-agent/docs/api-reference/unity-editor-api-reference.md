# Unity Editor API Reference — MCP Tool Operations

Task-focused reference for Unity Editor scripting used by our MCP handlers.
All code runs in the Editor (not at runtime). Namespace: `UnityEditor`.

---

## Table of Contents
1. Scene Management
2. GameObject Operations
3. Transform
4. Component Management
5. Serialized Properties (Generic Field Access)
6. Script Generation & Compilation
7. Prefab System
8. Asset Database & Import
9. Material Creation (URP)
10. Animator Controllers
11. Physics Setup
12. UI (Canvas)
13. Lighting & Post-Processing
14. Play Mode & Console
15. Build Pipeline
16. Test Runner
17. WebSocket Server (C# side)

---

## 1. Scene Management

```csharp
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

// Create new scene
var scene = EditorSceneManager.NewScene(
    NewSceneSetup.DefaultGameObjects,  // or EmptyScene
    NewSceneMode.Single                // or Additive
);

// Open existing scene
EditorSceneManager.OpenScene("Assets/Scenes/Level1.unity", OpenSceneMode.Single);

// Save current scene
EditorSceneManager.SaveScene(SceneManager.GetActiveScene());

// Save scene as
EditorSceneManager.SaveScene(SceneManager.GetActiveScene(), "Assets/Scenes/NewScene.unity");

// Get active scene info
var scene = SceneManager.GetActiveScene();
string name = scene.name;
string path = scene.path;
bool isDirty = scene.isDirty;
int rootCount = scene.rootCount;
GameObject[] roots = scene.GetRootGameObjects();

// Get full hierarchy
void GetHierarchy(Transform parent, int depth, List<object> result)
{
    foreach (Transform child in parent)
    {
        result.Add(new {
            name = child.name,
            path = GetGameObjectPath(child.gameObject),
            active = child.gameObject.activeSelf,
            layer = LayerMask.LayerToName(child.gameObject.layer),
            tag = child.gameObject.tag,
            components = child.GetComponents<Component>()
                .Select(c => c.GetType().Name).ToArray(),
            childCount = child.childCount,
            depth = depth
        });
        GetHierarchy(child, depth + 1, result);
    }
}

string GetGameObjectPath(GameObject go)
{
    string path = go.name;
    Transform t = go.transform.parent;
    while (t != null)
    {
        path = t.name + "/" + path;
        t = t.parent;
    }
    return path;
}
```

## 2. GameObject Operations

```csharp
// Create empty
var go = new GameObject("MyObject");

// Create primitive
var cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
// PrimitiveType: Cube, Sphere, Capsule, Cylinder, Plane, Quad

// Create from prefab
var prefab = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Prefabs/Wolf.prefab");
var instance = (GameObject)PrefabUtility.InstantiatePrefab(prefab);

// Find by name
var go = GameObject.Find("Player");  // Finds active GameObjects only

// Find by path in hierarchy
var go = GameObject.Find("Environment/Props/Barrel_01");

// Find all by tag
var enemies = GameObject.FindGameObjectsWithTag("Enemy");

// Find all by component type
var allRenderers = Object.FindObjectsByType<MeshRenderer>(FindObjectsSortMode.None);

// Set active
go.SetActive(false);

// Destroy
Object.DestroyImmediate(go);  // Use DestroyImmediate in Editor (not Destroy)

// Duplicate
var duplicate = Object.Instantiate(go);
duplicate.name = "Duplicate";

// Set parent
go.transform.SetParent(parentTransform, worldPositionStays: true);

// Set layer
go.layer = LayerMask.NameToLayer("Enemies");

// Set tag
go.tag = "Player";

// Register undo (important for Editor tools)
Undo.RegisterCreatedObjectUndo(go, "Create Object");
```

## 3. Transform

```csharp
Transform t = go.transform;

// World space
t.position = new Vector3(1, 2, 3);
t.rotation = Quaternion.Euler(0, 90, 0);
t.localScale = new Vector3(1, 1, 1);  // Scale is always local

// Local space
t.localPosition = new Vector3(0, 1, 0);
t.localRotation = Quaternion.identity;

// Look at
t.LookAt(targetTransform);
t.LookAt(new Vector3(0, 0, 0));

// Move
t.Translate(new Vector3(1, 0, 0), Space.World);

// Rotate
t.Rotate(new Vector3(0, 45, 0), Space.Self);

// Hierarchy
t.SetParent(parentTransform);
t.SetSiblingIndex(0);  // Move to top of parent's children
Transform child = t.GetChild(0);
int childCount = t.childCount;

// Reset
t.localPosition = Vector3.zero;
t.localRotation = Quaternion.identity;
t.localScale = Vector3.one;
```

## 4. Component Management

```csharp
// Add component by generic type
var rb = go.AddComponent<Rigidbody>();

// Add component by type name (string) — useful for MCP tools
System.Type type = System.Type.GetType("UnityEngine.Rigidbody, UnityEngine.PhysicsModule");
if (type == null)
    type = TypeCache.GetTypesDerivedFrom<Component>()
        .FirstOrDefault(t => t.Name == "Rigidbody");
if (type != null)
    go.AddComponent(type);

// Get component
var renderer = go.GetComponent<MeshRenderer>();

// Get all components
var components = go.GetComponents<Component>();
foreach (var comp in components)
{
    Debug.Log($"{comp.GetType().Name}");
}

// Remove component
Object.DestroyImmediate(go.GetComponent<BoxCollider>());

// Check if has component
bool hasColl = go.TryGetComponent<Collider>(out var collider);
```

## 5. Serialized Properties (Generic Field Access)

This is how MCP tools read/write arbitrary component fields without
knowing the type at compile time.

```csharp
using UnityEditor;

Component component = go.GetComponent("Rigidbody");
var so = new SerializedObject(component);

// Read properties
SerializedProperty prop = so.FindProperty("m_Mass");
float mass = prop.floatValue;

// Write properties
prop.floatValue = 5.0f;
so.ApplyModifiedProperties();

// Property types and their value accessors:
// prop.intValue           — int
// prop.floatValue         — float
// prop.boolValue          — bool
// prop.stringValue        — string
// prop.vector2Value       — Vector2
// prop.vector3Value       — Vector3
// prop.vector4Value       — Vector4
// prop.quaternionValue    — Quaternion
// prop.colorValue         — Color
// prop.boundsValue        — Bounds
// prop.rectValue          — Rect
// prop.enumValueIndex     — enum (as int index)
// prop.objectReferenceValue — UnityEngine.Object reference

// Iterate all properties of a component
var iterator = so.GetIterator();
iterator.Next(true);  // Enter first property
do
{
    Debug.Log($"{iterator.propertyPath} = {iterator.propertyType}");
} while (iterator.Next(false));

// Nested properties
var nested = so.FindProperty("m_Center");  // e.g., BoxCollider center
Vector3 center = nested.vector3Value;

// Array properties
SerializedProperty array = so.FindProperty("m_Materials");
int count = array.arraySize;
for (int i = 0; i < count; i++)
{
    var element = array.GetArrayElementAtIndex(i);
    // element.objectReferenceValue...
}
```

## 6. Script Generation & Compilation

```csharp
using UnityEditor.Compilation;
using System.IO;

// Write a script file
string scriptContent = @"
using UnityEngine;

public class PlayerController : MonoBehaviour
{
    public float speed = 5f;

    void Update()
    {
        float h = Input.GetAxis(""Horizontal"");
        float v = Input.GetAxis(""Vertical"");
        transform.Translate(new Vector3(h, 0, v) * speed * Time.deltaTime);
    }
}";

string path = "Assets/Scripts/Player/PlayerController.cs";
Directory.CreateDirectory(Path.GetDirectoryName(path));
File.WriteAllText(path, scriptContent);
AssetDatabase.Refresh();

// Wait for compilation to finish
// Method 1: Callback
CompilationPipeline.compilationFinished += OnCompilationFinished;

void OnCompilationFinished(object obj)
{
    CompilationPipeline.compilationFinished -= OnCompilationFinished;
    // Check for errors
    var messages = CompilationPipeline.GetCompilationMessages();
    // CompilerMessageType: Error, Warning, Info
}

// Method 2: Poll
bool IsCompiling() => EditorApplication.isCompiling;

// Get compilation errors
var messages = CompilationPipeline.GetCompilationMessages();
foreach (var msg in messages)
{
    if (msg.type == CompilerMessageType.Error)
        Debug.LogError($"{msg.file}({msg.line}): {msg.message}");
}

// After compilation, add script component to GameObject
// IMPORTANT: Must wait until compilation finishes
string typeName = "PlayerController";
var assemblies = System.AppDomain.CurrentDomain.GetAssemblies();
System.Type scriptType = null;
foreach (var asm in assemblies)
{
    scriptType = asm.GetType(typeName);
    if (scriptType != null) break;
}
if (scriptType != null)
    go.AddComponent(scriptType);
```

## 7. Prefab System

```csharp
// Save GameObject as prefab
string prefabPath = "Assets/Prefabs/PFB_Wolf.prefab";
Directory.CreateDirectory(Path.GetDirectoryName(prefabPath));
var prefab = PrefabUtility.SaveAsPrefabAsset(go, prefabPath);

// Save as prefab and keep connection (instance becomes prefab instance)
var prefab = PrefabUtility.SaveAsPrefabAssetAndConnect(
    go, prefabPath, InteractionMode.AutomatedAction);

// Instantiate prefab in scene
var prefabAsset = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
var instance = (GameObject)PrefabUtility.InstantiatePrefab(prefabAsset);

// Create prefab variant
var basePrefab = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Prefabs/PFB_Enemy.prefab");
var variantInstance = (GameObject)PrefabUtility.InstantiatePrefab(basePrefab);
// Make changes to variantInstance...
PrefabUtility.SaveAsPrefabAsset(variantInstance, "Assets/Prefabs/PFB_Enemy_Red.prefab");
Object.DestroyImmediate(variantInstance);

// Edit prefab contents
string assetPath = PrefabUtility.GetPrefabAssetPathOfNearestInstanceRoot(go);
using (var editScope = new PrefabUtility.EditPrefabContentsScope(assetPath))
{
    var root = editScope.prefabContentsRoot;
    // Modify root or its children
    root.transform.localScale = Vector3.one * 2;
}

// Check if is prefab
bool isPrefab = PrefabUtility.IsPartOfAnyPrefab(go);
```

## 8. Asset Database & Import

```csharp
// Refresh (detect new/changed files)
AssetDatabase.Refresh();

// Import specific asset
AssetDatabase.ImportAsset("Assets/Models/Wolf.fbx", ImportAssetOptions.ForceUpdate);

// Create asset
var material = new Material(Shader.Find("Universal Render Pipeline/Lit"));
AssetDatabase.CreateAsset(material, "Assets/Materials/MAT_Wolf.mat");

// Load asset
var mat = AssetDatabase.LoadAssetAtPath<Material>("Assets/Materials/MAT_Wolf.mat");
var mesh = AssetDatabase.LoadAssetAtPath<Mesh>("Assets/Models/Wolf.fbx");
var prefab = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Prefabs/PFB_Wolf.prefab");
var tex = AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/Textures/Wolf_Albedo.png");

// Find assets by type
string[] guids = AssetDatabase.FindAssets("t:Material", new[] { "Assets/Materials" });
foreach (string guid in guids)
{
    string path = AssetDatabase.GUIDToAssetPath(guid);
    var loadedMat = AssetDatabase.LoadAssetAtPath<Material>(path);
}

// Find assets by name
string[] guids = AssetDatabase.FindAssets("Wolf", new[] { "Assets" });

// Model Import Settings
var importer = AssetImporter.GetAtPath("Assets/Models/Wolf.fbx") as ModelImporter;
if (importer != null)
{
    // Scale
    importer.globalScale = 1.0f;
    importer.useFileScale = true;

    // Animation
    importer.animationType = ModelImporterAnimationType.Generic;
    // or Humanoid, Legacy, None

    // For humanoid, configure avatar
    if (importer.animationType == ModelImporterAnimationType.Humanoid)
    {
        importer.avatarSetup = ModelImporterAvatarSetup.CreateFromThisModel;
    }

    // Materials
    importer.materialImportMode = ModelImporterMaterialImportMode.ImportViaMaterialDescription;
    importer.materialLocation = ModelImporterMaterialLocation.InPrefab;

    // Mesh
    importer.meshCompression = ModelImporterMeshCompression.Medium;
    importer.isReadable = false;  // Optimize memory
    importer.importNormals = ModelImporterNormals.Import;
    importer.importTangents = ModelImporterTangents.CalculateMikk;

    // MUST call this after changes
    importer.SaveAndReimport();
}

// Texture Import Settings
var texImporter = AssetImporter.GetAtPath("Assets/Textures/Wolf_Normal.png") as TextureImporter;
if (texImporter != null)
{
    texImporter.textureType = TextureImporterType.NormalMap;
    // or Default, Sprite, Cursor, Cookie, Lightmap, SingleChannel
    texImporter.maxTextureSize = 2048;
    texImporter.textureCompression = TextureImporterCompression.Compressed;
    texImporter.sRGBTexture = false;  // false for normal maps, true for albedo
    texImporter.SaveAndReimport();
}

// Delete asset
AssetDatabase.DeleteAsset("Assets/OldStuff/Junk.mat");

// Move/rename asset
AssetDatabase.MoveAsset("Assets/Old/Wolf.fbx", "Assets/Models/Wolf.fbx");

// Create folder
AssetDatabase.CreateFolder("Assets", "NewFolder");
```

## 9. Material Creation (URP)

```csharp
// URP Lit material
var mat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
mat.name = "MAT_Wolf";

// Base color
mat.SetColor("_BaseColor", new Color(0.8f, 0.2f, 0.1f, 1f));

// Base map (albedo texture)
var tex = AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/Textures/Wolf_Albedo.png");
mat.SetTexture("_BaseMap", tex);

// Normal map
var normalTex = AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/Textures/Wolf_Normal.png");
mat.SetTexture("_BumpMap", normalTex);
mat.SetFloat("_BumpScale", 1.0f);
mat.EnableKeyword("_NORMALMAP");

// Metallic / Smoothness
mat.SetFloat("_Metallic", 0.0f);
mat.SetFloat("_Smoothness", 0.5f);

// Metallic map
mat.SetTexture("_MetallicGlossMap", metallicTex);
mat.EnableKeyword("_METALLICSPECGLOSSMAP");

// Emission
mat.SetColor("_EmissionColor", Color.red * 2f);
mat.EnableKeyword("_EMISSION");
mat.globalIlluminationFlags = MaterialGlobalIlluminationFlags.BakedEmissive;

// Transparency
mat.SetFloat("_Surface", 1);  // 0 = Opaque, 1 = Transparent
mat.SetFloat("_Blend", 0);     // 0 = Alpha, 1 = Premultiply, 2 = Additive, 3 = Multiply
mat.SetFloat("_AlphaClip", 0); // 0 = off, 1 = on
mat.renderQueue = (int)UnityEngine.Rendering.RenderQueue.Transparent;
mat.SetOverrideTag("RenderType", "Transparent");

// Render face
mat.SetFloat("_Cull", 2);  // 0 = Off (double-sided), 1 = Front, 2 = Back (default)

// Save material
AssetDatabase.CreateAsset(mat, "Assets/Materials/MAT_Wolf.mat");

// URP Unlit material
var unlitMat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));

// Assign material to renderer
var renderer = go.GetComponent<MeshRenderer>();
renderer.sharedMaterial = mat;  // Use sharedMaterial in Editor, not material
renderer.sharedMaterials = new Material[] { mat, mat2 };  // Multiple material slots

// Common URP shader property names:
// _BaseColor, _BaseMap, _BumpMap, _BumpScale, _Metallic, _Smoothness,
// _MetallicGlossMap, _OcclusionMap, _EmissionColor, _EmissionMap,
// _Surface, _Blend, _AlphaClip, _Cutoff, _Cull
```

## 10. Animator Controllers

```csharp
using UnityEditor.Animations;

// Create controller
var controller = AnimatorController.CreateAnimatorControllerAtPath(
    "Assets/Animations/AC_Wolf.controller");

// Add parameters
controller.AddParameter("Speed", AnimatorControllerParameterType.Float);
controller.AddParameter("IsGrounded", AnimatorControllerParameterType.Bool);
controller.AddParameter("Jump", AnimatorControllerParameterType.Trigger);
controller.AddParameter("AttackIndex", AnimatorControllerParameterType.Int);

// Get the root state machine
var rootStateMachine = controller.layers[0].stateMachine;

// Add states
var idleState = rootStateMachine.AddState("Idle", new Vector3(200, 0, 0));
var walkState = rootStateMachine.AddState("Walk", new Vector3(200, 100, 0));
var runState = rootStateMachine.AddState("Run", new Vector3(200, 200, 0));
var jumpState = rootStateMachine.AddState("Jump", new Vector3(400, 100, 0));

// Assign animation clips to states
var idleClip = AssetDatabase.LoadAssetAtPath<AnimationClip>("Assets/Animations/Wolf@Idle.fbx");
idleState.motion = idleClip;

// Set default state
rootStateMachine.defaultState = idleState;

// Add transitions
var toWalk = idleState.AddTransition(walkState);
toWalk.AddCondition(AnimatorConditionMode.Greater, 0.1f, "Speed");
toWalk.hasExitTime = false;
toWalk.duration = 0.25f;  // Transition duration in seconds

var toIdle = walkState.AddTransition(idleState);
toIdle.AddCondition(AnimatorConditionMode.Less, 0.1f, "Speed");
toIdle.hasExitTime = false;
toIdle.duration = 0.25f;

var toRun = walkState.AddTransition(runState);
toRun.AddCondition(AnimatorConditionMode.Greater, 0.5f, "Speed");

var toJump = rootStateMachine.AddAnyStateTransition(jumpState);
toJump.AddCondition(AnimatorConditionMode.If, 0, "Jump");

// AnimatorConditionMode:
// If (bool true), IfNot (bool false),
// Greater, Less, Equals, NotEqual (float/int)

// Assign controller to Animator component
var animator = go.GetComponent<Animator>();
animator.runtimeAnimatorController = controller;

// Sub-state machines
var combatSM = rootStateMachine.AddStateMachine("Combat", new Vector3(400, 0, 0));
var attackState = combatSM.AddState("Attack");

// Blend trees
var blendTree = new BlendTree();
blendTree.blendType = BlendTreeType.Simple1D;
blendTree.blendParameter = "Speed";
blendTree.AddChild(idleClip, 0f);      // At Speed=0
blendTree.AddChild(walkClip, 0.5f);    // At Speed=0.5
blendTree.AddChild(runClip, 1f);       // At Speed=1.0

var locomotionState = rootStateMachine.AddState("Locomotion");
locomotionState.motion = blendTree;
```

## 11. Physics Setup

```csharp
// Rigidbody
var rb = go.AddComponent<Rigidbody>();
rb.mass = 2f;
rb.linearDamping = 0.5f;  // was rb.drag in older Unity
rb.angularDamping = 0.05f;
rb.useGravity = true;
rb.isKinematic = false;
rb.interpolation = RigidbodyInterpolation.Interpolate;
rb.collisionDetectionMode = CollisionDetectionMode.ContinuousDynamic;
rb.constraints = RigidbodyConstraints.FreezeRotationX | RigidbodyConstraints.FreezeRotationZ;

// Box Collider
var box = go.AddComponent<BoxCollider>();
box.center = new Vector3(0, 0.5f, 0);
box.size = new Vector3(1, 1, 1);
box.isTrigger = false;

// Sphere Collider
var sphere = go.AddComponent<SphereCollider>();
sphere.center = Vector3.zero;
sphere.radius = 0.5f;

// Capsule Collider
var capsule = go.AddComponent<CapsuleCollider>();
capsule.center = new Vector3(0, 1, 0);
capsule.radius = 0.5f;
capsule.height = 2f;
capsule.direction = 1;  // 0=X, 1=Y, 2=Z

// Mesh Collider
var meshCol = go.AddComponent<MeshCollider>();
meshCol.convex = true;  // Required for Rigidbody
meshCol.sharedMesh = go.GetComponent<MeshFilter>().sharedMesh;

// Physics Material
var physicsMat = new PhysicsMaterial("Bouncy");
physicsMat.bounciness = 0.8f;
physicsMat.dynamicFriction = 0.4f;
physicsMat.staticFriction = 0.6f;
physicsMat.bounceCombine = PhysicsMaterialCombine.Maximum;
physicsMat.frictionCombine = PhysicsMaterialCombine.Average;
AssetDatabase.CreateAsset(physicsMat, "Assets/Physics/Bouncy.physicMaterial");
box.sharedMaterial = physicsMat;

// Layer Collision Matrix
Physics.IgnoreLayerCollision(
    LayerMask.NameToLayer("Player"),
    LayerMask.NameToLayer("PlayerProjectiles"),
    true  // ignore = true
);

// CharacterController (alternative to Rigidbody for player)
var cc = go.AddComponent<CharacterController>();
cc.center = new Vector3(0, 1, 0);
cc.height = 2f;
cc.radius = 0.5f;
cc.slopeLimit = 45f;
cc.stepOffset = 0.3f;
```

## 12. UI (Canvas)

```csharp
using UnityEngine.UI;
using UnityEngine;
using TMPro;  // TextMeshPro

// Create Canvas
var canvasGo = new GameObject("Canvas");
var canvas = canvasGo.AddComponent<Canvas>();
canvas.renderMode = RenderMode.ScreenSpaceOverlay;
// or ScreenSpaceCamera, WorldSpace

var scaler = canvasGo.AddComponent<CanvasScaler>();
scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
scaler.referenceResolution = new Vector2(1920, 1080);
scaler.matchWidthOrHeight = 0.5f;

canvasGo.AddComponent<GraphicRaycaster>();

// Create Panel
var panelGo = new GameObject("Panel");
panelGo.transform.SetParent(canvasGo.transform, false);
var panelImg = panelGo.AddComponent<Image>();
panelImg.color = new Color(0, 0, 0, 0.5f);  // Semi-transparent black
var panelRect = panelGo.GetComponent<RectTransform>();
panelRect.anchorMin = new Vector2(0, 0);
panelRect.anchorMax = new Vector2(1, 1);
panelRect.offsetMin = Vector2.zero;
panelRect.offsetMax = Vector2.zero;

// Create Button
var btnGo = new GameObject("StartButton");
btnGo.transform.SetParent(panelGo.transform, false);
var btnImg = btnGo.AddComponent<Image>();
var btn = btnGo.AddComponent<Button>();
var btnRect = btnGo.GetComponent<RectTransform>();
btnRect.sizeDelta = new Vector2(200, 60);

// Create TextMeshPro text
var textGo = new GameObject("ButtonText");
textGo.transform.SetParent(btnGo.transform, false);
var tmp = textGo.AddComponent<TextMeshProUGUI>();
tmp.text = "Start Game";
tmp.fontSize = 24;
tmp.alignment = TextAlignmentOptions.Center;
var textRect = textGo.GetComponent<RectTransform>();
textRect.anchorMin = Vector2.zero;
textRect.anchorMax = Vector2.one;
textRect.offsetMin = Vector2.zero;
textRect.offsetMax = Vector2.zero;

// Health Bar (Slider)
var sliderGo = new GameObject("HealthBar");
sliderGo.transform.SetParent(canvasGo.transform, false);
var slider = sliderGo.AddComponent<Slider>();
slider.minValue = 0;
slider.maxValue = 100;
slider.value = 100;

// Image (for HUD icons)
var imgGo = new GameObject("Icon");
imgGo.transform.SetParent(canvasGo.transform, false);
var img = imgGo.AddComponent<Image>();
img.sprite = AssetDatabase.LoadAssetAtPath<Sprite>("Assets/UI/icon.png");
img.preserveAspect = true;

// RectTransform anchoring reference:
// Full screen:     anchorMin(0,0) anchorMax(1,1)
// Top-left:        anchorMin(0,1) anchorMax(0,1) pivot(0,1)
// Top-right:       anchorMin(1,1) anchorMax(1,1) pivot(1,1)
// Bottom-center:   anchorMin(0.5,0) anchorMax(0.5,0) pivot(0.5,0)
// Center:          anchorMin(0.5,0.5) anchorMax(0.5,0.5) pivot(0.5,0.5)
```

## 13. Lighting & Post-Processing

```csharp
// Directional Light
var lightGo = new GameObject("Sun");
var light = lightGo.AddComponent<Light>();
light.type = LightType.Directional;
light.color = new Color(1f, 0.96f, 0.84f);
light.intensity = 1.5f;
light.shadows = LightShadows.Soft;
light.shadowStrength = 0.8f;
lightGo.transform.rotation = Quaternion.Euler(50, -30, 0);

// Point Light
light.type = LightType.Point;
light.range = 10f;

// Spot Light
light.type = LightType.Spot;
light.range = 20f;
light.spotAngle = 45f;

// Skybox
var skyboxMat = AssetDatabase.LoadAssetAtPath<Material>("Assets/Skybox/Sky.mat");
RenderSettings.skybox = skyboxMat;

// Ambient light
RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Skybox;
// or Trilight, Flat
RenderSettings.ambientIntensity = 1.0f;
// For flat mode:
RenderSettings.ambientLight = new Color(0.2f, 0.2f, 0.3f);

// Fog
RenderSettings.fog = true;
RenderSettings.fogMode = FogMode.ExponentialSquared;
RenderSettings.fogDensity = 0.02f;
RenderSettings.fogColor = new Color(0.7f, 0.8f, 0.9f);

// Post-Processing (URP Volume)
// Requires: com.unity.render-pipelines.universal
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

var volumeGo = new GameObject("PostProcessVolume");
var volume = volumeGo.AddComponent<Volume>();
volume.isGlobal = true;

var profile = ScriptableObject.CreateInstance<VolumeProfile>();
AssetDatabase.CreateAsset(profile, "Assets/Settings/PostProcess.asset");
volume.profile = profile;

// Bloom
var bloom = profile.Add<Bloom>();
bloom.threshold.Override(0.9f);
bloom.intensity.Override(1.5f);
bloom.scatter.Override(0.7f);

// Color adjustments
var colorAdj = profile.Add<ColorAdjustments>();
colorAdj.postExposure.Override(0.5f);
colorAdj.contrast.Override(10f);
colorAdj.saturation.Override(10f);

// Vignette
var vignette = profile.Add<Vignette>();
vignette.intensity.Override(0.3f);
vignette.smoothness.Override(0.5f);
```

## 14. Play Mode & Console

```csharp
// Enter play mode
EditorApplication.isPlaying = true;

// Exit play mode
EditorApplication.isPlaying = false;

// Check if in play mode
bool playing = EditorApplication.isPlaying;
bool aboutToPlay = EditorApplication.isPlayingOrWillChangePlaymode;

// Pause
EditorApplication.isPaused = true;

// Listen for play mode changes
EditorApplication.playModeStateChanged += (PlayModeStateChange state) =>
{
    // state: EnteredEditMode, ExitingEditMode, EnteredPlayMode, ExitingPlayMode
};

// Capture console logs
Application.logMessageReceived += (string condition, string stackTrace, LogType type) =>
{
    // type: Error, Assert, Warning, Log, Exception
    // Store these for sending back to Claude
};

// Get recent console logs (requires reflection or custom log handler)
// Best approach: maintain a ring buffer from the callback above

// Clear console
var assembly = System.Reflection.Assembly.GetAssembly(typeof(SceneView));
var logEntries = assembly.GetType("UnityEditor.LogEntries");
var clearMethod = logEntries.GetMethod("Clear");
clearMethod.Invoke(null, null);
```

## 15. Build Pipeline

```csharp
using UnityEditor.Build.Reporting;

var options = new BuildPlayerOptions
{
    scenes = new[] {
        "Assets/Scenes/MainMenu.unity",
        "Assets/Scenes/Level1.unity"
    },
    locationPathName = "Builds/Windows/MyGame.exe",
    target = BuildTarget.StandaloneWindows64,
    options = BuildOptions.None
    // BuildOptions: Development, AutoRunPlayer, ShowBuiltPlayer,
    //               CompressWithLz4, CompressWithLz4HC
};

BuildReport report = BuildPipeline.BuildPlayer(options);
BuildSummary summary = report.summary;

if (summary.result == BuildResult.Succeeded)
{
    Debug.Log($"Build succeeded: {summary.totalSize} bytes, {summary.totalTime}");
}
else
{
    Debug.LogError($"Build failed: {summary.result}");
    foreach (var step in report.steps)
    {
        foreach (var msg in step.messages)
        {
            if (msg.type == LogType.Error)
                Debug.LogError(msg.content);
        }
    }
}

// Build targets:
// StandaloneWindows64, StandaloneOSX, StandaloneLinux64,
// WebGL, Android, iOS
```

## 16. Test Runner

```csharp
using UnityEditor.TestTools.TestRunner.Api;

// Run tests programmatically
var testRunnerApi = ScriptableObject.CreateInstance<TestRunnerApi>();

var filter = new Filter
{
    testMode = TestMode.EditMode,  // or PlayMode
    // targetPlatform = BuildTarget.StandaloneWindows64  // for play mode
};

var callbacks = new TestCallbacks();
testRunnerApi.RegisterCallbacks(callbacks);
testRunnerApi.Execute(new ExecutionSettings(filter));

class TestCallbacks : ICallbacks
{
    public void RunStarted(ITestAdaptor testsToRun) { }
    public void RunFinished(ITestResultAdaptor result)
    {
        // result.ResultState: Passed, Failed, Skipped, Inconclusive
        Debug.Log($"Tests: {result.PassCount} passed, {result.FailCount} failed");
    }
    public void TestStarted(ITestAdaptor test) { }
    public void TestFinished(ITestResultAdaptor result)
    {
        if (result.TestStatus == TestStatus.Failed)
            Debug.LogError($"FAILED: {result.Name} - {result.Message}");
    }
}
```

## 17. WebSocket Server (C# Side)

Using websocket-sharp (add websocket-sharp.dll to Plugins/):

```csharp
using WebSocketSharp;
using WebSocketSharp.Server;

public class MCPWebSocketBehavior : WebSocketBehavior
{
    protected override void OnMessage(MessageEventArgs e)
    {
        // Parse JSON command, queue for main thread execution
        string json = e.Data;
        MCPBridge.Instance.QueueCommand(json, (response) =>
        {
            Send(response);
        });
    }

    protected override void OnOpen()
    {
        Debug.Log("MCP client connected");
    }

    protected override void OnClose(CloseEventArgs e)
    {
        Debug.Log($"MCP client disconnected: {e.Reason}");
    }
}

// In MCPBridge.cs (MonoBehaviour-like Editor script)
[InitializeOnLoad]
public static class MCPBridge
{
    static WebSocketServer _server;
    static Queue<(string json, Action<string> callback)> _commandQueue;

    static MCPBridge()
    {
        _commandQueue = new Queue<(string, Action<string>)>();
        EditorApplication.update += ProcessQueue;
        StartServer();
    }

    static void StartServer()
    {
        _server = new WebSocketServer("ws://localhost:8090");
        _server.AddWebSocketService<MCPWebSocketBehavior>("/mcp");
        _server.Start();
        Debug.Log("MCP WebSocket server started on ws://localhost:8090/mcp");
    }

    public static void QueueCommand(string json, Action<string> callback)
    {
        lock (_commandQueue)
        {
            _commandQueue.Enqueue((json, callback));
        }
    }

    static void ProcessQueue()
    {
        // Process one command per frame on the main thread
        lock (_commandQueue)
        {
            if (_commandQueue.Count > 0)
            {
                var (json, callback) = _commandQueue.Dequeue();
                string response = CommandRouter.Execute(json);
                callback(response);
            }
        }
    }
}
```
