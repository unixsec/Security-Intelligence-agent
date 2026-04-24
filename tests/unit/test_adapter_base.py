"""Unit tests for sia.adapters.base — Registry + BaseAdapter contract."""

from __future__ import annotations

import pytest

from sia.adapters.base import (
    AdapterConfig,
    AdapterConfigError,
    AdapterError,
    BaseAdapter,
    Registry,
)


class _FakeAdapter(BaseAdapter):
    async def _do(self, payload=None):
        if payload == "boom":
            raise RuntimeError("oops")
        if payload == "bug":
            raise AdapterError("explicit")
        return {"echo": payload}


class TestAdapterConfig:
    def test_require_returns_value(self):
        c = AdapterConfig({"url": "x"})
        assert c.require("url") == "x"

    @pytest.mark.parametrize("bad", [{}, {"url": ""}, {"url": None}])
    def test_require_raises_when_missing(self, bad):
        c = AdapterConfig(bad)
        with pytest.raises(AdapterConfigError):
            c.require("url")

    def test_require_type_check(self):
        c = AdapterConfig({"port": "80"})
        with pytest.raises(AdapterConfigError, match="wrong type"):
            c.require("port", int)

    def test_opt_default(self):
        c = AdapterConfig({})
        assert c.opt("missing", "fallback") == "fallback"


class TestRegistry:
    def _fresh(self):
        return Registry[_FakeAdapter]("test")

    def test_register_and_build(self):
        r = self._fresh()

        @r.register("fake")
        class F(_FakeAdapter):
            pass

        assert "fake" in list(r.kinds())
        assert F.kind == "fake"
        inst = r.build("fake", {"url": "y"})
        assert isinstance(inst, F)

    def test_double_registration_errors(self):
        r = self._fresh()
        r.register("fake")(type("A", (_FakeAdapter,), {}))
        with pytest.raises(RuntimeError, match="already registered"):
            r.register("fake")(type("B", (_FakeAdapter,), {}))

    def test_unknown_kind(self):
        r = self._fresh()
        with pytest.raises(AdapterConfigError, match="unknown"):
            r.get("nonexistent")


class TestBaseAdapterRun:
    @pytest.mark.asyncio
    async def test_run_success_translates_nothing(self):
        a = _FakeAdapter({}, name="n")
        out = await a.run("hello")
        assert out == {"echo": "hello"}

    @pytest.mark.asyncio
    async def test_run_wraps_unknown_exception_as_adapter_error(self):
        a = _FakeAdapter({}, name="n")
        with pytest.raises(AdapterError, match="oops"):
            await a.run("boom")

    @pytest.mark.asyncio
    async def test_run_passes_through_adapter_error(self):
        a = _FakeAdapter({}, name="n")
        with pytest.raises(AdapterError, match="explicit"):
            await a.run("bug")

    def test_name_defaults_to_kind(self):
        a = _FakeAdapter({})
        assert a.name == a.kind or a.name == ""  # kind may be "" on unregistered
