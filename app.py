import streamlit as st
from database import (
    init_db,
    inserir_lancamento,
    listar_lancamentos,
    resumo_por_categoria,
    atualizar_status,
    excluir_lancamento,
)
from extractor import extrair_dados_financeiros, extrair_texto_pdf, CATEGORIAS_VALIDAS

st.set_page_config(
    page_title="Extrator Financeiro IA -> SQL",
    page_icon="🧾",
    layout="wide",
)

init_db()

EXEMPLOS = {
    "Fatura Cloud (Azure)": (
        "FATURA DE SERVIÇOS EM NUVEM - MICROSOFT AZURE BRASIL\n"
        "Cliente: Blip Soluções Tecnológicas Ltda\n"
        "Referência: Clusters Kubernetes e Banco Gerenciado - Nov/2026\n"
        "Valor Total a Pagar: R$ 1.420,80\n"
        "Data de Vencimento: 28/11/2026\n"
        "Status: Aguardando pagamento via boleto."
    ),
    "Comprovante API WhatsApp": (
        "COMPROVANTE DE PAGAMENTO PIX\n"
        "Recebedor: Meta Platforms / WhatsApp Business API\n"
        "Descrição: Pacote de 50.000 conversas iniciadas por utilidade\n"
        "Valor Pago: R$ 640,00\n"
        "Data da Transação: 19/11/2026\n"
        "Situação: Transação concluída e liquidada."
    ),
    "Nota Fiscal Treinamento IA": (
        "NOTA FISCAL DE SERVIÇOS ELETRÔNICA (NFS-e)\n"
        "Prestador: Ada Tech Educação e Tecnologia S.A.\n"
        "Discriminação: Workshop corporativo de Engenharia de Prompt e Agentes\n"
        "Valor Líquido da Nota: R$ 2.950,00\n"
        "Vencimento: 05/12/2026"
    ),
}

if "texto_documento" not in st.session_state:
    st.session_state["texto_documento"] = EXEMPLOS["Fatura Cloud (Azure)"]
if "ultima_execucao" not in st.session_state:
    st.session_state["ultima_execucao"] = None

st.title("🧾 Extrator Inteligente de Cobranças e Recibos para SQL")
st.caption(
    "Transforma faturas, comprovantes e PDFs não estruturados em registros relacionais SQL "
    "via API REST de IA Generativa."
)

# Sidebar: configuração opcional da chave
with st.sidebar:
    st.header("⚙️ Configuração")
    secret_key = st.secrets.get("GEMINI_API_KEY", "") if hasattr(st, "secrets") else ""
    user_key = st.text_input(
        "Gemini API Key (opcional)",
        value=secret_key,
        type="password",
        help="Se deixado em branco, o sistema utiliza o parser local de contingência automaticamente.",
    )
    st.markdown("---")
    st.markdown("**Stack do Projeto:**")
    st.markdown("- **Linguagem:** Python 3.11+\n- **Banco de Dados:** SQLite (SQL puro)\n- **Integração:** API REST (JSON)\n- **Interface:** Streamlit")

# Bloco 1: Entrada de Documento
col_entrada, col_preview = st.columns([1.2, 1])

with col_entrada:
    st.subheader("1. Entrada do Documento")
    b1, b2, b3 = st.columns(3)
    if b1.button("📄 Exemplo Azure", use_container_width=True):
        st.session_state["texto_documento"] = EXEMPLOS["Fatura Cloud (Azure)"]
    if b2.button("✅ Exemplo Recibo", use_container_width=True):
        st.session_state["texto_documento"] = EXEMPLOS["Comprovante API WhatsApp"]
    if b3.button("🎓 Exemplo NFS-e", use_container_width=True):
        st.session_state["texto_documento"] = EXEMPLOS["Nota Fiscal Treinamento IA"]

    arquivo_pdf = st.file_uploader("Ou envie um recibo/fatura em PDF:", type=["pdf"])
    if arquivo_pdf is not None:
        texto_pdf = extrair_texto_pdf(arquivo_pdf)
        if texto_pdf:
            st.session_state["texto_documento"] = texto_pdf
            st.success("Texto extraído do PDF com sucesso!")
        else:
            st.warning("Não foi possível extrair texto selecionável deste PDF.")

    texto_input = st.text_area(
        "Conteúdo bruto da cobrança ou recibo:",
        value=st.session_state["texto_documento"],
        height=175,
    )

    if st.button("🚀 Extrair com IA e Gravar no Banco SQL", type="primary", use_container_width=True):
        if not texto_input.strip():
            st.error("Insira ou selecione um texto antes de extrair.")
        else:
            with st.spinner("Processando documento via API REST e persistindo no SQLite..."):
                dados_extraidos, meta_rest = extrair_dados_financeiros(texto_input, api_key=user_key)
                novo_id, query_insert = inserir_lancamento(dados_extraidos)
                st.session_state["ultima_execucao"] = {
                    "id": novo_id,
                    "dados": dados_extraidos,
                    "meta_rest": meta_rest,
                    "query_insert": query_insert,
                }
            st.success(f"Registro #{novo_id} inserido no banco SQLite ({dados_extraidos['fornecedor']})!")

with col_preview:
    st.subheader("2. Resultado da Última Extração")
    exec_info = st.session_state["ultima_execucao"]
    if exec_info:
        d = exec_info["dados"]
        m = exec_info["meta_rest"]
        st.info(f"**Motor utilizado:** {m['modo']} | **HTTP Status:** `{m['status_http']}`")
        c1, c2 = st.columns(2)
        c1.metric("Fornecedor", d["fornecedor"])
        c2.metric("Valor Extraído", f"R$ {float(d['valor']):,.2f}")
        c3, c4, c5 = st.columns(3)
        c3.write(f"**Categoria:**\n{d['categoria']}")
        c4.write(f"**Vencimento:**\n{d['vencimento']}")
        c5.write(f"**Status:**\n{d['status']}")
        st.write(f"**Descrição:** {d['descricao']}")
    else:
        st.info("Clique em **Extrair com IA e Gravar no Banco SQL** ao lado para testar o pipeline completo.")

st.markdown("---")

# Bloco 2: Consultas SQL e Indicadores
st.subheader("3. Consolidação Financeira (Consultas SQL em Tempo Real)")

df_todos, _ = listar_lancamentos()
total_geral = df_todos["valor"].sum() if not df_todos.empty else 0.0
total_pendente = df_todos[df_todos["status"] == "Pendente"]["valor"].sum() if not df_todos.empty else 0.0
total_pago = df_todos[df_todos["status"] == "Pago"]["valor"].sum() if not df_todos.empty else 0.0

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Consolidado", f"R$ {total_geral:,.2f}")
k2.metric("A Pagar (Pendente)", f"R$ {total_pendente:,.2f}")
k3.metric("Liquidado (Pago)", f"R$ {total_pago:,.2f}")
k4.metric("Documentos no Banco", len(df_todos))

col_tabela, col_grafico = st.columns([1.6, 1])

with col_tabela:
    f1, f2 = st.columns(2)
    filtro_cat = f1.selectbox("Filtrar por Categoria (`WHERE`):", ["Todas"] + CATEGORIAS_VALIDAS)
    filtro_status = f2.selectbox("Filtrar por Status (`WHERE`):", ["Todos", "Pendente", "Pago"])

    df_filtrado, query_select = listar_lancamentos(categoria=filtro_cat, status=filtro_status)
    st.dataframe(df_filtrado, use_container_width=True, hide_index=True)

    # Ações rápidas de UPDATE e DELETE
    if not df_filtrado.empty:
        with st.expander("✏️ Atualizar Status (UPDATE) ou Remover Registro (DELETE)"):
            col_id, col_acao1, col_acao2 = st.columns([1, 1, 1])
            id_alvo = col_id.number_input(
                "ID do lançamento:",
                min_value=int(df_filtrado["id"].min()),
                max_value=int(df_filtrado["id"].max()),
                step=1,
            )
            if col_acao1.button("✅ Marcar como Pago", use_container_width=True):
                atualizar_status(int(id_alvo), "Pago")
                st.rerun()
            if col_acao2.button("🗑️ Excluir Registro", use_container_width=True):
                excluir_lancamento(int(id_alvo))
                st.rerun()

with col_grafico:
    st.markdown("**Gastos por Categoria (`GROUP BY`)**")
    df_cat, query_group = resumo_por_categoria()
    if not df_cat.empty:
        st.bar_chart(df_cat.set_index("Categoria")["Total_BRL"])
        st.dataframe(df_cat, use_container_width=True, hide_index=True)

# Bloco 3: Transparência Técnica para Avaliadores
with st.expander("🔍 Por baixo dos panos: Queries SQL & Payload JSON da API REST"):
    st.markdown("**1. Consulta SQL Executada (`SELECT` / `WHERE`):**")
    st.code(query_select, language="sql")

    st.markdown("**2. Agregação Analítica (`GROUP BY`):**")
    st.code(query_group, language="sql")

    if st.session_state["ultima_execucao"]:
        st.markdown("**3. Persistência (`INSERT`) e Resposta JSON da API REST:**")
        st.code(st.session_state["ultima_execucao"]["query_insert"], language="sql")
        st.json(st.session_state["ultima_execucao"]["meta_rest"])
