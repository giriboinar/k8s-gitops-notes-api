"""Notes API — a small FastAPI app built to practise Kubernetes + GitOps.

It keeps an in-memory collection of short notes (title, body, tags) and
exposes a health endpoint and Prometheus metrics. It is intentionally
stateless: restarting the pod clears the notes, which is fine for a demo
and keeps the deployment simple (no database to manage).
"""
import uuid

from fastapi import FastAPI, HTTPException
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, Counter, Gauge, generate_latest
from pydantic import BaseModel, Field
from starlette.responses import Response

app = FastAPI(title="Notes API", version="1.0.0")

notes: dict[str, dict] = {}
notes_created_total = Counter("notes_created_total", "Total notes created")
notes_total = Gauge("notes_total", "Notes currently stored")


class NoteIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=5000)
    tags: list[str] = []


class NoteOut(NoteIn):
    id: str


@app.get("/")
def root():
    return {"service": "Notes API", "version": "1.0.0", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/notes", response_model=list[NoteOut])
def list_notes(tag: str | None = None):
    items = list(notes.values())
    if tag is not None:
        items = [n for n in items if tag in n["tags"]]
    return items


@app.post("/api/notes", response_model=NoteOut, status_code=201)
def create_note(note: NoteIn):
    note_id = str(uuid.uuid4())
    record = {"id": note_id, **note.model_dump()}
    notes[note_id] = record
    notes_created_total.inc()
    notes_total.set(len(notes))
    return record


@app.get("/api/notes/{note_id}", response_model=NoteOut)
def get_note(note_id: str):
    if note_id not in notes:
        raise HTTPException(status_code=404, detail="Note not found")
    return notes[note_id]


@app.delete("/api/notes/{note_id}", status_code=204)
def delete_note(note_id: str):
    if note_id not in notes:
        raise HTTPException(status_code=404, detail="Note not found")
    del notes[note_id]
    notes_total.set(len(notes))
    return None
