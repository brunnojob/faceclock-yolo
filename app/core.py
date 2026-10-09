from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import os
import sqlite3
import struct
import time
import uuid
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def normalize(vector):
    values = tuple(float(value) for value in vector)
    if len(values) != 512 or any(not math.isfinite(value) for value in values):
        raise ValueError("a finite 512-dimensional embedding is required")
    norm = math.sqrt(sum(value * value for value in values))
    if norm < 1e-9:
        raise ValueError("zero embedding")
    return tuple(value / norm for value in values)


class AttendanceStore:
    def __init__(self, path, encryption_key, audit_key):
        if len(encryption_key) != 32 or len(audit_key) < 32:
            raise ValueError("256-bit encryption and audit keys required")
        self.cipher = AESGCM(encryption_key)
        self.audit_key = audit_key
        self.db = sqlite3.connect(path, timeout=15, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS employees(id TEXT PRIMARY KEY,name TEXT NOT NULL,consent_at REAL NOT NULL,active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS templates(employee_id TEXT NOT NULL,nonce BLOB NOT NULL,ciphertext BLOB NOT NULL,FOREIGN KEY(employee_id) REFERENCES employees(id));
        CREATE TABLE IF NOT EXISTS reviews(id TEXT PRIMARY KEY,employee_id TEXT,score REAL NOT NULL,action TEXT NOT NULL,camera TEXT NOT NULL,created_at REAL NOT NULL,resolved INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS attendance(sequence INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT UNIQUE NOT NULL,payload TEXT NOT NULL,previous_mac TEXT NOT NULL,mac TEXT NOT NULL);
        """)
        self.db.execute("PRAGMA foreign_keys=ON")

    def enroll(self, employee_id, name, embeddings, consent):
        if (
            consent is not True
            or not employee_id
            or len(employee_id) > 80
            or not name
            or len(name) > 120
        ):
            raise ValueError("identity and explicit consent required")
        vectors = [normalize(vector) for vector in embeddings]
        if not 3 <= len(vectors) <= 8:
            raise ValueError("three to eight templates required")
        with self.db:
            self.db.execute(
                "INSERT INTO employees(id,name,consent_at) VALUES (?,?,?)",
                (employee_id, name, time.time()),
            )
            for vector in vectors:
                nonce = os.urandom(12)
                packed = struct.pack("<512f", *vector)
                ciphertext = self.cipher.encrypt(nonce, packed, employee_id.encode())
                self.db.execute(
                    "INSERT INTO templates VALUES (?,?,?)",
                    (employee_id, nonce, ciphertext),
                )

    def propose(self, embedding, action, camera, minimum=0.55, margin=0.05):
        if action not in ("clock_in", "clock_out") or not camera or len(camera) > 80:
            raise ValueError("valid action and camera required")
        vector = normalize(embedding)
        scores = {}
        rows = self.db.execute(
            "SELECT t.employee_id,t.nonce,t.ciphertext FROM templates t JOIN employees e ON e.id=t.employee_id WHERE e.active=1"
        ).fetchall()
        for employee_id, nonce, ciphertext in rows:
            packed = self.cipher.decrypt(nonce, ciphertext, employee_id.encode())
            template = normalize(struct.unpack("<512f", packed))
            score = sum(a * b for a, b in zip(vector, template))
            scores[employee_id] = max(scores.get(employee_id, -1), score)
        candidates = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        best_id, best_score = candidates[0] if candidates else (None, -1)
        second_score = candidates[1][1] if len(candidates) > 1 else -1
        candidate = (
            best_id
            if best_score >= minimum and best_score - second_score >= margin
            else None
        )
        review_id = str(uuid.uuid4())
        with self.db:
            self.db.execute(
                "INSERT INTO reviews(id,employee_id,score,action,camera,created_at) VALUES (?,?,?,?,?,?)",
                (review_id, candidate, best_score, action, camera, time.time()),
            )
        return {
            "reviewId": review_id,
            "candidate": candidate,
            "score": best_score,
            "decision": "human_review" if candidate else "no_confident_match",
        }

    def confirm(self, review_id, reviewer, approved):
        if not reviewer or len(reviewer) > 120 or not isinstance(approved, bool):
            raise ValueError("reviewer and explicit decision required")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute(
                "SELECT employee_id,action,camera,resolved FROM reviews WHERE id=?",
                (review_id,),
            ).fetchone()
            if not row or row[3]:
                raise ValueError("review missing or already resolved")
            if approved and row[0] is None:
                raise ValueError("cannot approve an unidentified candidate")
            payload = json.dumps(
                {
                    "reviewId": review_id,
                    "employeeId": row[0],
                    "action": row[1],
                    "camera": row[2],
                    "reviewer": reviewer,
                    "approved": approved,
                    "timestamp": time.time(),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            last = self.db.execute(
                "SELECT mac FROM attendance ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            previous = last[0] if last else "0" * 64
            mac = hmac.new(
                self.audit_key, (previous + "\n" + payload).encode(), hashlib.sha256
            ).hexdigest()
            self.db.execute(
                "INSERT INTO attendance(event_id,payload,previous_mac,mac) VALUES (?,?,?,?)",
                (review_id, payload, previous, mac),
            )
            self.db.execute("UPDATE reviews SET resolved=1 WHERE id=?", (review_id,))
            self.db.commit()
            return json.loads(payload)
        except Exception:
            self.db.rollback()
            raise

    def revoke(self, employee_id):
        with self.db:
            self.db.execute("UPDATE employees SET active=0 WHERE id=?", (employee_id,))
            self.db.execute("DELETE FROM templates WHERE employee_id=?", (employee_id,))

    def verify(self):
        previous = "0" * 64
        for payload, stored_previous, mac in self.db.execute(
            "SELECT payload,previous_mac,mac FROM attendance ORDER BY sequence"
        ):
            expected = hmac.new(
                self.audit_key, (previous + "\n" + payload).encode(), hashlib.sha256
            ).hexdigest()
            if stored_previous != previous or not hmac.compare_digest(expected, mac):
                return False
            previous = mac
        return True

    def export(self):
        return {
            "auditValid": self.verify(),
            "events": [
                json.loads(row[0])
                for row in self.db.execute(
                    "SELECT payload FROM attendance ORDER BY sequence"
                )
            ],
        }
