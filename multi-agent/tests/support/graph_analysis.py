"""An existing chat blueprint for graph-authoring and HTTP compatibility checks."""

from mas.elements.nodes.final_answer.spec.spec import FinalAnswerNodeElementSpec
from mas.elements.nodes.user_question.spec.spec import UserQuestionNodeElementSpec

from support.blueprints import inline_blueprint, library_elements


def graph_elements():
    elements = library_elements()
    elements.register_spec_class(UserQuestionNodeElementSpec)
    elements.register_spec_class(FinalAnswerNodeElementSpec)
    return elements


def graph_blueprint(token="EMPTY"):
    blueprint = inline_blueprint(token).model_dump(mode="json")
    blueprint["nodes"].extend(
        {"rid": rid, "name": rid, "type": kind, "config": {"type": kind}}
        for rid, kind in (("input", "user_question_node"), ("final", "final_answer_node"))
    )
    blueprint["plan"] = [
        {"uid": "start", "node": "input"},
        {"uid": "respond", "node": "agent", "after": "start"},
        {"uid": "finish", "node": "final", "after": "respond"},
    ]
    return blueprint
