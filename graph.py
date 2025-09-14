from pydantic import BaseModel
from typing import List

from langchain_ollama import ChatOllama
from langgraph.graph import START, END, StateGraph
from langgraph.types import Send
from tavily import TavilyClient
import streamlit as st

from schemas import *
from prompts import *

from dotenv import load_dotenv
load_dotenv()

llm = ChatOllama(model="llama3:8b-instruct-q4_1")
reasoning_llm = ChatOllama(model="deepseek-r1:14b")


# Nós
def build_first_queries_node(state: ReportState):
    class QueryList(BaseModel):
        queries: List[str]

    user_input = state.user_input

    prompt = build_first_queries.format(user_input=user_input)
    query_llm = llm.with_structured_output(QueryList)
    result = query_llm.invoke(prompt)

    return {"queries": result.queries}


def spawn_researchers(state: ReportState):
    return [Send("single_search", query) for query in state.queries]


def single_search(query: str):
    tavily_client = TavilyClient()

    results = tavily_client.search(
        query,
        max_results=1,
        include_raw_content=False
    )

    url = results["results"][0]["url"]
    url_extraction = tavily_client.extract(url)

    if len(url_extraction["results"]) > 0:
        raw_content = url_extraction["results"][0]["raw_content"]
        prompt = resume_search.format(user_input=query, search_results=raw_content)
        llm_result = llm.invoke(prompt)

        query_results = QueryResult(
            title=results["results"][0]["title"],
            url=url,
            resume=llm_result.content
        )

        return {"query_results": [query_results]}


def final_writer(state: ReportState):
    search_results = ""
    references = ""
    for i, result in enumerate(state.query_results):   # <--- corrigido aqui
        search_results += f"[{i+1}]\n\n"
        search_results += f"Title: {result.title}\n"
        search_results += f"URL: {result.url}\n"
        search_results += f"Content: {result.resume}\n\n"
        search_results += f"==============================\n\n"

        references += f"[{i+1}] - [{result.title}]({result.url})\n"

    prompt = build_final_response.format(
        user_input=state.user_input,
        search_results=search_results
    )

    llm_result = reasoning_llm.invoke(prompt)
    final_response = llm_result.content + "\n\nReferences:\n" + references

    return {"final_response": final_response}


# Edges
builder = StateGraph(ReportState)

builder.add_node("build_first_queries", build_first_queries_node)
builder.add_node("single_search", single_search)
builder.add_node("final_writer", final_writer)

builder.add_edge(START, "build_first_queries")
builder.add_conditional_edges("build_first_queries", spawn_researchers, ["single_search"])
builder.add_edge("single_search", "final_writer")
builder.add_edge("final_writer", END)

graph = builder.compile()


if __name__ == "__main__":
    from IPython.display import Image, display
    display(Image(graph.get_graph().draw_mermaid_png()))

    st.title("🐍Search Synthesiser")
    user_input = st.text_input(
        "Qual a sua pergunta?",
        value="Can you explain to me how is the full process of building an LLM? From scratch"
    )

    if st.button("Pesquisar"):
        with st.status("Gerando resposta"):
            for output in graph.stream({"user_input": user_input}, stream_mode="debug"):
                if output["type"] == "task_result":
                    st.write(f"Running {output['payload']['name']}")
                    st.write(output)

            response = output["payload"]["result"][0][1]
            think_str = response.split("</think>")[0]
            final_response = response.split("</think>")[1]

            with st.expander("Reflexão", expanded=False):
                st.markdown(think_str)
            st.write(final_response)

    # Exemplo sem Streamlit:
    # user_input = "Can you explain to me how is the full process of building an LLM? From scratch"
    # graph.invoke({"user_input": user_input})
