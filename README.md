# RAG_MindMap_Generation

A multimedia mind map generation system using Retrieval Augmented Generation (RAG).

The frontend UI is based on an open-source Vue3 mind map project:  
https://github.com/huangyuanyin/hyy-vue3-mindMap

My main contributions focus on backend architecture, multimedia processing pipelines, and RAG-based content generation.

---

# Demo Video

https://www.canva.com/design/DAGWnvrYu4A/OeNx8q4rlMauG9oRV4unHw/watch

---

# Poster

![Poster](Poster.JPG)

---

# Features

- PDF document parsing
- MP3 audio transcription and processing
- OCR image parsing
- YouTube video parsing
- RAG-based markdown generation
- Firebase cloud storage integration
- Mind map generation
- Google Sign-In authentication
- File management system
- Timestamp-linked YouTube navigation

---

# System Workflow

```text
PDF / MP3 / Image / YouTube URL
                ↓
        Content Extraction
                ↓
     OCR / Whisper Processing
                ↓
       RAG-based Generation
                ↓
        Markdown Generation
                ↓
       MindMap Visualization
```

---

# Tech Stack

## Backend

- Python
- Flask
- Firebase
- Firestore
- Firebase Storage

## AI / Processing

- Retrieval Augmented Generation (RAG)
- Whisper
- OCR
- YouTube Data API
- Markdown generation
- FAISS Vector Store
- LangChain

## Frontend

- Vue3
- MindMap visualization

---

# My Contributions

- Flask backend development
- Firebase integration
- Multimedia processing pipeline implementation
- PDF / MP3 / OCR parsing
- YouTube content extraction
- Timestamp-linked YouTube navigation
- RAG-based markdown generation
- AI-powered knowledge structure generation

---

# Notes

- Firebase credentials are excluded from the repository.
- API keys and sensitive information are managed through environment variables.
- Frontend visualization is adapted from an open-source Vue3 mind map project.
- Conducted in 2023 finished in 2024
