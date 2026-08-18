"""
Regression test for a real bug: create_app() (what gunicorn actually
runs for the live web service, via wsgi.py) previously never
configured the Celery instance at all -- only the separate worker
script (app/celery_app.py) did. Every .delay() call made from within
a live request (creating an invitation, sending a notification) was
queuing against Celery's unconfigured default broker
(amqp://guest@localhost//), completely disconnected from the real
Redis broker configured via REDIS_URL/CELERY_BROKER_URL. This is
exactly what "the invitation was created successfully but the email
never arrived" looks like from the outside -- confirmed as the real
cause, not guessed, by checking create_app()'s actual code before
writing this fix.
"""


class TestCeleryIsConfiguredByTheRealAppFactory:
    def test_create_app_configures_the_real_broker_url(self, app):
        """The exact regression: previously celery.conf.broker_url
        was Celery's unconfigured default after create_app() ran, not
        the real value from app.config['CELERY_BROKER_URL']."""
        from app.extensions import celery

        assert celery.conf.broker_url == app.config["CELERY_BROKER_URL"]
        assert celery.conf.broker_url != "amqp://guest@localhost//"

    def test_create_app_configures_the_real_result_backend(self, app):
        from app.extensions import celery

        assert celery.conf.result_backend == app.config["CELERY_RESULT_BACKEND"]

    def test_task_always_eager_reflects_the_real_config_value(self, app):
        """CELERY_TASK_ALWAYS_EAGER (app/config.py) -- the real,
        opt-in fix for a deployment with no separate worker process at
        all (e.g. Render's free tier)."""
        from app.extensions import celery

        assert celery.conf.task_always_eager == app.config["CELERY_TASK_ALWAYS_EAGER"]

    def test_eager_mode_runs_a_real_task_synchronously_with_no_worker(self, app):
        """The real, end-to-end proof this fix actually solves the
        reported problem: with eager mode on, a real task genuinely
        executes inline -- no separate worker process needed at all."""
        app.config["CELERY_TASK_ALWAYS_EAGER"] = True
        from app.extensions import celery, configure_celery

        configure_celery(app)
        assert celery.conf.task_always_eager is True

        from unittest.mock import patch

        with app.app_context():
            with patch("app.notifications.tasks.send_email") as mock_send:
                mock_send.return_value = True
                from app.notifications.tasks import send_email_notification

                result = send_email_notification.delay(to_address="test@example.com", subject="s", body="b")
                # .ready() being True with no worker running anywhere
                # in this test process is only possible because the
                # task actually ran synchronously, in-process, right
                # here -- proving eager mode is genuinely wired up,
                # not just set as an unused config value.
                assert result.ready() is True
                mock_send.assert_called_once()

        app.config["CELERY_TASK_ALWAYS_EAGER"] = False
        configure_celery(app)
