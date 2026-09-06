Set-Location "$PSScriptRoot\..\ai-service"
$env:AI_HOST = "127.0.0.1"
$env:AI_PORT = "8000"
$env:AI_API_KEY = "change-me-ai-gateway-key"
$env:AI_DATABASE_URL = "postgresql+psycopg://missinglink:missinglink-dev-password@localhost:5432/missinglink"
$env:AI_FALLBACK_ALLOWED = "true"
$env:AI_VECTOR_DIM = "512"
& "$PSScriptRoot\..\ai-service\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000