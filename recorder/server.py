#!/usr/bin/env python3
"""Dependency-free localhost server for the Vāgdhenu recording studio."""

from __future__ import annotations

import argparse
import base64
import csv
import json
import re
import shutil
import tempfile
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
DEFAULTS = ROOT / "defaults"
DATA_ROOT = ROOT.parent / "recorder_data"
SAFE_SLUG = re.compile(r"[^a-z0-9]+")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str) -> str:
    slug = SAFE_SLUG.sub("-", value.lower()).strip("-")
    return slug[:80] or "recording-project"


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.projects = self.root / "projects"
        self.projects.mkdir(parents=True, exist_ok=True)
        self.ensure_defaults()

    def ensure_defaults(self) -> None:
        default = DEFAULTS / "narayaneeyam.json"
        target = self.projects / "narayaneeyam" / "project.json"
        if default.exists() and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(default, target)
            atomic_json(target.parent / "progress.json", {})

    def project_dir(self, project: str) -> Path:
        safe = slugify(project)
        path = (self.projects / safe).resolve()
        if self.projects not in path.parents:
            raise ValueError("invalid project")
        return path

    def load_project(self, project: str) -> dict:
        path = self.project_dir(project) / "project.json"
        if not path.exists():
            raise FileNotFoundError(project)
        return json.loads(path.read_text(encoding="utf-8"))

    def load_progress(self, project: str) -> dict:
        path = self.project_dir(project) / "progress.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def list_projects(self) -> list[dict]:
        projects = []
        for path in sorted(self.projects.glob("*/project.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            progress = self.load_progress(payload["id"])
            accepted = sum(1 for value in progress.values() if value.get("status") == "accepted")
            projects.append(
                {
                    "id": payload["id"],
                    "name": payload["name"],
                    "description": payload.get("description", ""),
                    "total": len(payload.get("items", [])),
                    "accepted": accepted,
                }
            )
        return projects

    def bootstrap(self, project: Optional[str]) -> dict:
        projects = self.list_projects()
        if not projects:
            raise RuntimeError("no recording projects found")
        project_id = project if project and any(p["id"] == project for p in projects) else projects[0]["id"]
        payload = self.load_project(project_id)
        progress = self.load_progress(project_id)
        for item in payload["items"]:
            recording = progress.get(item["id"])
            if recording:
                recording["audio_url"] = f"/recordings/{project_id}/{recording['audio_path']}"
            item["recording"] = recording
        return {"projects": projects, "project": payload}

    def import_script(self, name: str, text: str) -> dict:
        project_id = slugify(name)
        if not text.strip():
            raise ValueError("script is empty")
        lines = []
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            lines.append(line)
        if not lines:
            raise ValueError("no quarter lines found")
        items = []
        for index, line in enumerate(lines, start=1):
            verse = (index - 1) // 4 + 1
            quarter = (index - 1) % 4 + 1
            items.append(
                {
                    "id": f"{project_id}_{verse:04d}_q{quarter}",
                    "project": project_id,
                    "collection": name.strip(),
                    "verse": verse,
                    "quarter": quarter,
                    "text": line,
                    "meter": "",
                    "syllables": 0,
                    "split_exact": True,
                    "source": "imported-quarter-per-line",
                }
            )
        directory = self.project_dir(project_id)
        if (directory / "project.json").exists():
            raise ValueError(f"a project named '{project_id}' already exists")
        payload = {
            "id": project_id,
            "name": name.strip(),
            "description": f"Imported {len(items)} quarter lines.",
            "language": "sa-Deva",
            "created_at": utc_now(),
            "items": items,
        }
        atomic_json(directory / "project.json", payload)
        atomic_json(directory / "progress.json", {})
        return payload

    def save_recording(self, payload: dict) -> dict:
        project = self.load_project(payload["project"])
        item = next((value for value in project["items"] if value["id"] == payload["item_id"]), None)
        if item is None:
            raise ValueError("unknown script item")
        encoded = payload.get("audio_base64", "")
        audio = base64.b64decode(encoded, validate=True)
        if len(audio) < 44 or len(audio) > 30 * 1024 * 1024 or audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
            raise ValueError("invalid or oversized WAV")
        item_dir = self.project_dir(project["id"]) / "audio" / item["id"]
        item_dir.mkdir(parents=True, exist_ok=True)
        takes = sorted(item_dir.glob("take_*.wav"))
        take_number = max([int(path.stem.split("_")[-1]) for path in takes] or [0]) + 1
        wav_name = f"take_{take_number:03d}.wav"
        wav_path = item_dir / wav_name
        wav_path.write_bytes(audio)
        record = {
            "project": project["id"],
            "item_id": item["id"],
            "take": take_number,
            "status": "accepted" if payload.get("accepted", True) else "recorded",
            "recorded_at": utc_now(),
            "audio_path": str(wav_path.relative_to(self.project_dir(project["id"]))),
            "text": item["text"],
            "collection": item.get("collection", project["name"]),
            "dasakam": item.get("dasakam"),
            "verse": item.get("verse"),
            "half": item.get("half"),
            "quarter": item.get("quarter"),
            "meter": item.get("meter", ""),
            "syllables": item.get("syllables", 0),
            "microphone": payload.get("microphone", ""),
            "notes": payload.get("notes", "").strip(),
            "metrics": payload.get("metrics", {}),
            "app_version": 1,
        }
        atomic_json(item_dir / f"take_{take_number:03d}.json", record)
        progress = self.load_progress(project["id"])
        progress[item["id"]] = record
        atomic_json(self.project_dir(project["id"]) / "progress.json", progress)
        self.write_manifests(project, progress)
        record["audio_url"] = f"/recordings/{project['id']}/{record['audio_path']}"
        return record

    def set_status(self, payload: dict) -> dict:
        project_id = payload["project"]
        progress = self.load_progress(project_id)
        item_id = payload["item_id"]
        if item_id not in progress:
            raise ValueError("item has no recording")
        status = payload.get("status")
        if status not in {"accepted", "recorded", "rejected", "skipped"}:
            raise ValueError("invalid status")
        progress[item_id]["status"] = status
        progress[item_id]["notes"] = payload.get("notes", progress[item_id].get("notes", "")).strip()
        atomic_json(self.project_dir(project_id) / "progress.json", progress)
        self.write_manifests(self.load_project(project_id), progress)
        return progress[item_id]

    def write_manifests(self, project: dict, progress: dict) -> None:
        directory = self.project_dir(project["id"])
        accepted = [progress[item["id"]] for item in project["items"] if progress.get(item["id"], {}).get("status") == "accepted"]
        jsonl = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in accepted)
        (directory / "metadata.jsonl").write_text(jsonl, encoding="utf-8")
        fields = [
            "item_id", "audio_path", "text", "collection", "dasakam", "verse", "half", "quarter",
            "meter", "syllables", "take", "recorded_at", "microphone", "notes", "duration_s",
            "sample_rate", "peak_dbfs", "rms_dbfs", "clipped_fraction", "silence_fraction",
        ]
        with (directory / "metadata.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in accepted:
                flat = {key: row.get(key, "") for key in fields}
                for key in fields:
                    if key in row.get("metrics", {}):
                        flat[key] = row["metrics"][key]
                writer.writerow(flat)


STORE: Store


class Handler(SimpleHTTPRequestHandler):
    server_version = "VagdhenuRecorder/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def send_json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 45 * 1024 * 1024:
            raise ValueError("request too large")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/bootstrap":
            query = dict(part.split("=", 1) for part in parsed.query.split("&") if "=" in part)
            try:
                self.send_json(STORE.bootstrap(query.get("project")))
            except Exception as exc:
                self.send_json({"error": str(exc)}, 500)
            return
        if parsed.path.startswith("/recordings/"):
            parts = unquote(parsed.path).strip("/").split("/", 2)
            if len(parts) != 3:
                self.send_error(404)
                return
            try:
                project_dir = STORE.project_dir(parts[1])
                target = (project_dir / parts[2]).resolve()
                if project_dir not in target.parents or not target.is_file():
                    raise FileNotFoundError
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(target.stat().st_size))
                self.end_headers()
                with target.open("rb") as handle:
                    shutil.copyfileobj(handle, self.wfile)
            except (FileNotFoundError, ValueError):
                self.send_error(404)
            return
        super().do_GET()

    def do_POST(self) -> None:
        try:
            payload = self.read_json()
            if self.path == "/api/import":
                result = STORE.import_script(payload.get("name", ""), payload.get("text", ""))
                self.send_json(result, HTTPStatus.CREATED)
            elif self.path == "/api/recordings":
                self.send_json(STORE.save_recording(payload), HTTPStatus.CREATED)
            elif self.path == "/api/status":
                self.send_json(STORE.set_status(payload))
            else:
                self.send_error(404)
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, 400)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", type=Path, default=DATA_ROOT)
    args = parser.parse_args()
    global STORE
    STORE = Store(args.data_dir)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Vāgdhenu Recorder: http://{args.host}:{args.port}")
    print(f"Dataset directory: {STORE.root}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
