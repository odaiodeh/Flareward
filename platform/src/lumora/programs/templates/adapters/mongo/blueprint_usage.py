"""Borrow a collection for resource-usage lookup without loading authoring schemas."""

from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from lumora.resources.errors import ResourceStorageError


class MongoBlueprintUsage:
    def __init__(self, collection: Collection) -> None:
        self._collection = collection

    def list_direct_usage(self, rid: str) -> list[str]:
        try:
            return [
                row["blueprint_id"]
                for row in self._collection.find({"rid_refs": rid}, {"blueprint_id": 1})
            ]
        except PyMongoError:
            raise ResourceStorageError() from None
