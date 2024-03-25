from bson import ObjectId
from flask import Blueprint, jsonify, request
from flask_login import current_user
from pydantic import EmailStr

from pydatalab.models.people import DisplayName

from pydatalab.mongo import flask_mongo
from pydatalab.permissions import get_default_permissions


user = Blueprint("users", __name__)


@user.route("/users")
def get_users():
    users = flask_mongo.db.users.aggregate([
        {"$match": get_default_permissions(user_only=True)},
        {
            "$lookup": {
                "from": "roles",
                "localField": "_id",
                "foreignField": "_id",
                "as": "role"
            }
        },
        {
            "$addFields": {
                "role": {
                    "$cond": {
                        "if": {"$eq": [{"$size": "$role"}, 0]},
                        "then": "user",
                        "else": {"$arrayElemAt": ["$role.role", 0]}
                    }
                }
            }
        }
    ])

    return jsonify({"status": "success", "data": list(users)})


@user.route("/users/<user_id>", methods=["PATCH"])
def save_user(user_id):
    request_json = request.get_json()

    display_name = request_json.get("display_name")
    contact_email = request_json.get("contact_email")

    if not current_user.is_authenticated:
        return jsonify(status="error"), 401

    if current_user.id != user_id and current_user.role != "admin":
        return jsonify(status="error"), 403

    update_data = {"display_name": DisplayName(display_name)}

    if contact_email == "":
        contact_email = None

    update_data["contact_email"] = EmailStr(
        contact_email) if contact_email is not None else None

    try:
        update_result = flask_mongo.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data},
        )
    except Exception as e:
        return jsonify(status="error", detail=str(e)), 500

    if update_result.modified_count != 1:
        return jsonify(
            status="error",
            detail="User does not have the appropriate permissions to update the given user ID.",
        ), 403

    return jsonify(status="success"), 200
