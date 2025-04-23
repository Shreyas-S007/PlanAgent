from langgraph.graph import StateGraph, END
from typing import Dict, List, TypedDict, Optional
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialize Groq LLM
llm = ChatGroq(groq_api_key=GROQ_API_KEY, model_name="gemma2-9b-it")

# State definition for LangGraph
class AgentState(TypedDict):
    user_query: str
    subtasks: List[str]
    current_subtask: Optional[str]
    subtask_results: Dict[str, str]
    final_result: Optional[str]
    iteration_count: int
    max_iterations: int
    history: List[Dict[str, List[str]]]  # Tracks subtasks at each stage per iteration

# Prompt templates
PLAN_PROMPT = PromptTemplate(
    input_variables=["query"],
    template="Break down the following user query into subtasks:\n{query}\n\nProvide a list of subtasks."
)

SOLVE_PROMPT = PromptTemplate(
    input_variables=["subtask"],
    template="Solve the following subtask:\n{subtask}\n\nProvide the solution."
)

REFINE_PROMPT = PromptTemplate(
    input_variables=["subtasks", "results"],
    template="Review the subtasks and their results:\nSubtasks: {subtasks}\nResults: {results}\n\nSuggest modifications, deletions, or additions to the subtasks. If no changes are needed, say 'No changes needed'."
)

# Node functions
async def plan_node(state: AgentState) -> AgentState:
    prompt = PLAN_PROMPT.format(query=state["user_query"])
    response = await llm.ainvoke(prompt)
    plan = response.content  # Extract the content from the response
    subtasks = [task.strip() for task in plan.strip().split("\n") if task.strip()]
    state["subtasks"] = subtasks
    state["subtask_results"] = {}
    state["iteration_count"] = 0
    state["max_iterations"] = 3
    state["history"] = [{"generated": subtasks.copy(), "solved": [], "refined": []}]
    return state

async def solve_node(state: AgentState) -> AgentState:
    if not state["subtasks"]:
        return state  # No subtasks left, exit to finalize
    current_subtask = state["subtasks"][0]
    state["current_subtask"] = current_subtask
    prompt = SOLVE_PROMPT.format(subtask=current_subtask)
    response = await llm.ainvoke(prompt)
    result = response.content  # Extract the content from the response
    state["subtask_results"][current_subtask] = result
    state["subtasks"].pop(0)
    # Update history with solved subtask
    state["history"][-1]["solved"].append(current_subtask)
    return state

async def refine_node(state: AgentState) -> AgentState:
    if not state["subtask_results"]:
        return state
    state["iteration_count"] += 1
    prompt = REFINE_PROMPT.format(subtasks=list(state["subtask_results"].keys()), results=state["subtask_results"])
    response = await llm.ainvoke(prompt)
    refinement = response.content  # Extract the content from the response
    if "No changes needed" in refinement:
        return state  # Exit refinement if no changes are needed
    new_subtasks = [task.strip() for task in refinement.strip().split("\n") if task.strip()]
    # Only add new subtasks that aren't already solved
    added_subtasks = [task for task in new_subtasks if task and task not in state["subtask_results"]]
    state["subtasks"].extend(added_subtasks)
    # Update history with refined subtasks and start a new iteration
    state["history"][-1]["refined"] = added_subtasks.copy()
    if added_subtasks or state["subtasks"]:
        state["history"].append({"generated": added_subtasks.copy(), "solved": [], "refined": []})
    return state

async def finalize_node(state: AgentState) -> AgentState:
    if not state["subtask_results"]:
        state["final_result"] = "No results generated."
    else:
        final_result = "\n".join([f"{task}: {result}" for task, result in state["subtask_results"].items()])
        state["final_result"] = final_result
    return state

# Define the workflow with LangGraph
def build_workflow():
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("plan", plan_node)
    workflow.add_node("solve", solve_node)
    workflow.add_node("refine", refine_node)
    workflow.add_node("finalize", finalize_node)

    # Define edges
    workflow.set_entry_point("plan")
    workflow.add_edge("plan", "solve")
    workflow.add_conditional_edges(
        "solve",
        lambda state: "finalize" if not state["subtasks"] and state["iteration_count"] >= state["max_iterations"] else "refine" if state["iteration_count"] < state["max_iterations"] else "finalize",
        {"refine": "refine", "finalize": "finalize"}
    )
    workflow.add_edge("refine", "solve")
    workflow.add_edge("finalize", END)

    return workflow.compile()

# Main function to run the agent system
async def run_plan_agent(query: str, return_history: bool = False) -> tuple[str, List[Dict[str, List[str]]]]:
    workflow = build_workflow()
    initial_state = AgentState(
        user_query=query,
        subtasks=[],
        current_subtask=None,
        subtask_results={},
        final_result=None,
        iteration_count=0,
        max_iterations=3,
        history=[]
    )
    final_state = await workflow.ainvoke(initial_state)
    if return_history:
        return final_state["final_result"], final_state["history"]
    return final_state["final_result"]