"""
Workflow deployment utility for n8n cloud using the MCP endpoint.
Allows checking existing workflows, uploading new ones, or updating configurations.
"""

import os
import sys
import json
import requests

N8N_MCP_URL = os.getenv("N8N_MCP_URL")
N8N_BEARER_TOKEN = os.getenv("N8N_BEARER_TOKEN")


def call_mcp_tool(tool_name: str, args: dict):
    if not N8N_MCP_URL or not N8N_BEARER_TOKEN:
        return {"error": "n8n MCP endpoint and bearer token are not configured"}

    headers = {
        "Authorization": f"Bearer {N8N_BEARER_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
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
