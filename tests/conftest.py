"""Outils communs aux tests.

Les tests n'utilisent jamais le vrai réseau : on simule les réponses des
sites avec `httpx.MockTransport`. Ils sont donc rapides et reproductibles.
"""

from collections.abc import Callable

import httpx
import pytest


@pytest.fixture
def mock_client() -> Callable[[Callable[[httpx.Request], httpx.Response]], httpx.AsyncClient]:
    def make(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    return make
