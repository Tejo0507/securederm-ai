"""Stopping a run before it has taken its first step must still end it."""

import asyncio

from web_backend.routers import training_router

HOSPITAL_ID = 987_654_000   # no real account has this id


def test_a_run_cancelled_before_it_starts_is_not_left_active():
    async def scenario():
        task = training_router._launch_simulation(HOSPITAL_ID, "Early Stop Clinic")
        task.cancel()   # no await in between: the coroutine never runs
        await asyncio.gather(task, return_exceptions=True)
        await asyncio.sleep(0)   # let the done callback run
        return task

    try:
        task = asyncio.run(scenario())
        state = training_router._training_state[HOSPITAL_ID]
        assert state["active"] is False
        assert state["logs"] == ["■ Training stopped."]
        assert HOSPITAL_ID not in training_router._running
        assert task not in training_router._background_tasks
    finally:
        training_router.forget_hospital(HOSPITAL_ID)
