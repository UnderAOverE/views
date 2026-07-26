What changed (the new contract)
ZelleService.get_service(cls, mongo_client, settings, email_service) — the factory, exactly like OSEFetchService.get_service. Builds the graph from mongo_client (DB picked via settings.mongo_database_name), owns its mTLS client.
No more register_zelle. Instead: service.startup_sweep(), service.start_watchdog() (an asyncio.create_task, like your monitor_task), and service.aclose() for teardown.
add_zelle_exception_handlers(app) registers the error handlers.
In main.py (where you create the app + include ose/saas routers)

from src.apis.routes import zelle_events_router, zelle_admin_router
from src.apis.dependencies.services.zelle import add_zelle_exception_handlers

app.include_router(zelle_events_router)
app.include_router(zelle_admin_router)
add_zelle_exception_handlers(app)
In initializer.py — imports

from src.apis.config.zelle import ZelleSettings
from src.apis.services.zelle.service import ZelleService
from src.common.constants import IS_PRODUCTION_ENVIRONMENT   # your path
In initializer.py — top of lifespan (with your other declarations)

    zelle_service: ZelleService | None = None
In the try: block — after mongo_client and email_service exist (exactly like your OSE services)

        # Create zelle service (get_service factory, like OSEFetchService)
        zelle_service = await ZelleService.get_service(
            mongo_client=mongo_client,
            settings=ZelleSettings(is_production=IS_PRODUCTION_ENVIRONMENT),
            email_service=email_service,
        )
        application.state.zelle_service = zelle_service  # noqa
        await zelle_service.startup_sweep()
        zelle_service.start_watchdog()
In the finally: block — next to your monitor_task cleanup

        # Zelle teardown: stop watchdog + close its mTLS client
        if zelle_service:
            await zelle_service.aclose()
Notes for your setup
Everything except is_production comes from ZELLE_* env vars in the container: ZELLE_MONGO_DATABASE_NAME (now required — which DB the zelle_* collections live in), ZELLE_TOKEN_AUD, ZELLE_CLIENT_ID, ZELLE_SIGNING_KID, ZELLE_SIGNING_KEY_PATH, ZELLE_ORG_ID, ZELLE_CONTACT_*, and the mTLS paths (ZELLE_CA_CERTIFICATE_PATH, ZELLE_CLIENT_CERTIFICATE_PATH, ZELLE_CLIENT_KEY_PATH).
It takes your mongo_client (the AsyncIOMotorClient) directly — no get_default_database() needed; it selects the DB by name from settings.
55 tests / ruff / mypy all green; the tests now wire the app the same host way (include routers → add_zelle_exception_handlers → get_service → startup_sweep), so the test suite exercises exactly this integration path.
One deviation from fetch.py I want to flag honestly: your OSEFetchService.get_service(cls, mongo_client) takes only mongo_client (it reads settings from the global environment_settings.ose). Zelle's get_service also takes settings and email_service as params, because its config is injected by the host (the is_production flag from your constant, and your EmailService) rather than read from a global. If you'd rather it read a module-level zelle_settings to match the signature exactly, tell me and I'll switch it.





main.py (where you create the app + include ose/saas routers)

from src.apis.routes import zelle_events_router, zelle_admin_router
from src.apis.dependencies.services.zelle import add_zelle_exception_handlers

app.include_router(zelle_events_router)
app.include_router(zelle_admin_router)
add_zelle_exception_handlers(app)
initializer.py — import

from src.apis.services.zelle.service import ZelleService
initializer.py — top of lifespan

    zelle_service: ZelleService | None = None
In the try: block — after mongo_client and email_service exist (now truly like your OSE services)

        # Create zelle service (get_service factory, like OSEFetchService)
        zelle_service = await ZelleService.get_service(
            mongo_client=mongo_client,
            email_service=email_service,
        )
        application.state.zelle_service = zelle_service  # noqa
        await zelle_service.startup_sweep()
        zelle_service.start_watchdog()
In the finally: block

        # Zelle teardown: stop watchdog + close its mTLS client
        if zelle_service:
            await zelle_service.aclose()
The one thing to decide: how is_production gets set
Because settings now come from the module-level accessor (reading ZELLE_* env), is_production comes from the ZELLE_IS_PRODUCTION env var. Two ways:

Pure module-level (matches fetch.py exactly): set ZELLE_IS_PRODUCTION in the deployment env from your IS_PRODUCTION_ENVIRONMENT. Then the lifespan call is just get_service(mongo_client=…, email_service=…) as above.
Keep passing the constant: inject settings for that one call —

from src.apis.config.zelle import ZelleSettings
from src.common.constants import IS_PRODUCTION_ENVIRONMENT
zelle_service = await ZelleService.get_service(
    mongo_client=mongo_client,
    email_service=email_service,
    settings=ZelleSettings(is_production=IS_PRODUCTION_ENVIRONMENT),
)
Both work — the first is the cleaner fetch.py match; the second reuses your Python prod constant directly.

Status
get_service(cls, mongo_client, email_service=None, settings=None, http_client=None) — mongo_client first, settings default to get_zelle_settings() (module-level), the rest optional for email/tests.
Everything else (ZELLE_MONGO_DATABASE_NAME, token/signing/org/contact/mTLS paths) comes from ZELLE_* env vars.
55 tests / ruff / mypy green; pushed to main (4fb77db).
That's the full host-standard alignment: get_service factory reading module-level settings, created + swept + watchdog-started in the lifespan, aclose() in finally, routers + add_zelle_exception_handlers in main.py.
