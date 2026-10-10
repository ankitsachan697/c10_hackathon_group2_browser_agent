"""
Workflow deployment utility for n8n cloud using the MCP endpoint.
Allows checking existing workflows, uploading new ones, or updating configurations.
"""

import os
import sys
import json
import requests

N8N_MCP_URL = "https://outskilltraining.app.n8n.cloud/mcp-server/http"
N8N_BEARER_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiI4MDMyMWU3Ni1iMjYyLTQzNDgtYjRiMy1mYTZhZWQwNGM3NzQiLCJpc3MiOiJuOG4iLCJhdWQiOiJtY3Atc2VydmVyLWFwaSIsImp0aSI6ImI2ZDJlNDc2LTFhYWMtNGE4Ny1iNmUwLTI2ZjA0MzZjMTQzMyIsImlhdCI6MTc5MTY0MjUwMn0."
    "CzpW6Y-No_9Sh9LekYlMyE-SoTOmjWFE3OCA641iFGg"
)

headers = {
    "Authorization": f"Bearer {N8N_BEARER_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def call_mcp_tool(tool_name: str, args: dict):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": args,
        },
    }
    resp = requests.post(N8N_MCP_URL, headers=headers, json=payload, timeout=30)
    for line in resp.text.split("\n"):
        if line.startswith("data:"):
            data = json.loads(line[5:])
            if "result" in data:
                content = data["result"].get("content", [])
                if content:
                    return json.loads(content[0]["text"])
                return data["result"]
            return data
    return {"error": "No data returned"}


def list_existing_workflows():
    res = call_mcp_tool("search_workflows", {})
    print("Existing n8n Workflows:")
    for wf in res.get("data", []):
        print(f"  • ID: {wf.get('id')} | Name: {wf.get('name')} | Active: {wf.get('active')}")


if __name__ == "__main__":
    list_existing_workflows()
