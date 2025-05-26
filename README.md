# Walmart Bill Splitter 🧾

A Streamlit app to parse Walmart PDF receipts, assign items to people using a drag-and-drop Kanban interface, and split costs with summary exports.

## Features

- PDF parsing with `pdfplumber`
- Dynamic Kanban assignment via `streamlit-sortables`
- Add custom items (like tax or delivery)
- Per-person cost summaries with export

## 📦 Requirements

```bash
pip install -r requirements.txt
```

## Run locally

```bash
streamlit run walsplit.py
```
