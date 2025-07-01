'''import os
import sqlite3
import yaml
from crewai import Agent, Task, Crew
from crewai.llm import LLM

# Initialize LLM
llm = LLM(
    model="ollama/mistral",
    base_url="http://localhost:11434",
    api_key="ollama",
    temperature=0.3
)

def get_db_schema():
    #conn = sqlite3.connect("database/db.sq")
    #conn = sqlite3.connect("database/sales_invoice.db")
    conn = sqlite3.connect("database/car_sales.sqlite3")

    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    schema = []
    for (table,) in tables:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        column_defs = ", ".join([f"{col[1]} ({col[2]})" for col in columns])
        schema.append(f"Table: {table}\n  Columns: {column_defs}")
    conn.close()
    return "\n".join(schema)

def load_yaml(path):
    with open(path, 'r') as file:
        return yaml.safe_load(file)

def process_user_question(question):
    agents_config = load_yaml("chat_sql_agent/agents.yaml")
    tasks_config = load_yaml("chat_sql_agent/tasks.yaml")

    # Create the Schema Retriever Agent
    schema_agent = Agent(
        role=agents_config['schema_retriever_agent']['role'],
        goal=agents_config['schema_retriever_agent']['goal'],
        backstory=agents_config['schema_retriever_agent']['backstory'],
        llm=llm,
        verbose=agents_config['schema_retriever_agent'].get('verbose', True),
        allow_delegation=agents_config['schema_retriever_agent'].get('allow_delegation', False)
    )

    # Create the SQL Generator Agent
    sql_agent = Agent(
        role=agents_config['sql_generator_agent']['role'],
        goal=agents_config['sql_generator_agent']['goal'],
        backstory=agents_config['sql_generator_agent']['backstory'],
        llm=llm,
        verbose=agents_config['sql_generator_agent'].get('verbose', True),
        allow_delegation=agents_config['sql_generator_agent'].get('allow_delegation', False)
    )

    # Get schema using Python function (since agents can't directly access DB)
    schema = get_db_schema()

    # Create the schema fetch task
    schema_task = Task(
        description=f"""
        {tasks_config['fetch_schema']['description']}
        
        Here is the database schema information:
        {schema}
        
        Please format and present this schema information clearly.
        """,
        agent=schema_agent,
        expected_output=tasks_config['fetch_schema']['expected_output']
    )

    # Create the SQL generation task
    sql_task = Task(
        description=f"""
        {tasks_config['generate_sql']['description']}
        
        USER QUESTION: {question}
        Use the user question and schema information to generate a contextually accurate SQL query.
        Only use date conditions **if the question specifies time range or month**.

        Use the schema information from the previous task to generate an appropriate SQL query.
        
        IMPORTANT SQLite DATE GUIDELINES:
        - Use DATE('now') for current date
        - Use DATE('now', 'start of month') for start of current month
        - Use DATE('now', 'start of month', '+1 month') for start of next month (end of current month)
        - For current month data: WHERE date_column >= DATE('now', 'start of month') AND date_column < DATE('now', 'start of month', '+1 month')
        - For total historical sales: Do not include date conditions.
        - For date patterns: Use LIKE '2025-05%' for May 2025
        - Avoid using 'end of month' - it's not valid in SQLite
        - For last month data: WHERE date_column >= DATE('now', 'start of month', '-1 month') AND date_column < DATE('now', 'start of month')
        - For sales on a specific date: WHERE date_column = 'YYYY-MM-DD'
        
        Return only the SQL query without any explanation.
        """,
        agent=sql_agent,
        expected_output=tasks_config['generate_sql']['expected_output'],
        context=[schema_task]  # This task depends on the schema task
    )

    # Create and execute the crew with both agents
    crew = Crew(
        agents=[schema_agent, sql_agent],
        tasks=[schema_task, sql_task],
        verbose=True
    )

    # Execute the crew and get the result
    result = crew.kickoff()
    #sql_query = str(result).strip()
    sql_query = str(result).strip().strip('`')

    
    return sql_query, execute_query(sql_query)

def execute_query(query):
    try:
        #conn = sqlite3.connect("database/db.sqlite3")
        #conn = sqlite3.connect("database/sales_invoice.db")
        conn = sqlite3.connect("database/car_sales.sqlite3")

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

#working good testing with new db
#new approach
import os
import re
import sqlite3
import yaml
from crewai import Agent, Task, Crew
from crewai.llm import LLM

# Initialize LLM
llm = LLM(
    model="ollama/mistral",
    base_url="http://localhost:11434",
    api_key="ollama",
    temperature=0.3
)

def get_db_schema():
    conn = sqlite3.connect("database/car_sales.sqlite3")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    schema = []
    for (table,) in tables:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        column_defs = "\n  - " + "\n  - ".join([f"{col[1]} ({col[2]})" for col in columns])
        schema.append(f"Table: {table}\nColumns:{column_defs}")
    conn.close()
    return "\n\n".join(schema)

def load_yaml(path):
    with open(path, 'r') as file:
        return yaml.safe_load(file)

def has_time_reference(text):
    patterns = [
        r"\bthis month\b", r"\blast month\b", r"\bthis year\b", r"\blast year\b",
        r"\b\d{4}\b",  # e.g., 2023
        r"\bJanuary|\bFebruary|\bMarch|\bApril|\bMay|\bJune|\bJuly|\bAugust|\bSeptember|\bOctober|\bNovember|\bDecember",
        r"\bon\b\s+\d{4}-\d{2}-\d{2}"  # on YYYY-MM-DD
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)

def process_user_question(question):
    agents_config = load_yaml("chat_sql_agent/agents.yaml")
    tasks_config = load_yaml("chat_sql_agent/tasks.yaml")

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

    schema = get_db_schema()

    schema_task = Task(
        description=f"""
{tasks_config['fetch_schema']['description']}

Here is the database schema information:
{schema}
""",
        agent=schema_agent,
        expected_output=tasks_config['fetch_schema']['expected_output']
    )

    # Only add date filter hints if relevant
    date_guidelines = ""
    if has_time_reference(question):
        date_guidelines = """
IMPORTANT SQLite DATE GUIDELINES:
- Use DATE('now') for current date
- Use DATE('now', 'start of month') for start of current month
- Use DATE('now', 'start of month', '+1 month') for start of next month (end of current month)
- For current month data: WHERE date_column >= DATE('now', 'start of month') AND date_column < DATE('now', 'start of month', '+1 month')
- For total historical sales: Do not include date conditions.
- For date patterns: Use LIKE '2025-05%' for May 2025
- Avoid using 'end of month' - it's not valid in SQLite
- For last month data: WHERE date_column >= DATE('now', 'start of month', '-1 month') AND date_column < DATE('now', 'start of month')
- For sales on a specific date: WHERE date_column = 'YYYY-MM-DD'
"""

    sql_task = Task(
        description=f"""
{tasks_config['generate_sql']['description']}

USER QUESTION: {question}
Use the user question and schema information to generate a contextually accurate SQL query.

{date_guidelines}

Return only the SQL query without any explanation.
""",
        agent=sql_agent,
        expected_output=tasks_config['generate_sql']['expected_output'],
        context=[schema_task]
    )

    crew = Crew(
        agents=[schema_agent, sql_agent],
        tasks=[schema_task, sql_task],
        verbose=True
    )

    result = crew.kickoff()
    sql_query = str(result).strip().strip('`')
    return sql_query, execute_query(sql_query)

def execute_query(query):
    try:
        conn = sqlite3.connect("database/car_sales.sqlite3")
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()
