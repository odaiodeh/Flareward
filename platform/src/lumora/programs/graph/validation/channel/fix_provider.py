from lumora.elements.catalog.element_registry import ElementRegistry
from lumora.programs.graph.graph_plan import GraphPlan
from lumora.programs.graph.validation.channel.matrix_builder import MatrixBuilder
from lumora.programs.graph.validation.channel.node_suggester import NodeSuggester
from lumora.programs.graph.validation.fix_models import FixSuggestion, FixType
from lumora.programs.graph.validation.interfaces import FixSuggestionProvider
from lumora.programs.graph.validation.models import MessageCode, ValidationReport


class ChannelFixProvider(FixSuggestionProvider):
    """Provides fix suggestions for channel/data flow issues."""

    name = "channel"

    def __init__(self, element_registry: ElementRegistry = None, *args, **kwargs):
        if element_registry is None:
            element_registry = kwargs.get("element_registry")

        if element_registry is None:
            raise ValueError("ChannelFixProvider requires element_registry parameter")

        # Build matrix from registry
        matrix = MatrixBuilder(element_registry).build()
        self._suggester = NodeSuggester()
        self._matrix = matrix

    def suggest_fixes(
        self, plan: GraphPlan, validation_report: ValidationReport | None = None
    ) -> list[FixSuggestion]:
        """Suggest nodes to fix channel/data flow issues."""
        suggestions = []

        if not validation_report or not validation_report.details:
            return suggestions  # No validation context available

        details = validation_report.details

        # Extract message codes from the validation report for consistency
        message_codes = self._extract_message_codes(validation_report)

        # Process each invalid path
        for path_validation in details.invalid_paths.values():
            suggestions.extend(
                self._suggest_for_missing_channels(path_validation, plan, message_codes)
            )
            suggestions.extend(
                self._suggest_for_impossible_channels(path_validation, plan, message_codes)
            )

        return suggestions

    def _extract_message_codes(self, validation_report: ValidationReport) -> dict[str, MessageCode]:
        """Extract message codes from validation report to ensure consistency."""
        codes = {}
        for message in validation_report.messages:
            if message.code:
                # Use the step_id or path_id as key to map codes
                key = message.context.get("step_id", message.context.get("path_id", "general"))
                codes[key] = message.code
        return codes

    def _suggest_for_missing_channels(
        self, path_validation, plan: GraphPlan, message_codes: dict[str, MessageCode]
    ) -> list[FixSuggestion]:
        """Suggest nodes to provide missing data."""
        suggestions = []

        # Collect all missing channels for this path and which steps need them
        missing_channels_by_step = path_validation.missing_channels
        if not missing_channels_by_step:
            return suggestions

        # Find all missing channels and the steps that need them
        all_missing = set()
        needing_steps = []  # UIDs for context
        needing_step_names = []  # Display names for text
        for step_id, channels in missing_channels_by_step.items():
            all_missing.update(channels)
            needing_steps.append(step_id)
            step = plan.get_step(step_id)
            step_name = step.meta.display_name if step and step.meta.display_name else step_id
            needing_step_names.append(step_name)

        # Generate node suggestions for missing channels
        node_suggestions = self._suggester.suggest_for_channels(all_missing, self._matrix)

        for node_suggestion in node_suggestions:
            # Use user-friendly language with path guidance
            data_description = self._describe_data_friendly(all_missing)
            steps_description = self._format_step_list(needing_step_names)

            suggestions.append(
                FixSuggestion(
                    text=(
                        f"Add a {node_suggestion.category} '{node_suggestion.node_type}' "
                        f"node in this path before {steps_description} to provide the "
                        f"missing {data_description}"
                    ),
                    fix_type=FixType.ADD_NODE,
                    code=message_codes.get("general", MessageCode.MISSING_CHANNELS),
                    context={
                        "path_id": path_validation.path_id,
                        "missing_data": list(all_missing),
                        "needing_steps": needing_steps,
                        "node_type": node_suggestion.node_type,
                        "node_category": node_suggestion.category,
                        "suggestion_reason": node_suggestion.reason,
                    },
                    priority=1,
                )
            )

        return suggestions

    def _suggest_for_impossible_channels(
        self, path_validation, plan: GraphPlan, message_codes: dict[str, MessageCode]
    ) -> list[FixSuggestion]:
        """Suggest fixes for impossible data dependencies."""
        suggestions = []

        for step_id, impossible_channels in path_validation.impossible_channels.items():
            step = plan.get_step(step_id)
            step_name = step.meta.display_name if step and step.meta.display_name else step_id

            for channel in impossible_channels:
                data_description = self._describe_data_friendly({channel})

                suggestions.append(
                    FixSuggestion(
                        text=(
                            f"Remove the requirement for {data_description} from the "
                            f"'{step_name}' node, as this data cannot be provided by any "
                            f"available node type"
                        ),
                        fix_type=FixType.MODIFY_CONNECTION,
                        code=message_codes.get(step_id, MessageCode.IMPOSSIBLE_CHANNELS),
                        context={
                            "path_id": path_validation.path_id,
                            "step_id": step_id,
                            "step_name": step_name,
                            "impossible_data": channel,
                        },
                        priority=2,  # Higher priority - these are errors, not warnings
                    )
                )

        return suggestions

    def _format_step_list(self, steps: list[str]) -> str:
        """Format a list of step names for user-friendly display."""
        if len(steps) == 1:
            return f"'{steps[0]}'"
        elif len(steps) == 2:
            return f"'{steps[0]}' and '{steps[1]}'"
        else:
            return f"'{steps[0]}', '{steps[1]}', and {len(steps) - 2} other step(s)"

    def _describe_data_friendly(self, channels: set[str]) -> str:
        """Convert technical channel names to user-friendly descriptions."""
        if len(channels) == 1:
            channel = next(iter(channels))
            # Convert technical names to friendly ones
            friendly_names = {
                "user_input": "user input data",
                "processed_text": "processed text data",
                "embeddings": "text embeddings",
                "search_results": "search results",
                "context": "context information",
                "response": "response data",
            }
            return friendly_names.get(channel, f"'{channel}' data")
        else:
            return f"data: {', '.join(sorted(channels))}"
