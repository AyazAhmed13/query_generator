'''
import os
import re
import sqlite3
import yaml
from crewai import Agent, Task, Crew
from crewai.llm import LLM

llm = LLM(
    model="ollama/mistral",
    base_url="http://localhost:11434",
    api_key="ollama",
    temperature=0.3
)

def load_yaml(path):
    with open(path, 'r') as file:
        return yaml.safe_load(file)

def has_time_reference(text):
    patterns = [
        r"\bthis month\b", r"\blast month\b", r"\bthis year\b", r"\blast year\b",
        r"\b\d{4}\b",
        r"\bJanuary|\bFebruary|\bMarch|\bApril|\bMay|\bJune|\bJuly|\bAugust|\bSeptember|\bOctober|\bNovember|\bDecember",
        r"\bon\s+\d{4}-\d{2}-\d{2}"
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)

def get_table_schema(db_path, table_name):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    conn.close()
    return "\n".join([f"- {col[1]} ({col[2]})" for col in columns])

def get_date_guidelines(db_engine):
    if db_engine == "sqlite":
        return """
SQLite DATE GUIDELINES:
- Use DATE('now') for current date
- Use DATE('now', 'start of month') for the first day of the current month
- Use DATE('now', 'start of month', '+1 month') to get the first day of the next month
- Use DATE('now', '-7 days') for last 7 days
- WHERE sale_date >= DATE('now', 'start of month') AND sale_date < DATE('now', 'start of month', '+1 month') for this month's data
- Use strftime('%Y-%m-%d', sale_date) for formatting comparison
- Use BETWEEN for date ranges: WHERE sale_date BETWEEN '2024-01-01' AND '2024-01-31'
- Compare specific dates directly using 'YYYY-MM-DD'
- Use datetime() for timestamps: datetime('now')
"""
    elif db_engine == "postgresql":
        return """
PostgreSQL DATE GUIDELINES:
- Use CURRENT_DATE for today's date
- Use DATE_TRUNC('month', CURRENT_DATE) for start of current month
- Use INTERVAL keyword for ranges: CURRENT_DATE - INTERVAL '7 days'
- Example for this month: sale_date >= DATE_TRUNC('month', CURRENT_DATE) AND sale_date < (DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month')
- Use TO_DATE('YYYY-MM-DD', 'YYYY-MM-DD') for fixed string to date conversion
- TIMESTAMP comparisons supported with BETWEEN
"""
    elif db_engine == "mysql":
        return """
MySQL DATE GUIDELINES:
- Use CURDATE() for current date
- Use DATE_FORMAT(CURDATE(), '%Y-%m-01') for start of current month
- Example for current month: sale_date >= DATE_FORMAT(CURDATE(), '%Y-%m-01') AND sale_date < DATE_FORMAT(DATE_ADD(CURDATE(), INTERVAL 1 MONTH), '%Y-%m-01')
- Use NOW() for current timestamp
- Use STR_TO_DATE('YYYY-MM-DD', '%Y-%m-%d') for conversions
- TIMESTAMPDIFF or DATEDIFF for custom calculations
- Example for past 30 days: sale_date >= CURDATE() - INTERVAL 30 DAY
"""
    else:
        return "\n# ⚠️ No specific date rules provided for selected engine.\n"

def process_user_question(db_path, table_name, question, db_engine="sqlite"):
    agents_config = load_yaml("chat_sql_agent/agents.yaml")
    tasks_config = load_yaml("chat_sql_agent/tasks.yaml")

    schema_text = get_table_schema(db_path, table_name)

    schema_agent = Agent(
        role=agents_config['schema_retriever_agent']['role'],
        goal=agents_config['schema_retriever_agent']['goal'],
        backstory=agents_config['schema_retriever_agent']['backstory'],
        llm=llm,
        verbose=agents_config['schema_retriever_agent'].get('verbose', True),
        allow_delegation=agents_config['schema_retriever_agent'].get('allow_delegation', False)
    )

    sql_agent = Agent(
        role=agents_config['sql_generator_agent']['role'],
        goal=agents_config['sql_generator_agent']['goal'],
        backstory=agents_config['sql_generator_agent']['backstory'],
        llm=llm,
        verbose=agents_config['sql_generator_agent'].get('verbose', True),
        allow_delegation=agents_config['sql_generator_agent'].get('allow_delegation', False)
    )

    schema_task = Task(
        description=f"{tasks_config['fetch_schema']['description']}\n\nSelected Table: {table_name}\n\n{schema_text}",
        agent=schema_agent,
        expected_output=tasks_config['fetch_schema']['expected_output']
    )

    date_guidelines = ""
    if has_time_reference(question):
        date_guidelines = get_date_guidelines(db_engine)

    sql_task = Task(
        description=f"{tasks_config['generate_sql']['description']}\n\nDatabase Engine: {db_engine.upper()}\nTable: {table_name}\nSchema:\n{schema_text}\n\nUSER QUESTION: {question}\n{date_guidelines}\n\nReturn only the SQL query.",
        agent=sql_agent,
        expected_output=tasks_config['generate_sql']['expected_output'],
        context=[schema_task]
    )

    crew = Crew(agents=[schema_agent, sql_agent], tasks=[schema_task, sql_task], verbose=True)
    print("🧠 Final prompt context:")
    print(schema_task.description)
    print(sql_task.description)
    result = crew.kickoff()
    #sql_query = str(result).strip().strip('`')
    sql_query = str(result).strip().strip('`')

# Remove common prefixes like "sql\n" or "```sql"
    if sql_query.lower().startswith("sql"):
        sql_query = sql_query.split('\n', 1)[-1].strip()
    elif sql_query.lower().startswith("```sql"):
        sql_query = sql_query.replace("```sql", "").replace("```", "").strip()

    return sql_query, execute_query(db_path, sql_query)

def execute_query(db_path, query):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()
'''
import os
import re
import sqlite3
import yaml
from dotenv import load_dotenv
from crewai import Agent, Task, Crew
from openai import OpenAI
import psycopg2
import mysql.connector

# === Load environment ===
load_dotenv()

# === CrewAI-compatible LLM Wrapper using OpenRouter + LiteLLM ===
class OpenRouterCrewAILLM:
    def __init__(self, model="mistralai/mistral-7b-instruct:free", api_key=None):
        self.model = model
        self.client = OpenAI(
            api_key=api_key or os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1"
        )

    def invoke(self, messages, **kwargs):
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages
        )
        return response.choices[0].message.content

    def call(self, prompt, **kwargs):
        return self.invoke([{"role": "user", "content": prompt}], **kwargs)

# === Initialize LLM ===
llm = OpenRouterCrewAILLM()

# === Utility Loaders ===
def load_yaml(path):
    with open(path, 'r') as f:
        return yaml.safe_load(f)

def has_time_reference(text):
    patterns = [
        r"\bthis month\b", r"\blast month\b", r"\bthis year\b", r"\blast year\b",
        r"\b\d{4}\b", r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\b",
        r"\bon\s+\d{4}-\d{2}-\d{2}"
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)

# === Schema Fetcher ===
def get_table_schema(db_path, table_name, db_engine):
    if db_engine == "sqlite":
        conn = sqlite3.connect(db_path)
    elif db_engine == "postgresql":
        conn = psycopg2.connect(db_path)
    elif db_engine == "mysql":
        conn = mysql.connector.connect(**eval(db_path))
    else:
        raise ValueError("Unsupported DB engine")

    cursor = conn.cursor()
    if db_engine == "sqlite":
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        schema = [f"- {col[1]} ({col[2]})" for col in columns]
    else:
        cursor.execute(
            f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table_name}'")
        columns = cursor.fetchall()
        schema = [f"- {col[0]} ({col[1]})" for col in columns]

    conn.close()
    return "\n".join(schema)

# === Date Guidelines per Engine ===
def get_date_guidelines(db_engine):
    if db_engine == "sqlite":
        return "SQLite: Use DATE('now'), DATE('now', 'start of month') etc."
    elif db_engine == "postgresql":
        return "PostgreSQL: Use CURRENT_DATE, DATE_TRUNC('month', CURRENT_DATE) etc."
    elif db_engine == "mysql":
        return "MySQL: Use CURDATE(), DATE_FORMAT(CURDATE(), '%Y-%m-01') etc."
    return ""

# === Query Execution ===
def execute_query(db_path, query, db_engine):
    try:
        if db_engine == "sqlite":
            conn = sqlite3.connect(db_path)
        elif db_engine == "postgresql":
            conn = psycopg2.connect(db_path)
        elif db_engine == "mysql":
            conn = mysql.connector.connect(**eval(db_path))
        else:
            raise ValueError("Unsupported database engine")

        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows] if rows else []

    except Exception as e:
        return {"error": str(e)}

    finally:
        if conn:
            conn.close()

# === Main Crew-Orchestrated Flow ===
def process_user_question(db_path, table_name, question, db_engine="sqlite"):
    agents_config = load_yaml("chat_sql_agent/agents.yaml")
    tasks_config = load_yaml("chat_sql_agent/tasks.yaml")

    schema_text = get_table_schema(db_path, table_name, db_engine)
    date_guidelines = get_date_guidelines(db_engine) if has_time_reference(question) else ""

    # Agents
    schema_agent = Agent(
        role=agents_config['schema_retriever_agent']['role'],
        goal=agents_config['schema_retriever_agent']['goal'],
        backstory=agents_config['schema_retriever_agent']['backstory'],
        llm=llm,
        verbose=True
    )

    sql_agent = Agent(
        role=agents_config['sql_generator_agent']['role'],
        goal=agents_config['sql_generator_agent']['goal'],
        backstory=agents_config['sql_generator_agent']['backstory'],
        llm=llm,
        verbose=True
    )

    # Tasks
    schema_task = Task(
        description=f"{tasks_config['fetch_schema']['description']}\n\nTable: {table_name}\n\n{schema_text}",
        agent=schema_agent,
        expected_output=tasks_config['fetch_schema']['expected_output']
    )

    sql_task = Task(
        description=f"{tasks_config['generate_sql']['description']}\n\nDB: {db_engine.upper()}\nTable: {table_name}\n\n{schema_text}\n\nUser: {question}\n{date_guidelines}\n\nReturn only SQL.",
        agent=sql_agent,
        expected_output=tasks_config['generate_sql']['expected_output'],
        context=[schema_task]
    )

    crew = Crew(agents=[schema_agent, sql_agent], tasks=[schema_task, sql_task], verbose=True)
    result = crew.kickoff()

    # Extract clean SQL
    sql_query = str(result).strip().strip('`')
    if sql_query.lower().startswith("sql"):
        sql_query = sql_query.split('\n', 1)[-1].strip()
    elif sql_query.lower().startswith("```sql"):
        sql_query = sql_query.replace("```sql", "").replace("```", "").strip()

    query_result = execute_query(db_path, sql_query, db_engine)
    return sql_query, query_result
