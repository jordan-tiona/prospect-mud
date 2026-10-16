"""
Test runner that supports Django's --parallel on Windows.

Windows starts each parallel worker as a fresh process, and Django's
worker setup only calls django.setup() - so Evennia's API (create_object,
search_tag, ...) is still None in the workers. This runner also calls
evennia._init() in each worker, as EvenniaTestSuiteRunner does in the
main process.

Used by run_tests.sh / run_tests.bat via --testrunner; not set as
TEST_RUNNER, so plain `evennia test` is unchanged.
"""

import traceback

from django.test.runner import ParallelTestSuite, RemoteTestResult, RemoteTestRunner, _init_worker
from evennia.server.tests.testrunner import EvenniaTestSuiteRunner


class RemoteError(Exception):
    """A worker's exception, flattened to its formatted traceback text."""

    def __str__(self):
        return self.args[0] if self.args else ""


def _flatten(err):
    """Tracebacks can't be pickled back to the main process without the
    optional tblib package; send the formatted text instead, so failures
    still name the test and line."""
    if err is None:
        return None
    return (RemoteError, RemoteError("".join(traceback.format_exception(*err)).rstrip()), None)


class TextTracebackResult(RemoteTestResult):
    def addError(self, test, err):
        super().addError(test, _flatten(err))

    def addFailure(self, test, err):
        super().addFailure(test, _flatten(err))

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, _flatten(err))

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, _flatten(err))


class TextTracebackRunner(RemoteTestRunner):
    resultclass = TextTracebackResult


def _init_evennia_worker(*args, **kwargs):
    _init_worker(*args, **kwargs)
    import evennia

    evennia._init()

    from django.conf import settings

    settings.TEST_ENVIRONMENT = True


class EvenniaParallelTestSuite(ParallelTestSuite):
    init_worker = _init_evennia_worker
    runner_class = TextTracebackRunner


class ParallelEvenniaTestSuiteRunner(EvenniaTestSuiteRunner):
    parallel_test_suite = EvenniaParallelTestSuite
