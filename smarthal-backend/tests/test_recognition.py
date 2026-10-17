"""Tests for Live Feed recognition (GET /recognitions), using the fake camera and face engine."""

import io

import cv2
import numpy as np

from app import RESIDENT_ANGLES
from conftest import bearer


def picture(faces=1, person=1, size=(100, 200)):
    """A frame the fake engine reads as `faces` faces belonging to `person`."""
    img = np.zeros((size[0], size[1], 3), np.uint8)
    img[:, :] = (faces, person, 0)
    return img


def register(client, token, name, person):
    """Register a resident whose five photos all show `person`."""
    data = {"name": name}
    for angle in RESIDENT_ANGLES:
        ok, buf = cv2.imencode(".png", picture(person=person, size=(64, 64)))
        data[angle] = (io.BytesIO(buf.tobytes()), f"{angle}.png")
    resp = client.post("/residents", data=data, headers=bearer(token), content_type="multipart/form-data")
    assert resp.status_code == 201
    return resp.get_json()["resident"]["id"]


def recognitions(client, token):
    resp = client.get("/recognitions", headers=bearer(token))
    assert resp.status_code == 200
    return resp.get_json()


def test_requires_login(client):
    assert client.get("/recognitions").status_code == 401


def test_no_frame_means_no_faces(client, token):
    body = recognitions(client, token)
    assert body["faces"] == []
    assert body["camera_online"] is True
    assert body["error"] is None


def test_registered_resident_is_named(client, token, camera):
    rid = register(client, token, "Jordan", person=3)
    camera.frame = picture(person=3)
    (face,) = recognitions(client, token)["faces"]
    assert (face["name"], face["resident_id"]) == ("Jordan", rid)
    assert face["score"] >= 0.5


def test_unregistered_person_is_unknown(client, token, camera):
    register(client, token, "Jordan", person=3)
    camera.frame = picture(person=5)
    (face,) = recognitions(client, token)["faces"]
    assert face["name"] is None and face["resident_id"] is None


def test_everyone_is_unknown_with_no_residents(client, token, camera):
    camera.frame = picture(person=3)
    (face,) = recognitions(client, token)["faces"]
    assert face["name"] is None


def test_boxes_are_fractions_of_the_frame(client, token, camera):
    camera.frame = picture(faces=2, size=(100, 200))
    faces = recognitions(client, token)["faces"]
    assert [f["box"] for f in faces] == [[0.0, 0.05, 0.04, 0.08], [0.05, 0.05, 0.04, 0.08]]


def test_two_residents_told_apart(client, token, camera):
    register(client, token, "Jordan", person=3)
    register(client, token, "Sam", person=4)
    camera.frame = picture(person=4)
    assert recognitions(client, token)["faces"][0]["name"] == "Sam"


def test_deleted_resident_is_no_longer_recognized(client, token, camera):
    rid = register(client, token, "Jordan", person=3)
    camera.frame = picture(person=3)
    assert recognitions(client, token)["faces"][0]["name"] == "Jordan"
    assert client.delete(f"/residents/{rid}", headers=bearer(token)).status_code == 204
    assert recognitions(client, token)["faces"][0]["name"] is None


def test_threshold_can_be_raised(client, token, camera, app):
    register(client, token, "Jordan", person=3)
    camera.frame = picture(person=3)
    app.extensions["recognizer"].threshold = 1.01  # nothing can score above 1
    assert recognitions(client, token)["faces"][0]["name"] is None


def test_engine_failure_is_reported_not_crashed(client, token, camera, app):
    camera.frame = picture()

    def broken(_img):
        raise RuntimeError("models missing")

    app.extensions["recognizer"].engine.detect_faces = broken
    body = recognitions(client, token)
    assert body["faces"] == [] and "unavailable" in body["error"]


def test_large_frames_are_shrunk_but_boxes_stay_relative(client, token, camera, app):
    seen = {}
    engine = app.extensions["recognizer"].engine
    original = engine.detect_faces

    def spy(img):
        seen["shape"] = img.shape
        return original(img)

    engine.detect_faces = spy
    camera.frame = picture(size=(2160, 3840))
    face = recognitions(client, token)["faces"][0]
    assert max(seen["shape"][:2]) == 1280
    assert face["box"][2] == round(8.0 / 1280, 4)


def test_boxes_are_kept_inside_the_frame(client, token, camera, app):
    engine = app.extensions["recognizer"].engine
    emb = engine.detect_faces(picture())[0][1]
    engine.detect_faces = lambda img: [((-20.0, -10.0, 260.0, 130.0), emb)]
    camera.frame = picture(size=(100, 200))
    assert recognitions(client, token)["faces"][0]["box"] == [0.0, 0.0, 1.0, 1.0]
