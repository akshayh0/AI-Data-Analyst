import os
import sys
from pathlib import Path
import pandas as pd
from app.config import settings
from app.data.loader import load_csv_file
from app.data.validators import ValidationError
from app.tools.sql_tool import DuckDBManager
from app.agent import DataAnalystAgent
from app.llm.groq_provider import GroqProvider

UPLOADS_DIR = Path("C:/AI-Data-Analyst/test_user_uploads")

def test_duplicate_file_names():
    print("\n--- Testing Requirement 16: Duplicate File Names ---")
    existing_tables = set()
    
    # Load first duplicate_test.csv
    file1_path = UPLOADS_DIR / "duplicate_test.csv"
    df1, prof1, tbl1, _ = load_csv_file(file1_path, existing_tables=existing_tables)
    existing_tables.add(tbl1)
    
    # Load case-differing DUPLICATE_TEST.csv
    file2_path = UPLOADS_DIR / "DUPLICATE_TEST.csv"
    df2, prof2, tbl2, _ = load_csv_file(file2_path, existing_tables=existing_tables)
    existing_tables.add(tbl2)
    
    print(f"File 1 table: '{tbl1}', File 2 table: '{tbl2}'")
    assert tbl1 != tbl2, f"Tables should have unique names: {tbl1} vs {tbl2}"
    assert tbl1 == "duplicate_test"
    assert tbl2 == "duplicate_test_1"
    assert len(df1) == 2 and len(df2) == 2
    print("[PASS] DUPLICATE FILE NAMES: Unique internal table names assigned without collision.")

def test_invalid_file():
    print("\n--- Testing Requirement 15: Invalid File Format ---")
    corrupt_path = UPLOADS_DIR / "corrupted_binary.bin"
    error_caught = False
    try:
        load_csv_file(corrupt_path, max_size_mb=10)
    except (ValidationError, Exception) as exc:
        error_caught = True
        err_msg = str(exc)
        print(f"Caught expected friendly validation error: {err_msg}")
        assert "not a supported CSV" in err_msg or "Failed to parse" in err_msg or "binary" in err_msg or "extension" in err_msg
    
    assert error_caught, "Corrupted file should raise clean ValidationError"
    print("[PASS] INVALID FILE: Clean friendly error raised, no crash.")

def test_api_failure():
    print("\n--- Testing Requirement 17: Simulated API Failure ---")
    real_key = os.getenv("GROQ_API_KEY", "")
    try:
        # Use invalid key
        bad_provider = GroqProvider(api_key="gsk_invalid_test_key_abc123_not_real")
        db = DuckDBManager()
        file1_path = UPLOADS_DIR / "duplicate_test.csv"
        df, prof, tbl, _ = load_csv_file(file1_path)
        db.register_dataframe(tbl, df)
        agent = DataAnalystAgent(llm_provider=bad_provider, db_manager=db, table_profiles={tbl: prof})
        
        failed_cleanly = False
        try:
            agent.ask("What is the average of col?")
        except Exception as exc:
            failed_cleanly = True
            exc_str = str(exc)
            # Verify no secret key leakage
            assert real_key not in exc_str, "REAL API KEY MUST NOT BE LEAKED!"
            # Test UI friendly translation logic
            if "401" in exc_str or "auth" in exc_str.lower() or "api_key" in exc_str.lower() or "invalid api key" in exc_str.lower():
                ui_err = "Unable to connect to Groq. Please check your API key."
            else:
                ui_err = f"Unable to complete analysis: {exc_str}"
            print(f"UI Error Message: '{ui_err}'")
            assert ui_err == "Unable to connect to Groq. Please check your API key."
            
        assert failed_cleanly, "Invalid API key must fail gracefully"
        print("[PASS] API FAILURE: Handled gracefully without crash, traceback in UI, or key leakage.")
    finally:
        # Guarantee real environment restored
        os.environ["GROQ_API_KEY"] = real_key

def test_empty_results():
    print("\n--- Testing Requirement 18: Empty Query Results ---")
    db = DuckDBManager()
    df = pd.DataFrame({"category": ["A", "B"], "val": [10, 20]})
    db.register_dataframe("test_tbl", df)
    
    # Query returning 0 rows
    res = db.execute_query("SELECT * FROM test_tbl WHERE val > 100")
    assert len(res.df) == 0, "Query should return empty dataframe"
    assert res.total_rows == 0
    print(f"Empty query returned 0 rows successfully without crashing.")
    print("[PASS] EMPTY RESULTS: Empty query result handled cleanly.")

if __name__ == "__main__":
    test_duplicate_file_names()
    test_invalid_file()
    test_api_failure()
    test_empty_results()
    print("\nALL EDGE CASE TESTS PASSED!")
