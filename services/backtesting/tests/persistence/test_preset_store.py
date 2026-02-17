"""Tests for PresetStore — async SQLite preset persistence."""

import os
import tempfile

import pytest
import pytest_asyncio

from grid_backtester.persistence.preset_store import PresetStore


@pytest_asyncio.fixture
async def preset_store():
    """Create a temporary preset store for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    store = PresetStore(db_path=db_path)
    await store.initialize()
    yield store
    await store.close()
    os.unlink(db_path)


@pytest.mark.asyncio
class TestPresetStore:

    async def test_create_returns_preset_id(self, preset_store):
        preset_id = await preset_store.create(
            symbol="BTCUSDT",
            config_yaml="num_levels: 15",
            cluster="blue_chips",
        )
        assert isinstance(preset_id, str)
        assert len(preset_id) > 0

    async def test_get_by_symbol(self, preset_store):
        await preset_store.create(
            symbol="ETHUSDT",
            config_yaml="num_levels: 10",
            cluster="mid_caps",
            metrics={"sharpe": 1.5},
        )
        preset = await preset_store.get_by_symbol("ETHUSDT")
        assert preset is not None
        assert preset["symbol"] == "ETHUSDT"
        assert preset["config_yaml"] == "num_levels: 10"
        assert preset["cluster"] == "mid_caps"
        assert preset["metrics"]["sharpe"] == 1.5
        assert preset["is_active"] is True

    async def test_get_by_symbol_not_found(self, preset_store):
        result = await preset_store.get_by_symbol("NONEXIST")
        assert result is None

    async def test_auto_deactivation_on_new_preset(self, preset_store):
        """Creating a new preset for the same symbol deactivates the old one."""
        id1 = await preset_store.create(symbol="BTCUSDT", config_yaml="v1")
        id2 = await preset_store.create(symbol="BTCUSDT", config_yaml="v2")

        # Old preset should be deactivated
        old = await preset_store.get(id1)
        assert old["is_active"] is False

        # New preset should be active
        new = await preset_store.get(id2)
        assert new["is_active"] is True

        # get_by_symbol should return the new one
        active = await preset_store.get_by_symbol("BTCUSDT")
        assert active["preset_id"] == id2

    async def test_list_presets_active_only(self, preset_store):
        await preset_store.create(symbol="BTCUSDT", config_yaml="v1")
        await preset_store.create(symbol="BTCUSDT", config_yaml="v2")
        await preset_store.create(symbol="ETHUSDT", config_yaml="v1")

        presets = await preset_store.list_presets(active_only=True)
        assert len(presets) == 2  # One active per symbol

    async def test_list_presets_all(self, preset_store):
        await preset_store.create(symbol="BTCUSDT", config_yaml="v1")
        await preset_store.create(symbol="BTCUSDT", config_yaml="v2")

        presets = await preset_store.list_presets(active_only=False)
        assert len(presets) == 2

    async def test_update_preset(self, preset_store):
        preset_id = await preset_store.create(
            symbol="BTCUSDT",
            config_yaml="old",
        )
        updated = await preset_store.update(preset_id, config_yaml="new")
        assert updated is True

        preset = await preset_store.get(preset_id)
        assert preset["config_yaml"] == "new"

    async def test_delete_preset(self, preset_store):
        preset_id = await preset_store.create(symbol="BTCUSDT", config_yaml="v1")
        deleted = await preset_store.delete(preset_id)
        assert deleted is True

        preset = await preset_store.get(preset_id)
        assert preset is None

    async def test_delete_by_symbol(self, preset_store):
        await preset_store.create(symbol="BTCUSDT", config_yaml="v1")
        await preset_store.create(symbol="BTCUSDT", config_yaml="v2")

        count = await preset_store.delete_by_symbol("BTCUSDT")
        assert count == 2

        presets = await preset_store.list_presets(active_only=False)
        assert len(presets) == 0
