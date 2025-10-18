import os, certifi
import re
import sqlite3
import yaml
import time
from pathlib import Path
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM

# --- TLS & OpenRouter setup ---
cafile = certifi.where()
os.environ["SSL_CERT_FILE"] = cafile
os.environ["REQUESTS_CA_BUNDLE"] = cafile
os.environ["CURL_CA_BUNDLE"] = cafile
os.environ["LITELLM_SSL_CERT_FILE"] = cafile
os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
os.environ.setdefault("OPENROUTER_HEADERS", '{"HTTP-Referer":"http://localhost","X-Title":"ChatSQL Crew"}')

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise RuntimeError("Missing OPENROUTER_API_KEY in your .env")

os.environ["OPENAI_API_KEY"] = OPENROUTER_API_KEY
os.environ["OPENAI_API_BASE"] = "https://openrouter.ai/api/v1"
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"

try:
    import psycopg2
except Exception:
    psycopg2 = None

try:
    import mysql.connector
except Exception:
    mysql = None
else:
    mysql = mysql

BASE_DIR = Path(__file__).resolve().parent.parent
YAML_DIR = BASE_DIR / "chat_sql_agent"

def load_yaml(name: str):
    with open(YAML_DIR / name, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def has_time_reference(text: str) -> bool:
    patterns = [
        r"\bthis month\b", r"\blast month\b", r"\bthis year\b", r"\blast year\b",
        r"\b\d{4}\b",
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\b",
        r"\bon\s+\d{4}-\d{2}-\d{2}"
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)

_SQL_BLOCK_RE = re.compile(r"```sql(.*?)```", flags=re.DOTALL | re.IGNORECASE)
_SQL_START_RE = re.compile(r"(?is)\b(with|select|insert|update|delete|create|drop|alter)\b.*")

def _strip_sql_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    sql = re.sub(r"(?m)^\s*--.*?$", "", sql)
    return sql

def extract_sql(text: str) -> str:
    if not text:
        return ""
    m = _SQL_BLOCK_RE.search(text)
    if m:
        sql = m.group(1)
    else:
        m2 = _SQL_START_RE.search(text)
        sql = m2.group(0) if m2 else text
    for fence in ("```sql", "```SQL", "```"):
        sql = sql.replace(fence, "")
    sql = sql.strip(" \n\t\r`")
    semi = sql.find(";")
    if semi != -1:
        sql = sql[:semi + 1]
    sql = _strip_sql_comments(sql).strip()
    return sql

# === 🔒 SQL VALIDATION ===
def validate_sql(sql: str) -> tuple[bool, str]:
    """Validate SQL for safety - only allow SELECT queries."""
    if not sql or len(sql.strip()) < 5:
        return False, "❌ Empty or invalid SQL query"
    
    sql_upper = sql.upper().strip()
    dangerous_keywords = ['DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE', 'INSERT', 'UPDATE', 'GRANT', 'REVOKE', 'EXEC', 'EXECUTE']
    
    for keyword in dangerous_keywords:
        if re.search(rf'\b{keyword}\b', sql_upper):
            return False, f"❌ Dangerous operation '{keyword}' not allowed. Only SELECT queries permitted."
    
    if not sql_upper.startswith('SELECT') and not sql_upper.startswith('WITH'):
        return False, "❌ Only SELECT queries are allowed"
    
    if sql.count('JOIN') > 10:
        return False, "❌ Query too complex (maximum 10 JOINs allowed)"
    
    if len(sql) > 5000:
        return False, "❌ Query too long (maximum 5000 characters)"
    
    return True, "✅ Query is safe"

def get_all_tables(db_path: str, db_engine: str) -> list:
    """Retrieve all table names from the database."""
    if db_engine == "sqlite":
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        return tables
    return []

def get_foreign_keys(db_path: str, table_name: str, db_engine: str) -> list:
    """Retrieve foreign key relationships for a table."""
    if db_engine == "sqlite":
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA foreign_key_list({table_name})")
        fks = cursor.fetchall()
        fk_info = []
        for fk in fks:
            fk_info.append({
                "from_table": table_name,
                "from_column": fk[3],
                "to_table": fk[2],
                "to_column": fk[4]
            })
        conn.close()
        return fk_info
    return []

def get_table_schema(db_path: str, table_name: str, db_engine: str):
    """Get schema for a single table."""
    if db_engine == "sqlite":
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        schema = [f"- {col[1]} ({col[2]})" for col in columns]
        conn.close()
        return "\n".join(schema)
    return ""

def get_comprehensive_schema(db_path: str, primary_table: str, db_engine: str) -> str:
    """Get schema for primary table + related tables through FK relationships."""
    all_tables = get_all_tables(db_path, db_engine)
    schema_parts = [f"=== PRIMARY TABLE: {primary_table} ==="]
    primary_schema = get_table_schema(db_path, primary_table, db_engine)
    schema_parts.append(primary_schema)
    
    primary_fks = get_foreign_keys(db_path, primary_table, db_engine)
    
    if primary_fks:
        schema_parts.append("\n--- Foreign Key Relationships ---")
        related_tables = set()
        for fk in primary_fks:
            schema_parts.append(f"• {fk['from_table']}.{fk['from_column']} → {fk['to_table']}.{fk['to_column']}")
            related_tables.add(fk['to_table'])
        
        for related_table in related_tables:
            if related_table in all_tables:
                schema_parts.append(f"\n=== RELATED TABLE: {related_table} ===")
                related_schema = get_table_schema(db_path, related_table, db_engine)
                schema_parts.append(related_schema)
                
                related_fks = get_foreign_keys(db_path, related_table, db_engine)
                if related_fks:
                    schema_parts.append("\n--- Additional Relationships ---")
                    for fk in related_fks:
                        if fk['to_table'] != primary_table:
                            schema_parts.append(f"• {fk['from_table']}.{fk['from_column']} → {fk['to_table']}.{fk['to_column']}")
    
    schema_parts.append(f"\n=== ALL AVAILABLE TABLES ===")
    schema_parts.append(", ".join(all_tables))
    return "\n".join(schema_parts)

def get_date_guidelines(db_engine: str) -> str:
    if db_engine == "sqlite":
        return "SQLite: Use DATE('now'), DATE('now', 'start of month'), etc."
    if db_engine == "postgresql":
        return "PostgreSQL: Use CURRENT_DATE, DATE_TRUNC('month', CURRENT_DATE), etc."
    if db_engine == "mysql":
        return "MySQL: Use CURDATE(), DATE_FORMAT(CURDATE(), '%Y-%m-01'), etc."
    return ""

# === ⚡ QUERY EXECUTION WITH PERFORMANCE TRACKING ===
def execute_query(db_path: str, query: str, db_engine: str):
    """Execute query with performance tracking."""
    start_time = time.time()
    conn = None
    
    try:
        if db_engine == "sqlite":
            conn = sqlite3.connect(db_path)
        elif db_engine == "postgresql":
            if not psycopg2:
                raise ImportError("psycopg2 not installed")
            conn = psycopg2.connect(db_path)
        elif db_engine == "mysql":
            if not mysql:
                raise ImportError("mysql-connector-python not installed")
            conn = mysql.connector.connect(**eval(db_path))
        else:
            raise ValueError("Unsupported database engine")

        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        execution_time = round(time.time() - start_time, 3)
        
        return {
            "data": [dict(zip(columns, row)) for row in rows] if rows else [],
            "execution_time": execution_time,
            "row_count": len(rows),
            "success": True
        }
        
    except Exception as e:
        execution_time = round(time.time() - start_time, 3)
        return {
            "error": str(e),
            "execution_time": execution_time,
            "success": False
        }
    finally:
        if conn:
            conn.close()

llm = LLM(
    model="openrouter/mistralai/mistral-small-3.1-24b-instruct:free",
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
    temperature=0
)

# === 🚀 MAIN PROCESS WITH DEBUG LOGS ===
def process_user_question(db_path, table_name, question, db_engine="sqlite"):
    """Process user question with comprehensive error handling and debug logs."""
    try:
        agents_config = load_yaml("agents.yaml")
        tasks_config = load_yaml("tasks.yaml")

        schema_text = get_comprehensive_schema(db_path, table_name, db_engine)
        date_guidelines = get_date_guidelines(db_engine) if has_time_reference(question) else ""

        # === DEBUG: PRINT SCHEMA ===
        print("\n" + "="*70)
        print("🔍 SCHEMA SENT TO AI:")
        print("="*70)
        print(schema_text)
        print("="*70 + "\n")

        schema_agent = Agent(
            role=agents_config['schema_retriever_agent']['role'],
            goal=agents_config['schema_retriever_agent']['goal'],
            backstory=agents_config['schema_retriever_agent']['backstory'],
            llm=llm,
            verbose=True  # ENABLE LOGS
        )

        sql_agent = Agent(
            role=agents_config['sql_generator_agent']['role'],
            goal=agents_config['sql_generator_agent']['goal'],
            backstory=agents_config['sql_generator_agent']['backstory'],
            llm=llm,
            verbose=True  # ENABLE LOGS
        )

        schema_task = Task(
            description=(
                f"{tasks_config['fetch_schema']['description']}\n\n"
                f"Primary Table: {table_name}\n\n{schema_text}\n\n"
                f"IMPORTANT: Use JOIN when question requires multiple tables."
            ),
            agent=schema_agent,
            expected_output=tasks_config['fetch_schema']['expected_output']
        )

        output_contract = (
            "Output format:\n```sql\n<single SQL statement with semicolon>\n```\n"
            "CRITICAL: If question mentions data from different tables, USE JOIN.\n"
            "Follow FK relationships. Use table aliases. No explanations."
        )

        sql_task = Task(
            description=(
                f"{tasks_config['generate_sql']['description']}\n\n"
                f"DB: {db_engine.upper()}\nPrimary Table: {table_name}\n\n"
                f"Schema:\n{schema_text}\n\n"
                f"Question: {question}\n{date_guidelines}\n\n{output_contract}"
            ),
            agent=sql_agent,
            expected_output=tasks_config['generate_sql']['expected_output'],
            context=[schema_task]
        )

        crew = Crew(agents=[schema_agent, sql_agent], tasks=[schema_task, sql_task], verbose=True)  # ENABLE LOGS
        result = crew.kickoff()

        raw = ""
        try:
            task_out = getattr(sql_task, "output", None)
            raw = getattr(task_out, "raw_output", None) or getattr(task_out, "final_output", None) or ""
        except Exception:
            raw = ""

        if not raw:
            raw = str(result or "")

        sql_query = extract_sql(raw)
        
        # === DEBUG: PRINT GENERATED SQL ===
        print("\n" + "="*70)
        print("🎯 GENERATED SQL:")
        print("="*70)
        print(sql_query)
        print("="*70 + "\n")
        
        if not sql_query:
            return "", {"error": "Failed to generate SQL", "success": False}
        
        # Validate SQL before execution
        is_valid, validation_msg = validate_sql(sql_query)
        if not is_valid:
            print(f"❌ VALIDATION FAILED: {validation_msg}\n")
            return sql_query, {"error": validation_msg, "success": False}
        
        print(f"✅ SQL VALIDATION PASSED\n")
        
        # Execute with performance tracking
        query_result = execute_query(db_path, sql_query, db_engine)
        
        # === DEBUG: PRINT EXECUTION RESULT ===
        if query_result.get("success"):
            print(f"✅ QUERY EXECUTED SUCCESSFULLY")
            print(f"   Rows returned: {query_result.get('row_count', 0)}")
            print(f"   Execution time: {query_result.get('execution_time', 0)}s\n")
        else:
            print(f"❌ QUERY EXECUTION FAILED")
            print(f"   Error: {query_result.get('error', 'Unknown')}\n")
        
        return sql_query, query_result
        
    except Exception as e:
        print(f"\n❌ PROCESSING ERROR: {str(e)}\n")
        return "", {"error": f"Processing error: {str(e)}", "success": False}