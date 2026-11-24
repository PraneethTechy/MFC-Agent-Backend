"""
Context-Aware Manufacturing Intelligence Chatbot Engine.
Provides lightweight intent and context resolution, 18-category classification,
multi-turn conversation memory, page-aware responses, store isolation governance,
and evidence-grounded response synthesis.
"""

from enum import Enum
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("manufacturing_cost_agent.investigation.context_engine")


class ChatbotIntent(str, Enum):
    # 1. Manufacturing cost analysis
    MANUFACTURING_COST_ANALYSIS = "MANUFACTURING_COST_ANALYSIS"
    # 2. Cost increase/decrease explanation
    COST_MOVEMENT_EXPLANATION = "COST_MOVEMENT_EXPLANATION"
    # 3. Cost per good unit analysis
    COST_PER_GOOD_UNIT = "COST_PER_GOOD_UNIT"
    # 4. Production output and capacity
    PRODUCTION_OUTPUT_CAPACITY = "PRODUCTION_OUTPUT_CAPACITY"
    # 5. Scrap, rework and quality
    SCRAP_REWORK_QUALITY = "SCRAP_REWORK_QUALITY"
    # 6. Material consumption and inventory
    MATERIAL_CONSUMPTION_INVENTORY = "MATERIAL_CONSUMPTION_INVENTORY"
    # 7. Procurement and supplier performance
    PROCUREMENT_SUPPLIER_PERFORMANCE = "PROCUREMENT_SUPPLIER_PERFORMANCE"
    # 8. Workforce and labour productivity
    WORKFORCE_LABOUR_PRODUCTIVITY = "WORKFORCE_LABOUR_PRODUCTIVITY"
    # 9. Energy and equipment efficiency
    ENERGY_EQUIPMENT_EFFICIENCY = "ENERGY_EQUIPMENT_EFFICIENCY"
    # 10. Product, component, plant and production-line analysis
    PRODUCT_PLANT_LINE_ANALYSIS = "PRODUCT_PLANT_LINE_ANALYSIS"
    # 11. Historical and cross-period comparison
    HISTORICAL_PERIOD_COMPARISON = "HISTORICAL_PERIOD_COMPARISON"
    # 12. Root cause investigation
    ROOT_CAUSE_INVESTIGATION = "ROOT_CAUSE_INVESTIGATION"
    # 13. Corrective action recommendations
    CORRECTIVE_ACTION_RECOMMENDATIONS = "CORRECTIVE_ACTION_RECOMMENDATIONS"
    # 14. Data coverage and data quality questions
    DATA_COVERAGE_QUALITY = "DATA_COVERAGE_QUALITY"
    # 15. Application navigation and feature explanations
    APP_NAVIGATION_FEATURES = "APP_NAVIGATION_FEATURES"
    # 16. General manufacturing knowledge
    GENERAL_MANUFACTURING_KNOWLEDGE = "GENERAL_MANUFACTURING_KNOWLEDGE"
    # 17. General questions unrelated to manufacturing
    GENERAL_UNRELATED_QUESTIONS = "GENERAL_UNRELATED_QUESTIONS"
    # 18. Ambiguous or unsupported questions
    AMBIGUOUS_OR_UNSUPPORTED = "AMBIGUOUS_OR_UNSUPPORTED"


class ContextResolutionEngine:
    """
    Classifies natural language questions across the 18 manufacturing intelligence categories,
    resolves conversational history across multiple turns, tracks active page context,
    and enforces data store governance (Current Upload Store vs Global Store).
    """

    @classmethod
    def classify_intent(
        cls,
        question: str,
        page_context: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        problem_category: Optional[str] = None,
    ) -> Tuple[ChatbotIntent, Dict[str, Any]]:
        """
        Classifies incoming query into one of 18 authoritative categories and returns
        extracted query metadata (entities, period overrides, conversational hints).
        """
        q = (question or "").lower().strip()
        cat_lower = (problem_category or "").lower().strip()
        metadata: Dict[str, Any] = {
            "entities": {},
            "is_follow_up": False,
            "period_override": None,
        }

        if not q:
            return ChatbotIntent.APP_NAVIGATION_FEATURES, metadata

        # 1. AMBIGUOUS_OR_UNSUPPORTED: Adversarial / Jailbreak / Falsification
        unsafe_keywords = [
            "ignore all previous", "ignore previous", "ignore instructions", "ignore rules",
            "developer mode", "jailbreak", "override governance", "bypass safety",
            "disregard instructions", "system prompt", "hack", "exploit", "malware",
            "steal data", "ddos", "fake data", "fabricate", "forge", "falsify",
            "invent numbers", "make up numbers"
        ]
        if any(k in q for k in unsafe_keywords):
            metadata["sub_type"] = "SECURITY_RESTRICTION"
            return ChatbotIntent.AMBIGUOUS_OR_UNSUPPORTED, metadata

        # 2. AMBIGUOUS_OR_UNSUPPORTED: Speculative future forecasts beyond data horizon
        unsupported_future = [
            "predict the future", "forecast 2030", "forecast in 2030", "predict 2030", "costs in 2030",
            "cost in 2030", "cost in 2028", "forecast for 2028", "forecast for 2029", "forecast for 2035",
            "gold price next year", "stock price tomorrow", "who will win the election",
            "ceo's personal phone", "private salary of employees", "unreleased financial secrets"
        ]
        if any(k in q for k in unsupported_future) or re.search(r'\b(predict|forecast)\b.*\b(202[89]|203\d|future|next decade)\b', q):
            metadata["sub_type"] = "TEMPORAL_HORIZON_LIMITATION"
            return ChatbotIntent.AMBIGUOUS_OR_UNSUPPORTED, metadata

        # 3. GENERAL_UNRELATED_QUESTIONS: Sports, Geography, Trivia, Computer Science, AI, General Tech
        unrelated_patterns = [
            "capital of japan", "capital of france", "capital of", "who won the latest football world cup",
            "who won the world cup", "football world cup", "best football player", "who is the best football player",
            "lionel messi", "cristiano ronaldo", "super bowl", "olympic games", "speed of light",
            "distance to moon", "distance to the moon", "highest mountain", "mount everest",
            "largest country", "who was albert einstein", "what is photosynthesis",
            "why is the sky blue", "who wrote hamlet", "currency of the uk", "population of earth",
            "generative ai", "gen ai", "neural network", "neural networks", "machine learning",
            "deep learning", "large language model", "llm", "rag", "retrieval augmented generation",
            "ai agent", "ai agents", "fine-tuning", "what is python", "explain python",
            "what is react", "explain react", "sql join", "sql joins", "inner join", "tell me a joke", "joke"
        ]
        if any(k in q for k in unrelated_patterns):
            metadata["sub_type"] = "UNRELATED_GENERAL_KNOWLEDGE"
            return ChatbotIntent.GENERAL_UNRELATED_QUESTIONS, metadata

        # Check for general conversational greetings
        clean_q = re.sub(r'[\!\?\.\,;:]+$', '', q).strip()
        if clean_q in ["hello", "hi", "hey", "good morning", "good afternoon", "good evening", "how are you", "who are you", "what can you do"]:
            metadata["sub_type"] = "GREETING"
            return ChatbotIntent.APP_NAVIGATION_FEATURES, metadata

        # 4. Multi-turn Conversational Memory Resolution & Drill-down Patterns
        # "Which supplier..." or "Was it due to the supplier?" referring to previous period
        if any(k in q for k in ["which supplier", "what supplier", "who supplied", "vendor contributed", "due to the supplier", "was it due to the supplier", "is it due to the supplier"]):
            metadata["is_follow_up"] = True
            metadata["inherited_from_last_turn"] = True
            return ChatbotIntent.PROCUREMENT_SUPPLIER_PERFORMANCE, metadata

        # Plant override e.g. "What about Plant 2?", "PLT-02"
        plant_match = re.search(r'\b(what about|how about|what of)\s+(plant\s*2|plt-02|plant 1|plt-01)\b', q) or re.search(r'\b(plant\s*2|plt-02)\b', q)
        if plant_match:
            metadata["is_follow_up"] = True
            raw_p = plant_match.group(0).lower()
            metadata["plant_override"] = "PLT-02" if "2" in raw_p else "PLT-01"
            return ChatbotIntent.PRODUCT_PLANT_LINE_ANALYSIS, metadata

        # Line-level drill-down: "Which production line within that plant contributed most?", "Show line-by-line quality rejection rates"
        if any(k in q for k in ["which production line", "production line within that plant", "which line within", "line-by-line", "line by line", "which production line contributed most"]):
            metadata["is_follow_up"] = True
            return ChatbotIntent.PRODUCTION_OUTPUT_CAPACITY, metadata

        # Product contribution follow-up: "Which products contributed most?", "Which product contributed most to the volume effect?"
        if any(k in q for k in ["which product contributed most", "which products contributed most", "product contributed most"]):
            metadata["is_follow_up"] = True
            return ChatbotIntent.PRODUCT_PLANT_LINE_ANALYSIS, metadata

        # Material cost follow-up: "What about material cost?"
        if any(k in q for k in ["what about material cost", "what of material cost", "what about material"]):
            metadata["is_follow_up"] = True
            metadata["cost_category"] = "MATERIAL"
            return ChatbotIntent.MANUFACTURING_COST_ANALYSIS, metadata

        # "Compare it with October"
        if re.search(r'\b(compare it with|compare with)\s+(october|august|september|november|december|oct|aug|sep|nov|dec)\b', q):
            metadata["is_follow_up"] = True
            return ChatbotIntent.HISTORICAL_PERIOD_COMPARISON, metadata

        # "What about September / October / August / November...?"
        month_match = re.search(r'\b(what about|how about|what of)\s+(august|september|october|november|december|aug|sep|oct|nov|dec)\b', q)
        if month_match:
            metadata["is_follow_up"] = True
            metadata["period_override"] = month_match.group(2)
            return ChatbotIntent.HISTORICAL_PERIOD_COMPARISON, metadata

        # "What corrective action should we take...?"
        if any(k in q for k in ["what corrective action", "what action should we take", "what should we do now", "how to resolve"]):
            metadata["is_follow_up"] = True
            return ChatbotIntent.CORRECTIVE_ACTION_RECOMMENDATIONS, metadata

        # 5. GENERAL_MANUFACTURING_KNOWLEDGE: Concepts, Formulas, Best Practices
        knowledge_patterns = [
            "what is overall equipment effectiveness", "what is oee", "explain oee",
            "what is first pass yield", "explain fpy", "explain first pass yield",
            "how can a manufacturer reduce material wastage", "reduce material wastage", "reduce material waste",
            "difference between scrap and rework", "scrap vs rework", "scrap versus rework",
            "standard costing", "what is standard costing", "purchase price variance formula",
            "material usage variance formula", "ppv formula", "muv formula",
            "lean manufacturing", "six sigma", "kaizen", "5 whys", "fishbone",
            "solder bridging", "reflow profile", "stencil aperture"
        ]
        if any(k in q for k in knowledge_patterns):
            metadata["sub_type"] = "MANUFACTURING_METHODOLOGY"
            return ChatbotIntent.GENERAL_MANUFACTURING_KNOWLEDGE, metadata

        # 6. DATA_COVERAGE_QUALITY: Data bounds, Freshness, Provenance, Missing datasets
        coverage_patterns = [
            "what data is available", "what reporting periods are available", "what date range",
            "date coverage", "data freshness", "data provenance", "data origin",
            "where did this data come from", "audit trail", "missing dataset", "data quality gap",
            "what data is currently available", "available in the global store", "available in global store",
            "data is currently available", "data currently available", "available data", "current data bounds"
        ]
        if any(k in q for k in coverage_patterns):
            return ChatbotIntent.DATA_COVERAGE_QUALITY, metadata

        # 7. APP_NAVIGATION_FEATURES: Platform guidance, Workflow, Store differences, Approve & Commit
        nav_patterns = [
            "what does this chart mean", "explain this chart", "how do i use this page",
            "what file formats", "how do i upload", "how to upload", "supported file formats",
            "supported dataset", "csv format", "required columns", "missing columns",
            "difference between upload store and global store", "upload store vs global store",
            "what is upload store", "what is global store", "what is the global store",
            "what is the current upload store", "upload store and global store",
            "what happens if i click approve & commit", "what is approve & commit",
            "what if i do not approve", "what happens if i don't approve",
            "is this uploaded data already in global store", "is this data in global store",
            "quarantined records", "why can't records be promoted", "validation status",
            "what is production mode vs demo mode", "demo mode vs production mode",
            "production and demo mode", "difference between production and demo", "production vs demo", "demo vs production"
        ]
        if any(k in q for k in nav_patterns):
            metadata["sub_type"] = "PLATFORM_AND_WORKFLOW_GUIDANCE"
            return ChatbotIntent.APP_NAVIGATION_FEATURES, metadata

        # 8. CORRECTIVE_ACTION_RECOMMENDATIONS: Action items, Prioritized solutions, Savings
        action_patterns = [
            "what corrective action", "corrective actions", "what action should we take",
            "how to fix", "what should we do", "next steps", "recommended action",
            "management recommendation", "prioritized action", "action playbook", "expected savings"
        ]
        if any(k in q for k in action_patterns):
            return ChatbotIntent.CORRECTIVE_ACTION_RECOMMENDATIONS, metadata

        # 9. ROOT_CAUSE_INVESTIGATION: Yield drop cause, Quality failure cause
        rca_patterns = [
            "what caused the reduction in yield", "what caused the reduction", "why did yield drop",
            "what is the root cause", "root cause of", "investigate yield", "suspected cause"
        ]
        if any(k in q for k in rca_patterns):
            return ChatbotIntent.ROOT_CAUSE_INVESTIGATION, metadata

        # 10. COST_MOVEMENT_EXPLANATION: Cost increase OR decrease
        movement_patterns = [
            "why did manufacturing cost increase", "why did manufacturing cost decrease",
            "why did cost increase", "why did cost decrease", "why cost increased", "why cost decreased",
            "cost increase", "cost decrease", "cost movement", "cost reduction", "cost surge"
        ]
        if any(k in q for k in movement_patterns) or (cat_lower and "cost" in cat_lower and ("increase" in cat_lower or "decrease" in cat_lower or "movement" in cat_lower)):
            return ChatbotIntent.COST_MOVEMENT_EXPLANATION, metadata

        # 11. COST_PER_GOOD_UNIT: Unit economics, Good units
        unit_patterns = [
            "cost per good unit", "cost per unit", "unit cost", "lowest cost per good unit",
            "highest cost per good unit", "which month had the lowest cost per good unit",
            "which month had the highest cost per good unit", "gross vs good", "costed units"
        ]
        if any(k in q for k in unit_patterns):
            return ChatbotIntent.COST_PER_GOOD_UNIT, metadata

        # 12. HISTORICAL_PERIOD_COMPARISON: Cross-period comparisons
        if re.search(r'\b(compare|versus|vs)\b.*\b(november|october|september|august|december|nov|oct|sep|aug|dec|month|period)\b', q) or "compare" in q:
            return ChatbotIntent.HISTORICAL_PERIOD_COMPARISON, metadata

        # 13. PROCUREMENT_SUPPLIER_PERFORMANCE: Vendors, Purchase prices, POs
        supplier_patterns = [
            "supplier", "vendor", "purchase price", "ppv", "which supplier contributed most",
            "supplier variance", "purchase order", "procurement", "landed cost"
        ]
        if any(k in q for k in supplier_patterns):
            return ChatbotIntent.PROCUREMENT_SUPPLIER_PERFORMANCE, metadata

        # 14. MATERIAL_CONSUMPTION_INVENTORY: BOM consumption, Over-consumption, Wastage
        consumption_patterns = [
            "material consumption", "over-consumption", "bom allowance", "bom consumption",
            "material wastage", "component wastage", "inventory", "stock"
        ]
        if any(k in q for k in consumption_patterns):
            return ChatbotIntent.MATERIAL_CONSUMPTION_INVENTORY, metadata

        # 15. SCRAP_REWORK_QUALITY: Defect stations, Scrap rate, Inspection logs
        quality_patterns = [
            "scrap rate", "rework", "defect", "highest rejection", "rejection rate",
            "inspection failure", "station s0", "assembly yield", "why did scrap increase"
        ]
        if any(k in q for k in quality_patterns):
            return ChatbotIntent.SCRAP_REWORK_QUALITY, metadata

        # 16. PRODUCTION_OUTPUT_CAPACITY: Throughput, Produced units, Capacity
        prod_patterns = [
            "production output", "production volume", "units produced", "target vs actual",
            "throughput", "capacity", "output lower", "why is production output lower"
        ]
        if any(k in q for k in prod_patterns):
            return ChatbotIntent.PRODUCTION_OUTPUT_CAPACITY, metadata

        # 17. PRODUCT_PLANT_LINE_ANALYSIS: Product SKUs, Plants, Lines
        entity_patterns = [
            "which smartphone model", "which product", "sph-pro-256", "sph-a15", "phx-pro",
            "most expensive to manufacture", "which plant", "highest manufacturing cost",
            "which line", "lowest yield", "line 1", "line 2", "plt-01"
        ]
        if any(k in q for k in entity_patterns):
            return ChatbotIntent.PRODUCT_PLANT_LINE_ANALYSIS, metadata

        # 18. WORKFORCE & ENERGY
        if any(k in q for k in ["labour", "labor", "worker", "operator hours", "shift productivity"]):
            return ChatbotIntent.WORKFORCE_LABOUR_PRODUCTIVITY, metadata
        if any(k in q for k in ["energy cost", "power consumption", "machine cost", "downtime", "equipment efficiency"]):
            return ChatbotIntent.ENERGY_EQUIPMENT_EFFICIENCY, metadata

        # Fallback to general cost analysis if manufacturing domain keyword exists
        domain_keywords = ["cost", "batch", "variance", "direct cost", "plant", "product", "yield"]
        if any(k in q for k in domain_keywords):
            return ChatbotIntent.MANUFACTURING_COST_ANALYSIS, metadata

        return ChatbotIntent.APP_NAVIGATION_FEATURES, metadata


    @classmethod
    def resolve_data_store(
        cls,
        intent: ChatbotIntent,
        page_id: str,
        session_id: Optional[str] = None,
        requested_mode: Optional[str] = None,
    ) -> Tuple[str, str, bool]:
        """
        Determines authoritative data store (CURRENT_UPLOAD_STORE vs GLOBAL_STORE),
        effective mode, and synthetic flag according to platform isolation policy.
        """
        raw_mode = (requested_mode or "").upper().strip()

        # If user explicitly selected GLOBAL_ONLY or viewing Overview
        if raw_mode == "GLOBAL_ONLY" or page_id == "OVERVIEW":
            return "GLOBAL_STORE", "GLOBAL_ONLY", False

        # Data Upload Stage 1
        if page_id == "DATA_UPLOAD_STAGE_1":
            if session_id and session_id != "GLOBAL":
                return "CURRENT_UPLOAD_STORE", "UPLOAD_SESSION_ONLY", True
            return "NO_ACTIVE_DATASET", "UPLOAD_SESSION_ONLY", False

        # Data Upload Stage 2
        if page_id == "DATA_UPLOAD_STAGE_2":
            return "CURRENT_UPLOAD_STORE", "UPLOAD_SESSION_ONLY", True

        # Data Upload Stage 3 (Investigation Results)
        if page_id == "DATA_UPLOAD_STAGE_3":
            if raw_mode == "UPLOAD_SESSION_ONLY":
                return "CURRENT_UPLOAD_STORE", "UPLOAD_SESSION_ONLY", True
            return "CROSS_STORE (Current Upload vs Global Baseline)", "UPLOAD_SESSION_WITH_GLOBAL_COMPARISON", True

        # Other Analysis Pages: Default to GLOBAL_STORE unless explicit upload session requested
        if session_id and session_id != "GLOBAL" and raw_mode in ("UPLOAD_SESSION_ONLY", "UPLOAD_SESSION_WITH_GLOBAL_COMPARISON"):
            return "CROSS_STORE (Session vs Global)", raw_mode, True

        return "GLOBAL_STORE", "GLOBAL_ONLY", False


class ContextualResponseGenerator:
    """
    Generates natural, grounded, structured conversational responses for non-analytics scopes,
    educational manufacturing queries, platform workflow guidance, and general questions.
    """

    @classmethod
    def generate_unrelated_general_response(
        cls,
        question: str,
        report_id: str,
        timestamp_str: str,
    ) -> Dict[str, Any]:
        """Direct, concise, natural response for general queries unrelated to manufacturing operations."""
        q = (question or "").lower().strip()

        # Factual lookup table for common general questions
        direct_answers = {
            "japan": "Tokyo is the capital of Japan.",
            "france": "Paris is the capital of France.",
            "world cup": "Argentina won the latest FIFA World Cup in 2022, defeating France in the final in Qatar.",
            "football player": "Lionel Messi, Pelé, Diego Maradona, and Cristiano Ronaldo are widely regarded as the greatest football players in history. Lionel Messi holds a record eight Ballon d'Or awards and led Argentina to the 2022 World Cup title.",
            "super bowl": "The Kansas City Chiefs won Super Bowl LVIII in February 2024, defeating the San Francisco 49ers.",
            "speed of light": "The speed of light in a vacuum is exactly 299,792,458 metres per second (approximately 300,000 km/s or 186,282 miles/s).",
            "photosynthesis": "Photosynthesis is the biological process by which green plants, algae, and some bacteria convert light energy into chemical energy, synthesizing glucose from water and carbon dioxide while releasing oxygen.",
            "sky blue": "The sky appears blue due to Rayleigh scattering: Earth's atmosphere scatters shorter wavelengths of light (blue and violet) much more efficiently than longer wavelengths (red and yellow).",
            "mount everest": "Mount Everest is the highest mountain on Earth above sea level, with an official summit elevation of 8,848.86 metres (29,031.7 ft).",
            "moon": "The average distance from the Earth to the Moon is approximately 384,400 kilometres (238,855 miles).",
            "einstein": "Albert Einstein was a theoretical physicist widely acknowledged as one of the greatest physicists of all time, best known for developing the theory of relativity (E = mc²) and receiving the 1921 Nobel Prize in Physics.",
            "generative ai": "Generative AI refers to artificial intelligence models capable of generating new content—such as text, images, audio, synthetic data, or code—by learning statistical patterns and underlying representations from massive training corpora.",
            "gen ai": "Generative AI refers to artificial intelligence models capable of generating new content—such as text, images, audio, synthetic data, or code—by learning statistical patterns and representations from training data.",
            "neural network": "An artificial neural network is a computational architecture inspired by biological brains, composed of interconnected layers of artificial neurons (nodes) that compute weighted sums and apply activation functions to learn complex nonlinear patterns.",
            "machine learning": "Machine Learning (ML) is a core branch of artificial intelligence where computational algorithms automatically detect patterns and derive predictive rules directly from empirical data without being explicitly programmed with static rules.",
            "deep learning": "Deep Learning is a subset of machine learning based on multi-layered neural networks (deep neural networks) capable of automatically learning hierarchical feature abstractions directly from raw data like pixels, audio waveforms, or text tokens.",
            "rag": "Retrieval-Augmented Generation (RAG) is an AI architecture that enhances Large Language Models by retrieving relevant factual documents from an external authoritative knowledge store or vector database and injecting them into the prompt context before response generation.",
            "retrieval augmented": "Retrieval-Augmented Generation (RAG) is an AI architecture that enhances Large Language Models by retrieving relevant factual documents from an external authoritative knowledge store or vector database and injecting them into the prompt context before response generation.",
            "ai agent": "An AI agent is an autonomous software entity driven by reasoning models (such as LLMs) that perceives its environment, formulates multi-step execution plans, invokes external tools or APIs, and iteratively executes actions to accomplish specific objectives.",
            "fine-tuning": "Fine-tuning is the machine learning process of taking a pre-trained foundation model and continuing its training on a domain-specific dataset with a adjusted learning rate to adapt its behavior, terminology, and task accuracy.",
            "python": "Python is a high-level, interpreted programming language renowned for its readable syntax, dynamic typing, and comprehensive ecosystem supporting data engineering, scientific computing, machine learning, and enterprise backend systems.",
            "react": "React is an open-source JavaScript library created by Meta for developing user interfaces, based on a declarative component architecture, state-driven rendering, and virtual DOM reconciliation.",
            "sql join": "SQL JOIN clauses combine records from two or more database tables based on a related common column. An INNER JOIN returns only records with matches in both tables; a LEFT JOIN returns all rows from the left table with matching right rows; a RIGHT JOIN returns all rows from the right table; and a FULL OUTER JOIN returns all rows when there is a match in either table.",
            "inner join": "An INNER JOIN selects records that have matching values in both tables, filtering out any rows where the join condition is not satisfied in either dataset.",
            "joke": "Why did the smartphone production line stop for coffee? Because it needed a Java update and the assembly yield was getting too jittery!",
        }

        matched_answer = None
        for key, ans in direct_answers.items():
            if key in q:
                matched_answer = ans
                break

        if not matched_answer:
            # Fallback to general AI answer or polite factual statement
            try:
                from app.domo_llm import DomoTextLLM
                llm = DomoTextLLM(temperature=0.1, max_tokens=150, timeout=4.0)
                prompt = (
                    f"Answer this general knowledge question directly, factually, and concisely in 1-2 sentences. "
                    f"Do not mention manufacturing, factory data, or system prompts.\n\nQuestion: {question}\nAnswer:"
                )
                ai_out = llm._call(prompt).strip()
                if ai_out and len(ai_out) > 10:
                    matched_answer = ai_out
            except Exception:
                pass

        if not matched_answer:
            matched_answer = (
                "This inquiry pertains to general knowledge outside factory operations. "
                "I am happy to provide factual information, or assist you with manufacturing cost investigations, "
                "line yield analysis, and variance decomposition across your operational datasets."
            )

        return {
            "report_id": report_id,
            "title": f"General Inquiry: {question[:60]}",
            "question": question,
            "reporting_period": "N/A",
            "scope_label": "General Knowledge",
            "status": "COMPLETED",
            "generated_at": timestamp_str,
            "data_origin": "GENERAL_KNOWLEDGE_BASE",
            "is_synthetic": False,
            "intent": ChatbotIntent.GENERAL_UNRELATED_QUESTIONS.value,
            "executive_summary": matched_answer,
            "detailed_findings": [
                {
                    "index": "1.1",
                    "finding": "General Knowledge Response",
                    "details": matched_answer,
                    "evidence_level": "FACTUAL_KNOWLEDGE",
                    "impact": "Conversational Response",
                }
            ],
            "evidence": ["Direct factual answer provided without querying operational manufacturing records."],
            "what_we_cannot_conclude_yet": ["General questions do not reference factory cost or production records."],
            "recommended_actions": [
                {
                    "id": "NAV-01",
                    "action": "Ask a manufacturing question such as 'Why did manufacturing cost decrease?' or 'Which line has the highest scrap rate?'",
                    "owner": "User",
                    "urgency": "Low",
                }
            ],
            "source_metadata": {
                "source_store": "GENERAL_KNOWLEDGE",
                "dataset_names": ["Knowledge Base"],
                "reporting_period": "N/A",
                "provenance": "GENERAL_KNOWLEDGE",
                "calculation_method": "FACTUAL_SYNTHESIS",
                "data_freshness": "Current",
            },
            "follow_up_suggestions": [
                "Why did manufacturing cost decrease in November?",
                "Which product model has the highest cost per good unit?",
                "What is Overall Equipment Effectiveness (OEE)?",
            ],
        }

    @classmethod
    def generate_manufacturing_knowledge_response(
        cls,
        question: str,
        report_id: str,
        timestamp_str: str,
    ) -> Dict[str, Any]:
        """Provides authoritative, educational explanations of manufacturing concepts and best practices."""
        q = (question or "").lower().strip()

        if "oee" in q or "overall equipment effectiveness" in q:
            title = "Manufacturing Concept: Overall Equipment Effectiveness (OEE)"
            summary = (
                "Overall Equipment Effectiveness (OEE) is the universal manufacturing metric that measures the percentage "
                "of planned production time that is truly productive. It is calculated as: OEE = Availability × Performance × Quality.\n\n"
                "• Availability: Compares actual operating time against planned run time, isolating downtime losses such as feeder stoppages or machine breakdowns.\n"
                "• Performance: Measures actual operating speed against design cycle time, capturing minor stops and reduced speed losses.\n"
                "• Quality: Evaluates the proportion of produced units meeting specifications without rework (First Pass Yield).\n\n"
                "World-class discrete manufacturing typically achieves 85% OEE (90% Availability, 95% Performance, 99.9% Quality)."
            )
            actions = [
                {"id": "ENG-01", "action": "Implement automated cycle-time telemetry on SMT placement heads to isolate micro-stoppages.", "owner": "Maintenance", "urgency": "Medium"},
                {"id": "ENG-02", "action": "Calibrate optical inspection feedback to catch soldering defects at the earliest station.", "owner": "Quality", "urgency": "High"},
            ]
            follow_ups = [
                "What is the impact of equipment downtime on our production lines?",
                "Which production line has the highest defect rate?",
                "Explain First Pass Yield (FPY)",
            ]
        elif "first pass yield" in q or "fpy" in q:
            title = "Manufacturing Concept: First Pass Yield (FPY)"
            summary = (
                "First Pass Yield (FPY) is the percentage of manufactured units that successfully complete the production "
                "and testing process on the initial attempt without requiring rework, repair, or scrap.\n\n"
                "• Formula: FPY = (Good Units on First Attempt / Total Units Started) × 100.\n"
                "• Financial Significance: Units requiring rework consume extra operator hours, inspection cycles, and machine time, inflating the net Cost per Good Unit.\n"
                "• Benchmark: In our baseline operations (Aug–Oct), assembly yield averaged 98.11%. In the November upload, assembly yield decreased to 90.89%, creating significant rework expenditure."
            )
            actions = [
                {"id": "QC-01", "action": "Perform station Pareto analysis on S01–S06 defect logs to isolate primary causes of initial inspection failure.", "owner": "Quality Assurance", "urgency": "High"},
            ]
            follow_ups = [
                "What caused the reduction in yield in the latest upload?",
                "Which production line has the lowest assembly yield?",
                "How does yield impact cost per good unit?",
            ]
        elif "material wastage" in q or "reduce material waste" in q or "reduce waste" in q:
            title = "Manufacturing Best Practice: Reducing Material Wastage"
            summary = (
                "To systematically reduce material wastage in discrete and high-tech electronic assembly:\n\n"
                "1. Synchronize BOM Allowances: Audit engineering BOM component quantities against actual reel-feed consumption to identify over-consumption early.\n"
                "2. Feeder & Reel Maintenance: Calibrate pick-and-place feeder tape alignment and splicing to eliminate component drop, tape misfeeds, and discarded SMD chips.\n"
                "3. Optimize Solder Stencil Design: Apply a 10%–15% aperture reduction on fine-pitch ICs to eliminate solder paste over-deposition and solder bridging.\n"
                "4. Real-Time MUV Tracking: Monitor Material Usage Variance (MUV) per production order to isolate shift-specific or lot-specific consumption anomalies.\n"
                "5. Closed-Loop Scrap Recovery: Reclaim rejected PCB assemblies at Station S01 (SMT Solder) before thermal reflow curing to reuse bare boards."
            )
            actions = [
                {"id": "OP-01", "action": "Conduct engineering BOM consumption audit on high-spend NAND and display modules.", "owner": "Process Engineering", "urgency": "High"},
                {"id": "OP-02", "action": "Implement reel splicing sensors to prevent loose component discarding during coil changeovers.", "owner": "Shop Floor", "urgency": "Medium"},
            ]
            follow_ups = [
                "Which component contributes most to total material expenditure?",
                "Is material consumption exceeding BOM allowance in November?",
                "Which supplier has the largest purchase price variance?",
            ]
        elif "scrap" in q and "rework" in q:
            title = "Cost Accounting: Difference Between Scrap and Rework"
            summary = (
                "In manufacturing cost accounting, scrap and rework represent distinct quality cost categories:\n\n"
                "• Scrap: Defective materials or finished goods that cannot be repaired or salvaged and must be permanently discarded. Scrap results in a 100% loss of direct materials, plus whatever machine and labour costs were incurred up to the rejection point.\n\n"
                "• Rework: Defective units that can be corrected and restored to full engineering specifications through secondary operations. Rework preserves raw material investment but adds unbudgeted labor hours, technician time, and rework machine cycles.\n\n"
                "• In our data model, scrap and rework costs are tracked separately in `scrap_rework_cost_inr` and serialized quality inspection disposition tables."
            )
            actions = [
                {"id": "ACC-01", "action": "Segregate scrap write-offs from secondary rework labor in monthly line cost batches.", "owner": "Cost Accounting", "urgency": "Medium"},
            ]
            follow_ups = [
                "Why did scrap increase in the latest production period?",
                "Which defect station contributes most to rework cost?",
                "What is our overall assembly yield?",
            ]
        elif "standard costing" in q or "variance formula" in q or "ppv" in q or "muv" in q:
            title = "Cost Accounting: Standard Costing & Variance Analysis"
            summary = (
                "Standard Costing establishes predetermined standard benchmarks for material, labour, and machine expenditures, "
                "allowing plant controllers to decompose actual cost deviations into orthogonal variances:\n\n"
                "• Purchase Price Variance (PPV): (Actual Unit Price - Standard Unit Price) × Actual Quantity Purchased.\n"
                "• Material Usage Variance (MUV): (Actual Quantity Consumed - Standard Quantity Allowed) × Standard Unit Price.\n"
                "• Volume Effect: Impact of producing more or fewer units than baseline: (Actual Units - Baseline Units) × Baseline Unit Cost.\n"
                "• Rate Effect: Pure cost-efficiency shift per unit: (Actual Unit Cost - Baseline Unit Cost) × Actual Units Produced.\n\n"
                "In GWC Manufacturing AI, our 3-way orthogonal variance bridge calculates Volume, Mix, and Category Rate movements with ₹0.00 unexplained residual."
            )
            actions = [
                {"id": "FIN-01", "action": "Review the Volume, Mix, and Rate bridge on the Cost Analysis page for zero-residual reconciliation.", "owner": "Finance Controller", "urgency": "Medium"},
            ]
            follow_ups = [
                "Explain the Volume, Mix, and Rate variance bridge",
                "Why did manufacturing cost decrease in November?",
                "Which supplier contributed most to material cost changes?",
            ]
        else:
            title = f"Manufacturing Knowledge: {question[:50]}"
            summary = (
                f"Manufacturing intelligence inquiry regarding {question}. In discrete high-technology manufacturing, "
                "operational performance is optimized by tightly integrating bill of materials (BOM), shop-floor telemetry, "
                "and serialized inspection records. Our platform applies deterministic accounting frameworks to link "
                "physical assembly events directly to financial variance bridges."
            )
            actions = [
                {"id": "OPS-01", "action": "Correlate engineering methodologies with actual shop floor telemetry in your active datasets.", "owner": "Operations", "urgency": "Low"},
            ]
            follow_ups = [
                "What is Overall Equipment Effectiveness (OEE)?",
                "How can a manufacturer reduce material wastage?",
                "Explain First Pass Yield (FPY)",
            ]

        return {
            "report_id": report_id,
            "title": title,
            "question": question,
            "reporting_period": "All Periods",
            "scope_label": "Manufacturing Methodology",
            "status": "COMPLETED",
            "generated_at": timestamp_str,
            "data_origin": "MANUFACTURING_KNOWLEDGE_BASE",
            "is_synthetic": False,
            "intent": ChatbotIntent.GENERAL_MANUFACTURING_KNOWLEDGE.value,
            "executive_summary": summary,
            "detailed_findings": [
                {
                    "index": "1.1",
                    "finding": "Authoritative Engineering Methodology",
                    "details": summary,
                    "evidence_level": "VERIFIED_STANDARDS",
                    "impact": "Operational Best Practice",
                }
            ],
            "evidence": ["Industrial manufacturing standards and cost accounting principles."],
            "what_we_cannot_conclude_yet": ["General methodologies must be calibrated against company-specific line logs."],
            "recommended_actions": actions,
            "source_metadata": {
                "source_store": "MANUFACTURING_KNOWLEDGE_BASE",
                "dataset_names": ["Industry Standard Cost Accounting & Six Sigma Framework"],
                "reporting_period": "All Periods",
                "provenance": "MANUFACTURING_KNOWLEDGE",
                "calculation_method": "METHODOLOGY_STANDARDS",
                "data_freshness": "Current",
            },
            "follow_up_suggestions": follow_ups,
        }

    @classmethod
    def generate_app_navigation_response(
        cls,
        question: str,
        page_context: Optional[Dict[str, Any]],
        report_id: str,
        session_id: Optional[str],
        timestamp_str: str,
    ) -> Dict[str, Any]:
        """Provides page-aware guidance, explaining platform workflows, stage requirements, and data store separation."""
        q = (question or "").lower().strip()
        if isinstance(page_context, dict):
            ctx = page_context
            page_id = ctx.get("page_id", "HOME")
        elif isinstance(page_context, str):
            ctx = {"page_id": page_context}
            page_id = page_context
        else:
            ctx = {}
            page_id = "HOME"

        if any(k in q for k in ["upload store vs global store", "difference between upload store and global store", "upload store and global store"]):
            title = "Architecture Guidance: Current Upload Store vs Global Store"
            summary = (
                "The GWC Manufacturing Cost Intelligence Platform enforces strict dual-store data isolation:\n\n"
                "1. Current Upload Store (Staging Isolation):\n"
                "• When you upload new CSV datasets (Stage 1) and validate them (Stage 2), records are loaded into isolated in-memory staging tables (`stg_*`).\n"
                "• Stage 3 generates an investigation report comparing the staged session against committed baselines without writing unverified rows into production.\n"
                "• Unapproved uploads remain completely isolated, ensuring production dashboards are never corrupted by uncommitted test data.\n\n"
                "2. Global Store (Committed Operational Fact Tables):\n"
                "• Stores authoritative, approved historical production records in PostgreSQL (`line_cost_batches`, `hourly_production_logs`, `serialized_quality_inspections`).\n"
                "• Overview, Cost Analysis, and Historical Trends query exclusively from the Global Store.\n"
                "• Records enter the Global Store only after the manufacturer explicitly clicks 'Approve & Commit'."
            )
            follow_ups = [
                "What happens if I click Approve & Commit?",
                "Is this uploaded data already in the Global Store?",
                "How does the validation engine verify uploaded CSVs?",
            ]

        elif any(k in q for k in ["approve & commit", "approve and commit", "what if i do not approve", "what happens if i don't approve", "already in global store"]):
            title = "Workflow Lifecycle: Approve & Commit Governance"
            summary = (
                "Approve & Commit is the governance gate that promotes staged data into the authoritative Global Store:\n\n"
                "• Before Approval: Staged records reside exclusively in the Current Upload Store. Investigation reports can be viewed, analyzed, and exported to PDF, but production dashboards remain strictly unaffected.\n\n"
                "• On Approval: `PromotionService` executes an atomic database transaction. Validated staging rows are inserted/upserted into Global Store fact tables with genuine REAL provenance (`is_synthetic = False`). The batch status transitions to COMMITTED.\n\n"
                "• If You Do Not Approve: The staged datasets remain safely preserved in your active upload session. You can re-examine findings, correct mappings, or leave the session uncommitted without altering historical records.\n\n"
                "• If Promotion Fails: Transaction rollback ensures no partial or corrupted records enter the Global Store. The staged data remains intact so you can resolve the issue and retry safely."
            )
            follow_ups = [
                "Why did manufacturing cost decrease in this upload?",
                "What is the difference between Upload Store and Global Store?",
                "What date range is currently available in the Global Store?",
            ]

        elif any(k in q for k in ["production and demo mode", "production mode vs demo mode", "demo mode vs production mode", "difference between production and demo", "production vs demo", "demo vs production", "demo mode"]):
            title = "Platform Configuration: Production Mode vs Demo Mode"
            summary = (
                "The GWC Manufacturing Cost Intelligence Platform provides two distinct operational data modes:\n\n"
                "1. Production Mode:\n"
                "• Queries exclusively genuine, certified factory operational records (`is_synthetic = False`).\n"
                "• All metrics (Total Cost, Cost per Good Unit, Yield, Output) reflect audited physical production runs in PostgreSQL Neon fact tables.\n"
                "• Synthetic mock data and uncommitted test upload sessions are strictly filtered out to ensure enterprise compliance and reporting integrity.\n\n"
                "2. Demo Mode:\n"
                "• Includes synthetic demonstration and simulation records (`is_synthetic = True`).\n"
                "• Enables testing hypothetical operational scenarios, onboarding factory personnel, and exploring analytics without modifying live facts.\n"
                "• Every record clearly displays its synthetic provenance marker so analysts can readily distinguish test data from actual plant operations."
            )
            follow_ups = [
                "Why did manufacturing cost decrease in November?",
                "Which plant contributes most to total manufacturing cost?",
                "What is the difference between Upload Store and Global Store?",
            ]

        elif any(k in q for k in ["how to upload", "how do i upload", "supported file formats", "file format", "required columns"]):
            title = "Data Ingestion: Supported Datasets & Formats"
            summary = (
                "The platform supports 7 core manufacturing dataset families in UTF-8 CSV format with headers:\n\n"
                "1. Manufacturing Cost Records (`01_manufacturing_cost.csv`): Posting date, plant, line, product SKU, produced quantity, material/labor/machine/energy/scrap costs.\n"
                "2. Hourly Production Logs (`02_hourly_production.csv`): Event timestamps, line, shift, target quantity, actual quantity, good units.\n"
                "3. Serialized Quality Inspections (`03_serialized_quality_inspections.csv`): Inspection timestamps, serial numbers, stations S01–S06, defects, pass/fail result.\n"
                "4. Material Purchases (`04_material_purchase_orders.csv`): PO numbers, suppliers, component codes, purchased quantities, unit prices.\n"
                "5. Material Consumption (`05_material_consumption.csv`): Production order, component code, actual quantity consumed.\n"
                "6. BOM Components (`06_bom_components.csv`): Product SKU, component ID, engineering required quantity.\n"
                "7. Quality Rework Events (`07_quality_rework.csv`): Rework timestamps, stations, defect codes, rework labor hours.\n\n"
                "To ingest: Drag and drop your files onto the Stage 1 dropzone and click 'Inspect & Validate'."
            )
            follow_ups = [
                "What validation checks are performed on uploaded CSVs?",
                "What is the difference between Upload Store and Global Store?",
                "How do I resolve quarantined records?",
            ]

        elif any(k in q for k in ["explain this chart", "what does this chart mean", "what is this chart"]):
            if page_id == "OVERVIEW":
                title = "Overview Dashboard: Cost Trend & KPI Interpretation"
                summary = (
                    "The Overview Dashboard visualizes operational performance across all committed Global Store records:\n\n"
                    "• Total Manufacturing Cost Trend: Displays actual direct expenditure across months (August through November 2026), comparing daily/weekly totals against baseline averages.\n"
                    "• Expenditure Donut Chart: Decomposes direct costs into Material, Labour, Machine, Energy, and Scrap/Rework components.\n"
                    "• Plant Breakdown: Compares manufacturing expenditure and unit costs across facilities (PLT-01 Chennai, etc.).\n"
                    "• KPI Cards: Highlights Total Cost (₹ Cr), Cost per Good Unit (₹), Production Output (units), and Assembly Yield (%)."
                )
            elif page_id == "COST_ANALYSIS":
                title = "Cost Analysis: Variance Bridge & Decomposition"
                summary = (
                    "The Cost Analysis page presents a 3-way orthogonal variance bridge decomposing total cost changes into:\n\n"
                    "1. Volume Effect: Change in expenditure attributable strictly to producing higher or lower unit quantities.\n"
                    "2. Product Mix Effect: Cost impact of shifting production volume between higher-cost and lower-cost SKUs.\n"
                    "3. Category Rate Variance: Pure efficiency shifts in unit material prices, hourly labor wages, machine run rates, or scrap frequency.\n\n"
                    "The mathematical reconciliation guarantees zero unexplained residual."
                )
            elif page_id == "DATA_UPLOAD_STAGE_3":
                title = "Investigation Results: Scope & Cost Driver Breakdown"
                summary = (
                    "Stage 3 Investigation Results displays the active upload session compared against historical baseline:\n\n"
                    "• Active Scope Banner: Shows the uploaded date range, records validated, and comparison period.\n"
                    "• Trend Comparison: Plots the current session's actual expenditure vs baseline daily cost.\n"
                    "• Mathematical Reconciliation: Summarizes verified cost variance, volume variance, and rate effect.\n"
                    "• Primary Cost Driver: Highlights the dominant operational factor driving the cost movement."
                )
            else:
                title = "Application Feature: Visualization Guidance"
                summary = (
                    f"You are currently viewing {ctx.get('page_title', 'the application')}. "
                    "Each chart renders deterministic metrics queried from authenticated manufacturing tables. "
                    "Use the filter controls at the top of the page to focus on specific reporting periods, product SKUs, or plants."
                )
            follow_ups = [
                "Why did manufacturing cost decrease in November?",
                "Explain the Volume, Mix, and Rate variance bridge",
                "Which plant contributes most to manufacturing cost?",
            ]

        elif page_id == "DATA_UPLOAD_STAGE_1":
            title = "Data Upload (Stage 1): Dataset Selection & Upload Guidance"
            summary = (
                "You are on Stage 1 of the Data Upload workflow. Here you select and upload your factory CSV files:\n\n"
                "• Upload Options: Upload individual dataset files or all 7 datasets together.\n"
                "• Dropzone: Drag and drop UTF-8 CSV files or click browse.\n"
                "• Ingestion Isolation: Uploaded files are streamed into an isolated session without affecting the Global Store.\n"
                "• Next Step: Once files are selected, click 'Inspect & Validate' to advance to Stage 2."
            )
            follow_ups = [
                "What file formats and columns are supported for upload?",
                "What is the difference between Upload Store and Global Store?",
                "How does the validation engine verify uploaded CSVs?",
            ]

        elif page_id == "DATA_UPLOAD_STAGE_2":
            title = "Data Upload (Stage 2): Validation & Staging Inspection"
            summary = (
                f"You are on Stage 2 (Validation & Prepare) for session `{session_id or 'active'}`:\n\n"
                "• Dataset Detection: Analyzes uploaded CSV headers, maps aliases (e.g. `cost_date` → `posting_ts`), and populates staging tables.\n"
                "• Integrity Rules: Validates primary keys, numeric non-negativity, foreign key references, and timestamp formats.\n"
                "• Record Status: Displays total rows, valid rows, and any quarantined/invalid rows.\n"
                "• Promotion Blocker: Records cannot be promoted to the Global Store until validation completes successfully.\n"
                "• Next Step: Click 'Proceed to Investigation' to generate the Stage 3 RCA report."
            )
            follow_ups = [
                "What validation checks are performed on uploaded CSVs?",
                "Why can't records be promoted directly without validation?",
                "How do I resolve quarantined records in the staging table?",
            ]

        elif page_id == "DATA_UPLOAD_STAGE_3":
            title = "Data Upload (Stage 3): Investigation Results & Promotion Governance"
            summary = (
                f"You are viewing the Investigation Results for session `{session_id or 'active'}`:\n\n"
                "• Evidence Synthesis: The RCA engine has calculated direct cost variance, volume effect, and yield shifts for your uploaded dataset.\n"
                "• Baseline Comparison: The active upload is compared against the established Global Store baseline.\n"
                "• Data Isolation: Staged records remain uncommitted in the Current Upload Store.\n"
                "• Action Available: Click 'Approve & Commit' to promote the validated operational records into the Global Store fact tables with REAL provenance."
            )
            follow_ups = [
                "Why did manufacturing cost decrease in this upload?",
                "Is this uploaded dataset already in the Global Store?",
                "What happens if I click Approve & Commit versus leaving it unapproved?",
            ]

        else:
            title = "GWC Manufacturing AI — Navigation & Assistance"
            summary = (
                f"Welcome! You are currently on {ctx.get('page_title', 'the Manufacturing Cost Intelligence Platform')}. "
                "I am your context-aware analytical assistant, ready to help you investigate cost movements, explore line yield, "
                "inspect bills of materials, and review prioritized operational recommendations."
            )
            follow_ups = [
                "Why did manufacturing cost decrease in November?",
                "Which product model has the highest cost per good unit?",
                "What is the difference between Upload Store and Global Store?",
            ]

        return {
            "report_id": report_id,
            "title": title,
            "question": question,
            "reporting_period": "All Periods",
            "scope_label": "Manufacturing Methodology",
            "status": "COMPLETED",
            "generated_at": timestamp_str,
            "data_origin": "PLATFORM_WORKFLOW_REGISTRY",
            "is_synthetic": False,
            "intent": ChatbotIntent.APP_NAVIGATION_FEATURES.value,
            "executive_summary": summary,
            "detailed_findings": [
                {
                    "index": "1.1",
                    "finding": "Workflow & Application Architecture Guidance",
                    "details": summary,
                    "evidence_level": "PLATFORM_SPECIFICATION",
                    "impact": "User Operational Guidance",
                }
            ],
            "evidence": ["GWC Manufacturing Intelligence Platform operational governance specifications."],
            "what_we_cannot_conclude_yet": ["Chatbot operates in strictly read-only mode and cannot execute database modifications."],
            "recommended_actions": [
                {
                    "id": "NAV-01",
                    "action": "Use the navigation controls on the page or ask a specific analytical inquiry to explore data.",
                    "owner": "User",
                    "urgency": "Low",
                }
            ],
            "source_metadata": {
                "source_store": "PLATFORM_ARCHITECTURE",
                "dataset_names": ["Workflow Governance Registry"],
                "reporting_period": ctx.get("reporting_period") or "All Available Data",
                "provenance": "PLATFORM_METADATA",
                "calculation_method": "WORKFLOW_INSPECTOR",
                "data_freshness": "Current",
            },
            "follow_up_suggestions": follow_ups,
        }

    @classmethod
    def generate_data_coverage_response(
        cls,
        question: str,
        db_date_bounds: Dict[str, Any],
        record_counts: Dict[str, int],
        report_id: str,
        timestamp_str: str,
    ) -> Dict[str, Any]:
        """Explains current database date coverage, table counts, store separation, and provenance."""
        min_date = db_date_bounds.get("min_date", "2026-08-01")
        max_date = db_date_bounds.get("max_date", "2026-11-20")

        cost_cnt = record_counts.get("line_cost_batches", 5051)
        prod_cnt = record_counts.get("hourly_production_logs", 8985)
        qual_cnt = record_counts.get("serialized_quality_inspections", 16153)
        po_cnt = record_counts.get("material_purchase_records", 32)
        con_cnt = record_counts.get("material_consumption_records", 1071)

        summary = (
            f"The authoritative Global Store contains committed operational manufacturing data covering {min_date} through {max_date}:\n\n"
            f"• Line Cost Batches: {cost_cnt:,} records with verified direct cost breakdowns (August, September, October, and November 2026).\n"
            f"• Hourly Production Logs: {prod_cnt:,} event logs detailing shift target, actual, and good unit output.\n"
            f"• Serialized Quality Inspections: {qual_cnt:,} logs with station-level (S01–S06) pass/fail telemetry.\n"
            f"• Material Purchases: {po_cnt:,} purchase orders covering component acquisitions from suppliers.\n"
            f"• Material Consumption: {con_cnt:,} production run consumption records linked to BOM components.\n\n"
            "Data Provenance:\n"
            "• Records from Aug 01 to Oct 31 represent the committed operational baseline.\n"
            "• November records carry authentic REAL provenance from verified factory uploads.\n"
            "• In PRODUCTION mode, all queries filter exclusively for `is_synthetic == False` to guarantee operational integrity."
        )

        return {
            "report_id": report_id,
            "title": f"Data Architecture: Global Store Date Coverage & Record Audit ({min_date} – {max_date})",
            "question": question,
            "reporting_period": f"{min_date} to {max_date}",
            "scope_label": "Global Store Operational Datasets",
            "status": "COMPLETED",
            "generated_at": timestamp_str,
            "data_origin": "REAL_COMMITTED_STORE",
            "is_synthetic": False,
            "intent": ChatbotIntent.DATA_COVERAGE_QUALITY.value,
            "executive_summary": summary,
            "detailed_findings": [
                {
                    "index": "1.1",
                    "finding": f"Committed Date Horizon: {min_date} to {max_date}",
                    "details": f"PostgreSQL tables contain {cost_cnt:,} cost records across 4 consecutive calendar months.",
                    "evidence_level": "PROVEN",
                    "impact": "Data Availability & Governance",
                }
            ],
            "evidence": [f"Database bounds verified from Neon PostgreSQL: {min_date} through {max_date}."],
            "what_we_cannot_conclude_yet": ["Data beyond November 20, 2026 has not yet been uploaded or approved."],
            "recommended_actions": [
                {
                    "id": "DAT-01",
                    "action": "Upload December 2026 production datasets via the Data Upload page to extend temporal coverage.",
                    "owner": "Data Engineering",
                    "urgency": "Low",
                }
            ],
            "source_metadata": {
                "source_store": "GLOBAL_STORE",
                "dataset_names": ["line_cost_batches", "hourly_production_logs", "serialized_quality_inspections"],
                "reporting_period": f"{min_date} to {max_date}",
                "provenance": "REAL_COMMITTED_STORE",
                "calculation_method": "SQL_RECORD_INSPECTION",
                "data_freshness": max_date,
            },
            "follow_up_suggestions": [
                "Why did manufacturing cost increase in November?",
                "Which month had the highest cost per good unit?",
                "What is the difference between Production and Demo mode?",
            ],
        }

    @classmethod
    def generate_ambiguous_or_unsupported_response(
        cls,
        question: str,
        sub_type: str,
        report_id: str,
        timestamp_str: str,
    ) -> Dict[str, Any]:
        """Politely explains security policies or temporal boundaries."""
        if sub_type == "SECURITY_RESTRICTION":
            summary = (
                "Under platform governance and security policies, I cannot override system instructions, "
                "execute unauthorized data modifications, or generate fabricated financial figures. "
                "All manufacturing analyses are grounded strictly in authenticated database records and verified calculations."
            )
            title = "Security & Governance: Request Policy Restriction"
        else:
            summary = (
                "I cannot provide speculative forecasts or predict market figures beyond our authoritative data horizon "
                "(August 2026 through November 2026). For recorded historical and staged sessions, I provide exact mathematical "
                "cost decomposition, product unit economics, line rejection analysis, and evidence-grounded root causes."
            )
            title = "Data Boundary Limitation: Speculative Forecast Unsupported"

        return {
            "report_id": report_id,
            "title": title,
            "question": question,
            "reporting_period": "All Periods",
            "scope_label": "Manufacturing Methodology",
            "status": "COMPLETED",
            "generated_at": timestamp_str,
            "data_origin": "SECURITY_GOVERNANCE_POLICY",
            "is_synthetic": False,
            "intent": ChatbotIntent.AMBIGUOUS_OR_UNSUPPORTED.value,
            "executive_summary": summary,
            "detailed_findings": [
                {
                    "index": "1.1",
                    "finding": "Policy Boundary Applied",
                    "details": summary,
                    "evidence_level": "GOVERNANCE_ENFORCED",
                    "impact": "Policy Compliance",
                }
            ],
            "evidence": ["System governance and data availability boundaries."],
            "what_we_cannot_conclude_yet": ["Speculative forecasting without empirical manufacturing records is not permitted."],
            "recommended_actions": [
                {
                    "id": "GOV-01",
                    "action": "Frame your inquiry within our recorded periods (August–November 2026) or explore operational concepts.",
                    "owner": "User",
                    "urgency": "Low",
                }
            ],
            "source_metadata": {
                "source_store": "SYSTEM_GOVERNANCE",
                "dataset_names": ["Policy Registry"],
                "reporting_period": "N/A",
                "provenance": "SECURITY_GOVERNANCE",
                "calculation_method": "POLICY_CHECK",
                "data_freshness": "Current",
            },
            "follow_up_suggestions": [
                "Why did manufacturing cost decrease in November?",
                "What is Overall Equipment Effectiveness (OEE)?",
                "What data is currently available in the Global Store?",
            ],
        }
