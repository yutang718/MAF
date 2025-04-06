# MAF (LLM Model Application Firewall)

A comprehensive security framework for LLM applications, providing content filtering, compliance checking, and prompt safety analysis. MAF acts as a protective layer between your application and LLM services, ensuring safe and compliant interactions.

## Core Functions

1. **Content Security**
   - PII (Personal Identifiable Information) Detection and Masking
   - Prompt Injection Detection
   - Input/Output Sanitization

2. **Compliance Checking**
   - Islamic Content Compliance
   - Cultural Sensitivity Analysis
   - Content Policy Enforcement

3. **LLM Safety**
   - Prompt Safety Verification
   - Response Validation
   - Model Output Filtering

## Features

- Prompt Injection Detection
- User Input Sanitization
- Return Value Validation
- Semantic Analysis
- Log Management
- Web-based Management Interface

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
Create a `.env` file with the following variables:
```
HUGGINGFACE_TOKEN=your_token_here
SECRET_KEY=your_secret_key_here
```

4. Run the application:
```bash
uvicorn app.main:app --reload
```

## Project Structure

```
maf/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── core/
│   │   ├── config.py        # Configuration settings
│   │   ├── security.py      # Security utilities
│   │   └── logging.py       # Logging configuration
│   ├── models/
│   │   └── schemas.py       # Pydantic models
│   ├── services/
│   │   ├── prompt_checker.py    # Prompt injection detection
│   │   ├── sanitizer.py         # Input sanitization
│   │   └── validator.py         # Return value validation
│   └── api/
│       └── endpoints.py     # API endpoints
├── tests/                   # Test files
├── logs/                    # Application logs
└── requirements.txt         # Project dependencies
```

## API Documentation

Once the application is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Security Features

1. **Prompt Injection Detection**
   - Analyzes user input for potential injection attacks
   - Uses semantic analysis to identify malicious patterns

2. **Input Sanitization**
   - Automatically removes sensitive information
   - Logs sanitization actions for audit purposes

3. **Return Value Validation**
   - Ensures output complies with security rules
   - Prevents sensitive data leakage

4. **Logging**
   - Comprehensive logging of all security-related events
   - File-based storage for audit trails

## Running the Application

1. Start the Backend Server:
```bash
./server.sh
# or
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

2. Start the Frontend Application:
```bash
cd frontend
streamlit run main.py
```

## Frontend Features

1. **Prompt Safety Checking**
   - Real-time prompt analysis
   - Safety score visualization
   - Detailed threat analysis
   - Model selection options

2. **PII Detection Interface**
   - Interactive text analysis
   - PII highlighting and masking
   - Rule configuration management
   - Detection statistics

3. **Islamic Compliance System**
   - Comparative analysis view
   - Rule management interface
   - Multi-language support
   - Compliance testing tools

## Frontend Access

- Main application: http://localhost:8501
- Prompt checking: http://localhost:8501/prompt_checking
- PII filtering: http://localhost:8501/pii_filtering
- Islamic rules: http://localhost:8501/islamic_rules 