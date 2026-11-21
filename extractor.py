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

MODELOS_PRIORITARIOS = [
    "models/gemini-2.5-flash-lite",
    "models/gemini-2.0-flash",
    "models/gemini-2.0-flash-lite",
    "models/gemini-2.5-flash",
    "models/gemini-flash-latest",
]


def extrair_texto_pdf(uploaded_file) -> str:
    reader = PdfReader(uploaded_file)
    paginas = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(paginas).strip()


def _fallback_extracao_local(texto: str) -> dict:
    """Parser determinístico de backup caso a chave da API REST não esteja configurada ou sem cota."""
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
        "descricao": "Extraído via parser de contingência (verifique cota/chave GEMINI_API_KEY).",
    }


def _listar_modelos_disponiveis(chave: str) -> list[str]:
    """Combina modelos prioritários de alta cota gratuita com modelos descobertos via API."""
    fila = list(MODELOS_PRIORITARIOS)
    try:
        url_modelos = f"https://generativelanguage.googleapis.com/v1beta/models?key={chave}"
        resp = requests.get(url_modelos, timeout=8)
        if resp.status_code == 200:
            modelos = resp.json().get("models", [])
            ignorados = ["embedding", "image", "tts", "audio", "robotics", "computer-use", "deep-research", "pro"]
            for m in modelos:
                nome = m.get("name", "")
                if (
                    "generateContent" in m.get("supportedGenerationMethods", [])
                    and "gemini" in nome.lower()
                    and not any(termo in nome.lower() for termo in ignorados)
                    and nome not in fila
                ):
                    fila.append(nome)
    except Exception:
        pass
    return fila[:6]


def extrair_dados_financeiros(texto: str, api_key: str | None = None) -> tuple[dict, dict]:
    """
    Consome a API REST do Google Gemini com failover automático entre modelos.
    Retorna: (dados_estruturados, metadados_execucao_rest)
    """
    chave = (api_key or os.getenv("GEMINI_API_KEY", "")).strip().strip('"').strip("'")

    if not chave:
        dados = _fallback_extracao_local(texto)
        meta = {
            "modo": "Fallback Local (Sem API Key)",
            "endpoint": "N/A",
            "status_http": 200,
            "json_bruto": dados,
        }
        return dados, meta

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

    candidatos = _listar_modelos_disponiveis(chave)
    tentativas = []
    ultimo_status = 500
    ultimo_detalhe = ""

    for modelo in candidatos:
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/{modelo}:generateContent?key={chave}"
        try:
            response = requests.post(
                endpoint,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=15,
            )
            ultimo_status = response.status_code

            if response.status_code == 200:
                resposta_api = response.json()
                conteudo_texto = resposta_api["candidates"][0]["content"]["parts"][0]["text"]
                conteudo_limpo = conteudo_texto.replace("```json", "").replace("```", "").strip()
                dados = json.loads(conteudo_limpo)

                if dados.get("categoria") not in CATEGORIAS_VALIDAS:
                    dados["categoria"] = "Outros"

                try:
                    dados["valor"] = float(str(dados.get("valor", 0)).replace(",", "."))
                except ValueError:
                    dados["valor"] = 0.0

                nome_exibicao = modelo.replace("models/", "")
                meta = {
                    "modo": f"API REST ({nome_exibicao})",
                    "endpoint": f"POST /v1beta/{modelo}:generateContent",
                    "status_http": 200,
                    "failover_tentativas": tentativas,
                    "json_bruto": dados,
                }
                return dados, meta

            # Registra falha (ex: 429 cota zero ou 404) e tenta o próximo modelo
            tentativas.append({"modelo": modelo, "status": response.status_code})
            ultimo_detalhe = response.text[:250]

            # Se a chave for inválida (400/403), interrompe o loop imediatamente
            if response.status_code in (400, 403):
                break

        except Exception as erro:
            tentativas.append({"modelo": modelo, "erro": type(erro).__name__})
            ultimo_detalhe = str(erro)[:250]

    # Se todos os modelos falharem, aciona o fallback determinístico
    dados = _fallback_extracao_local(texto)
    meta = {
        "modo": f"Fallback após failover ({ultimo_status})",
        "endpoint": "POST /v1beta/models/*:generateContent",
        "status_http": ultimo_status,
        "tentativas": tentativas,
        "detalhe_erro": ultimo_detalhe,
        "json_bruto": dados,
    }
    return dados, meta
