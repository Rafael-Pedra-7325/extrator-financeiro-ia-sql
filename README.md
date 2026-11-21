[![Live Demo](https://img.shields.io/badge/Live_Demo-Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://api-health-monitor-ia.streamlit.app/)
# 🧾 Extrator Inteligente de Cobranças e Recibos para SQL

Aplicação desenvolvida em **Python**, **SQL (SQLite)** e **Streamlit** que automatiza a entrada de dados financeiros a partir de faturas, recibos em texto ou PDFs, estruturando informações via **API REST de Inteligência Artificial** e persistindo tudo em um banco relacional com painel analítico em tempo real.

## 🎯 Dor Real Resolvida
Equipes financeiras e administrativas recebem cobranças, notas fiscais e comprovantes em formatos não estruturados (e-mails, textos soltos e PDFs) e perdem tempo digitando manualmente fornecedor, valor, categoria e vencimento em sistemas ou planilhas — processo lento e sujeito a erros humanos.

## ⚙️ Arquitetura e Fluxo Técnico
1. **Ingestão:** Leitura de texto bruto ou extração automática de texto de arquivos PDF (`pypdf`).
2. **Extração Estruturada (API REST + IA):** Envio do conteúdo via requisição HTTP `POST` para a API REST do Google Gemini (`responseMimeType: application/json`), garantindo retorno padronizado em JSON (com *fallback* determinístico local caso não haja chave configurada).
3. **Persistência Relacional (SQL):** Inserção parametrizada (`INSERT`) no SQLite, consultas filtradas (`SELECT ... WHERE`), agregações financeiras (`GROUP BY`, `SUM`, `COUNT`), atualização de status (`UPDATE`) e exclusão (`DELETE`).
4. **Observabilidade:** Painel *"Por baixo dos panos"* exibindo em tempo real as queries SQL executadas e o JSON retornado pela API.

## 🚀 Como Executar Localmente

```bash
git clone [https://github.com/Rafael-Pedra-7325/extrator-financeiro-ia-sql.git](https://github.com/Rafael-Pedra-7325/extrator-financeiro-ia-sql.git)
cd extrator-financeiro-ia-sql
pip install -r requirements.txt
streamlit run app.py
