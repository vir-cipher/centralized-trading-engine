"""plugin/openapi.json is what other teams build against. It must match the running code exactly."""
import json
from pathlib import Path

from engine.api import create_app


def test_committed_contract_matches_code():
    committed = json.loads((Path(__file__).resolve().parent.parent / "plugin" / "openapi.json").read_text(encoding="utf-8"))
    assert create_app(start_background=False).openapi() == committed


def test_every_route_in_the_proposal_is_published():
    paths = json.loads((Path(__file__).resolve().parent.parent / "plugin" / "openapi.json").read_text(encoding="utf-8"))["paths"]
    for p in ["/prices/{symbol}", "/candles", "/account/balance", "/orders", "/orders/{order_id}", "/signals/{symbol}"]:
        assert p in paths, p
