# Model Firewall (MAF)

A security system designed to protect AI models from prompt injection attacks and ensure safe data handling.

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