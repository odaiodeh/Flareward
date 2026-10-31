import logging

from flask import Blueprint, jsonify, current_app
from mas.application.actions.contracts import ActionContext, ActionType
from mas.application.actions.service import ActionMissing, ActionInputInvalid
from mas.core.identity import Identity
from global_utils.utils.async_bridge import get_async_bridge

from inbound.flask.decorators import with_authenticated_user
from global_utils.helpers.apiargs import from_body, from_query
from webargs import fields

logger = logging.getLogger(__name__)

actions_bp = Blueprint("actions", __name__)


@actions_bp.route("/actions.list", methods=["GET"])
@from_query(
    {
        "category": fields.Str(required=False),
        "type": fields.Str(required=False),
        "action_type": fields.Str(data_key="actionType", required=False),
        "tags": fields.List(fields.Str(), required=False),
    }
)
def list_actions(category=None, type=None, action_type=None, tags=None):
    """
    List actions with optional filtering.

    Query parameters:
    - category: Element category (e.g., "PROVIDER", "LLMS") [optional]
    - type: Element type (e.g., "mcp_server", "openai_llm") [optional]
    - actionType: Filter by action type (validation, discovery, utility) [optional]
    - tags: Filter by tags (comma-separated) [optional]

    If no parameters provided, returns all actions.

    Response format:
    {
        "actions": [
            {
                "uid": "mcp.validate_connection",
                "name": "validate_connection",
                "description": "Validate that the MCP server endpoint is reachable",
                "action_type": "validation",
                "elements": [{"category": "PROVIDER", "type": "mcp_server"}],
                "tags": ["mcp", "validation"],
                "input_schema": {...},
                "output_schema": {...}
            }
        ],
        "total_actions": 2,
        "filters_applied": {
            "category": "PROVIDER",
            "type": "mcp_server",
            "action_type": "validation",
            "tags": ["mcp"]
        }
    }
    """
    try:
        svc = current_app.container.actions_service

        # Get actions metadata based on filters - let service handle validation
        actions_metadata = svc.get_actions_metadata(
            action_type=ActionType(action_type.lower()) if action_type else None,
            tags=set(tags) if tags else None,
            category=category,
            element_type=type,
        )

        return jsonify(
            {
                "actions": [item.model_dump(mode="json") for item in actions_metadata],
                "total_actions": len(actions_metadata),
                "filters_applied": {
                    "category": category,
                    "type": type,
                    "action_type": action_type,
                    "tags": tags,
                },
            }
        ), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@actions_bp.route("/action.execute", methods=["POST"])
@with_authenticated_user
@from_body(
    {
        "uid": fields.Str(required=True),
        "input_data": fields.Dict(data_key="inputData", required=False, load_default={}),
        "context": fields.Dict(required=False, load_default={}),
    }
)
def execute_action(authenticated_user, uid, input_data, context):
    """Execute a specific action by UID (synchronously)."""
    try:
        if authenticated_user:
            input_data["user_id"] = authenticated_user

        svc = current_app.container.actions_service
        # Transitional synchronous Flask boundary; the native API never uses this bridge.
        with get_async_bridge() as bridge:
            result = bridge.run(
                svc.execute(
                    uid,
                    input_data,
                    ActionContext(
                        owner=Identity.user(authenticated_user),
                        credential_user_id=authenticated_user,
                        data=context,
                    ),
                )
            ).model_dump(mode="json")

        return jsonify(result), 200

    except ActionMissing:
        return jsonify({"error": "Action not found"}), 404
    except ActionInputInvalid:
        return jsonify({"error": "Invalid action input"}), 422
    except Exception as e:
        logger.exception("Action execution failed: %s", uid)
        return jsonify({"error": "Action execution failed"}), 500
