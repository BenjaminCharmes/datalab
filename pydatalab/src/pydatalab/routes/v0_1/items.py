import datetime
import json

from bson import ObjectId
from flask import Blueprint, jsonify, redirect, request
from flask_login import current_user
from pydantic import ValidationError
from pymongo.command_cursor import CommandCursor
from pymongo.errors import DuplicateKeyError
from werkzeug.exceptions import BadRequest

from pydatalab.apps import BLOCK_TYPES
from pydatalab.config import CONFIG
from pydatalab.logger import LOGGER
from pydatalab.middleware import clean_objectids_middleware
from pydatalab.models import ITEM_MODELS
from pydatalab.models.items import Item
from pydatalab.models.people import Person
from pydatalab.models.relationships import RelationshipType
from pydatalab.models.utils import generate_unique_refcode
from pydatalab.mongo import flask_mongo
from pydatalab.permissions import PUBLIC_USER_ID, active_users_or_get_only, get_default_permissions

ITEMS = Blueprint("items", __name__)


@ITEMS.before_request
@active_users_or_get_only
def _(): ...


def reserialize_blocks(display_order: list[str], blocks_obj: dict[str, dict]) -> dict[str, dict]:
    """Create the corresponding Python objects from JSON block data, then
    serialize it again as JSON to populate any missing properties.

    Parameters:
        blocks_obj: A dictionary containing the JSON block data, keyed by block ID.

    Returns:
        A dictionary with the re-serialized block data.

    """
    for block_id in display_order:
        try:
            block_data = blocks_obj[block_id]
        except KeyError:
            LOGGER.warning(f"block_id {block_id} found in display order but not in blocks_obj")
            continue
        blocktype = block_data["blocktype"]
        blocks_obj[block_id] = (
            BLOCK_TYPES.get(blocktype, BLOCK_TYPES["notsupported"]).from_db(block_data).to_web()
        )

    return blocks_obj


# Seems to be obselete now?
def dereference_files(file_ids: list[str | ObjectId]) -> dict[str, dict]:
    """For a list of Object IDs (as strings or otherwise), query the files collection
    and return a dictionary of the data stored under each ID.

    Parameters:
        file_ids: The list of IDs of files to return;

    Returns:
        The dereferenced data as a dictionary with (string) ID keys.

    """
    results = {
        str(f["_id"]): f
        for f in flask_mongo.db.files.find(
            {
                "_id": {"$in": [ObjectId(_id) for _id in file_ids]},
            }
        )
    }
    if len(results) != len(file_ids):
        raise RuntimeError(
            "Some file IDs did not have corresponding database entries.\n"
            f"Returned: {list(results.keys())}\n"
            f"Requested: {file_ids}\n"
        )

    return results


@ITEMS.route("/equipment/", methods=["GET"])
def get_equipment_summary():
    _project = {
        "_id": 0,
        "item_id": 1,
        "name": 1,
        "type": 1,
        "date": 1,
        "refcode": 1,
        "location": 1,
    }

    items = [
        doc
        for doc in flask_mongo.db.items.aggregate(
            [
                {
                    "$match": {
                        "type": "equipment",
                    }
                },
                {"$project": _project},
            ]
        )
    ]
    return jsonify({"status": "success", "items": items})


@ITEMS.route("/starting-materials/", methods=["GET"])
def get_starting_materials():
    items = [
        doc
        for doc in flask_mongo.db.items.aggregate(
            [
                {
                    "$match": {
                        "type": "starting_materials",
                        **get_default_permissions(user_only=False),
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "item_id": 1,
                        "blocks": {"blocktype": 1, "title": 1},
                        "nblocks": {"$size": "$display_order"},
                        "nfiles": {"$size": "$file_ObjectIds"},
                        "date": 1,
                        "chemform": 1,
                        "name": 1,
                        "type": 1,
                        "chemical_purity": 1,
                        "barcode": 1,
                        "refcode": 1,
                        "supplier": 1,
                        "location": 1,
                    }
                },
                {
                    "$sort": {
                        "date": -1,
                    },
                },
            ]
        )
    ]
    return jsonify({"status": "success", "items": items})


get_starting_materials.methods = ("GET",)  # type: ignore


def get_items_summary(match: dict | None = None, project: dict | None = None) -> CommandCursor:
    """Return a summary of item entries that match some criteria.

    Parameters:
        match: A MongoDB aggregation match query to filter the results.
        project: A MongoDB aggregation project query to filter the results, relative
            to the default included below.

    """
    if not match:
        match = {}
    match.update(get_default_permissions(user_only=False))

    _project = {
        "_id": 0,
        "blocks": {"blocktype": 1, "title": 1},
        "creators": {
            "display_name": 1,
            "contact_email": 1,
        },
        "collections": {
            "collection_id": 1,
            "title": 1,
        },
        "item_id": 1,
        "name": 1,
        "chemform": 1,
        "nblocks": {"$size": "$display_order"},
        "nfiles": {"$size": "$file_ObjectIds"},
        "characteristic_chemical_formula": 1,
        "type": 1,
        "date": 1,
        "refcode": 1,
    }

    # Cannot mix 0 and 1 keys in MongoDB project so must loop and check
    if project:
        for key in project:
            if project[key] == 0:
                _project.pop(key, None)
            else:
                _project[key] = 1

    return flask_mongo.db.items.aggregate(
        [
            {"$match": match},
            {"$lookup": creators_lookup()},
            {"$lookup": collections_lookup()},
            {"$project": _project},
            {"$sort": {"date": -1}},
        ]
    )


def get_samples_summary(match: dict | None = None, project: dict | None = None) -> CommandCursor:
    """Return a summary of samples/cells entries that match some criteria.

    Parameters:
        match: A MongoDB aggregation match query to filter the results.
        project: A MongoDB aggregation project query to filter the results, relative
            to the default included below.

    """
    if not match:
        match = {}
    match.update(get_default_permissions(user_only=False))
    match["type"] = {"$in": ["samples", "cells"]}

    _project = {
        "_id": 0,
        "blocks": {"blocktype": 1, "title": 1},
        "creators": {
            "display_name": 1,
            "contact_email": 1,
        },
        "collections": {
            "collection_id": 1,
            "title": 1,
        },
        "item_id": 1,
        "name": 1,
        "chemform": 1,
        "nblocks": {"$size": "$display_order"},
        "nfiles": {"$size": "$file_ObjectIds"},
        "characteristic_chemical_formula": 1,
        "type": 1,
        "date": 1,
        "refcode": 1,
    }

    # Cannot mix 0 and 1 keys in MongoDB project so must loop and check
    if project:
        for key in project:
            if project[key] == 0:
                _project.pop(key, None)
            else:
                _project[key] = 1

    return flask_mongo.db.items.aggregate(
        [
            {"$match": match},
            {"$lookup": creators_lookup()},
            {"$lookup": collections_lookup()},
            {"$project": _project},
            {"$sort": {"date": -1}},
        ]
    )


def creators_lookup() -> dict:
    return {
        "from": "users",
        "let": {"creator_ids": "$creator_ids"},
        "pipeline": [
            {"$match": {"$expr": {"$in": ["$_id", {"$ifNull": ["$$creator_ids", []]}]}}},
            {"$addFields": {"__order": {"$indexOfArray": ["$$creator_ids", "$_id"]}}},
            {"$sort": {"__order": 1}},
            {"$project": {"_id": 1, "display_name": 1, "contact_email": 1}},
        ],
        "as": "creators",
    }


def files_lookup() -> dict:
    return {
        "from": "files",
        "localField": "file_ObjectIds",
        "foreignField": "_id",
        "as": "files",
    }


def collections_lookup() -> dict:
    """Looks inside the relationships of the item, searches for IDs in the collections
    table and then projects only the collection ID and name for the response.

    """

    return {
        "from": "collections",
        "let": {"collection_ids": "$relationships.immutable_id"},
        "pipeline": [
            {
                "$match": {
                    "$expr": {
                        "$in": ["$_id", {"$ifNull": ["$$collection_ids", []]}],
                    },
                    "type": "collections",
                }
            },
            {"$project": {"_id": 1, "collection_id": 1}},
        ],
        "as": "collections",
    }


def _check_collections(sample_dict: dict) -> list[dict[str, str]]:
    """Loop through the provided collection metadata for the sample and
    return the list of references to store (i.e., just the `immutable_id`
    of the collection).

    Raises:
        ValueError: if any of the linked collections cannot be found in
        the database.

    Returns:
        A list of dictionaries with singular key `immutable_id` returning
        the database ID of the collection.

    """
    if sample_dict.get("collections", []):
        for ind, c in enumerate(sample_dict.get("collections", [])):
            query = {}
            query.update(c)
            if "immutable_id" in c:
                query["_id"] = ObjectId(query.pop("immutable_id"))
            result = flask_mongo.db.collections.find_one({**query, **get_default_permissions()})
            if not result:
                raise ValueError(f"No collection found matching request: {c}")
            sample_dict["collections"][ind] = {"immutable_id": result["_id"]}

    return sample_dict.get("collections", []) or []


@ITEMS.route("/samples/", methods=["GET"])
def get_samples():
    return jsonify({"status": "success", "samples": list(get_samples_summary())})


@ITEMS.route("/search-items/", methods=["GET"])
def search_items():
    """Perform free text search on items and return the top results.
    GET parameters:
        query: String with the search terms.
        nresults: Maximum number of  (default 100)
        types: If None, search all types of items. Otherwise, a list of strings
               giving the types to consider. (e.g. ["samples","starting_materials"])

    Returns:
        response list of dictionaries containing the matching items in order of
        descending match score.
    """
    try:
        query = request.args.get("query", type=str)
        nresults = request.args.get("nresults", default=100, type=int)
        types = request.args.get("types", default=None)
        if isinstance(types, str):
            # should figure out how to parse as list automatically
            types = types.split(",")

        pipeline = []

        if isinstance(query, str):
            query = query.strip("'")

        if isinstance(query, str) and query.startswith("%"):
            query = query.lstrip("%")
            match_obj = {
                "$text": {"$search": query},
                **get_default_permissions(user_only=False),
            }
            if types is not None:
                match_obj["type"] = {"$in": types}

            pipeline.append({"$match": match_obj})
            pipeline.append({"$sort": {"score": {"$meta": "textScore"}}})

        else:
            regex_fields = ["item_id", "name", "description", "chemform", "refcode"]
            match_obj = {
                "$or": [{field: {"$regex": query, "$options": "i"}} for field in regex_fields]
            }
            match_obj = {"$and": [get_default_permissions(user_only=False), match_obj]}
            if types is not None:
                match_obj["$and"].append({"type": {"$in": types}})

            pipeline.append({"$match": match_obj})

        pipeline.append({"$limit": nresults})
        pipeline.append(
            {
                "$project": {
                    "_id": 0,
                    "type": 1,
                    "item_id": 1,
                    "name": 1,
                    "chemform": 1,
                    "refcode": 1,
                }
            }
        )

        cursor = flask_mongo.db.items.aggregate(pipeline)

        return jsonify({"status": "success", "items": list(cursor)}), 200
    except Exception as e:
        LOGGER.exception(f"Error in search_items: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


def _create_sample(
    sample_dict: dict,
    copy_from_item_id: str | None = None,
    generate_id_automatically: bool = False,
) -> tuple[dict, int]:
    sample_dict["item_id"] = sample_dict.get("item_id")
    if generate_id_automatically and sample_dict["item_id"]:
        return (
            dict(
                status="error",
                messages=f"""Request to create item with generate_id_automatically = true is incompatible with the provided item data,
                which has an item_id included (provided id: {sample_dict["item_id"]}")""",
            ),
            400,
        )

    if copy_from_item_id:
        copied_doc = flask_mongo.db.items.find_one({"item_id": copy_from_item_id})

        LOGGER.debug(f"Copying from pre-existing item {copy_from_item_id} with data:\n{copied_doc}")
        if not copied_doc:
            return (
                dict(
                    status="error",
                    message=f"Request to copy item with id {copy_from_item_id} failed because item could not be found.",
                    item_id=sample_dict["item_id"],
                ),
                404,
            )

        # the provided item_id, name, and date take precedence over the copied parameters, if provided
        try:
            copied_doc["item_id"] = sample_dict["item_id"]
            copied_doc.pop("_id", None)
        except KeyError:
            return (
                dict(
                    status="error",
                    message=f"Request to copy item with id {copy_from_item_id} to new item failed because the target new item_id was not provided.",
                    item_id=sample_dict["item_id"],
                ),
                404,
            )

        copied_doc["name"] = sample_dict.get("name")
        copied_doc["date"] = sample_dict.get("date")

        # any provided constituents will be added to the synthesis information table in
        # addition to the constituents copied from the copy_from_item_id, avoiding duplicates
        if copied_doc["type"] == "samples":
            existing_consituent_ids = [
                constituent["item"].get("item_id", None)
                for constituent in copied_doc["synthesis_constituents"]
            ]
            copied_doc["synthesis_constituents"] += [
                constituent
                for constituent in sample_dict.get("synthesis_constituents", [])
                if constituent["item"].get("item_id") is None
                or constituent["item"].get("item_id") not in existing_consituent_ids
            ]
            sample_dict = copied_doc

        elif copied_doc["type"] == "cells":
            for component in (
                "positive_electrode",
                "negative_electrode",
                "electrolyte",
            ):
                existing_consituent_ids = [
                    constituent["item"].get("item_id", None)
                    for constituent in copied_doc[component]
                ]
                copied_doc[component] += [
                    constituent
                    for constituent in sample_dict.get(component, [])
                    if constituent["item"].get("item_id", None) is None
                    or constituent["item"].get("item_id") not in existing_consituent_ids
                ]

            sample_dict = copied_doc

    try:
        # If passed collection data, dereference it and check if the collection exists
        sample_dict["collections"] = _check_collections(sample_dict)
    except ValueError as exc:
        return (
            dict(
                status="error",
                message=f"Unable to create new item {sample_dict['item_id']!r} inside non-existent collection(s): {exc}",
                item_id=sample_dict["item_id"],
            ),
            401,
        )

    sample_dict.pop("refcode", None)
    type_ = sample_dict["type"]
    if type_ not in ITEM_MODELS:
        raise BadRequest(f"Invalid type {type_!r}, must be one of {ITEM_MODELS.keys()}")

    model = ITEM_MODELS[type_]

    # the following code was used previously to explicitely check schema properties.
    # it doesn't seem to be necessary now, with extra = "ignore" turned on in the pydantic models,
    # and it breaks in instances where the models use aliases (e.g., in the starting_material model)
    # so we are taking it out now, but leaving this comment in case it needs to be reverted.
    # schema = model.schema()
    # new_sample = {k: sample_dict[k] for k in schema["properties"] if k in sample_dict}
    new_sample = sample_dict

    if type_ in ("starting_materials", "equipment"):
        # starting_materials and equipment are open to all in the deploment at this point,
        # so no creators are assigned
        new_sample["creator_ids"] = []
        new_sample["creators"] = []
    elif CONFIG.TESTING:
        # Set fake ID to ObjectId("000000000000000000000000") so a dummy user can be created
        # locally for testing creator UI elements
        new_sample["creator_ids"] = [str(PUBLIC_USER_ID)]
        new_sample["creators"] = [
            {
                "display_name": "Public testing user",
            }
        ]
    else:
        new_sample["creator_ids"] = [str(current_user.person.immutable_id)]
        new_sample["creators"] = [
            {
                "display_name": current_user.person.display_name,
                "contact_email": current_user.person.contact_email,
            }
        ]

    if "file_ObjectIds" in new_sample and isinstance(new_sample["file_ObjectIds"], list):
        from pydatalab.models.utils import PyObjectId

        new_sample["file_ObjectIds"] = [
            PyObjectId(id_) if isinstance(id_, str) else id_ for id_ in new_sample["file_ObjectIds"]
        ]

    # Generate a unique refcode for the sample
    new_sample["refcode"] = generate_unique_refcode()
    if generate_id_automatically:
        new_sample["item_id"] = new_sample["refcode"].split(":")[1]

    # check to make sure that item_id isn't taken already
    if flask_mongo.db.items.find_one({"item_id": str(sample_dict["item_id"])}):
        LOGGER.debug("item_id %s already exists in database", sample_dict["item_id"])
        return (
            dict(
                status="error",
                message=f"item_id_validation_error: {sample_dict['item_id']!r} already exists in database.",
                item_id=new_sample["item_id"],
            ),
            409,  # 409: Conflict
        )

    new_sample["date"] = new_sample.get("date", datetime.datetime.now(tz=datetime.timezone.utc))
    try:
        if "immutable_id" in new_sample:
            del new_sample["immutable_id"]

        data_model: Item = model(**new_sample)

    except ValidationError as error:
        return (
            dict(
                status="error",
                message=f"Unable to create new item with ID {new_sample['item_id']}: {str(error)}.",
                item_id=new_sample["item_id"],
                output=str(error),
            ),
            400,
        )

    # Do not store the fields `collections` or `creators` in the database as these should be populated
    # via joins for a specific query.
    # TODO: encode this at the model level, via custom schema properties or hard-coded `.store()` methods
    # the `Entry` model.
    try:
        result = flask_mongo.db.items.insert_one(
            data_model.model_dump(
                exclude={"creators", "collections"}, exclude_none=True, by_alias=True
            )
        )
    except DuplicateKeyError as error:
        LOGGER.debug("item_id %s already exists in database", sample_dict["item_id"], sample_dict)
        return (
            dict(
                status="error",
                message=f"Duplicate key error: {str(error)}.",
                item_id=new_sample["item_id"],
            ),
            409,
        )

    if not result.acknowledged:
        return (
            dict(
                status="error",
                message=f"Failed to add new item {new_sample['item_id']!r} to database.",
                item_id=new_sample["item_id"],
                output=result.raw_result,
            ),
            400,
        )

    sample_list_entry = {
        "refcode": data_model.refcode,
        "item_id": data_model.item_id,
        "nblocks": 0,
        "nfiles": 0,
        "date": data_model.date,
        "name": data_model.name,
        "creator_ids": data_model.creator_ids,
        # TODO: This workaround for creators & collections is still gross, need to figure this out properly
        "creators": [json.loads(c.model_dump_json(exclude_unset=True)) for c in data_model.creators]
        if data_model.creators
        else [],
        "collections": [
            json.loads(c.model_dump_json(exclude_unset=True, exclude_none=True))
            for c in data_model.collections
        ]
        if data_model.collections
        else [],
        "type": data_model.type,
    }

    # hack to let us use _create_sample() for equipment too. We probably want to make
    # a more general create_item() to more elegantly handle different returns.
    if data_model.type == "equipment":
        sample_list_entry["location"] = data_model.location

    return (
        {
            "status": "success",
            "item_id": data_model.item_id,
            "sample_list_entry": sample_list_entry,
        },
        201,  # 201: Created
    )


@ITEMS.route("/new-sample/", methods=["POST"])
def create_sample():
    request_json = request.get_json()  # noqa: F821 pylint: disable=undefined-variable
    if "new_sample_data" in request_json:
        response, http_code = _create_sample(
            sample_dict=request_json["new_sample_data"],
            copy_from_item_id=request_json.get("copy_from_item_id"),
            generate_id_automatically=request_json.get("generate_id_automatically", False),
        )
    else:
        response, http_code = _create_sample(request_json)

    return jsonify(response), http_code


@ITEMS.route("/new-samples/", methods=["POST"])
def create_samples():
    """attempt to create multiple samples at once.
    Because each may result in success or failure, 207 is returned along with a
    json field containing all the individual http_codes"""

    request_json = request.get_json()  # noqa: F821 pylint: disable=undefined-variable

    sample_jsons = request_json["new_sample_datas"]

    if len(sample_jsons) > CONFIG.MAX_BATCH_CREATE_SIZE:
        return jsonify(
            {
                "status": "error",
                "message": f"Batch size limit exceeded. Maximum allowed: {CONFIG.MAX_BATCH_CREATE_SIZE}, requested: {len(sample_jsons)}",
            }
        ), 400

    copy_from_item_ids = request_json.get("copy_from_item_ids")
    generate_ids_automatically = request_json.get("generate_ids_automatically")

    if copy_from_item_ids is None:
        copy_from_item_ids = [None] * len(sample_jsons)

    outputs = [
        _create_sample(
            sample_dict=sample_json,
            copy_from_item_id=copy_from_item_id,
            generate_id_automatically=generate_ids_automatically,
        )
        for sample_json, copy_from_item_id in zip(sample_jsons, copy_from_item_ids)
    ]
    responses, http_codes = zip(*outputs)

    statuses = [response["status"] for response in responses]
    nsuccess = statuses.count("success")
    nerror = statuses.count("error")

    return (
        jsonify(
            nsuccess=nsuccess,
            nerror=nerror,
            responses=responses,
            http_codes=http_codes,
        ),
        207,
    )  # 207: multi-status


@ITEMS.route("/items/<refcode>/permissions", methods=["PATCH"])
def update_item_permissions(refcode: str):
    """Update the permissions of an item with the given refcode."""

    request_json = request.get_json()
    creator_ids: list[ObjectId] = []

    if len(refcode.split(":")) != 2:
        refcode = f"{CONFIG.IDENTIFIER_PREFIX}:{refcode}"

    current_item = flask_mongo.db.items.find_one(
        {"refcode": refcode, **get_default_permissions(user_only=True)},
        {"_id": 1, "creator_ids": 1},
    )  # type: ignore

    if not current_item:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": f"No valid item found with the given {refcode=}.",
                }
            ),
            401,
        )

    current_creator_ids = current_item["creator_ids"]

    if "creators" in request_json:
        creator_ids = [
            ObjectId(creator.get("immutable_id", None))
            for creator in request_json["creators"]
            if creator.get("immutable_id", None) is not None
        ]

    if not creator_ids:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "No valid creator IDs found in the request.",
                }
            ),
            400,
        )

    # Validate all creator IDs are present in the database
    found_ids = [d for d in flask_mongo.db.users.find({"_id": {"$in": creator_ids}}, {"_id": 1})]  # type: ignore
    if len(found_ids) != len(creator_ids):
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "One or more creator IDs not found in the database.",
                }
            ),
            400,
        )

    # Make sure a user cannot remove their own access to an item
    current_user_id = current_user.person.immutable_id
    try:
        creator_ids.remove(current_user_id)
    except ValueError:
        pass
    creator_ids.insert(0, current_user_id)

    # The first ID in the creator list takes precedence; always make sure this is included to avoid orphaned items
    if current_creator_ids:
        base_owner = current_creator_ids[0]
        try:
            creator_ids.remove(base_owner)
        except ValueError:
            pass
        creator_ids.insert(0, base_owner)

    if set(creator_ids) == set(current_creator_ids):
        # Short circuit if the creator IDs are the same
        return jsonify({"status": "success"}), 200

    LOGGER.warning("Setting permissions for item %s to %s", refcode, creator_ids)
    result = flask_mongo.db.items.update_one(
        {"refcode": refcode, **get_default_permissions(user_only=True)},
        {"$set": {"creator_ids": creator_ids}},
    )

    if result.modified_count != 1:
        return jsonify(
            {
                "status": "error",
                "message": "Failed to update permissions: you cannot remove yourself or the base owner as a creator.",
            }
        ), 400

    return jsonify({"status": "success"}), 200


@ITEMS.route("/delete-sample/", methods=["POST"])
def delete_sample():
    request_json = request.get_json()  # noqa: F821 pylint: disable=undefined-variable
    item_id = request_json["item_id"]

    result = flask_mongo.db.items.delete_one(
        {"item_id": item_id, **get_default_permissions(user_only=True, deleting=True)}
    )

    if result.deleted_count != 1:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": f"Authorization required to attempt to delete sample with {item_id=} from the database.",
                }
            ),
            401,
        )
    return (
        jsonify(
            {
                "status": "success",
            }
        ),
        200,
    )


@ITEMS.route("/items/<refcode>", methods=["GET"])
@ITEMS.route("/get-item-data/<item_id>", methods=["GET"])
def get_item_data(
    item_id: str | None = None, refcode: str | None = None, load_blocks: bool = False
):
    """Generates a JSON response for the item with the given `item_id`,
    or `refcode` additionally resolving relationships to files and other items.

    Parameters:
       load_blocks: Whether to regenerate any data blocks associated with this
           sample (i.e., create the Python object corresponding to the block and
           call its render function).

    """
    try:
        redirect_to_ui = bool(request.args.get("redirect-to-ui", default=False, type=json.loads))
        if refcode and redirect_to_ui and CONFIG.APP_URL:
            return redirect(f"{CONFIG.APP_URL}/items/{refcode}", code=307)

        if item_id:
            match = {"item_id": item_id}
        elif refcode:
            if len(refcode.split(":")) != 2:
                refcode = f"{CONFIG.IDENTIFIER_PREFIX}:{refcode}"
            match = {"refcode": refcode}
        else:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "No item_id or refcode provided.",
                    }
                ),
                400,
            )

        # retrieve the entry from the database:
        cursor = flask_mongo.db.items.aggregate(
            [
                {
                    "$match": {
                        **match,
                        **get_default_permissions(user_only=False),
                    }
                },
                {"$lookup": creators_lookup()},
                {"$lookup": collections_lookup()},
                {"$lookup": files_lookup()},
            ],
        )

        try:
            doc = list(cursor)[0]

        except IndexError:
            doc = None

        if not doc:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"No matching items for {match=} with current authorization.",
                    }
                ),
                404,
            )

        try:
            ItemModel = ITEM_MODELS[doc["type"]]
        except KeyError:
            if "type" in doc:
                raise KeyError(f"Item {item_id=} has invalid type: {doc['type']}")
            else:
                raise KeyError(f"Item {item_id=} has no type field in document.")

        try:
            doc = ItemModel(**doc)
        except ValidationError as e:
            LOGGER.error(f"Pydantic validation error: {e}")
            LOGGER.error(f"Document keys: {list(doc.keys())}")
            raise

        if load_blocks:
            doc.blocks_obj = reserialize_blocks(doc.display_order, doc.blocks_obj)

        # find any documents with relationships that mention this document
        relationships_query_results = flask_mongo.db.items.find(
            filter={
                "$or": [
                    {"relationships.item_id": doc.item_id},
                    {"relationships.refcode": doc.refcode},
                    {"relationships.immutable_id": doc.immutable_id},
                ]
            },
            projection={
                "item_id": 1,
                "refcode": 1,
                "relationships": {
                    "$elemMatch": {
                        "$or": [
                            {"item_id": doc.item_id},
                            {"refcode": doc.refcode},
                        ],
                    },
                },
            },
        )

        # loop over and collect all 'outer' relationships presented by other items
        incoming_relationships: dict[RelationshipType, set[str]] = {}
        for d in relationships_query_results:
            for k in d["relationships"]:
                if k["relation"] not in incoming_relationships:
                    incoming_relationships[k["relation"]] = set()
                incoming_relationships[k["relation"]].add(
                    d["item_id"] or d["refcode"] or d["immutable_id"]
                )

        # loop over and aggregate all 'inner' relationships presented by this item
        inlined_relationships: dict[RelationshipType, set[str]] = {}
        if doc.relationships is not None:
            inlined_relationships = {
                relation: {
                    d.item_id or d.refcode or d.immutable_id
                    for d in doc.relationships
                    if d.relation == relation
                }
                for relation in RelationshipType
            }

        # reunite parents and children from both directions of the relationships field
        parents = incoming_relationships.get(RelationshipType.CHILD, set()).union(
            inlined_relationships.get(RelationshipType.PARENT, set())
        )
        children = incoming_relationships.get(RelationshipType.PARENT, set()).union(
            inlined_relationships.get(RelationshipType.CHILD, set())
        )

        # Must be exported to JSON first to apply the custom pydantic JSON encoders
        try:
            return_dict = doc.model_dump(mode="json", exclude_unset=True)
        except Exception:
            from bson import json_util

            return_dict = doc.model_dump(exclude_unset=True)
            json_str = json_util.dumps(return_dict)
            return_dict = json.loads(json_str)

            def clean_mongodb_dates(obj):
                """Recursively clean MongoDB date format {'$date': '...'} to ISO strings"""
                if isinstance(obj, dict):
                    if "$date" in obj and len(obj) == 1:
                        return obj["$date"]
                    elif "$oid" in obj and len(obj) == 1:
                        return obj["$oid"]
                    else:
                        return {k: clean_mongodb_dates(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [clean_mongodb_dates(item) for item in obj]
                else:
                    return obj

            return_dict = clean_mongodb_dates(return_dict)

        if item_id is None:
            item_id = return_dict["item_id"]

        # create the files_data dictionary keyed by file ObjectId
        files_data: dict[str, dict] = {}
        for f in return_dict.get("files") or []:
            file_id_str = str(f.get("immutable_id", ""))
            if file_id_str and file_id_str != "None":
                files_data[file_id_str] = {**f, "immutable_id": file_id_str, "_id": file_id_str}

        if not files_data:
            files_data = {}

        return jsonify(
            {
                "status": "success",
                "item_id": item_id,
                "item_data": return_dict,
                "files_data": files_data,
                "child_items": sorted(children),
                "parent_items": sorted(parents),
            }
        )
    except Exception as e:
        LOGGER.exception(f"Error in get_item_data: {e}")
        return jsonify({"status": "error", "message": str(e), "error_type": type(e).__name__}), 500


@ITEMS.route("/save-item/", methods=["POST"])
@clean_objectids_middleware
def save_item():
    request_json = request.get_json()  # noqa: F821 pylint: disable=undefined-variable

    if "item_id" not in request_json:
        raise BadRequest(
            "`/save-item/` endpoint requires 'item_id' to be passed in JSON request body"
        )

    if "data" not in request_json:
        raise BadRequest("`/save-item/` endpoint requires 'data' to be passed in JSON request body")

    item_id = str(request_json["item_id"])
    updated_data = request_json["data"]

    # These keys should not be updated here and cannot be modified by the user through this endpoint
    for k in (
        "_id",
        "file_ObjectIds",
        "files",
        "creators",
        "creator_ids",
        "item_id",
        "relationships",
    ):
        if k in updated_data:
            del updated_data[k]

    updated_data["last_modified"] = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

    for block_id, block_data in updated_data.get("blocks_obj", {}).items():
        blocktype = block_data["blocktype"]

        block = BLOCK_TYPES.get(blocktype, BLOCK_TYPES["notsupported"]).from_web(block_data)

        updated_data["blocks_obj"][block_id] = block.to_db()

    # Bit of a hack for now: starting materials and equipment should be editable by anyone,
    # so we adjust the query above to be more permissive when the user is requesting such an item
    # but before returning we need to check that the actual item did indeed have that type
    item = flask_mongo.db.items.find_one(
        {"item_id": item_id, **get_default_permissions(user_only=False)}
    )

    if not item:
        return (
            jsonify(
                status="error",
                message=f"Unable to find item with appropriate permissions and {item_id=}.",
            ),
            404,
        )

    user_only = item["type"] not in ("starting_materials", "equipment")

    item = flask_mongo.db.items.find_one(
        {"item_id": item_id, **get_default_permissions(user_only=user_only)}
    )

    if not item:
        return (
            jsonify(
                status="error",
                message=f"Unable to find item with appropriate permissions and {item_id=}.",
            ),
            404,
        )

    if updated_data.get("collections", []):
        try:
            updated_data["collections"] = _check_collections(updated_data)
        except ValueError as exc:
            return (
                dict(
                    status="error",
                    message=f"Cannot update {item_id!r} with missing collections {updated_data['collections']!r}: {exc}",
                    item_id=item_id,
                ),
                401,
            )

    existing_item = flask_mongo.db.items.find_one({"item_id": item_id})
    if existing_item:
        existing_relationships = existing_item.get("relationships", [])
        non_collection_relationships = [
            rel for rel in existing_relationships if rel.get("type") != "collections"
        ]

        collection_relationships = []
        for coll in updated_data.get("collections", []):
            immutable_id = coll.get("immutable_id")
            collection_id = coll.get("collection_id")

            if immutable_id:
                if isinstance(immutable_id, str):
                    from bson import ObjectId

                    immutable_id = ObjectId(immutable_id)
            elif collection_id:
                collection_doc = flask_mongo.db.collections.find_one(
                    {"collection_id": collection_id}
                )
                if collection_doc:
                    immutable_id = collection_doc["_id"]

            if immutable_id:
                collection_relationships.append(
                    {
                        "relation": None,
                        "immutable_id": immutable_id,
                        "type": "collections",
                        "description": "Is a member of",
                    }
                )

        updated_data["relationships"] = non_collection_relationships + collection_relationships

    item_type = item["type"]
    item.update(updated_data)

    try:
        model_instance = ITEM_MODELS[item_type](**item)
        item = model_instance.model_dump(
            exclude_none=True,
            exclude_unset=True,
            by_alias=True,
            exclude={"collections", "creators"},
        )
    except ValidationError as exc:
        return (
            jsonify(
                status="error",
                message=f"Unable to update item {item_id=} ({item_type=}) with new data {updated_data}",
                output=str(exc),
            ),
            400,
        )

    # remove collections and creators and any other reference fields
    item.pop("collections", None)
    item.pop("creators", None)

    result = flask_mongo.db.items.update_one(
        {"item_id": item_id},
        {"$set": item},
    )

    if result.matched_count != 1:
        return (
            jsonify(
                status="error",
                message=f"{item_id} item update failed. no subdocument matched",
                output=result.raw_result,
            ),
            400,
        )

    return jsonify(status="success", last_modified=updated_data["last_modified"]), 200


@ITEMS.route("/search-users/", methods=["GET"])
def search_users():
    """Perform free text search on users and return the top results.
    GET parameters:
        query: String with the search terms.
        nresults: Maximum number of  (default 100)

    Returns:
        response list of dictionaries containing the matching items in order of
        descending match score.
    """

    query = request.args.get("query", type=str)
    nresults = request.args.get("nresults", default=100, type=int)
    types = request.args.get("types", default=None)

    match_obj = {"$text": {"$search": query}}
    if types is not None:
        match_obj["type"] = {"$in": types}

    cursor = flask_mongo.db.users.aggregate(
        [
            {"$match": match_obj},
            {"$sort": {"score": {"$meta": "textScore"}}},
            {"$limit": nresults},
            {
                "$project": {
                    "_id": 1,
                    "identities": 1,
                    "display_name": 1,
                    "contact_email": 1,
                }
            },
        ]
    )
    return jsonify(
        {
            "status": "success",
            "users": list(json.loads(Person(**d).model_dump_json()) for d in cursor),
        }
    ), 200
