from enum import Enum

from pydantic import (
    BaseModel,
    field_validator,
    model_validator,
)

from pydatalab.models.utils import (
    HumanReadableIdentifier,
    KnownType,
    PyObjectId,
    Refcode,
)


class RelationshipType(str, Enum):
    """An enumeration of the possible types of relationship between two entries.

    ```mermaid
    classDiagram
    class entryC
    entryC --|> entryA: parent
    entryC ..|> entryD
    entryA <..> entryD: sibling
    entryA --|> entryB : child
    ```

    """

    PARENT = "parent"
    CHILD = "child"
    SIBLING = "sibling"
    PARTHOOD = "is_part_of"
    OTHER = "other"


class TypedRelationship(BaseModel):
    description: str | None = None
    """A description of the relationship."""

    relation: RelationshipType | None = None
    """The type of relationship between the two items. If the type is 'other', then a human-readable description should be provided."""

    type: KnownType
    """The type of the related resource."""

    immutable_id: PyObjectId | None = None
    """The immutable ID of the entry that is related to this entry."""

    item_id: HumanReadableIdentifier | None = None
    """The ID of the entry that is related to this entry."""

    refcode: Refcode | None = None
    """The refcode of the entry that is related to this entry."""

    @field_validator("relation")
    @classmethod
    def check_for_description(cls, v, info):
        if v == RelationshipType.OTHER:
            data = info.data if hasattr(info, "data") and info.data else {}
            if data.get("description") is None:
                raise ValueError(
                    f"A description must be provided if the relationship type is {RelationshipType.OTHER.value!r}."
                )
        return v

    @model_validator(mode="before")
    @classmethod
    def check_id_fields(cls, values):
        """Check that at least one of the possible identifier fields is provided."""
        id_fields = ("immutable_id", "item_id", "refcode")
        if all(values.get(f) is None for f in id_fields):
            raise ValueError(f"Must provide at least one of {id_fields!r}")

        if values.get("refcode") and values.get("item_id"):
            pass
        elif values.get("immutable_id") and (values.get("refcode") or values.get("item_id")):
            raise ValueError(f"Must provide only one of {id_fields!r}")

        return values
