import re
import json
import logging
from typing import Any
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.workflow import Workflow, node, Edge, START
from google.adk.tools import AgentTool, McpToolset
from google.adk.events import RequestInput
from google.adk.agents.context import Context
from mcp import StdioServerParameters
from app.config import config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("study-sync-agents")

# ── MCP Toolset ──────────────────────────────────────────────────────────────
mcp_toolset = McpToolset(
    connection_params=StdioServerParameters(
        command="uv",
        args=["run", "python", "-m", "app.mcp_server"]
    )
)

# ── Specialized Sub-Agents ────────────────────────────────────────────────────

syllabus_parser_agent = Agent(
    name="syllabus_parser",
    model=Gemini(model=config.model),
    instruction=(
        "You are an academic syllabus parser. Take the course syllabus text provided "
        "and extract key exam dates, assignments, and weekly topics. "
        "Use the MCP tool parse_syllabus_dates to assist. "
        "Return a clean, structured markdown list."
    ),
    tools=[mcp_toolset]
)

schedule_generator_agent = Agent(
    name="schedule_generator",
    model=Gemini(model=config.model),
    instruction=(
        "You are a study schedule planner. Generate weekly calendars, study time blocks, "
        "and suggest focus techniques based on course difficulty. "
        "Use MCP tools generate_calendar_weeks and suggest_focus_techniques. "
        "Recommend active recall and spaced repetition patterns."
    ),
    tools=[mcp_toolset]
)

# ── Orchestrator Agent (direct workflow node, output saved to state) ───────────

orchestrator_agent = Agent(
    name="orchestrator",
    model=Gemini(model=config.model),
    instruction=(
        "You are the lead academic concierge. Triage the user request. "
        "If they provide syllabus content, delegate parsing to the syllabus_parser agent. "
        "Then delegate study schedule generation to the schedule_generator agent. "
        "Synthesise their outputs into a clear, student-friendly study plan."
    ),
    tools=[
        AgentTool(agent=syllabus_parser_agent),
        AgentTool(agent=schedule_generator_agent)
    ],
    output_key="orchestrator_response"   # saves LLM output to ctx.state automatically
)

# ── Workflow Function Nodes ───────────────────────────────────────────────────

@node
async def security_checkpoint(ctx: Context, node_input: Any = None):
    """Scrubs PII, detects prompt injection, writes audit log. Sets ctx.route.

    `node_input` receives the raw user message from the workflow runner.
    ADK resolves it because 'node_input' is the reserved pass-through name
    in state-binding mode.
    """
    request = str(node_input) if node_input else ""
    ctx.state["raw_request"] = request
    audit: dict = {"event": "security_check", "length": len(request)}

    # 1. PII scrubbing
    pii_patterns = [
        r"\b\d{3}-\d{2}-\d{4}\b",                         # SSN
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,7}\b",  # email
        r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b",               # phone
    ]
    scrubbed = request
    for pat in pii_patterns:
        scrubbed = re.sub(pat, "[REDACTED]", scrubbed)
    if scrubbed != request:
        audit["pii_redacted"] = True
        logger.warning(json.dumps({"severity": "WARNING", **audit}))
    ctx.state["scrubbed_request"] = scrubbed

    # 2. Prompt injection check (domain-specific rule)
    injection_keywords = [
        "ignore previous instructions",
        "system prompt",
        "override instructions",
        "bypass security",
        "jailbreak",
    ]
    if any(kw in request.lower() for kw in injection_keywords):
        audit["status"] = "REJECTED_INJECTION"
        logger.error(json.dumps({"severity": "CRITICAL", **audit}))
        ctx.route = "unsafe"
        return "Security violation detected."

    audit["status"] = "PASSED"
    logger.info(json.dumps({"severity": "INFO", **audit}))
    ctx.route = "safe"
    return scrubbed


@node
async def hours_checker(ctx: Context, node_input: Any = None):
    """Checks if the request exceeds the 10-hour/week study limit. Sets ctx.route.

    Reads scrubbed text from ctx.state (written by security_checkpoint).
    Falls back to node_input if state key is missing.
    """
    req = ctx.state.get("scrubbed_request", str(node_input) if node_input else "")
    match = re.search(r"(\d+)\s*(?:hours?|hrs?)", req.lower())
    if match and int(match.group(1)) > 10:
        ctx.state["intensity_hours"] = int(match.group(1))
        audit = {
            "event": "hours_check",
            "hours": ctx.state["intensity_hours"],
            "status": "NEEDS_APPROVAL",
        }
        logger.warning(json.dumps({"severity": "WARNING", **audit}))
        ctx.route = "needs_approval"
    else:
        ctx.route = "auto_approved"
    return req


@node(rerun_on_resume=True)
async def human_approval(ctx: Context):
    """HITL node — pauses for explicit user consent when study hours exceed limit."""
    response = ctx.resume_inputs.get("study_plan_approval")
    if response is not None:
        ctx.state["approval_status"] = response
        logger.info(json.dumps({
            "severity": "INFO",
            "event": "human_approval",
            "decision": response,
            "hours": ctx.state.get("intensity_hours"),
        }))
        return str(response)

    hours = ctx.state.get("intensity_hours", 12)
    return RequestInput(
        interruptId="study_plan_approval",
        message=(
            f"⚠️ Consent Required: The requested plan involves {hours} hours of study per week, "
            "which exceeds the recommended safety limit of 10 hours. Do you approve? (Yes / No)"
        ),
    )


@node
async def security_error(ctx: Context):
    """Terminal node for policy violations."""
    return "🚫 Request rejected due to a safety or security policy violation."


@node
async def final_output(ctx: Context):
    """Compiles the 🎓 StudySync dashboard from state."""
    response = ctx.state.get("orchestrator_response", "")
    approval = ctx.state.get("approval_status")
    header = "🎓 **StudySync — Your Personalised Study Dashboard**\n\n"
    if approval:
        header += f"*(Intensive plan authorised — approval: {approval})*\n\n"
    return f"{header}{response}"


# ── Workflow Graph ────────────────────────────────────────────────────────────
#
#  START → security_checkpoint ─(safe)──────→ hours_checker ─(auto_approved)──→ orchestrator_agent → final_output
#                               └─(unsafe)──→ security_error                │
#                                                              (needs_approval)→ human_approval ──→ orchestrator_agent
#
# EDGE RULE: only ONE edge between any (source, target) pair.
# Both "auto_approved" and "human_approval exit" converge on orchestrator_agent
# via a single unconditional edge from human_approval.

workflow_edges = [
    Edge(from_node=START,               to_node=security_checkpoint),
    Edge(from_node=security_checkpoint, to_node=hours_checker,       route="safe"),
    Edge(from_node=security_checkpoint, to_node=security_error,      route="unsafe"),
    Edge(from_node=hours_checker,       to_node=orchestrator_agent,  route="auto_approved"),
    Edge(from_node=hours_checker,       to_node=human_approval,      route="needs_approval"),
    Edge(from_node=human_approval,      to_node=orchestrator_agent),   # unconditional
    Edge(from_node=orchestrator_agent,  to_node=final_output),         # unconditional
]

root_workflow = Workflow(
    name="studysync_workflow",
    edges=workflow_edges,
)

app = App(
    root_agent=root_workflow,
    name="app",
)

# Export alias for tests
root_agent = root_workflow
