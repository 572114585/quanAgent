"""Tool package.

Tools are intentionally imported from their concrete modules. Keeping this
package side-effect free prevents optional document/ML dependencies from being
loaded during agent startup.
"""

__all__: list[str] = []
