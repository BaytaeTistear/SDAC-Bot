import os


SENTRY_ENABLED = False


def init_sentry(service_name):
    global SENTRY_ENABLED
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return False

    try:
        import sentry_sdk
    except ImportError:
        print(
            "SENTRY_DSN is set but sentry-sdk is not installed.",
            flush=True,
        )
        return False

    kwargs = {
        "dsn": dsn,
        "environment": os.getenv("SENTRY_ENVIRONMENT", "production"),
        "server_name": os.getenv("SDAC_SERVER_NAME", service_name),
        "send_default_pii": False,
    }
    release = os.getenv("SDAC_RELEASE", "").strip()
    if release:
        kwargs["release"] = release
    sample_rate = os.getenv("SENTRY_TRACES_SAMPLE_RATE", "").strip()
    if sample_rate:
        try:
            kwargs["traces_sample_rate"] = float(sample_rate)
        except ValueError:
            print(
                "Ignoring invalid SENTRY_TRACES_SAMPLE_RATE.",
                flush=True,
            )

    if service_name == "sdac-dashboard":
        try:
            from sentry_sdk.integrations.flask import FlaskIntegration
            kwargs["integrations"] = [FlaskIntegration()]
        except ImportError:
            pass

    sentry_sdk.init(**kwargs)
    SENTRY_ENABLED = True
    print(f"Sentry enabled for {service_name}.", flush=True)
    return True


def capture_exception(error):
    if not SENTRY_ENABLED:
        return
    try:
        import sentry_sdk
        sentry_sdk.capture_exception(error)
    except Exception:
        pass
