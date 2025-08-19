#!/usr/bin/env python3
"""
Test script to verify MCP server connection and tool registration
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

async def test_mcp_server():
    """Test MCP server connection"""
    print("🧪 Testing MCP server connection...")
    
    # Start the MCP server as a subprocess
    cmd = [sys.executable, "-m", "cover_agent.cc_mcp.hybrid_server"]
    
    try:
        # Start the server process
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=project_root
        )
        
        print(f"✅ MCP server started with PID: {process.pid}")
        
        # Send initialization request
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        
        # Send request
        request_data = json.dumps(init_request) + "\n"
        process.stdin.write(request_data.encode())
        await process.stdin.drain()
        
        # Read response
        response = await process.stdout.readline()
        if response:
            response_data = json.loads(response.decode())
            print(f"📨 Received response: {json.dumps(response_data, indent=2)}")
            
            # Check if tools are available
            if "result" in response_data and "capabilities" in response_data["result"]:
                capabilities = response_data["result"]["capabilities"]
                if "tools" in capabilities:
                    tools = capabilities["tools"]
                    print(f"🔧 Available tools: {tools}")
                    # Request tool list
                    list_tools_request = {
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/list"
                    }
                    
                    request_data = json.dumps(list_tools_request) + "\n"
                    process.stdin.write(request_data.encode())
                    await process.stdin.drain()
                    
                    # Read tools list response
                    tools_response = await process.stdout.readline()
                    if tools_response:
                        tools_data = json.loads(tools_response.decode())
                        print(f"📋 Tools list: {json.dumps(tools_data, indent=2)}")
                    else:
                        print("❌ No tools list response")
                else:
                    print("❌ No tools found in capabilities")
            else:
                print("❌ No capabilities found in response")
        else:
            print("❌ No response received")
        
        # Send shutdown request
        shutdown_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "shutdown"
        }
        
        request_data = json.dumps(shutdown_request) + "\n"
        process.stdin.write(request_data.encode())
        await process.stdin.drain()
        
        # Wait for process to finish
        await process.wait()
        
    except Exception as e:
        print(f"❌ Error testing MCP server: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_mcp_server())
    if success:
        print("✅ MCP server test completed successfully")
    else:
        print("❌ MCP server test failed")
        sys.exit(1)
