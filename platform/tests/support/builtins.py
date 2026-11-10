"""Portable curated-resource scenarios shared by policy and actual-store tests."""

from lumora.resources.authoring import ResourceRecord
from lumora.resources.domain.builtins import BuiltinResourceDescriptor
from lumora.resources.domain.models import Resource
from lumora.services.identity.domain import Identity

ADMIN = Identity.user("curator")


def curated_record(key: str, *, dependency: str | None = None, public: bool | None = False):
    return ResourceRecord(
        resource=Resource(
            rid=key,
            identity=ADMIN,
            category="tools",
            type="platform_dependency",
            name=key,
            cfg_dict={"dependency": "$ref:" + dependency} if dependency else {},
            nested_refs=[dependency] if dependency else [],
        ),
        descriptor=BuiltinResourceDescriptor(rid=key, visibility="public" if public else "draft")
        if public is not None
        else None,
    )


def chain():
    return (
        curated_record("root", dependency="middle"),
        curated_record("middle", dependency="leaf", public=None),
        curated_record("leaf", public=None),
    )
