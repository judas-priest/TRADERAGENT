"""Unit tests for event system"""

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from bot.orchestrator.events import EventType, TradingEvent


class TestTradingEvent:
    """Test TradingEvent class."""

    def test_create_event(self):
        """Test creating a trading event."""
        event = TradingEvent.create(
            event_type=EventType.BOT_STARTED,
            bot_name="test_bot",
            data={"strategy": "grid"},
        )

        assert event.event_type == EventType.BOT_STARTED
        assert event.bot_name == "test_bot"
        assert event.data == {"strategy": "grid"}
        assert event.timestamp is not None

    def test_create_event_without_data(self):
        """Test creating event without data."""
        event = TradingEvent.create(
            event_type=EventType.BOT_STOPPED,
            bot_name="test_bot",
        )

        assert event.data == {}

    def test_to_json(self):
        """Test serializing event to JSON."""
        event = TradingEvent.create(
            event_type=EventType.ORDER_PLACED,
            bot_name="test_bot",
            data={"order_id": "123", "price": "45000"},
        )

        json_str = event.to_json()
        assert isinstance(json_str, str)

        # Parse JSON
        parsed = json.loads(json_str)
        assert parsed["event_type"] == "order_placed"
        assert parsed["bot_name"] == "test_bot"
        assert parsed["data"]["order_id"] == "123"

    def test_from_json(self):
        """Test deserializing event from JSON."""
        event = TradingEvent.create(
            event_type=EventType.ORDER_FILLED,
            bot_name="test_bot",
            data={"order_id": "456"},
        )

        json_str = event.to_json()
        restored_event = TradingEvent.from_json(json_str)

        assert restored_event.event_type == event.event_type
        assert restored_event.bot_name == event.bot_name
        assert restored_event.data == event.data

    def test_decimal_conversion(self):
        """Test that Decimal values are converted to strings."""
        event = TradingEvent.create(
            event_type=EventType.DCA_TRIGGERED,
            bot_name="test_bot",
            data={
                "price": Decimal("45000.50"),
                "amount": Decimal("0.001"),
                "nested": {"value": Decimal("100.25")},
                "list_values": [Decimal("1.5"), Decimal("2.5")],
            },
        )

        json_str = event.to_json()
        parsed = json.loads(json_str)

        # All Decimals should be strings
        assert parsed["data"]["price"] == "45000.50"
        assert parsed["data"]["amount"] == "0.001"
        assert parsed["data"]["nested"]["value"] == "100.25"
        assert parsed["data"]["list_values"] == ["1.5", "2.5"]


class TestEventType:
    """Test EventType enum."""

    def test_event_types_exist(self):
        """Test that all expected event types exist."""
        expected_types = [
            "BOT_STARTED",
            "BOT_STOPPED",
            "BOT_PAUSED",
            "BOT_RESUMED",
            "BOT_EMERGENCY_STOP",
            "ORDER_PLACED",
            "ORDER_FILLED",
            "ORDER_CANCELLED",
            "ORDER_FAILED",
            "GRID_INITIALIZED",
            "GRID_REBALANCED",
            "DCA_TRIGGERED",
            "TAKE_PROFIT_HIT",
            "RISK_LIMIT_HIT",
            "STOP_LOSS_TRIGGERED",
            "PRICE_UPDATED",
            "ERROR_OCCURRED",
        ]

        for event_name in expected_types:
            assert hasattr(EventType, event_name)

    def test_event_type_values(self):
        """Test that event type values are lowercase with underscores."""
        assert EventType.BOT_STARTED.value == "bot_started"
        assert EventType.ORDER_FILLED.value == "order_filled"
        assert EventType.DCA_TRIGGERED.value == "dca_triggered"
