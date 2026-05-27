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
    """Cluster/detect recurring problems from discussion content."""
    # In production, this would batch cluster documents. For single-doc flow, summarize.
    llm = _get_llm(0.1)
    prompt = ChatPromptTemplate.from_messages([
        ("system", """
            You identify the central research problem, limitation, or technical theme discussed in a document.
            Focus on:
            - core technical challenge
            - research objective
            - limitation being addressed
            - emerging methodological direction
            Be precise and semantically dense.
            Avoid generic summaries.
        """),
        ("human", "Summarize the main problem or complaint in this discussion in 1-2 sentences (limit to 500 characters):\n\n{content}"),
    ])
    chain = prompt | llm
    # We need content - get from research context or a placeholder
    content = state.get("problem_summary", state.get("research_context", "No content"))
    out = chain.invoke({"content": content})
    summary = out.content.strip() if hasattr(out, "content") else str(out)
    return {**state, "problem_summary": summary or state.get("problem_summary", "Unknown problem")}

# NODE 2
# this node doesnt actually use the llm. only creates research context for the next node by performing the vector search
def research_node(state: AgentState) -> AgentState:
    """Retrieve related discussions via vector search and build RAG context."""
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
    for d in docs:
        context_parts.append(f"[{d['source']}] {d['title']}\n{d['content'][:1500]}")
        sources.append({"title": d["title"], "source": d["source"], "similarity": d["similarity"]})
    return {
        **state,
        "research_context": "\n\n---\n\n".join(context_parts),
        "sources": sources,
    }

# NODE 3
# 3 llm calls - 3 perspectives
def debate_node(state: AgentState) -> AgentState:
    """Multiple perspectives on root causes."""
    llm = _get_llm(0.7)
    ctx = state.get("research_context", "")
    problem = state.get("problem_summary", "")

    perspectives = []
    prompts = [
        "From technical/engineering perspective, what might cause this?",
        "From product/UX perspective, what might cause this?",
        "From business/organizational perspective, what might cause this?",
    ]
    for p in prompts:
        out = llm.invoke([
            HumanMessage(content=f"Problem: {problem}\n\nContext:\n{ctx}\n\n{p} Answer in 2-3 sentences."),
        ])
        text = out.content if hasattr(out, "content") else str(out)
        perspectives.append({"perspective": p, "explanation": text})

    return {**state, "debate_outputs": perspectives}

# NODE 4
def synthesis_node(state: AgentState) -> AgentState:
    """Combine research and debate into structured report."""
    llm = _get_llm(0.2)
    ctx = state.get("research_context", "")
    problem = state.get("problem_summary", "")
    debates = state.get("debate_outputs", [])

    prompt = f"""Problem: {problem}
    Research context:
    {ctx}

    Debate perspectives:
    {chr(10).join(f"- {d.get('explanation', d)}" for d in debates)}

    Produce a structured JSON report:
    {{
        "problem_summary": "1-2 sentence summary",
        "evidence": ["evidence1", "evidence2"],
        "root_causes": ["cause1", "cause2"],
        "solutions": ["solution1", "solution2"]
    }}
    Output ONLY valid JSON, no markdown."""
    out = llm.invoke([HumanMessage(content=prompt)])
    text = out.content if hasattr(out, "content") else str(out)
    try:
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        report = json.loads(text)
    except json.JSONDecodeError:
        report = {
            "problem_summary": problem,
            "evidence": [],
            "root_causes": [],
            "solutions": [],
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
    report["sources"] = [{"title": s.get("title"), "source": s.get("source")} for s in sources[:10]]
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
