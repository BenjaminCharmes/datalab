from typing import TYPE_CHECKING, Any

from pydantic import (
    BaseModel,
    Field,
    model_validator,
)

from pydatalab.models.people import Person
from pydatalab.models.utils import Constituent, InlineSubstance, PyObjectId

if TYPE_CHECKING:
    from pydatalab.models.collections import Collection


class HasOwner(BaseModel):
    creator_ids: list[PyObjectId] = Field(default_factory=list)
    """The database IDs of the user(s) who created the item."""

    creators: list[Person] | None = Field(None)
    """Inlined info for the people associated with this item."""


class HasRevisionControl(BaseModel):
    revision: int = 1
    """The revision number of the entry."""

    revisions: dict[int, Any] | None = None
    """An optional mapping from old revision numbers to the model state at that revision."""


class HasBlocks(BaseModel):
    blocks_obj: dict[str, Any] = Field(default_factory=dict)
    """A mapping from block ID to block data."""

    display_order: list[str] = Field(default_factory=list)
    """The order in which to display block data in the UI."""


class IsCollectable(BaseModel):
    """Trait mixin for models that can be
    added to collections.
    """

    collections: list["Collection"] = Field(default_factory=list)
    """Inlined info for the collections associated with this item."""

    @model_validator(mode="before")
    @classmethod
    def add_missing_collection_relationships(cls, values):
        from pydatalab.models.relationships import TypedRelationship

        if values.get("collections") is not None:
            new_ids = {coll.immutable_id for coll in values["collections"]}
            existing_collection_relationship_ids = set()

            if values.get("relationships") is not None:
                existing_collection_relationship_ids = {
                    relationship.immutable_id
                    for relationship in values["relationships"]
                    if relationship.type == "collections"
                }

            if "relationships" not in values:
                values["relationships"] = []

            for collection in values.get("collections", []):
                if collection.immutable_id not in existing_collection_relationship_ids:
                    relationship = TypedRelationship(
                        relation=None,
                        immutable_id=collection.immutable_id,
                        type="collections",
                        description="Is a member of",
                    )
                    values["relationships"].append(relationship)

            values["relationships"] = [
                d
                for d in values.get("relationships", [])
                if d.type != "collections" or d.immutable_id in new_ids
            ]

        if len([d for d in values.get("relationships", []) if d.type == "collections"]) != len(
            values.get("collections", [])
        ):
            raise RuntimeError("Relationships and collections mismatch")

        return values


class HasSynthesisInfo(BaseModel):
    """Trait mixin for models that have synthesis information."""

    synthesis_constituents: list[Constituent] = Field(default_factory=list)
    """A list of references to constituent materials giving the amount and relevant inlined details of consituent items."""

    synthesis_description: str | None = None
    """Free-text details of the procedure applied to synthesise the sample"""

    @model_validator(mode="before")
    @classmethod
    def add_missing_synthesis_relationships(cls, values):
        """Add any missing sample synthesis constituents to parent relationships"""
        from pydatalab.models.relationships import RelationshipType, TypedRelationship

        constituents_set = set()
        if values.get("synthesis_constituents") is not None:
            existing_relationships = values.get("relationships", [])
            existing_parent_relationship_ids = set()

            if existing_relationships:
                existing_parent_relationship_ids = {
                    relationship.refcode or relationship.item_id
                    for relationship in existing_relationships
                    if relationship.relation == RelationshipType.PARENT
                }

            if "relationships" not in values:
                values["relationships"] = []

            for constituent in values.get("synthesis_constituents", []):
                item_data = (
                    constituent.get("item") if isinstance(constituent, dict) else constituent.item
                )

                # If this is an inline relationship (has name but no item_id/refcode), just skip it
                if isinstance(item_data, dict):
                    if not item_data.get("item_id") and not item_data.get("refcode"):
                        continue
                    constituent_id = item_data.get("refcode") or item_data.get("item_id")
                else:
                    if isinstance(item_data, InlineSubstance):
                        continue
                    constituent_id = item_data.refcode or item_data.item_id

                if constituent_id not in existing_parent_relationship_ids:
                    if isinstance(item_data, dict):
                        relationship = TypedRelationship(
                            relation=RelationshipType.PARENT,
                            refcode=item_data.get("refcode"),
                            item_id=item_data.get("item_id"),
                            type=item_data.get("type"),
                            description="Is a constituent of",
                        )
                    else:
                        relationship = TypedRelationship(
                            relation=RelationshipType.PARENT,
                            refcode=item_data.refcode,
                            item_id=item_data.item_id,
                            type=item_data.type,
                            description="Is a constituent of",
                        )
                    values["relationships"].append(relationship)

                # Accumulate all constituent IDs in a set to filter those that have been deleted
                constituents_set.add(constituent_id)

        # Finally, filter out any parent relationships with item that were removed
        # from the synthesis constituents
        if "relationships" in values:
            values["relationships"] = [
                rel
                for rel in values["relationships"]
                if not (
                    (rel.refcode or rel.item_id) not in constituents_set
                    and rel.relation == RelationshipType.PARENT
                    and rel.type in ("samples", "starting_materials")
                )
            ]

        return values


class HasChemInfo:
    smile: str | None = Field(None)
    """A SMILES string representation of the chemical structure associated with this sample."""
    inchi: str | None = Field(None)
    """An InChI string representation of the chemical structure associated with this sample."""
    inchi_key: str | None = Field(None)
    """An InChI key representation of the chemical structure associated with this sample."""
    """A unique key derived from the InChI string."""
    chemform: str | None = Field(None)
