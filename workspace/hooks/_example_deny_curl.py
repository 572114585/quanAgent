# Example hook — rename to deny_curl.py (remove leading underscore) to enable.
#
# def before_tool(ctx):
#     """ctx: HookContext(tool_name, tool_args, tool_call_id, mode, entrypoint)"""
#     cmd = str((ctx.tool_args or {}).get("command", ""))
#     if ctx.tool_name == "execute" and "curl" in cmd:
#         return {"action": "deny", "message": "[E_HOOK] curl blocked by example hook"}
#     return {"action": "allow"}
#
# def after_tool(ctx):
#     return None
