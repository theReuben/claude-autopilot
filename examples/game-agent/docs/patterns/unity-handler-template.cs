/*
 * Unity MCP Command Handler Template
 * ===================================
 * Copy this file and rename for each new handler category.
 * File: unity-project/Assets/Plugins/MCPBridge/Editor/Handlers/{Category}Handler.cs
 *
 * Each handler:
 * 1. Implements ICommandHandler
 * 2. Has a Category property matching the MCP tool category
 * 3. Routes commands via a switch statement
 * 4. Returns JObject with { success, data, error }
 * 5. ALL Unity API calls happen on the main thread (guaranteed by MCPBridge queue)
 */

using UnityEngine;
using UnityEditor;
using Newtonsoft.Json.Linq;
using System;
using System.Linq;

namespace MCPBridge.Handlers
{
    public class TemplateHandler : ICommandHandler
    {
        public string Category => "template"; // Must match category in MCP tool definition

        public JObject Handle(string command, JObject parameters)
        {
            try
            {
                return command switch
                {
                    "example_command" => HandleExampleCommand(parameters),
                    "another_command" => HandleAnotherCommand(parameters),
                    _ => Error($"Unknown command in '{Category}': {command}"),
                };
            }
            catch (Exception e)
            {
                Debug.LogError($"[MCP] {Category}.{command} failed: {e.Message}\n{e.StackTrace}");
                return Error(e.Message);
            }
        }

        private JObject HandleExampleCommand(JObject parameters)
        {
            // Extract parameters with defaults
            string name = parameters.Value<string>("name") ?? "Default";
            float value = parameters.Value<float?>("value") ?? 1.0f;
            
            // Optional nested object (e.g., Vector3)
            Vector3 position = Vector3.zero;
            var posObj = parameters["position"];
            if (posObj != null)
            {
                position = new Vector3(
                    posObj.Value<float>("x"),
                    posObj.Value<float>("y"),
                    posObj.Value<float>("z")
                );
            }

            // --- Unity API calls go here ---
            // Everything in this method runs on the main thread.
            
            // Example: create a GameObject
            var go = new GameObject(name);
            go.transform.position = position;
            Undo.RegisterCreatedObjectUndo(go, $"MCP Create {name}");

            // --- Return result ---
            return Success(new JObject
            {
                ["name"] = go.name,
                ["instanceId"] = go.GetInstanceID(),
                ["position"] = SerializeVector3(go.transform.position),
            });
        }

        private JObject HandleAnotherCommand(JObject parameters)
        {
            // Implement next command...
            return Success(new JObject { ["result"] = "done" });
        }

        // ─── Helpers ─────────────────────────────────────────────

        private JObject Success(JObject data)
        {
            return new JObject
            {
                ["success"] = true,
                ["data"] = data,
                ["error"] = null,
            };
        }

        private JObject Error(string message)
        {
            return new JObject
            {
                ["success"] = false,
                ["data"] = null,
                ["error"] = message,
            };
        }

        // ─── Serialization Helpers ───────────────────────────────

        public static JObject SerializeVector3(Vector3 v)
        {
            return new JObject { ["x"] = v.x, ["y"] = v.y, ["z"] = v.z };
        }

        public static Vector3 DeserializeVector3(JToken token, Vector3 defaultValue = default)
        {
            if (token == null) return defaultValue;
            return new Vector3(
                token.Value<float>("x"),
                token.Value<float>("y"),
                token.Value<float>("z")
            );
        }

        public static JObject SerializeQuaternion(Quaternion q)
        {
            var euler = q.eulerAngles;
            return new JObject { ["x"] = euler.x, ["y"] = euler.y, ["z"] = euler.z };
        }

        public static JObject SerializeColor(Color c)
        {
            return new JObject { ["r"] = c.r, ["g"] = c.g, ["b"] = c.b, ["a"] = c.a };
        }

        public static Color DeserializeColor(JToken token, Color defaultValue = default)
        {
            if (token == null) return defaultValue;
            return new Color(
                token.Value<float>("r"),
                token.Value<float>("g"),
                token.Value<float>("b"),
                token.Value<float?>("a") ?? 1f
            );
        }
    }
}
