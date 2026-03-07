# Sample Data

Place sample markdown, CSV, or session log files here for testing the ingestion pipeline.

The system expects:
- **Markdown files** (.md): PRDs, decision logs, general documents
- **CSV files** (.csv): Event taxonomies, data mapping tables
- **Session logs** (.md): Claude session summaries (with metadata/completed/changes sections)

## Quick test

```bash
# Ingest sample data
python main.py ingest --path data/sample/

# Query
python main.py query "What projects exist in the sample data?"
```
