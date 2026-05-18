#!/usr/bin/env python3
"""
Simple hook to allow bash commands.
This is a placeholder hook that allows all commands.
"""
import sys
import json

# Read the hook input
hook_input = json.loads(sys.stdin.read())

# Allow all commands by default
result = {
    "allow": True
}

print(json.dumps(result))
sys.exit(0)
