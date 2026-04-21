/*
 * ICommandHandler.cs — Interface for all MCP command handlers
 * File: unity-project/Assets/Plugins/MCPBridge/Editor/ICommandHandler.cs
 */

using Newtonsoft.Json.Linq;

namespace MCPBridge
{
    public interface ICommandHandler
    {
        /// <summary>The category this handler responds to (e.g., "scene", "gameobject").</summary>
        string Category { get; }

        /// <summary>Handle a command and return a JSON response.</summary>
        /// <param name="command">The specific command name within this category.</param>
        /// <param name="parameters">The parameters as a JSON object.</param>
        /// <returns>JSON response with { success, data, error }.</returns>
        JObject Handle(string command, JObject parameters);
    }
}
