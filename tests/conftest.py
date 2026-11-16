"""Shared test helpers. Tests never use the internet: they use the MOCK replay file and FakeExchange."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
