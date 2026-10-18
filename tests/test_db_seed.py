from backend.db import init_db, session, TABLES
from backend.seed import seed_all, qr_token_for
from fastapi.testclient import TestClient
from backend.main import app


def test_init_db_and_tables(tmp_path):
    test_db = str(tmp_path / "test_swasthyasanjaal.db")
    applied = init_db(test_db)
    assert isinstance(applied, list)

    with session(test_db) as con:
        present = {
            row["name"]
            for row in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        for table in TABLES:
            assert table in present


def test_seed_all(tmp_path):
    test_db = str(tmp_path / "test_swasthyasanjaal.db")
    init_db(test_db)
    with session(test_db) as con:
        counts = seed_all(con)
        assert counts["patients"] >= 3
        assert counts["allergies"] >= 2
        assert counts["entries"] >= 3
        assert counts["lexicon"] == 300

        # Verify Ram
        ram = con.execute("SELECT * FROM patients WHERE id = 'patient_ram'").fetchone()
        assert ram is not None
        assert ram["name"] == "Ram Bahadur Shrestha"
        assert ram["sanjaal_id"].startswith(("SS-", "SANJAAL-"))
        assert ram["sanchai_id"].startswith("SANCHAI-")
        assert ram["qr_token"] == qr_token_for(ram["sanchai_id"])

        # Verify Ram's allergies
        ram_allergies = con.execute("SELECT * FROM allergies WHERE patient_id = 'patient_ram'").fetchall()
        assert len(ram_allergies) >= 1
        assert any(a["substance_en"] == "Penicillin" for a in ram_allergies)

        # Verify entries
        entries = con.execute("SELECT * FROM record_entries WHERE patient_id = 'patient_ram'").fetchall()
        assert len(entries) >= 2


def test_health_with_seeded_db():
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        db_service = next((s for s in data["services"] if s["service"] == "db"), None)
        assert db_service is not None
        assert db_service["status"] == "up"
