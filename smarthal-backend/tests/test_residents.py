"""Tests for POST /residents (Register Resident), using the fake face engine from conftest."""

import io

import cv2
import numpy as np
import pytest

from app import RESIDENT_ANGLES
from conftest import bearer
from db import get_connection


def photo(faces=1, person=1):
    """A small JPEG the fake engine reads as `faces` faces belonging to `person`."""
    img = np.zeros((64, 64, 3), np.uint8)
    img[:, :] = (faces, person, 0)
    ok, buf = cv2.imencode(".png", img)  # PNG: lossless, so the marker values survive
    return buf.tobytes()


def form(name="Jordan", **overrides):
    """Multipart form with a name and one good photo per angle; overrides replace angles' bytes."""
    data = {"name": name}
    for angle in RESIDENT_ANGLES:
        data[angle] = (io.BytesIO(overrides.get(angle, photo())), f"{angle}.png")
    return data


def post(client, token, data):
    """Send the registration form."""
    return client.post("/residents", data=data, headers=bearer(token), content_type="multipart/form-data")


def rows(sql, *args):
    """Run a query on the test database and return all rows."""
    conn = get_connection()
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def test_requires_login(client):
    assert client.post("/residents", data=form(), content_type="multipart/form-data").status_code == 401


def test_registers_resident_with_all_angles(client, token, tmp_path):
    resp = post(client, token, form(name="  Jordan  "))
    assert resp.status_code == 201
    resident = resp.get_json()["resident"]
    assert resident["name"] == "Jordan"
    assert resident["angles"] == list(RESIDENT_ANGLES)

    (row,) = rows("SELECT registered_by, name, photo_path, facial_embedding FROM residents")
    assert (row["registered_by"], row["name"], row["photo_path"]) == (1, "Jordan", f"{resident['id']}/front.jpg")
    assert row["facial_embedding"] is None  # embeddings live in resident_face_angles

    angles = rows("SELECT angle, embedding, model, photo_path FROM resident_face_angles ORDER BY id")
    assert [a["angle"] for a in angles] == list(RESIDENT_ANGLES)
    assert all(a["model"] == "fake-engine" for a in angles)
    assert np.frombuffer(angles[0]["embedding"], np.float32).shape == (8,)
    for a in angles:
        saved = tmp_path / "residents" / a["photo_path"]
        assert saved.exists() and cv2.imread(str(saved)) is not None


@pytest.mark.parametrize("name", ["", "   ", "x" * 101])
def test_rejects_bad_name(client, token, name):
    assert post(client, token, form(name=name)).status_code == 400
    assert rows("SELECT * FROM residents") == []


def test_rejects_missing_angle(client, token):
    data = form()
    del data["left"]
    resp = post(client, token, data)
    assert resp.status_code == 400
    assert resp.get_json()["angle"] == "left"


def test_rejects_file_that_is_not_an_image(client, token):
    resp = post(client, token, form(up=b"%PDF-1.4 definitely not a photo"))
    assert resp.status_code == 400
    assert resp.get_json()["reason"] == "invalid_image"
    assert resp.get_json()["angle"] == "up"


def test_rejects_photo_with_no_face(client, token):
    resp = post(client, token, form(right=photo(faces=0)))
    assert resp.status_code == 400
    assert (resp.get_json()["angle"], resp.get_json()["reason"]) == ("right", "no_face")


def test_rejects_photo_with_two_faces(client, token):
    resp = post(client, token, form(front=photo(faces=2)))
    assert resp.status_code == 400
    assert (resp.get_json()["angle"], resp.get_json()["reason"]) == ("front", "multiple_faces")


def test_rejects_different_person_partway_through(client, token):
    resp = post(client, token, form(down=photo(person=2)))
    assert resp.status_code == 400
    assert (resp.get_json()["angle"], resp.get_json()["reason"]) == ("down", "different_person")
    assert rows("SELECT * FROM residents") == []
    assert rows("SELECT * FROM resident_face_angles") == []


def test_rejects_oversized_photo(client, token):
    huge = photo() + b"\0" * (5 * 1024 * 1024)
    resp = post(client, token, form(left=huge))
    assert resp.status_code == 400
    assert resp.get_json()["reason"] == "too_large"


def test_nothing_saved_if_writing_photos_fails(client, token, monkeypatch, tmp_path):
    import app as app_module
    monkeypatch.setattr(app_module.cv2, "imwrite", lambda *a, **k: False)
    assert post(client, token, form()).status_code == 500
    assert rows("SELECT * FROM residents") == []
    assert not any((tmp_path / "residents").glob("*/*.jpg"))


# --- listing and deleting -------------------------------------------------

def login_as(client, username, role):
    """Create another user with this role and return their session token."""
    import auth
    conn = get_connection()
    conn.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                 (username, auth.hash_password("password-123"), role))
    conn.commit()
    conn.close()
    resp = client.post("/login", json={"username": username, "password": "password-123"})
    return resp.get_json()["token"]


def register(client, token, name="Jordan"):
    """Register a resident and return their id."""
    resp = post(client, token, form(name=name))
    assert resp.status_code == 201
    return resp.get_json()["resident"]["id"]


def test_list_requires_login(client):
    assert client.get("/residents").status_code == 401


def test_list_shows_residents_newest_first(client, token):
    register(client, token, "First")
    register(client, token, "Second")
    residents = client.get("/residents", headers=bearer(token)).get_json()["residents"]
    assert [(r["name"], r["registered_by"], r["angles"], r["can_delete"]) for r in residents] == [
        ("Second", "alex", 5, True),
        ("First", "alex", 5, True),
    ]


def test_delete_removes_resident_embeddings_and_photos(client, token, tmp_path):
    rid = register(client, token)
    assert (tmp_path / "residents" / str(rid) / "front.jpg").exists()
    assert client.delete(f"/residents/{rid}", headers=bearer(token)).status_code == 204
    assert rows("SELECT * FROM residents") == []
    assert rows("SELECT * FROM resident_face_angles") == []
    assert not (tmp_path / "residents" / str(rid)).exists()


def test_delete_unknown_resident_is_404(client, token):
    assert client.delete("/residents/999", headers=bearer(token)).status_code == 404


def test_delete_requires_login(client, token):
    rid = register(client, token)
    assert client.delete(f"/residents/{rid}").status_code == 401
    assert len(rows("SELECT * FROM residents")) == 1


def test_other_home_user_cannot_delete(client, token):
    rid = register(client, token)
    other = login_as(client, "sam", "home_user")
    listed = client.get("/residents", headers=bearer(other)).get_json()["residents"]
    assert listed[0]["can_delete"] is False
    assert client.delete(f"/residents/{rid}", headers=bearer(other)).status_code == 403
    assert len(rows("SELECT * FROM residents")) == 1


def test_admin_can_delete_anyones_resident(client, token):
    rid = register(client, token)
    admin = login_as(client, "boss", "admin")
    assert client.delete(f"/residents/{rid}", headers=bearer(admin)).status_code == 204


def test_resident_with_detection_events_is_not_deleted(client, token, tmp_path):
    rid = register(client, token)
    conn = get_connection()
    conn.execute("INSERT INTO cameras (id) VALUES (1)")
    conn.execute("INSERT INTO detection_events (camera_id, resident_id, timestamp, classification)"
                 " VALUES (1, ?, '2026-10-09T12:00:00', 'Resident')", (rid,))
    conn.commit()
    conn.close()
    assert client.delete(f"/residents/{rid}", headers=bearer(token)).status_code == 409
    assert len(rows("SELECT * FROM resident_face_angles")) == 5
    assert (tmp_path / "residents" / str(rid) / "front.jpg").exists()
