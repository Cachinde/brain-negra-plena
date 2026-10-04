---
title: Plenitude Negra Plena
emoji: 🧁
colorFrom: purple
colorTo: pink
sdk: docker
app_port: 7860
pinned: false
---

# Plenitude — cérebro da Negra Plena

API FastAPI da assistente **Plenitude**, atendimento da pastelaria **Negra Plena**.  
Criada pela **Softedge**. Destinada a Hugging Face Spaces (sdk: docker, porta 7860).

O conector WhatsApp (Node, Railway) envia POST /api/escutar e recebe { "texto": "..." }.

## GPU ativada
A anotacao @spaces.GPU esta configurada para suportar inferencia rapida.
