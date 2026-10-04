FROM python:3.11-slim

RUN useradd -m -u 1000 user
WORKDIR /app

COPY --chown=user ./requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY --chown=user . /app

# Pesos do Llama local: NÃO embutidos na imagem (8B em bf16 ≈ 16GB).
# São baixados no arranque para o cache do disco (ver warmup em app.py)
# e reutilizados nos arranques seguintes. Para pré-baixar na build
# (opt-in, só com disco e licença garantidos), descommentar:
# ARG LOCAL_MODEL_ID=NousResearch/Meta-Llama-3-8B-Instruct
# ARG HF_TOKEN=""
# RUN HF_TOKEN=$HF_TOKEN python -c "from transformers import AutoTokenizer, AutoModelForCausalLM; AutoTokenizer.from_pretrained('$LOCAL_MODEL_ID'); AutoModelForCausalLM.from_pretrained('$LOCAL_MODEL_ID', torch_dtype='auto')"
# Nota: repo gated (ex. Meta Llama) exige licença aceite + HF_TOKEN com acesso.

USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PORT=7860

EXPOSE 7860

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1 --proxy-headers"]
