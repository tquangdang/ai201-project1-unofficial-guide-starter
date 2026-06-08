"""Gradio UI for The Unofficial Guide. Run: python app.py -> http://localhost:7860"""

import gradio as gr
from rag import ask


def handle_query(question):
    if not question.strip():
        return "", ""
    result = ask(question)
    sources = "\n".join(f"• {s}" for s in result["sources"])
    return result["answer"], sources


with gr.Blocks(title="The Unofficial Guide") as demo:
    gr.Markdown("# The Unofficial Guide\nAsk about CS professors — answers come only from collected student reviews.")
    inp = gr.Textbox(label="Your question", placeholder="e.g. Whose exams track the lecture slides?")
    btn = gr.Button("Ask", variant="primary")
    answer = gr.Textbox(label="Answer", lines=8)
    sources = gr.Textbox(label="Retrieved from", lines=4)
    btn.click(handle_query, inputs=inp, outputs=[answer, sources])
    inp.submit(handle_query, inputs=inp, outputs=[answer, sources])

demo.launch()
