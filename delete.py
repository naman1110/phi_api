import psycopg2
import os
import json



# PostgreSQL connection details
connection_details = "dbname='ai' user='ai' host='localhost' password='ai' port='5532'"

# Function to delete rows by matching column "name" with the given variable
def delete_rows_by_name(kb_name, name_value):
    # Connect to PostgreSQL
    conn = psycopg2.connect(connection_details)
    cur = conn.cursor()
    
    # SQL query to delete rows with parameterized input
    sql_query = f"""DELETE FROM groq_rag_documents_openai_{kb_name} WHERE name = %s"""
    
    try:
        # Execute the query with parameterized input
        
        cur.execute(sql_query, (name_value,))
        # Commit the changes
        conn.commit()
        response = {
            "message": f"File with name = '{name_value}' has been deleted.",
            "status": 200
        }
    except Exception as e:
        response = {
            "error": str(e),
            "status": 500
        }
    finally:
        # Close the connection
        cur.close()
        conn.close()
    return json.dumps(response)

# Example usage
# name_to_delete = "2405"
# response = delete_rows_by_name("test1", name_to_delete)
# print(response)
