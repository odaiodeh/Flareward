"""
RefRemapper - Recursively remap Ref objects in any object graph.

Only remaps actual Ref types (and subclasses like NodeRef, LLMRef, etc.)
and explicit $ref: string patterns.

SOLID: Single responsibility - reference remapping only.
"""

from typing import Any, Dict

from pydantic import BaseModel

from flareward.resources.domain.references import Ref


class RefRemapper:
    """
    Recursively remaps Ref objects in any object graph.

    Handles:
    - Ref objects and subclasses (NodeRef, LLMRef, ConditionRef, etc.)
    - Explicit $ref:xxx string patterns in dicts
    - Nested structures (BaseModel, dict, list, tuple)

    Thread-safe: stateless utility with static methods.
    """

    @staticmethod
    def remap(node: Any, mapping: Dict[str, str]) -> Any:
        """
        Walk object graph and replace Ref objects according to mapping.

        Args:
            node: Any object (Pydantic model, dict, list, Ref, etc.)
            mapping: Dict of old_rid → new_rid (new_rid should include $ref: if needed)

        Returns:
            New object with Ref objects replaced (deep copy for mutable objects)
        """
        # Ref objects (NodeRef, LLMRef, ConditionRef, etc.)
        if isinstance(node, Ref):
            return RefRemapper._remap_ref(node, mapping)

        # Pydantic models - traverse fields
        if isinstance(node, BaseModel):
            new_node = node.model_copy(deep=True)
            for field_name, field_value in new_node.__dict__.items():
                setattr(new_node, field_name, RefRemapper.remap(field_value, mapping))
            return new_node

        # Dicts - traverse values
        if isinstance(node, dict):
            return {k: RefRemapper.remap(v, mapping) for k, v in node.items()}

        # Lists/tuples - traverse
        if isinstance(node, (list, tuple)):
            result = [RefRemapper.remap(v, mapping) for v in node]
            return tuple(result) if isinstance(node, tuple) else result

        # Strings - only remap explicit $ref:xxx patterns
        if isinstance(node, str) and node.startswith(Ref.REF_PREFIX):
            old_rid = node[len(Ref.REF_PREFIX) :]
            if old_rid in mapping:
                return Ref.make_external(mapping[old_rid])

        # Everything else - return as-is
        return node

    @staticmethod
    def _remap_ref(ref_obj: Ref, mapping: Dict[str, str]) -> Ref:
        """Remap a single Ref object if it's in the mapping."""
        old_rid = ref_obj.ref
        if old_rid not in mapping:
            return ref_obj

        new_rid = mapping[old_rid]

        # Create new Ref with updated rid, preserving external/inline status
        if ref_obj.is_external_ref():
            return ref_obj.to_external(new_rid)
        else:
            return type(ref_obj)(new_rid)
