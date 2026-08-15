"""End-to-end Phase 2 acceptance against Neon development only."""

from __future__ import annotations

from io import BytesIO
import socket
import subprocess
from time import monotonic, sleep
from urllib.request import urlopen
from uuid import uuid4

import pandas as pd

from database.models import Observation
from database.repository import ObservationRepository
from services.export import EXPORT_COLUMNS, observations_csv_bytes
from services.validation import (
    validate_bird_session,
    validate_horse_session,
    validate_material_entry,
)


def _add(repository: ObservationRepository, record) -> int:
    saved = repository.add(
        category_type=record.category_type,
        item_name=record.item,
        level=record.level,
        attempt_count=record.attempt_count,
        observed_at=record.observed_at,
        green_count=record.green_count,
        blue_count=record.blue_count,
        purple_count=record.purple_count,
        orange_count=record.orange_count,
        unaccounted_count=record.unaccounted_count,
        session_id=record.session_id,
        remark=record.remark,
    )
    return saved.id


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def _start_streamlit() -> subprocess.Popen:
    port = _free_port()
    process = subprocess.Popen(
        [
            ".venv/bin/streamlit", "run", "app.py", "--server.headless=true",
            f"--server.port={port}", "--browser.gatherUsageStats=false",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = monotonic() + 30
    while monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError("Streamlit failed to start")
        try:
            with urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=1) as response:
                if response.status == 200:
                    return process
        except OSError:
            sleep(0.25)
    process.terminate()
    process.wait(timeout=10)
    raise AssertionError("Streamlit health check timed out")


def _stop_streamlit(process: subprocess.Popen) -> None:
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def test_phase2_acceptance_a_through_g(postgres_factory) -> None:
    marker = f"phase2-acceptance-{uuid4().hex}"
    ids: list[int] = []
    first_process = None
    second_process = None
    try:
        material = validate_material_entry(
            material="丝线", skill_level=9, quantity=18, orange_count=1,
            remark=f"{marker}-A",
        )
        horse = validate_horse_session(
            horse="浴火烈马", level=10, search_count=8,
            green_count=3, blue_count=4, purple_count=0, orange_count=1,
            remark=f"{marker}-B",
        )
        bird_results = [
            ("铁羽雁", "BLUE"), ("九炎鹊", "PURPLE"),
            ("出云鹤", "ORANGE"), ("暗铁鸦", "BLUE"),
            ("铁羽雁", "BLUE"), ("九炎鹊", "PURPLE"),
            ("出云鹤", "BLUE"), ("暗铁鸦", "ORANGE"),
        ]
        birds = validate_bird_session(
            level=10, results=bird_results, remark=f"{marker}-C"
        )

        with postgres_factory.begin() as session:
            repository = ObservationRepository(session)
            material_id = _add(repository, material)
            horse_id = _add(repository, horse)
            ids.extend((material_id, horse_id))
            ids.extend(_add(repository, bird) for bird in birds)

        with postgres_factory() as session:
            saved_material = session.get(Observation, material_id)
            assert (
                saved_material.attempt_count, saved_material.orange_count
            ) == (18, 1)
            saved_horse = session.get(Observation, horse_id)
            assert (
                saved_horse.attempt_count, saved_horse.green_count,
                saved_horse.blue_count, saved_horse.purple_count,
                saved_horse.orange_count,
            ) == (8, 3, 4, 0, 1)
            saved_birds = [session.get(Observation, bird_id) for bird_id in ids[2:]]
            assert len(saved_birds) == 8
            assert len({bird.session_id for bird in saved_birds}) == 1
            assert [bird.item.name for bird in saved_birds] == [
                species for species, _ in bird_results
            ]

        first_process = _start_streamlit()
        _stop_streamlit(first_process)
        first_process = None
        second_process = _start_streamlit()
        with postgres_factory() as session:
            assert all(session.get(Observation, observation_id) for observation_id in ids)
            old_updated_at = session.get(Observation, material_id).updated_at
        _stop_streamlit(second_process)
        second_process = None

        sleep(0.02)
        with postgres_factory.begin() as session:
            edited = ObservationRepository(session).update(
                material_id, remark=f"{marker}-A-edited"
            )
            assert edited.id == material_id
        with postgres_factory() as session:
            edited = session.get(Observation, material_id)
            assert edited.id == material_id
            assert edited.updated_at > old_updated_at

            raw = ObservationRepository(session).dataframe()
            acceptance = raw[raw["remark"].str.startswith(marker, na=False)]
            payload = observations_csv_bytes(acceptance)
            exported = pd.read_csv(BytesIO(payload), encoding="utf-8-sig")
            assert tuple(exported.columns) == EXPORT_COLUMNS
            assert len(exported) == 10
            assert set(ids).issubset(set(exported["id"].astype(int)))

        with postgres_factory.begin() as session:
            assert ObservationRepository(session).delete(horse_id)
        with postgres_factory() as session:
            assert session.get(Observation, horse_id) is None
    finally:
        if first_process is not None:
            _stop_streamlit(first_process)
        if second_process is not None:
            _stop_streamlit(second_process)
        with postgres_factory.begin() as session:
            repository = ObservationRepository(session)
            for observation_id in ids:
                repository.delete(observation_id)
