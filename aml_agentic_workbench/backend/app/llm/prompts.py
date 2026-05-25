"""Role-aware prompt templates for AML agents."""

import json
from typing import Any

from app.schemas.roles import SupportedRole

ROLE_STYLE_GUIDANCE: dict[SupportedRole, str] = {
    SupportedRole.INVESTIGATOR: "Use plain AML investigation language and emphasize concrete behavioural evidence.",
    SupportedRole.DATA_SCIENTIST: (
        "Include feature, model, and data quality detail suitable for AML data science review."
    ),
    SupportedRole.MODEL_VALIDATOR: "Emphasize auditability, uncertainty, validation limits, and model governance.",
    SupportedRole.COMPLIANCE_STRATEGY: (
        "Emphasize typology coverage, policy alignment, and careful non-conclusive language."
    ),
}


def render_prompt(agent_name: str, role: SupportedRole, query: str, inputs: dict[str, Any]) -> str:
    """Render a compact role-aware prompt for a specific agent."""
    return "\n".join(
        [
            f"Agent: {agent_name}",
            f"Role: {role.value}",
            f"Role guidance: {ROLE_STYLE_GUIDANCE[role]}",
            f"User query: {query}",
            "Use structured JSON only. Be cautious, evidence-grounded, and non-conclusive.",
            f"Inputs: {json.dumps(inputs, default=str, separators=(',', ':'))}",
            _agent_instruction(agent_name),
        ]
    )


def _agent_instruction(agent_name: str) -> str:
    instructions = {
        "transaction_behaviour_agent": (
            "Analyze velocity change, new counterparty ratio, cross-border amount ratio, active hours entropy, "
            "in/out amount ratio, counterparty concentration, amount spike, and round amount pattern."
        ),
        "model_explanation_agent": (
            "Explain risk drivers and uncertainty. Clearly state the model score is not proof of suspicious activity."
        ),
        "typology_mapping_agent": (
            "Map behaviour to knowledge documents using careful phrases such as "
            "'resembles indicators associated with', "
            "'may warrant further review', and 'evidence is insufficient to conclude'. Do not say to file an STR."
        ),
        "feature_critic_agent": (
            "Critique feature quality and recommend PySpark features with rationale, formula, columns, edge cases, "
            "leakage risk, expected direction, and pseudocode."
        ),
        "evidence_assembly_agent": (
            "Assemble a final report with only sections supported by executed agents. Include Executive Summary, "
            "Evidence Table, Limitations and Uncertainty, and Recommended Analytical Next Steps."
        ),
        "judge_panel_agent": "Score groundedness, coverage, and governance readiness with rationale.",
        "guardrail_agent": (
            "Review final outputs for prohibited AML conclusions, unsupported claims, and missing disclaimers."
        ),
    }
    return instructions.get(agent_name, "Produce a careful structured AML output.")
