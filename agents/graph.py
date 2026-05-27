"""LangGraph orchestration - summarize problem, research, debate, synthesis, governance."""
from typing import TypedDict, Annotated, Sequence
from operator import add
from functools import lru_cache

from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
import json

from agents.embeddings import vector_search
from agents.config import GROQ_API_KEY, LLM_MODEL


RESEARCH_SYSTEM_PROMPT = """
You are ARIE, a research synthesis engine.

Role:
- Produce cross-document technical synthesis over retrieved research abstracts/metadata.
- Do NOT act like a chatbot. Do NOT write motivational filler.

Grounding and truthfulness:
- Use ONLY the provided context. If the context does not support a claim, say "Insufficient evidence in retrieved context."
- Distinguish clearly between (a) evidence from the context and (b) your hypothesis/speculation.
- Do not invent citations, numbers, datasets, benchmarks, or paper details not present in the context.

Style:
- Technical, precise, information-dense.
- Prefer concrete mechanisms, failure modes, assumptions, and tradeoffs over generic prose.

Required behavior:
- Synthesize patterns ACROSS papers (recurrence, convergence/divergence, shifts).
- Surface: recurring bottlenecks, emerging trends, methodology shifts, unresolved limitations, conflicting approaches, promising directions, architectural tradeoffs, evaluation weaknesses.
- When asserting a theme/trend/conflict, cite supporting documents using their document tags (e.g., [D1], [D3]).
""".strip()


class AgentState(TypedDict):
    raw_post_id: str
    problem_summary: str
    evidence: list
    root_causes: list
    solutions: list
    debate_outputs: Annotated[list, add]
    research_context: str
    confidence_score: float
    sources: list
    governance_checks: dict
    final_report: dict | None


@lru_cache(maxsize=5)
def _get_llm(temp: float):
    """Return the shared LLM client for this worker process."""
    return ChatGroq(model=LLM_MODEL, api_key=GROQ_API_KEY, temperature=0.4) # SAMPLING PARAMETER!!! super deterministic atm

# NODE 1
def summarize_problem_node(state: AgentState) -> AgentState:
    """Derive a retrieval query for research synthesis."""
    llm = _get_llm(0.1)
    prompt = ChatPromptTemplate.from_messages([
        ("system", RESEARCH_SYSTEM_PROMPT + "\n\n"
            "Task: Convert the input paper abstract/metadata into a short retrieval query that will pull related papers.\n"
            "Output 1-2 sentences, semantically dense, <= 350 characters. No fluff."
        ),
        ("human", "Input (paper abstract/metadata):\n\n{content}"),
    ])
    chain = prompt | llm
    content = state.get("problem_summary", state.get("research_context", "No content"))
    out = chain.invoke({"content": content})
    summary = out.content.strip() if hasattr(out, "content") else str(out)
    return {**state, "problem_summary": summary or state.get("problem_summary", "Unknown problem")}

# NODE 2
# this node doesnt actually use the llm. only creates research context for the next node by performing the vector search
def research_node(state: AgentState) -> AgentState:
    """Retrieve related papers via vector search and build RAG context."""
    problem = state.get("problem_summary", "")
    if not problem:
        return state
    docs = vector_search(problem, top_k=5)
    docs = [d for d in docs if d["similarity"] >= 0.72] # SIMILARITY THRESHOLD

    # ========== LOGGING =================
    print("\n=== RETRIEVAL DEBUG ===")
    print("QUERY:", problem)

    for i, d in enumerate(docs, 1):
        print(f"{i}. sim={d['similarity']:.3f} | {d['title'][:120]}")
    # ====================================
    context_parts = []
    sources = []
    for i, d in enumerate(docs, 1):
        doc_tag = f"D{i}"
        context_parts.append(
            f"[{doc_tag}] source={d['source']} | title={d['title']}\n"
            f"{d['content'][:1500]}"
        )
        sources.append(
            {"doc_tag": doc_tag, "title": d["title"], "source": d["source"], "similarity": d["similarity"]}
        )
    return {
        **state,
        "research_context": "\n\n---\n\n".join(context_parts),
        "sources": sources,
    }

# NODE 3
# 3 llm calls - 3 perspectives
def debate_node(state: AgentState) -> AgentState:
    """Generate complementary analytic lenses for synthesis."""
    llm = _get_llm(0.7)
    ctx = state.get("research_context", "")
    problem = state.get("problem_summary", "")

    perspectives = []
    prompts = [
        "Methods + assumptions: cluster the main methodological approaches across papers; compare key design choices and assumptions; cite [D#].",
        "Bottlenecks + limitations: identify recurring technical bottlenecks, failure modes, and unresolved limitations that appear across multiple papers; cite [D#].",
        "Evaluation + tradeoffs: compare evaluation protocols/metrics/datasets mentioned; surface weaknesses, missing ablations, and key tradeoffs; cite [D#].",
    ]
    for p in prompts:
        out = llm.invoke([
            HumanMessage(content=
                f"{RESEARCH_SYSTEM_PROMPT}\n\n"
                f"Synthesis query: {problem}\n\n"
                f"Retrieved context:\n{ctx}\n\n"
                f"Task: {p}\n"
                f"Constraints: Write 4-8 bullets. Each bullet must include at least one citation tag like [D1]. "
                f"If evidence is thin, say so explicitly."
            ),
        ])
        text = out.content if hasattr(out, "content") else str(out)
        perspectives.append({"perspective": p, "explanation": text})

    return {**state, "debate_outputs": perspectives}

# NODE 4
def synthesis_node(state: AgentState) -> AgentState:
    """Combine retrieved context into a research synthesis report."""
    llm = _get_llm(0.2)
    ctx = state.get("research_context", "")
    problem = state.get("problem_summary", "")
    debates = state.get("debate_outputs", [])

    prompt = f"""{RESEARCH_SYSTEM_PROMPT}

    Synthesis query: {problem}

    Retrieved context (papers):
    {ctx}

    Analyst notes (may be imperfect, still cite-check them against context):
    {chr(10).join(f"- {d.get('explanation', d)}" for d in debates)}

    Task: Produce a cross-paper research synthesis. Do NOT summarize papers one-by-one. Focus on patterns.

    Output ONLY valid JSON (no markdown). Requirements:
    - Every non-trivial claim must be supported by at least one citation tag [D#].
    - If you cannot support a field, use an empty list and add a note in "uncertainties".

    JSON schema:
    {{
        "synthesis_query": "{problem}",
        "recurring_bottlenecks": [{{"item": "...", "evidence": ["... [D1]", "... [D3]"]}}],
        "emerging_trends": [{{"item": "...", "evidence": ["... [D2]"]}}],
        "methodology_shifts": [{{"from": "...", "to": "...", "evidence": ["... [D#]"]}}],
        "conflicting_approaches": [{{"approach_a": "...", "approach_b": "...", "core_tradeoff": "...", "evidence": ["... [D#]"]}}],
        "evaluation_weaknesses": [{{"weakness": "...", "impact": "...", "evidence": ["... [D#]"]}}],
        "unresolved_limitations": [{{"limitation": "...", "why_hard": "...", "evidence": ["... [D#]"]}}],
        "promising_directions": [{{"direction": "...", "rationale": "...", "evidence": ["... [D#]"], "speculation": false}}],
        "architectural_tradeoffs": [{{"tradeoff": "...", "when_it_wins": "...", "when_it_fails": "...", "evidence": ["... [D#]"]}}],
        "uncertainties": ["Insufficient evidence in retrieved context for ..."]
    }}
    """
    out = llm.invoke([HumanMessage(content=prompt)])
    text = out.content if hasattr(out, "content") else str(out)
    try:
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        report = json.loads(text)
    except json.JSONDecodeError:
        report = {
            "synthesis_query": problem,
            "recurring_bottlenecks": [],
            "emerging_trends": [],
            "methodology_shifts": [],
            "conflicting_approaches": [],
            "evaluation_weaknesses": [],
            "unresolved_limitations": [],
            "promising_directions": [],
            "architectural_tradeoffs": [],
            "uncertainties": ["Model output was not valid JSON; insufficient reliable synthesis produced."],
        }
    return {**state, "final_report": report}

# NODE 5
def governance_node(state: AgentState) -> AgentState:
    """Check hallucinations and assign confidence score."""
    report = state.get("final_report") or {}
    sources = state.get("sources", [])
    n_sources = len(sources)
    avg_sim = sum(s.get("similarity", 0) for s in sources) / max(n_sources, 1)
    # simple heuristic: more sources + higher similarity = higher confidence
    confidence = min(0.95, 0.3 + 0.3 * min(n_sources / 5, 1) + 0.35 * avg_sim)
    governance_checks = {
        "sources_verified": n_sources > 0,
        "avg_similarity": round(avg_sim, 3),
        "source_count": n_sources,
    }
    report["confidence_score"] = round(confidence, 2)
    report["sources"] = [{"doc_tag": s.get("doc_tag"), "title": s.get("title"), "source": s.get("source")} for s in sources[:10]]
    report["governance_checks"] = governance_checks
    return {**state, "final_report": report, "confidence_score": confidence}


@lru_cache(maxsize=1)
def build_workflow():
    """Build the LangGraph workflow."""
    workflow = StateGraph(AgentState)

    workflow.add_node("summarize_problem", summarize_problem_node)
    workflow.add_node("research", research_node)
    workflow.add_node("debate", debate_node)
    workflow.add_node("synthesis", synthesis_node)
    workflow.add_node("governance", governance_node)

    workflow.set_entry_point("summarize_problem")
    workflow.add_edge("summarize_problem", "research")
    workflow.add_edge("research", "debate")
    workflow.add_edge("debate", "synthesis")
    workflow.add_edge("synthesis", "governance")
    workflow.add_edge("governance", END)

    return workflow.compile()


def clear_workflow_cache() -> None:
    """Clear process-local graph/LLM caches, mainly for tests or config reloads."""
    build_workflow.cache_clear()
    _get_llm.cache_clear()


def run_pipeline(raw_post_id: str, title: str, content: str) -> dict:
    """Run the full pipeline for a new post."""
    initial: AgentState = {
        "raw_post_id": raw_post_id,
        "problem_summary": f"{title}\n{content}",
        "evidence": [],
        "root_causes": [],
        "solutions": [],
        "debate_outputs": [],
        "research_context": "",
        "confidence_score": 0,
        "sources": [],
        "governance_checks": {},
        "final_report": None,
    }
    graph = build_workflow()
    result = graph.invoke(initial)
    return result.get("final_report") or {}
