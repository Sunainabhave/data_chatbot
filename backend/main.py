from fastapi import FastAPI, UploadFile, File, HTTPException
from pathlib import Path
import uuid
import pandas as pd
import traceback
import math
from backend.data_handler import DataHandler
from backend.query_router import classify_query, generate_sql, generate_answer, route_query_with_tools  # Added import

app = FastAPI()
handler = DataHandler()

@app.get("/")
async def root():
    return {"message": "Backend is running!"}

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    allowed_structured = {".csv", ".xls", ".xlsx"}
    allowed_unstructured = {".pdf", ".docx"}
    file_ext = Path(file.filename).suffix.lower()

    try:
        # Validate file type
        if file_ext not in allowed_structured | allowed_unstructured:
            raise HTTPException(400, f"Unsupported file type: {file_ext}")
        
        file_id = str(uuid.uuid4())
        file_path = Path("uploads") / f"{file_id}_{file.filename}"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save file
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
            print(f"📁 Saved file: {file_path}")

        # Process file
        if file_ext in allowed_structured:
            print("🔢 Processing structured file")
            handler.save_structured(file_path, file_id)
            file_type = "structured"
        else:  # Unstructured
            print("📄 Processing unstructured file")
            handler.process_unstructured(file_path, file_id)
            file_type = "unstructured"
            
        return {"file_id": file_id, "file_type": file_type}
    
    except Exception as e:
        print("🔥 UPLOAD ERROR:", e)
        traceback.print_exc()
        raise HTTPException(500, f"Upload failed: {str(e)}")

@app.post("/ask")
async def ask_question(query: str, file_id: str, file_type: str):
    try:
        # Prepare columns for structured files
        columns = None
        if file_type == "structured":
            columns = pd.read_sql(f'PRAGMA table_info("{file_id}")', handler.conn)["name"].tolist()
        
        # First try tool calling
        tool_call = route_query_with_tools(query, file_type, columns)
        
        if tool_call:
            tool_name = tool_call["tool_name"]
            args = tool_call["arguments"]
            
            if tool_name == "execute_sql":
                sql = args.get("sql", "")
                if not sql:  # Fallback if Gemini didn't generate SQL
                    sql = generate_sql(query, columns)
                result = handler.get_sql_result(file_id, sql)
                return {
                    "type": "sql",
                    "result": clean_nans(result),
                    "sql": sql
                }
                
            elif tool_name == "semantic_search":
                search_query = args.get("query", query)
                context = handler.semantic_search(search_query, file_id)
                answer = generate_answer(query, context)
                return {
                    "type": "text",
                    "answer": answer,
                    "context": context
                }
        
        # Fallback to original classification if tool call fails
        classification = classify_query(query)
        
        if classification == "SQL":
            # Get table columns
            if not columns:  # Ensure columns are loaded
                columns = pd.read_sql(f'PRAGMA table_info("{file_id}")', handler.conn)["name"].tolist()
            
            # Generate SQL
            sql = generate_sql(query, columns)
            print(f"🔍 Generated SQL: {sql}")
            
            # Execute query and clean NaN values
            result = handler.get_sql_result(file_id, sql)
            cleaned_result = clean_nans(result)
            
            return {
                "type": "sql",
                "result": cleaned_result,
                "sql": sql
            }
            
        else:  # GENERAL (semantic) query
            if file_type != "unstructured":
                raise HTTPException(400, "❌ Semantic questions are only supported for unstructured files like PDF or DOCX.")
            
            # Perform semantic search
            context = handler.semantic_search(query, file_id)
            print(f"🔍 Retrieved context: {context}")
            
            # Generate answer using context
            answer = generate_answer(query, context)
            return {
                "type": "text",
                "answer": answer,
                "context": context
            }
            
    except Exception as e:
        print("🔥 ASK ERROR:", e)
        traceback.print_exc()
        raise HTTPException(500, str(e))

def clean_nans(obj):
    """Recursively replace NaN and inf values with None for JSON serialization."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, dict):
        return {k: clean_nans(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nans(item) for item in obj]
    return obj
