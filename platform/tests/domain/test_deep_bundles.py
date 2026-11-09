"""Portable bundle integrity does not depend on Python's call-stack limit."""

from support.construction_values import dependency_chain

from flareward.resources.domain.bundles import BundleEntry, ElementBundle


def test_deep_dependency_bundle_round_trip():
    resources = dependency_chain(1200)
    bundle = ElementBundle(
        root=resources[0].key,
        entries=tuple(
            BundleEntry(
                resource=resource,
                dependencies=(resources[index + 1].key,) if index + 1 < len(resources) else (),
            )
            for index, resource in reversed(list(enumerate(resources)))
        ),
    )
    assert ElementBundle.model_validate_json(bundle.model_dump_json()) == bundle
