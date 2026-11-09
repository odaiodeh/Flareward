"""
Built-in tools for the multi-agent system.

These tools are generic and can be used by any node type.
They are organized by category:
- workplan: Tools for managing work plans
- topology: Tools for inspecting node topology
- delegation: Tools for delegating tasks between nodes
- workspace: Tools for reading workspace context
- time: Tools for getting time and date information
- retriever: Tool wrapper for using retrievers as tools
"""

# Import all built-in tools for easy access
from plugins.mas.elements.builtin.delegation import *
from plugins.mas.elements.builtin.retriever import *
from plugins.mas.elements.builtin.time import *
from plugins.mas.elements.builtin.topology import *
from plugins.mas.elements.builtin.workplan import *
from plugins.mas.elements.builtin.workspace import *
