"""
Unit tests for scripts/run_scheduled_task.py -- the command Render Cron
Jobs run. No database needed: the helpers are pure and the task
registry is faked.
"""
import json

from scripts import run_scheduled_task as rst

BEAT = {
    "daily-a": {"task": "mod.task_a", "schedule": 86400},
    "daily-b": {"task": "mod.task_b", "schedule": 86400},
}


def test_allowed_names_come_from_the_beat_schedule():
    assert rst.allowed_task_names(BEAT) == {"mod.task_a", "mod.task_b"}


def test_refuses_a_task_that_is_not_scheduled(capsys):
    called = []
    registry = {"mod.evil": lambda: called.append(1)}
    assert rst.run("mod.evil", BEAT, registry) == 2
    assert called == []
    assert "Unknown or non-scheduled task" in capsys.readouterr().err


def test_scheduled_but_unregistered_task_is_a_usage_error(capsys):
    assert rst.run("mod.task_a", BEAT, {}) == 2
    assert "not registered" in capsys.readouterr().err


def test_clean_run_prints_json_summary_and_exits_zero(capsys):
    registry = {"mod.task_a": lambda: {"created": 3, "errors": []}}
    assert rst.run("mod.task_a", BEAT, registry) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"task": "mod.task_a", "status": "completed", "result": {"created": 3, "errors": []}}


def test_per_tenant_errors_make_the_run_fail(capsys):
    registry = {"mod.task_a": lambda: {"created": 1, "errors": [{"tenant_id": "t1", "error": "boom"}]}}
    assert rst.run("mod.task_a", BEAT, registry) == 1
    # Summary is still printed so the Render log shows which tenant failed.
    assert "boom" in capsys.readouterr().out


def test_a_crashing_task_exits_one_without_a_traceback_swallowing_the_cause(capsys):
    def boom():
        raise RuntimeError("db down")

    assert rst.run("mod.task_a", BEAT, {"mod.task_a": boom}) == 1
    assert "db down" in capsys.readouterr().err


def test_non_dict_results_count_as_success():
    assert rst.exit_code_for(None) == 0
    assert rst.exit_code_for("ok") == 0


def test_main_requires_exactly_one_argument(capsys):
    assert rst.main(["run_scheduled_task"]) == 2
    assert rst.main(["run_scheduled_task", "a", "b"]) == 2
