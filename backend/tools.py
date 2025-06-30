tools = [
    {
        "name": "execute_sql",
        "description": "Run SQL queries on structured data (CSV/Excel)",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "sql": {
                    "type": "STRING",
                    "description": "SQL query to execute on structured data"
                }
            },
            "required": ["sql"]
        }
    },
    {
        "name": "semantic_search",
        "description": "Search unstructured documents (PDF/DOCX)",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "Search query for unstructured documents"
                }
            },
            "required": ["query"]
        }
    }
]
