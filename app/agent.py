"""
Manufacturing Cost Agent - Agent Implementation
Implements the JSON-action loop powered by Domo AI Text Generation and LangChain Core.
Enforces Master Prompt 4.2 evidence governance, tool de-duplication, and
evidence classification rules (PROVEN, OBSERVED_CORRELATION, HYPOTHESIS, UNAVAILABLE).
"""

from decimal import Decimal
import json
import logging
import re
from typing import Any, Tuple
from pydantic import BaseModel, Field, ValidationError

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from .domo_llm import DomoTextLLM
from .tools import TOOLS

logger = logging.getLogger("manufacturing_cost_agent.agent")

# Map of tool names to callable tool objects
TOOL_MAP = {t.name: t for t in TOOLS}

# Build concise tool documentation for prompt injection
TOOL_DOCS_LIST = []
for t in TOOLS:
    schema_props = t.args if hasattr(t, "args") else {}
    TOOL_DOCS_LIST.append(f"- {t.name}: {t.description}\n  Parameters: {json.dumps(schema_props)}")
TOOL_DOC = "\n".join(TOOL_DOCS_LIST)


# =============================================================================
# Action Schemas for Strict Model Response Validation
# =============================================================================

class ToolCallAction(BaseModel):
    action: str = Field(..., description="Name of the deterministic tool to invoke")
    input: dict[str, Any] = Field(default_factory=dict, description="Tool argument dictionary")


class FinalAnswerAction(BaseModel):
    action: str = Field("final", description="Termination indicator")
    answer: str = Field(..., description="Comprehensive, evidence-backed answer for the user")


AGENT_SYSTEM_PROMPT = """You are the Manufacturing Cost Investigator, a specialized enterprise AI agent for manufacturing cost and variance analysis.
Your purpose is to help plant controllers, finance directors, and operations analysts understand manufacturing costs with rigorous evidence governance.

CORE PRINCIPLE:
Python calculates financial results. You understand the user's analytical question, select appropriate tools, analyze returned facts, and explain findings using strict evidence classifications. Never fabricate numbers or calculate financial totals yourself.

CRITICAL EVIDENCE GOVERNANCE (MASTER PROMPT 4.2 RULES):
1. Strict Evidence Classification:
   Every finding in your response MUST be explicitly classified as:
   - PROVEN: Directly supported by verified records and reproducible calculations (e.g. actual direct costs from line_cost_batches).
   - OBSERVED_CORRELATION: A measurable relationship exists, but causality is not established (e.g. standard vs actual variance, since standards are unverified).
   - HYPOTHESIS: A possible explanation requiring additional evidence (e.g. BOM differences causing cost variance, since purchase prices are missing).
   - UNAVAILABLE: Required information is missing or unreliable (e.g. factory overhead, price vs usage split).
   NEVER promote a HYPOTHESIS to PROVEN.

2. Unverified Standard Cost Baseline:
   - Source standards are UNVERIFIED_STANDARD.
   - NEVER treat unverified standards as approved financial baselines.
   - NEVER classify standard-based findings as PROVEN. Clearly label comparisons as PROVISIONAL.

3. Price vs Usage Variance Split:
   - If user asks why material cost is higher or about price vs quantity, report PRICE_USAGE_SPLIT_NOT_AVAILABLE unless itemized purchase prices and consumption are verified.
   - Do NOT infer whether price or usage caused the variance.

4. Bill of Materials (BOM) Safety:
   - BOM records contain engineering component quantities only. Verified purchase prices are UNAVAILABLE.
   - NEVER claim a product has costlier components merely from product name or unverified standard. BOM component cost differences MUST be classified as HYPOTHESIS.

5. Confidence Assessment:
   - If confidence cannot be calculated defensibly, state NOT_ASSESSED or OBSERVED_CORRELATION. Never generate arbitrary numeric confidence scores.

6. Tool Execution Rules:
   - DO NOT repeat identical tool calls with the same arguments. Reuse observations already in the scratchpad.
   - Limit tool interactions to what is strictly necessary (maximum 5 iterations).

7. Response Structure for Investigations:
   When answering investigation or cost driver questions, provide:
   - Executive Finding
   - Verified Financial Metrics (Actual Costs in ₹)
   - Proven Findings
   - Observed Correlations
   - Hypotheses & Explanatory Inference
   - Unavailable Evidence & Disclosures (Overhead NOT_AVAILABLE, Standards UNVERIFIED, Split UNAVAILABLE)
   - Recommended Next Investigation

8. Tool Selection Guidelines & Authoritative 18 RCA Dimensions:
   - For discovering available datasets, temporal coverage, or checking whether evidence exists for a dimension: call 'discover_manufacturing_datasets'.
   - For material component requirements, actual consumption, consumption variance, Pareto spend, or landed purchase cost: call 'get_material_intelligence' (Dimensions 6, 17, 13).
   - For production throughput, operational yield, station defects (S01-S06), or abnormal line rejections: call 'get_production_quality_intelligence' (Dimensions 3, 4, 18).
   - For product SKU unit economics, volume/mix share, gross vs good unit costs, or cost anomalies: call 'get_product_intelligence' (Dimensions 2, 5).
   - For decomposing multi-period cost changes into Volume, Mix, and Category Rate effects: call 'analyze_cost_movement'. (Note: Cost movement is an analytical technique mapping to Dimensions 1, 2, and 5).
   - For prioritized operational recommendations: call 'get_management_recommendations'.
   - For basic actual cost expenditures by category, plant, and product: call 'get_cost_summary' (Dimension 1).
   - Authoritative 18 Dimensions:
     1. Total manufacturing cost
     2. Cost per good unit
     3. Scrap and rework
     4. Plant and production-line performance
     5. Product-wise manufacturing cost
     6. Material consumption and machine efficiency
     7. Energy consumption
     8. Employee absenteeism
     9. Workforce allocation
     10. Employee skill gaps — DEFERRED
     11. Training effectiveness — DEFERRED
     12. Labour productivity
     13. Procurement and supplier performance
     14. Inventory management
     15. Management and organizational decisions — DEFERRED
     16. Production capacity and capacity utilization
     17. Material consumption and inventory reconciliation
     18. Smartphone testing and inspection efficiency
   - Deferral Rules: Dimensions 10 (Employee skill gaps), 11 (Training effectiveness), and 15 (Management and organizational decisions) are strictly DEFERRED due to absence of MES/HR telemetry. NEVER claim them as confirmed root causes.

AVAILABLE TOOLS:
{tools}

RESPONSE PROTOCOL:
You MUST reply with EXACTLY ONE valid JSON object. No markdown code blocks (do NOT use ```json), no conversation before or after:
To call a tool:
{{"action": "<tool_name>", "input": {{<param_key>: <param_value>}}}}

To return your final answer:
{{"action": "final", "answer": "<your thorough, professional response with evidence and disclosures>"}}

CONVERSATION HISTORY:
{history}

USER QUESTION:
{question}

SCRATCHPAD (Previous tool calls and deterministic observations):
{scratchpad}

Your single JSON reply:"""

agent_prompt = PromptTemplate.from_template(AGENT_SYSTEM_PROMPT)
agent_chain = agent_prompt | DomoTextLLM(temperature=0.0) | StrOutputParser()


def _parse_and_validate_action(raw_output: str) -> dict[str, Any]:
    """
    Parses and strictly validates the agent action using Pydantic schemas.
    Recovers cleanly from markdown fences or trailing prose.
    """
    clean_text = raw_output.strip()
    # Strip markdown code fences if model enclosed JSON
    if clean_text.startswith("```json"):
        clean_text = clean_text[7:]
    elif clean_text.startswith("```"):
        clean_text = clean_text[3:]
    if clean_text.endswith("```"):
        clean_text = clean_text[:-3]
    clean_text = clean_text.strip()

    # Extract JSON object using regex
    match = re.search(r"\{.*\}", clean_text, re.DOTALL)
    if not match:
        logger.warning("No JSON structure found in output. Treating as final answer.")
        return {"action": "final", "answer": clean_text}

    json_str = match.group(0)
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as exc:
        logger.warning("JSON decode error from model output '%s': %s", clean_text, exc)
        return {"action": "final", "answer": clean_text}

    action_name = parsed.get("action", "").strip().lower()

    if action_name == "final":
        try:
            val_final = FinalAnswerAction(**parsed)
            return {"action": "final", "answer": val_final.answer}
        except ValidationError:
            return {"action": "final", "answer": str(parsed.get("answer", clean_text))}

    # Validate tool call action
    if action_name in TOOL_MAP:
        try:
            val_tool = ToolCallAction(**parsed)
            return {"action": val_tool.action, "input": val_tool.input}
        except ValidationError as val_err:
            logger.warning("Tool call validation error: %s", val_err)
            return {
                "action": "final",
                "answer": f"Agent encountered invalid tool arguments: {val_err}. Please rephrase your query.",
            }

    # Unknown tool requested
    logger.warning("Agent requested unsupported tool: '%s'", action_name)
    return {
        "action": "unsupported_tool",
        "tool_name": action_name,
        "input": parsed.get("input", {}),
    }


def run_agent(
    question: str,
    history: list[dict[str, str]],
    max_steps: int = 5,
    investigation_context: Optional[dict[str, Any]] = None,
) -> Tuple[str, list[dict[str, Any]], dict[str, Any]]:
    """
    Executes the JSON-action agent loop with de-duplication and strict governance.
    Repeatedly prompts the Domo LLM, executes chosen tools, updates the scratchpad,
    and terminates upon 'final' action or step exhaustion (max 5 iterations).
    Supports unified investigation context (form parameters and dataset selections).
    """
    recent_history = history[-8:] if history else []
    formatted_history = "\n".join(f"{msg.get('role', 'user')}: {msg.get('content', '')}" for msg in recent_history) or "(none)"

    # Build investigation context block if user provided form context
    context_block = ""
    if investigation_context:
        ctx = investigation_context
        start_d = ctx.get("start_date") or "Unspecified"
        end_d = ctx.get("end_date") or "Unspecified"
        prod = ctx.get("product_code") or "All Products"
        plant = ctx.get("plant_code") or "All Plants"
        line = ctx.get("line_code") or "All Lines"
        cost_cat = ctx.get("cost_category") or "All Categories"
        exp_val = ctx.get("expected_value")
        act_val = ctx.get("actual_value")
        obs_issue = ctx.get("observed_issue") or "Unspecified"
        known_chg = ctx.get("known_changes") or []
        add_ctx = ctx.get("additional_context") or "None"
        sel_ds = ctx.get("selected_dataset_ids") or []
        up_batch = ctx.get("uploaded_batch_id")
        up_ds = ctx.get("uploaded_dataset_ids") or []
        inv_mode = (ctx.get("investigation_mode") or "quick").lower()
        stores_map = ctx.get("dataset_stores") or {}

        stores_info = []
        for ds in sel_ds:
            s_type = stores_map.get(ds, "GLOBAL_STORE")
            stores_info.append(f"{ds} [{s_type}]")
        stores_summary = ", ".join(stores_info) if stores_info else "All 10 Global Store datasets"

        var_str = "N/A"
        if exp_val is not None and act_val is not None and float(exp_val) > 0:
            var_pct = ((float(act_val) - float(exp_val)) / float(exp_val)) * 100
            var_str = f"{var_pct:+.2f}%"

        if inv_mode == "quick":
            context_block = (
                "=============================================================================\n"
                "INVESTIGATION MODE: QUICK INVESTIGATION (AUTONOMOUS DATA-DRIVEN DISCOVERY)\n"
                f"- Mode: Quick Investigation (No form constraints; discovery driven by datasets)\n"
                f"- Selected Datasets & Stores: {stores_summary}\n"
                + (f"- Staged Uploaded Dataset Batch ID: {up_batch} (CURRENT_UPLOAD_STORE: UNCOMMITTED)\n" if up_batch else "")
                + (f"- Newly Uploaded Datasets: {', '.join(up_ds)}\n" if up_ds else "")
                + "AUTONOMOUS DATA DISCOVERY & TWO-STORE GOVERNANCE RULES:\n"
                "1. Autonomous Mode: The user has selected datasets without pre-filled hypotheses or cost categories. Do NOT assume a specific root cause in advance.\n"
                "2. Dynamic Discovery: Use deterministic tools (inspect_available_datasets, discover_investigation_evidence, analyze_manufacturing_cost_variance, etc.) to discover active date bounds, top variance drivers, scrap/rework loops, and line performance anomalies.\n"
                "3. TWO-STORE ARCHITECTURE RULES:\n"
                "   - Datasets from GLOBAL_STORE are verified committed facts in PostgreSQL / baseline storage.\n"
                "   - Datasets from CURRENT_UPLOAD_STORE are newly uploaded/staged. They are NOT committed to the Global Store.\n"
                "   - Never represent uncommitted staging uploads as globally committed.\n"
                "   - If both stores contain the same dataset, prioritize the staged version for this analysis session without duplicating rows.\n"
                "4. Respect Authoritative Dimensions: Dimensions 10, 11, and 15 are DEFERRED and cannot be investigated.\n"
                "=============================================================================\n"
            )
        else:
            context_block = (
                "=============================================================================\n"
                "INVESTIGATION MODE: CUSTOMIZED INVESTIGATION (USER CONTEXT + DATASET EVIDENCE)\n"
                f"- Investigation Question: {question}\n"
                f"- Investigation Period Scope: {start_d} to {end_d}\n"
                f"- Scope Filters: Product={prod}, Plant={plant}, Line={line}, Cost Category={cost_cat}\n"
                f"- User Observed Issue: {obs_issue}\n"
                f"- User Known Operational Changes: {', '.join(known_chg) if known_chg else 'None'}\n"
                f"- User Expected vs Actual Cost: Expected=₹{exp_val if exp_val is not None else 'N/A'}, "
                f"Actual=₹{act_val if act_val is not None else 'N/A'} (Variance={var_str})\n"
                f"- Additional User Context: {add_ctx}\n"
                f"- Active Selected Datasets: {stores_summary}\n"
                + (f"- Staged Uploaded Dataset Batch ID: {up_batch} (CURRENT_UPLOAD_STORE: UNCOMMITTED)\n" if up_batch else "")
                + (f"- Newly Uploaded Datasets: {', '.join(up_ds)}\n" if up_ds else "")
                + "EVIDENCE GOVERNANCE & CONFLICT DETECTION RULES:\n"
                "1. User-provided context and form statements are HYPOTHESES, not verified manufacturing facts.\n"
                "2. Form-stated costs, supplier assertions, and defect claims must be verified independently against actual dataset records using deterministic tools.\n"
                "3. CONFLICT HANDLING: If user-stated context directly contradicts dataset evidence (e.g. user claims a cost increase that is not supported by line batches, or attributes variance to a supplier when standard PO price is unchanged or missing), you MUST explicitly flag and explain the discrepancy under 'Observed Correlations' or 'Hypotheses & Explanatory Inference'.\n"
                "4. TWO-STORE RULES: Datasets from CURRENT_UPLOAD_STORE are pending/staged; maintain strict separation from global facts.\n"
                "5. Do not speculate on Deferred Dimensions (10: Skill gaps, 11: Training effectiveness, 15: Management override) without verified HR/MES records.\n"
                "=============================================================================\n"
            )

    effective_question = f"{context_block}\nUSER QUESTION:\n{question}" if context_block else question

    scratchpad = ""
    executed_traces: list[dict[str, Any]] = []
    executed_call_signatures: set[str] = set()

    metadata: dict[str, Any] = {
        "iterations": 0,
        "data_as_of": "2026-10-31",
        "investigation_context": investigation_context,
        "evidence_governance": {
            "standards_status": "UNVERIFIED_STANDARD",
            "overhead_status": "NOT_AVAILABLE",
            "price_usage_split": "PRICE_USAGE_SPLIT_NOT_AVAILABLE",
            "quality_lineage": "UNRESOLVED_LINEAGE",
            "bom_costing_status": "HYPOTHESIS_ONLY (Purchase prices unavailable)",
        },
        "limitations": [
            "Cost calculations cover only direct-costed runs (5,000 batches).",
            "3,832 operational runs (1,054,321 units) remain uncosted.",
        ],
    }

    for step_num in range(1, max_steps + 1):
        metadata["iterations"] = step_num
        logger.info("Executing Manufacturing Cost Agent iteration %d/%d", step_num, max_steps)

        try:
            raw_output = agent_chain.invoke({
                "tools": TOOL_DOC,
                "history": formatted_history,
                "question": effective_question,
                "scratchpad": scratchpad or "(empty)",
            })
        except Exception as exc:
            logger.error("Error contacting Domo AI Services: %s", exc)
            return (
                f"**Error contacting Domo AI Services:** {exc}. Please verify network connectivity and DOMO credentials.",
                executed_traces,
                metadata,
            )

        action_dict = _parse_and_validate_action(raw_output)
        action = action_dict.get("action")

        # 1. Termination condition: Final Answer
        if action == "final":
            final_answer = action_dict.get("answer", "")
            return final_answer, executed_traces, metadata

        # 2. Unsupported tool handler
        if action == "unsupported_tool":
            bad_tool = action_dict.get("tool_name")
            obs = f"Error: Tool '{bad_tool}' is not an approved deterministic tool. Approved tools are: {list(TOOL_MAP.keys())}."
            scratchpad += f"\nStep {step_num}: Attempted '{bad_tool}'\nObservation: {obs}\n"
            executed_traces.append({
                "step": step_num,
                "tool": bad_tool,
                "input": action_dict.get("input", {}),
                "error": obs,
            })
            continue

        # 3. Approved tool call execution with de-duplication check
        tool_name = action
        tool_input = action_dict.get("input", {})
        call_sig = f"{tool_name}:{json.dumps(tool_input, sort_keys=True)}"

        if call_sig in executed_call_signatures:
            logger.info("Duplicate tool call detected (%s). Reusing cached observation.", call_sig)
            obs = f"Notice: Tool '{tool_name}' with arguments {json.dumps(tool_input)} was already executed. Please use previous observation to formulate your final answer."
            scratchpad += f"\nStep {step_num}: Repeated '{tool_name}'\nObservation: {obs}\n"
            continue

        executed_call_signatures.add(call_sig)
        tool_func = TOOL_MAP.get(tool_name)

        logger.info("Executing tool: %s with args: %s", tool_name, tool_input)

        try:
            tool_result = tool_func.invoke(tool_input)
            obs_str = json.dumps(tool_result, default=str)
        except Exception as exc:
            logger.error("Tool execution failed for %s: %s", tool_name, exc)
            tool_result = {"status": "ERROR", "error": str(exc)}
            obs_str = f"Tool '{tool_name}' failed with error: {exc}"

        executed_traces.append({
            "step": step_num,
            "tool": tool_name,
            "input": tool_input,
            "result": tool_result,
        })

        scratchpad += f"\nStep {step_num}: Called '{tool_name}' with {json.dumps(tool_input)}\nObservation: {obs_str}\n"

    # Step exhaustion fallback
    fallback_msg = (
        "**Investigation Note:** Reached the maximum limit of 5 investigation iterations. "
        "Based on evidence gathered so far:\n\n"
    )
    for trace in executed_traces:
        t_name = trace.get("tool")
        res = trace.get("result", {})
        if t_name == "get_cost_summary" and res.get("status") == "SUCCESS":
            total_dir = res.get("total_direct_actual_cost_inr", 0.0)
            fallback_msg += f"- [PROVEN] Total Direct Manufacturing Cost evaluated: **₹{total_dir:,.2f}**.\n"
            mat = res.get("categories", {}).get("material_cost", {})
            fallback_msg += f"- [PROVEN] Raw Material expenditure: **₹{mat.get('actual_cost', 0):,.2f}** ({mat.get('share_pct', 0)}% of total).\n"

    fallback_msg += "\n*Data Governance Disclosures:* Factory overhead is UNAVAILABLE; standards are UNVERIFIED_STANDARD; price vs usage split is PRICE_USAGE_SPLIT_NOT_AVAILABLE."
    return fallback_msg, executed_traces, metadata
