# Prerequistes

Postgres DB should be installed and running. 
Username and Password of the DB should be postgres/postgres
create voiceai DB in it

# Steps to run the program

```Powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Tests:

```Powershell
pytest
```