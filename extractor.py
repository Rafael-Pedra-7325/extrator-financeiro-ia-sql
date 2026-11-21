import json
import os
import re
import requests
from pypdf import PdfReader

CATEGORIAS_VALIDAS = [
    "Infraestrutura Cloud",
    "Inteligência Artificial",
    "Ferramentas Dev",
    "Serviços",
    "Comunicação",
    "Design & Produto",
    "Outros",
]


def extrair_texto_pdf(uploaded_file) -> str:
    reader = PdfReader(uploaded_file)
    paginas = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(paginas).strip()


def _fallback_extracao_local(texto: str) -> dict:
    """Parser determinístico de backup caso a chave da API REST não esteja configurada."""
    valor_match = re.search(r"R\$\s*([\d\.]+,\d{2}|\d+\.\d{2})", texto)
    valor = 0.0
    if valor_match:
        bruto = valor_match.group(1)
        if "," in bruto:
            bruto = bruto.replace(".", "").replace(",", ".")
        valor = float(bruto)

    data_match = re.search(r"(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})", texto)
    vencimento = "2026-11-30"
    if data_match:
        d = data_match.group(1)
        if "/" in d:
            dia, mes, ano = d.split("/")
            vencimento = f"{ano}-{mes}-{dia}"
        else:
            vencimento = d

    primeira_linha = next((l.strip() for l in texto.splitlines() if l.strip()), "Fornecedor Extraído")
    fornecedor = primeira_linha[:45]

    texto_lower = texto.lower()
    if any(k in texto_lower for k in ["aws", "cloud", "servidor", "azure", "gcp"]):
        categoria = "Infraestrutura Cloud"
    elif any(k in texto_lower for k in ["ia", "llm", "token", "gemini", "openai"]):
        categoria = "Inteligência Artificial"
    elif any(k in texto_lower for k in ["whatsapp", "sms", "twilio", "mensageria"]):
        categoria = "Comunicação"
    else:
        categoria = "Serviços"

    status = "Pago" if "pago" in texto_lower or "comprovante" in texto_lower else "Pendente"

    return {
        "fornecedor": fornecedor,
        "categoria": categoria,
        "valor": valor,
        "vencimento": vencimento,
        "status": status,
        "descricao": "Extraído via parser de contingência (configure GEMINI_API_KEY para IA generativa).",
    }


def extrair_dados_financeiros(texto: str, api_key: str | None = None) -> tuple[dict, dict]:
    """
    Consome a API REST do Google Gemini para estruturar textos/recibos em JSON.
    Retorna: (dados_estruturados, metadados_execucao_rest)
    """
    chave = api_key or os.getenv("GEMINI_API_KEY", "").strip()

    if not chave:
        dados = _fallback_extracao_local(texto)
        meta = {
            "modo": "Fallback Local (Sem API Key)",
            "endpoint": "N/A",
            "status_http": 200,
            "json_bruto": dados,
        }
        return dados, meta

    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={chave}"
    )

    prompt = f"""
    Você é um agente de automação financeira. Extraia os dados do documento abaixo e retorne
    EXCLUSIVAMENTE um objeto JSON válido com estas chaves exatas:
    - "fornecedor": string (nome da empresa/emissor)
    - "categoria": string (escolha estritamente uma entre: {', '.join(CATEGORIAS_VALIDAS)})
    - "valor": number (valor numérico total em reais, ex: 1250.50)
    - "vencimento": string (data no formato YYYY-MM-DD; se não houver, use 2026-11-30)
    - "status": string ("Pago" se for recibo/comprovante já quitado, senão "Pendente")
    - "descricao": string (resumo curto de até 80 caracteres do serviço/cobrança)

    Documento:
    \"\"\"{texto[:4000]}\"\"\"
    """

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }

    try:
        response = requests.post(
            endpoint,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        resposta_api = response.json()
        conteudo_texto = resposta_api["candidates"][0]["content"]["parts"][0]["text"]
        conteudo_limpo = conteudo_texto.replace("```json", "").replace("```", "").strip()
        dados = json.loads(conteudo_limpo)

        if dados.get("categoria") not in CATEGORIAS_VALIDAS:
            dados["categoria"] = "Outros"

        meta = {
            "modo": "API REST Gemini 2.5 Flash",
            "endpoint": "POST /v1beta/models/gemini-2.5-flash:generateContent",
            "status_http": response.status_code,
            "json_bruto": dados,
        }
        return dados, meta

    except Exception as erro:
        dados = _fallback_extracao_local(texto)
        meta = {
            "modo": f"Fallback após erro na API ({type(erro).__name__})",
            "endpoint": "POST /v1beta/models/gemini-2.5-flash:generateContent",
            "status_http": getattr(getattr(erro, "response", None), "status_code", 500),
            "json_bruto": dados,
        }
        return dados, meta
