import sqlite3
from pathlib import Path
import pandas as pd

DB_PATH = Path("financeiro.db")

SEED_DATA = [
    ("Amazon Web Services (AWS)", "Infraestrutura Cloud", 489.90, "2026-11-10", "Pago", "Fatura mensal servidor EC2 e RDS"),
    ("OpenAI / APIs de IA", "Inteligência Artificial", 165.50, "2026-11-12", "Pago", "Consumo de tokens ambiente de homologação"),
    ("GitHub Enterprise", "Ferramentas Dev", 112.00, "2026-11-15", "Pago", "Assinatura repositórios e Actions"),
    ("Consultoria Contábil Silva", "Serviços", 850.00, "2026-11-20", "Pendente", "Honorários mensais contabilidade"),
    ("Datadog Monitoring", "Infraestrutura Cloud", 310.00, "2026-11-22", "Pendente", "Observabilidade e logs de produção"),
    ("Figma Organization", "Design & Produto", 95.00, "2026-11-25", "Pendente", "Licença de prototipação UI/UX"),
    ("Google Workspace", "Ferramentas Dev", 144.00, "2026-11-05", "Pago", "E-mails corporativos e Drive"),
    ("Twilio Mensageria", "Comunicação", 275.40, "2026-11-28", "Pendente", "Disparos SMS e API WhatsApp"),
]


def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS lancamentos_financeiros (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fornecedor TEXT NOT NULL,
        categoria TEXT NOT NULL,
        valor REAL NOT NULL,
        vencimento TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pendente',
        descricao TEXT,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(ddl)
        cursor.execute("SELECT COUNT(*) FROM lancamentos_financeiros;")
        total = cursor.fetchone()[0]
        if total == 0:
            cursor.executemany(
                """
                INSERT INTO lancamentos_financeiros
                (fornecedor, categoria, valor, vencimento, status, descricao)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                SEED_DATA,
            )
        conn.commit()


def inserir_lancamento(dados: dict) -> tuple[int, str]:
    query = """
    INSERT INTO lancamentos_financeiros
    (fornecedor, categoria, valor, vencimento, status, descricao)
    VALUES (?, ?, ?, ?, ?, ?);
    """
    params = (
        dados.get("fornecedor", "Não identificado"),
        dados.get("categoria", "Outros"),
        float(dados.get("valor", 0.0)),
        dados.get("vencimento", "2026-11-30"),
        dados.get("status", "Pendente"),
        dados.get("descricao", ""),
    )
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor.lastrowid, query.strip()


def listar_lancamentos(categoria: str = "Todas", status: str = "Todos") -> tuple[pd.DataFrame, str]:
    condicoes = []
    params = []

    if categoria != "Todas":
        condicoes.append("categoria = ?")
        params.append(categoria)
    if status != "Todos":
        condicoes.append("status = ?")
        params.append(status)

    where_clause = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""
    query = f"""
    SELECT id, fornecedor, categoria, valor, vencimento, status, descricao
    FROM lancamentos_financeiros
    {where_clause}
    ORDER BY vencimento ASC, id DESC;
    """.strip()

    with get_connection() as conn:
        df = pd.read_sql_query(query, conn, params=params)
    return df, query


def resumo_por_categoria() -> tuple[pd.DataFrame, str]:
    query = """
    SELECT
        categoria AS Categoria,
        COUNT(*) AS Qtd_Documentos,
        ROUND(SUM(valor), 2) AS Total_BRL
    FROM lancamentos_financeiros
    GROUP BY categoria
    ORDER BY Total_BRL DESC;
    """.strip()

    with get_connection() as conn:
        df = pd.read_sql_query(query, conn)
    return df, query


def atualizar_status(lancamento_id: int, novo_status: str) -> str:
    query = "UPDATE lancamentos_financeiros SET status = ? WHERE id = ?;"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (novo_status, lancamento_id))
        conn.commit()
    return query


def excluir_lancamento(lancamento_id: int) -> str:
    query = "DELETE FROM lancamentos_financeiros WHERE id = ?;"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (lancamento_id,))
        conn.commit()
    return query
