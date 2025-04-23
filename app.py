import streamlit as st
import asyncio
from implementation import run_plan_agent
import networkx as nx
from pyvis.network import Network
import streamlit.components.v1 as components
import os

# Streamlit app
st.title("PlanAgent System")

# User input
user_query = st.text_input("Enter your query:", "How to plan a trip to Japan?")

# Button to run the agent
if st.button("Run PlanAgent"):
    if user_query:
        with st.spinner("Processing your query..."):
            # Run the agent system (assuming run_plan_agent returns both result and history)
            result, history = asyncio.run(run_plan_agent(user_query, return_history=True))
            st.success("Done!")
            st.write("### Result:")
            st.write(result)

            # Create a directed graph to visualize the subtask lifecycle
            G = nx.DiGraph()
            node_colors = {}
            edge_labels = {}

            # Add nodes and edges based on history
            for iteration, data in enumerate(history):
                iteration_label = f"Iteration {iteration + 1}"
                G.add_node(iteration_label, label=iteration_label, color="lightblue")
                node_colors[iteration_label] = "lightblue"

                # Add subtask nodes for this iteration
                for subtask in data.get("generated", []):
                    subtask_node = f"{subtask} (Generated, Iter {iteration + 1})"
                    G.add_node(subtask_node, label=subtask, color="lightgreen")
                    G.add_edge(iteration_label, subtask_node, label="Generated")
                    edge_labels[(iteration_label, subtask_node)] = "Generated"
                    node_colors[subtask_node] = "lightgreen"

                for subtask in data.get("solved", []):
                    subtask_node = f"{subtask} (Solved, Iter {iteration + 1})"
                    G.add_node(subtask_node, label=subtask, color="yellow")
                    original_subtask = f"{subtask} (Generated, Iter {iteration + 1})"
                    if original_subtask in G.nodes:
                        G.add_edge(original_subtask, subtask_node, label="Solved")
                        edge_labels[(original_subtask, subtask_node)] = "Solved"
                    node_colors[subtask_node] = "yellow"

                for subtask in data.get("refined", []):
                    subtask_node = f"{subtask} (Refined, Iter {iteration + 1})"
                    G.add_node(subtask_node, label=subtask, color="lightcoral")
                    original_subtask = f"{subtask} (Solved, Iter {iteration + 1})"
                    if original_subtask in G.nodes:
                        G.add_edge(original_subtask, subtask_node, label="Refined")
                        edge_labels[(original_subtask, subtask_node)] = "Refined"
                    node_colors[subtask_node] = "lightcoral"

            # Initialize PyVis network
            net = Network(height="500px", width="100%", directed=True, notebook=True)
            net.from_nx(G)

            # Customize node colors and edge labels
            for node in net.nodes:
                node_id = node["id"]
                node["color"] = node_colors.get(node_id, "lightblue")
                node["label"] = G.nodes[node_id]["label"]

            for edge in net.edges:
                edge["label"] = edge_labels.get((edge["from"], edge["to"]), "")

            # Save the graph to a temporary HTML file
            net.save_graph("graph.html")

            # Display the graph in Streamlit
            st.write("### Subtask Lifecycle Graph:")
            with open("graph.html", "r", encoding="utf-8") as f:
                graph_html = f.read()
            components.html(graph_html, height=500)

            # Clean up the temporary file
            os.remove("graph.html")
    else:
        st.error("Please enter a query.")