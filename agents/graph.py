"""LangGraph orchestration - problem detection, research, debate, synthesis, governance."""
from typing import TypedDict, Annotated, Sequence
from operator import add

from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
import json

from agents.embeddings import vector_search, store_document, get_embedding
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


def _get_llm():
    return ChatGroq(model=LLM_MODEL, api_key=GROQ_API_KEY, temperature=0.3)


def problem_detection_node(state: AgentState) -> AgentState:
    """Cluster/detect recurring problems from discussion content."""
    # In production, this would batch cluster documents. For single-doc flow, summarize.
    llm = _get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You identify recurring problems or complaints from user discussions. Be concise."),
        ("human", "Summarize the main problem or complaint in this discussion in 1-2 sentences:\n\n{content}"),
    ])
    chain = prompt | llm
    # We need content - get from research context or a placeholder
    content = state.get("research_context", state.get("problem_summary", "No content"))
    out = chain.invoke({"content": content})
    summary = out.content.strip() if hasattr(out, "content") else str(out)
    return {**state, "problem_summary": summary or state.get("problem_summary", "Unknown problem")}


def research_node(state: AgentState) -> AgentState:
    """Retrieve related discussions via vector search and build RAG context."""
    problem = state.get("problem_summary", "")
    if not problem:
        return state
    docs = vector_search(problem, top_k=8)
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


def debate_node(state: AgentState) -> AgentState:
    """Multiple perspectives on root causes."""
    llm = _get_llm()
    ctx = state.get("research_context", "")[:4000]
    problem = state.get("problem_summary", "")

    perspectives = []
    prompts = [
        "From a technical/engineering perspective, what might cause this?",
        "From a product/UX perspective, what might cause this?",
        "From a business/organizational perspective, what might cause this?",
    ]
    for p in prompts:
        out = llm.invoke([
            HumanMessage(content=f"Problem: {problem}\n\nContext:\n{ctx}\n\n{p} Answer in 2-3 sentences."),
        ])
        text = out.content if hasattr(out, "content") else str(out)
        perspectives.append({"perspective": p, "explanation": text})

    return {**state, "debate_outputs": perspectives}


def synthesis_node(state: AgentState) -> AgentState:
    """Combine research and debate into structured report."""
    llm = _get_llm()
    ctx = state.get("research_context", "")
    problem = state.get("problem_summary", "")
    debates = state.get("debate_outputs", [])

    prompt = f"""Problem: {problem}

Research context:
{ctx[:6000]}

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


def governance_node(state: AgentState) -> AgentState:
    """Check hallucinations and assign confidence score."""
    report = state.get("final_report") or {}
    sources = state.get("sources", [])
    n_sources = len(sources)
    avg_sim = sum(s.get("similarity", 0) for s in sources) / max(n_sources, 1)
    # Simple heuristic: more sources + higher similarity = higher confidence
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


def build_workflow():
    """Build the LangGraph workflow."""
    workflow = StateGraph(AgentState)

    workflow.add_node("problem_detection", problem_detection_node)
    workflow.add_node("research", research_node)
    workflow.add_node("debate", debate_node)
    workflow.add_node("synthesis", synthesis_node)
    workflow.add_node("governance", governance_node)

    workflow.set_entry_point("problem_detection")
    workflow.add_edge("problem_detection", "research")
    workflow.add_edge("research", "debate")
    workflow.add_edge("debate", "synthesis")
    workflow.add_edge("synthesis", "governance")
    workflow.add_edge("governance", END)

    return workflow.compile()


def run_pipeline(raw_post_id: str, title: str, content: str) -> dict:
    """Run the full pipeline for a new post."""
    initial: AgentState = {
        "raw_post_id": raw_post_id,
        "problem_summary": f"{title}\n{content}"[:500],
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
