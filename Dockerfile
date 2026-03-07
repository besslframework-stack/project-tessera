FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src/ src/
COPY mcp_server.py main.py ./

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["python", "mcp_server.py"]
