# Importing this package's submodules runs each one's module-level
# @register_fetcher(...) decorators, populating
# agent.fetcher_registry.CUSTOM_FETCHERS. This is the one place a new
# site module needs to be added — see docs/adding-a-source.md.
from agent.fetchers import acb  # noqa: F401
from agent.fetchers import bidv  # noqa: F401
from agent.fetchers import decisionlab  # noqa: F401
from agent.fetchers import iav  # noqa: F401
from agent.fetchers import mbbank  # noqa: F401
from agent.fetchers import nso  # noqa: F401
from agent.fetchers import ssi  # noqa: F401
from agent.fetchers import techcombank  # noqa: F401
from agent.fetchers import vcbs  # noqa: F401
from agent.fetchers import vietcombank  # noqa: F401
from agent.fetchers import vpbank  # noqa: F401
