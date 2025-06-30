import google.generativeai as genai
import re
from backend.config import GEMINI_API_KEY
from backend.tools import tools

genai.configure(api_key=GEMINI_API_KEY)

def classify_query(query: str) -> str:
    sql_keywords = ["show", "list", "select", "count", "sum", "filter", "where", "rows", "columns"]
    semantic_keywords = ["summarize", "summary", "explain", "describe", "what is", "meaning of", "overview"]
    
    query_lower = query.lower()
    
    if any(kw in query_lower for kw in sql_keywords):
        return "SQL"
    if any(kw in query_lower for kw in semantic_keywords):
        return "GENERAL"
    
    response = genai.GenerativeModel('gemini-1.5-flash').generate_content(
        f"Classify as SQL or GENERAL: {query}\nReturn only the classification."
    )
    return "SQL" if "SQL" in response.text.upper() else "GENERAL"

def route_query_with_tools(query: str, file_type: str, columns: list = None):
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = (
        f"You are querying a {file_type} file. "
        f"User query: {query}\n\n"
        "Decide which tool to use based on:\n"
        "- Use execute_sql for quantitative queries on structured data\n"
        "- Use semantic_search for content questions on documents"
    )
    
    if file_type == "structured" and columns:
        prompt += f"\nAvailable columns: {columns}"
    
    response = model.generate_content(prompt, tools=tools)
    
    if response.candidates and response.candidates[0].content.parts:
        part = response.candidates[0].content.parts[0]
        if hasattr(part, 'function_call'):
            return {
                "tool_name": part.function_call.name,
                "arguments": part.function_call.args
            }
    return None

def generate_sql(query: str, columns: list) -> str:
    # Improved prompt to prevent markdown
    prompt = (
        f"Generate ONLY the SQLite SELECT query for columns {columns} to answer: {query}\n"
        "Return ONLY the SQL query without markdown, explanations, or additional text."
    )
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(prompt)
    raw_sql = response.text.strip()
    return clean_sql(raw_sql)

def clean_sql(raw_sql: str) -> str:
    """Remove markdown, explanations, and invalid syntax from SQL"""
    # Remove markdown code blocks (``````)
    if re.search(r'``````', raw_sql, re.DOTALL):
        raw_sql = re.sub(r'``````', '', raw_sql, flags=re.DOTALL)
    
    # Remove standalone ```
    raw_sql = raw_sql.replace('```', '')
    
    # Remove line comments (-- ...)
    raw_sql = re.sub(r'--.*$', '', raw_sql, flags=re.MULTILINE)
    
    # Remove non-SQL text (like "Replace ...")
    sql_lines = []
    for line in raw_sql.split('\n'):
        if re.match(r'^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP)', line, re.IGNORECASE):
            sql_lines.append(line)
        elif re.match(r'^\s*[A-Za-z]', line):  # Remove explanatory lines
            continue
    
    clean_sql = ' '.join(sql_lines).strip()
    
    # Remove trailing semicolons
    return clean_sql.rstrip(';').strip()

def generate_answer(query: str, context: list) -> str:
    response = genai.GenerativeModel('gemini-1.5-flash').generate_content(
        f"Answer using this context: {context}\nQuestion: {query}"
    )
    return response.text
