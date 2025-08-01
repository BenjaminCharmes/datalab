from flask import Blueprint, jsonify, request

from pydatalab.logger import LOGGER
from pydatalab.models.relationships import RelationshipType
from pydatalab.mongo import flask_mongo
from pydatalab.permissions import active_users_or_get_only, get_default_permissions

GRAPHS = Blueprint("graphs", __name__)


@GRAPHS.before_request
@active_users_or_get_only
def _(): ...


@GRAPHS.route("/item-graph", methods=["GET"])
@GRAPHS.route("/item-graph/<item_id>", methods=["GET"])
def get_graph_cy_format(
    item_id: str | None = None,
    collection_id: str | None = None,
    hide_collections: bool = True,
):
    try:
        collection_id = request.args.get("collection_id", type=str)

        if item_id is None:
            if collection_id is not None:
                collection_immutable_id = flask_mongo.db.collections.find_one(
                    {"collection_id": collection_id}, projection={"_id": 1}
                )
                if not collection_immutable_id:
                    return (
                        jsonify(
                            status="error", message=f"No collection found with ID {collection_id!r}"
                        ),
                        404,
                    )
                collection_immutable_id = collection_immutable_id["_id"]
                query = {
                    "$and": [
                        {"relationships.immutable_id": collection_immutable_id},
                        {"relationships.type": "collections"},
                    ]
                }
            else:
                query = {}
            all_documents = flask_mongo.db.items.find(
                {**query, **get_default_permissions(user_only=False)},
                projection={"item_id": 1, "name": 1, "type": 1, "relationships": 1},
            )
            node_ids: set[str] = {document["item_id"] for document in all_documents}
            all_documents.rewind()

        else:
            all_documents = list(
                flask_mongo.db.items.find(
                    {
                        "$or": [{"item_id": item_id}, {"relationships.item_id": item_id}],
                        **get_default_permissions(user_only=False),
                    },
                    projection={"item_id": 1, "name": 1, "type": 1, "relationships": 1},
                )
            )

            node_ids = {document["item_id"] for document in all_documents} | {
                relationship.get("item_id")
                for document in all_documents
                for relationship in document.get("relationships", [])
            }
            if len(node_ids) > 1:
                or_query = [{"item_id": id} for id in node_ids if id != item_id]
                next_shell = flask_mongo.db.items.find(
                    {
                        "$or": or_query,
                        **get_default_permissions(user_only=False),
                    },
                    projection={"item_id": 1, "name": 1, "type": 1, "relationships": 1},
                )

                all_documents.extend(next_shell)
                node_ids = node_ids | {document["item_id"] for document in all_documents}

        nodes = []
        edges = []

        # Collect the elements that have already been added to the graph, to avoid duplication
        drawn_elements = set()
        node_collections: set[str] = set()
        for document in all_documents:
            # for some reason, document["relationships"] is sometimes equal to None, so we
            # need this `or` statement.
            for relationship in document.get("relationships") or []:
                # only considering child-parent relationships
                if relationship.get("type") == "collections" and not collection_id:
                    if hide_collections:
                        continue
                    collection_data = flask_mongo.db.collections.find_one(
                        {
                            "_id": relationship["immutable_id"],
                            **get_default_permissions(user_only=False),
                        },
                        projection={"collection_id": 1, "title": 1, "type": 1},
                    )
                    if collection_data:
                        if relationship["immutable_id"] not in node_collections:
                            _id = f"Collection: {collection_data['collection_id']}"
                            if _id not in drawn_elements:
                                nodes.append(
                                    {
                                        "data": {
                                            "id": _id,
                                            "name": collection_data["title"],
                                            "type": collection_data["type"],
                                            "shape": "triangle",
                                        }
                                    }
                                )
                                node_collections.add(relationship["immutable_id"])
                                drawn_elements.add(_id)

                        source = f"Collection: {collection_data['collection_id']}"
                        target = document.get("item_id")
                        if target in node_ids:
                            edges.append(
                                {
                                    "data": {
                                        "id": f"{source}->{target}",
                                        "source": source,
                                        "target": target,
                                        "value": 1,
                                    }
                                }
                            )
                    continue

            for relationship in document.get("relationships") or []:
                # only considering child-parent relationships:
                if relationship.get("relation") not in (
                    "parent",
                    "is_part_of",
                    RelationshipType.PARENT.value,
                ):
                    continue

                target = document["item_id"]
                source = relationship["item_id"]
                if source not in node_ids or target not in node_ids:
                    continue
                edge_id = f"{source}->{target}"
                if edge_id not in drawn_elements:
                    drawn_elements.add(edge_id)
                    edges.append(
                        {
                            "data": {
                                "id": edge_id,
                                "source": source,
                                "target": target,
                                "value": 1,
                            }
                        }
                    )

            if document["item_id"] not in drawn_elements:
                drawn_elements.add(document["item_id"])
                nodes.append(
                    {
                        "data": {
                            "id": document["item_id"],
                            "name": document.get("name") or document["item_id"],
                            "type": document["type"],
                            "special": document["item_id"] == item_id,
                        }
                    }
                )

        whitelist = {edge["data"]["source"] for edge in edges} | {item_id}

        nodes = [
            node
            for node in nodes
            if node["data"]["type"] in ("samples", "cells") or node["data"]["id"] in whitelist
        ]

        result = {"nodes": nodes, "edges": edges}
        LOGGER.debug(f"Graph result: nodes={len(nodes)}, edges={len(edges)}")
        return jsonify(result), 200

    except Exception as e:
        LOGGER.exception(f"Error in get_graph_cy_format: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
