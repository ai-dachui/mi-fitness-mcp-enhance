import json

import pytest

from mi_fitness_mcp.adapters.mi_fitness_cloud import (
    MiFitnessCloudAdapter,
    _is_authentication_error,
)
from mi_fitness_mcp.models import SleepStage


async def _collect(async_iterable):
    items = []
    async for item in async_iterable:
        items.append(item)
    return items


def test_optional_number_helpers():
    adapter = MiFitnessCloudAdapter(user_id="u1", pass_token="p1")
    assert adapter._optional_float(0) is None
    assert adapter._optional_float("1.5") == 1.5
    assert adapter._optional_int(0) is None
    assert adapter._optional_int("7") == 7


def test_parse_value_dict_and_json():
    adapter = MiFitnessCloudAdapter(user_id="u1", pass_token="p1")
    assert adapter._parse_value({"value": {"steps": 1}}) == {"steps": 1}
    assert adapter._parse_value({"value": '{"steps": 2}'}) == {"steps": 2}


def test_record_datetime_uses_zone_offset():
    adapter = MiFitnessCloudAdapter(user_id="u1", pass_token="p1")
    dt = adapter._record_datetime({"time": 0, "zone_offset": 10800})
    assert dt.isoformat().startswith("1970-01-01T03:00:00")


@pytest.mark.asyncio
async def test_iter_daily_activity_aggregates_steps_and_calories(monkeypatch):
    adapter = MiFitnessCloudAdapter(user_id="u1", pass_token="p1")
    adapter._connected = True
    adapter._client = object()

    async def fake_fetch(key, start_date, end_date, region=None):
        if key == "steps":
            return [
                {
                    "time": 1743467400,
                    "zone_offset": 0,
                    "value": '{"steps": 10, "distance": 8, "calories": 1}',
                },
                {
                    "time": 1743467460,
                    "zone_offset": 0,
                    "value": '{"steps": 20, "distance": 16, "calories": 2}',
                },
            ]
        if key == "calories":
            return [
                {"time": 1743467400, "zone_offset": 0, "value": '{"calories": 5}'},
                {"time": 1743467460, "zone_offset": 0, "value": '{"calories": 7}'},
            ]
        return []

    monkeypatch.setattr(adapter, "_fetch_key", fake_fetch)
    items = await _collect(adapter.iter_daily_activity("2025-04-01", "2025-04-01"))

    assert len(items) == 1
    assert items[0].steps == 30
    assert items[0].distance_m == 24
    assert items[0].active_kcal == 12


@pytest.mark.asyncio
async def test_fetch_key_rejects_repeated_pagination_cursor(monkeypatch):
    adapter = MiFitnessCloudAdapter(user_id="u1", pass_token="p1", region="cn")
    adapter._client = object()

    async def fake_request(base_url, api_path, payload):
        return {"data_list": [], "has_more": True, "next_key": "same"}

    monkeypatch.setattr(adapter, "_request", fake_request)
    with pytest.raises(RuntimeError, match="cursor loop"):
        await adapter._fetch_key("steps", "2026-07-06", "2026-07-12")


@pytest.mark.asyncio
async def test_connect_failure_closes_client(monkeypatch):
    adapter = MiFitnessCloudAdapter(user_id="u1", pass_token="bad", region="cn")

    async def failed_login(user_id, pass_token):
        raise RuntimeError("invalid credentials")

    monkeypatch.setattr(adapter, "_login_with_token", failed_login)
    assert await adapter.connect() is False
    assert adapter._client is None
    assert "invalid credentials" in adapter.last_error


def test_authentication_error_detection():
    assert _is_authentication_error(401, "denied")
    assert _is_authentication_error(0, "session expired")
    assert _is_authentication_error(-10001, "unknown")
    assert not _is_authentication_error(500, "temporary server failure")


def test_sleep_stage_name_maps_mi_fitness_codes():
    adapter = MiFitnessCloudAdapter(user_id="u1", pass_token="p1")

    assert adapter._sleep_stage_name(1) == "deep"
    assert adapter._sleep_stage_name(2) == "deep"
    assert adapter._sleep_stage_name(3) == "light"
    assert adapter._sleep_stage_name(4) == "rem"
    assert adapter._sleep_stage_name(5) == "awake"
    assert adapter._sleep_stage_name(6) == "light"
    assert adapter._sleep_stage_name(None) == "light"


def test_date_range_accepts_iso_datetime():
    adapter = MiFitnessCloudAdapter(user_id="u1", pass_token="p1", region="cn")

    start, end = adapter._date_range_to_timestamps(
        "2026-11-06T09:00:00", "2026-11-06T11:00:00"
    )

    assert end - start == 7200


@pytest.mark.asyncio
async def test_fetch_key_uses_epoch_window(monkeypatch):
    adapter = MiFitnessCloudAdapter(user_id="u1", pass_token="p1", region="cn")
    adapter._client = object()
    captured = {}

    async def fake_request(base_url, api_path, payload):
        captured.update(payload)
        return {"data_list": []}

    monkeypatch.setattr(adapter, "_request", fake_request)
    await adapter._fetch_key("heart_rate", start_time=1743467400, end_time=1743474600)

    assert captured["start_time"] == 1743467400
    assert captured["end_time"] == 1743474600


@pytest.mark.asyncio
async def test_fetch_key_requires_dates_or_window():
    adapter = MiFitnessCloudAdapter(user_id="u1", pass_token="p1")

    with pytest.raises(ValueError, match="start_time"):
        await adapter._fetch_key("heart_rate")


@pytest.mark.asyncio
async def test_iter_sleep_sessions_fills_score_and_deep_stage(monkeypatch):
    adapter = MiFitnessCloudAdapter(user_id="u1", pass_token="p1", region="cn")
    adapter._connected = True
    adapter._client = object()

    async def fake_scores(start_date, end_date, region=None):
        return {(1743467400, 1743496200): 88}

    async def fake_fetch(
        key, start_date=None, end_date=None, region=None, start_time=None, end_time=None
    ):
        return [
            {
                "time": 1743496200,
                "zone_offset": 0,
                "sid": "s1",
                "value": json.dumps(
                    {
                        "bedtime": 1743467400,
                        "wake_up_time": 1743496200,
                        "duration": 28800,
                        "items": [
                            {
                                "start_time": 1743467400,
                                "end_time": 1743474600,
                                "state": 2,
                            }
                        ],
                    }
                ),
            }
        ]

    monkeypatch.setattr(adapter, "_fetch_aggregated_sleep_scores", fake_scores)
    monkeypatch.setattr(adapter, "_fetch_key", fake_fetch)

    items = await _collect(adapter.iter_sleep_sessions("2026-04-01", "2026-04-02"))

    assert len(items) == 1
    assert items[0].sleep_score == 88
    assert items[0].stages == [SleepStage(stage="deep", minutes=120)]
