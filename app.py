import gradio as gr
from main import app as fastapi_app

# Uma interface visual basica apenas para satisfazer a validacao ZeroGPU da Hugging Face
with gr.Blocks(title="Cerebro Plenitude") as demo:
    gr.Markdown("# 🧠 Motor de Inteligencia Artificial - Negra Plena")
    gr.Markdown("A interface visual esta inativa. O sistema esta a correr no modo API para atender o WhatsApp usando a placa grafica ZeroGPU local!")

# O grande truque: Montamos o nosso FastAPI (que o WhatsApp usa) por cima da interface do Gradio!
app = gr.mount_gradio_app(fastapi_app, demo, path="/")
