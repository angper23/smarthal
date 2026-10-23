"""Tests for liveness (anti-spoofing) on Live Feed, with a stand-in for the MiniFASNet models."""

import numpy as np
import pytest

from conftest import FakeFaceEngine
from liveness import INPUT_SIZE, LivenessChecker, crop_face
from recognition import Recognizer
from test_recognition import picture, register


class FakeLiveness:
    """Says a face is fake when the test picture's red channel is 1 (a "photo"), real otherwise."""
    threshold = 0.5
    min_face_px = 0

    def __init__(self):
        self.calls = 0

    def real_score(self, frame, box):
        self.calls += 1
        return 0.1 if int(frame[0, 0, 2]) == 1 else 0.9


def photo_of(person):
    """A picture of `person` that the fake liveness check sees as a photo or screen."""
    img = picture(person=person)
    img[:, :, 2] = 1
    return img


@pytest.fixture
def checker():
    return FakeLiveness()


@pytest.fixture
def recognizer(app, camera, clock, checker):
    """A recognizer with liveness, on the same database and camera as the app."""
    return Recognizer(camera, FakeFaceEngine(), background=False, clock=clock, liveness=checker)


def statuses(recognizer, passes):
    """Run `passes` recognition passes and return each pass's first face (status, name)."""
    out = []
    for _ in range(passes):
        face = recognizer.latest()["faces"][0]
        out.append((face["status"], face["name"]))
    return out


def test_real_resident_is_named_after_enough_real_looking_passes(client, token, camera, recognizer):
    register(client, token, "Jordan", person=3)
    camera.frame = picture(person=3)
    assert statuses(recognizer, 3) == [("checking", None), ("checking", None), ("resident", "Jordan")]


def test_photo_of_resident_is_never_named(client, token, camera, recognizer):
    register(client, token, "Jordan", person=3)
    camera.frame = photo_of(3)
    results = statuses(recognizer, 5)
    assert all(name is None for _, name in results)
    assert results[-1] == ("spoof", None)


def test_unknown_people_skip_the_liveness_check(client, token, camera, recognizer, checker):
    register(client, token, "Jordan", person=3)
    camera.frame = picture(person=5)
    face = recognizer.latest()["faces"][0]
    assert (face["status"], face["name"], face["liveness"]) == ("unknown", None, None)
    assert checker.calls == 0


def test_faces_too_small_to_judge_stay_unknown(client, token, camera, recognizer, checker):
    register(client, token, "Jordan", person=3)
    checker.min_face_px = 50  # the fake engine's faces are 8 px tall
    camera.frame = picture(person=3)
    assert statuses(recognizer, 4) == [("too_far", None)] * 4
    assert checker.calls == 0


def test_one_photo_frame_does_not_undo_a_verified_resident(client, token, camera, recognizer):
    register(client, token, "Jordan", person=3)
    camera.frame = picture(person=3)
    statuses(recognizer, 3)
    camera.frame = photo_of(3)  # e.g. one blurry or glary frame
    assert statuses(recognizer, 1) == [("resident", "Jordan")]


def test_votes_reset_after_the_resident_leaves(client, token, camera, recognizer, clock):
    register(client, token, "Jordan", person=3)
    camera.frame = picture(person=3)
    statuses(recognizer, 3)
    clock.advance(10)
    assert statuses(recognizer, 1) == [("checking", None)]


def test_missing_model_files_hide_names_and_report_it(client, token, camera, clock, tmp_path):
    register(client, token, "Jordan", person=3)
    broken = LivenessChecker(models_dir=str(tmp_path / "nothing-here"))
    broken.min_face_px = 0
    rec = Recognizer(camera, FakeFaceEngine(), background=False, clock=clock, liveness=broken)
    camera.frame = picture(person=3)
    result = rec.latest()
    assert (result["faces"][0]["status"], result["faces"][0]["name"]) == ("unverified", None)
    assert "Liveness check unavailable" in result["error"]


def test_without_liveness_residents_are_named_immediately(client, token, camera, clock):
    register(client, token, "Jordan", person=3)
    rec = Recognizer(camera, FakeFaceEngine(), background=False, clock=clock, liveness=None)
    camera.frame = picture(person=3)
    face = rec.latest()["faces"][0]
    assert (face["status"], face["name"]) == ("resident", "Jordan")


# --- crop_face: must match the original project's crop so the models see what they were trained on

def test_crop_is_model_sized():
    frame = np.zeros((720, 1280, 3), np.uint8)
    assert crop_face(frame, (600, 300, 100, 120), 2.7).shape == (INPUT_SIZE, INPUT_SIZE, 3)


def test_crop_is_centered_on_the_face():
    frame = np.zeros((720, 1280, 3), np.uint8)
    frame[340:380, 620:660] = 255  # a bright square in the middle of the face box
    patch = crop_face(frame, (590, 310, 100, 100), 2.7)
    assert patch[38:42, 38:42].min() == 255 and patch[0, 0].max() == 0


def test_crop_near_the_edge_slides_inside_the_frame():
    frame = np.zeros((720, 1280, 3), np.uint8)
    frame[:, :5] = 255  # mark the left edge
    patch = crop_face(frame, (0, 300, 100, 100), 4.0)  # crop would start left of the frame
    assert patch.shape == (INPUT_SIZE, INPUT_SIZE, 3) and patch[:, 0].min() == 255


def test_crop_is_limited_to_the_frame_size():
    frame = np.zeros((100, 100, 3), np.uint8)
    assert crop_face(frame, (20, 20, 60, 60), 4.0).shape == (INPUT_SIZE, INPUT_SIZE, 3)


def test_missing_files_are_listed(tmp_path):
    assert len(LivenessChecker(models_dir=str(tmp_path)).missing_files()) == 2
