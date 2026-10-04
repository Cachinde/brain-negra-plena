import os

import gradio as gr
import uvicorn

try:
    import spaces

    print(f"[boot] spaces real: {getattr(spaces, '__file__', '?')}", flush=True)
except ImportError:  # fora do ZeroGPU (dev local)
    print("[boot] AVISO: pacote 'spaces' ausente, fallback local (ZeroGPU desligado)", flush=True)

    class _SpacesFallback:
        @staticmethod
        def GPU(task=None, **kwargs):
            if task is None:
                return lambda fn: fn
            return task

    spaces = _SpacesFallback()

from ai_engine import AIEngine
from config import Config
from main import app as api_app

PORT = int(os.getenv("PORT") or os.getenv("GRADIO_SERVER_PORT") or 7860)

_engine = AIEngine()


def _demo_reply(pergunta: str) -> str:
    pergunta = (pergunta or "").strip()
    if not pergunta:
        return "Escreve uma pergunta, por exemplo: quanto custa a pizza?"
    return _engine.generate_reply("demo", pergunta, "Visitante")


@spaces.GPU(duration=120)
def _zerogpu_status() -> str:
    return "ZeroGPU activo neste Space."


api_app.router.routes = [r for r in api_app.router.routes if getattr(r, "path", None) != "/"]

with gr.Blocks(title=f"{Config.ASSISTANT_NAME} - {Config.COMPANY_NAME}") as demo:
    gr.Markdown(
        f"# {Config.ASSISTANT_NAME} - cérebro da {Config.COMPANY_NAME}\n"
        "API de atendimento usada pelo bot WhatsApp.  \n"
        "`POST /api/escutar` · `GET /health` · `GET /docs`"
    )
    entrada = gr.Textbox(label="Pergunta de teste", placeholder="quanto custa a pizza?")
    btn = gr.Button("Enviar", variant="primary")
    saida = gr.Markdown()
    btn.click(_demo_reply, inputs=entrada, outputs=saida)
    entrada.submit(_demo_reply, inputs=entrada, outputs=saida)
    gr.Button("Estado ZeroGPU").click(_zerogpu_status, inputs=None, outputs=saida)

# SSR desligado: o proxy Node do Gradio fica com a 7860 e o uvicorn precisa dela.
app = gr.mount_gradio_app(api_app, demo, path="/", ssr_mode=False)

# ZeroGPU: o demo TEM de ser lançado para o scan de startup detectar o @spaces.GPU.
# Padrão comprovado (Gradio + ZeroGPU + Uvicorn): launch interno não-bloqueante
# numa porta livre e fecha; o tráfego real é servido pelo uvicorn na $PORT.
try:
    demo.launch(prevent_thread_lock=True, server_name="127.0.0.1", server_port=8000)
    demo.close()
    print("[boot] demo lançado e fechado para o scan ZeroGPU", flush=True)
except Exception as exc:
    print(f"[boot] lançamento interno do demo falhou: {exc!r}", flush=True)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
