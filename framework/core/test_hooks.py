import pytest
from framework.core.hooks import HookPoint, HookRegistry, HookContext, HookOutcome
from framework.shared.exceptions import HookError


def test_hook_point_properties():
    # Verify is_before works correctly
    assert HookPoint.BEFORE_COLLECTOR.is_before is True
    assert HookPoint.AFTER_COLLECTOR.is_before is False
    assert HookPoint.BEFORE_PLUGIN.is_before is True
    assert HookPoint.AFTER_PLUGIN.is_before is False

    # Verify counterpart mappings
    assert HookPoint.BEFORE_COLLECTOR.counterpart == HookPoint.AFTER_COLLECTOR
    assert HookPoint.AFTER_COLLECTOR.counterpart == HookPoint.BEFORE_COLLECTOR
    assert HookPoint.BEFORE_NORMALIZER.counterpart == HookPoint.AFTER_NORMALIZER
    assert HookPoint.AFTER_NORMALIZER.counterpart == HookPoint.BEFORE_NORMALIZER
    assert HookPoint.BEFORE_VALIDATOR.counterpart == HookPoint.AFTER_VALIDATOR
    assert HookPoint.AFTER_VALIDATOR.counterpart == HookPoint.BEFORE_VALIDATOR
    assert HookPoint.BEFORE_CORRELATOR.counterpart == HookPoint.AFTER_CORRELATOR
    assert HookPoint.AFTER_CORRELATOR.counterpart == HookPoint.BEFORE_CORRELATOR
    assert HookPoint.BEFORE_PLUGIN.counterpart == HookPoint.AFTER_PLUGIN
    assert HookPoint.AFTER_PLUGIN.counterpart == HookPoint.BEFORE_PLUGIN
    assert HookPoint.BEFORE_RUN.counterpart == HookPoint.AFTER_RUN
    assert HookPoint.AFTER_RUN.counterpart == HookPoint.BEFORE_RUN


def test_hook_registry_registration():
    registry = HookRegistry()
    assert len(registry) == 0

    def dummy_callback(context: HookContext) -> None:
        pass

    hook = registry.register(HookPoint.BEFORE_RUN, dummy_callback, name="dummy")
    assert len(registry) == 1
    assert hook.name == "dummy"
    assert hook.point == HookPoint.BEFORE_RUN
    assert hook.callback == dummy_callback

    # Test auto name generation
    hook2 = registry.register(HookPoint.AFTER_RUN, dummy_callback)
    assert len(registry) == 2
    assert hook2.name == "dummy_callback"


def test_hook_registry_unregistration():
    registry = HookRegistry()

    def cb(context: HookContext) -> None:
        pass

    hook = registry.register(HookPoint.BEFORE_RUN, cb)
    assert len(registry) == 1

    removed = registry.unregister(hook)
    assert removed is True
    assert len(registry) == 0

    # Unregistering twice returns False
    removed_again = registry.unregister(hook)
    assert removed_again is False


def test_hook_registry_clear():
    registry = HookRegistry()
    def cb(context: HookContext) -> None:
        pass

    registry.register(HookPoint.BEFORE_RUN, cb)
    registry.register(HookPoint.AFTER_RUN, cb)
    assert len(registry) == 2

    registry.clear()
    assert len(registry) == 0


def test_hook_registry_priority_order():
    registry = HookRegistry()
    order = []

    def cb1(context: HookContext) -> None:
        order.append(1)

    def cb2(context: HookContext) -> None:
        order.append(2)

    def cb3(context: HookContext) -> None:
        order.append(3)

    registry.register(HookPoint.BEFORE_RUN, cb1, priority=200)
    registry.register(HookPoint.BEFORE_RUN, cb2, priority=50)
    registry.register(HookPoint.BEFORE_RUN, cb3, priority=100)

    # Calling hooks_at should return in sorted priority order: 50, then 100, then 200
    hooks = registry.hooks_at(HookPoint.BEFORE_RUN)
    assert [h.priority for h in hooks] == [50, 100, 200]

    registry.invoke(HookPoint.BEFORE_RUN, "test_target")
    assert order == [2, 3, 1]


def test_hook_registry_isolation():
    registry = HookRegistry()
    order = []

    def cb_success(context: HookContext) -> None:
        order.append("success")

    def cb_fail(context: HookContext) -> None:
        order.append("fail")
        raise ValueError("Simulated error")

    registry.register(HookPoint.BEFORE_RUN, cb_success)
    registry.register(HookPoint.BEFORE_RUN, cb_fail)

    outcome = registry.invoke(HookPoint.BEFORE_RUN, "test_target")
    assert len(outcome.errors) == 1
    assert isinstance(outcome.errors[0], ValueError)
    assert order == ["success", "fail"]


def test_hook_registry_error_propagation():
    registry = HookRegistry()

    def cb_fail(context: HookContext) -> None:
        raise ValueError("Simulated error")

    registry.register(HookPoint.BEFORE_RUN, cb_fail, required=True)

    with pytest.raises(HookError) as exc_info:
        registry.invoke(HookPoint.BEFORE_RUN, "test_target")

    assert "Required hook failed" in str(exc_info.value)


def test_hook_registry_veto():
    registry = HookRegistry()

    def cb_veto(context: HookContext) -> str:
        return "Not allowed"

    def cb_after_veto(context: HookContext) -> None:
        pass

    registry.register(HookPoint.BEFORE_RUN, cb_veto, priority=10)
    registry.register(HookPoint.BEFORE_RUN, cb_after_veto, priority=20)

    outcome = registry.invoke(HookPoint.BEFORE_RUN, "test_target")
    assert outcome.vetoed is True
    assert outcome.veto_reason == "Not allowed"
    # The outcome shows the total number of registered hooks
    assert outcome.invoked == 2
