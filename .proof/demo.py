import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def run(argv, expected=0):
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=30)
    if result.returncode != expected:
        raise RuntimeError(result.stderr + result.stdout)
    return result.stdout

from app.core import AttendanceStore

with tempfile.TemporaryDirectory() as temp:
    store = AttendanceStore(Path(temp) / 'attendance.db', b'e' * 32, b'a' * 32)
    vector = [1.0] + [0.0] * 511
    store.enroll('synthetic-person', 'Synthetic Person', [vector] * 3, True)
    proposal = store.propose(vector, 'clock_in', 'fixture-camera')
    assert proposal['decision'] == 'human_review' and store.export()['events'] == []
    store.confirm(proposal['reviewId'], 'fixture-operator', True)
    assert store.verify()
    recorded = len(store.export()['events'])
    store.revoke('synthetic-person')
    assert store.propose(vector, 'clock_out', 'fixture-camera')['candidate'] is None
    store.db.execute("UPDATE attendance SET payload='{}'")
    assert not store.verify()
    print(json.dumps({'review_required': True, 'recorded_events': recorded, 'revocation_effective': True, 'tampering_detected': True}, sort_keys=True))
    store.db.close()
