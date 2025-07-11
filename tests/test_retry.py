import logging
import time
import uuid
from contextlib import AbstractContextManager
from types import TracebackType
from typing import Type

import rnsh.retry

logging.getLogger().setLevel(logging.DEBUG)


class State(AbstractContextManager):
    def __init__(self, delay: float):
        self.delay = delay
        self.retry_thread = rnsh.retry.RetryThread(self.delay / 10.0)
        self.tries = 0
        self.callbacks = 0
        self.timed_out = False
        self.tag = str(uuid.uuid4())
        self.results = [self.tag, self.tag, self.tag]
        self.got_tag = None
        assert self.retry_thread.is_alive()

    def cleanup(self):
        self.retry_thread.wait()
        assert self.tries != 0
        self.retry_thread.close()
        assert not self.retry_thread.is_alive()

    def retry(self, tag, tries):
        self.tries = tries
        self.got_tag = tag
        self.callbacks += 1
        return self.results[tries - 1]

    def timeout(self, tag, tries):
        self.tries = tries
        self.got_tag = tag
        self.timed_out = True
        self.callbacks += 1

    def __exit__(self, __exc_type: Type[BaseException], __exc_value: BaseException,
                 __traceback: TracebackType) -> bool:
        self.cleanup()
        return False


def test_retry_timeout():

    with State(0.1) as state:
        return_tag = state.retry_thread.begin(try_limit=3,
                                              wait_delay=state.delay,
                                              try_callback=state.retry,
                                              timeout_callback=state.timeout)
        assert return_tag == state.tag
        assert state.tries == 1
        assert state.callbacks == 1
        assert state.got_tag is None
        assert not state.timed_out
        time.sleep(state.delay / 2.0)
        time.sleep(state.delay)
        assert state.tries == 2
        assert state.callbacks == 2
        assert state.got_tag == state.tag
        assert not state.timed_out
        time.sleep(state.delay)
        assert state.tries == 3
        assert state.callbacks == 3
        assert state.got_tag == state.tag
        assert not state.timed_out

        # check timeout
        time.sleep(state.delay)
        assert state.tries == 3
        assert state.callbacks == 4
        assert state.got_tag == state.tag
        assert state.timed_out

        # check no more callbacks
        time.sleep(state.delay * 3.0)
        assert state.callbacks == 4
        assert state.tries == 3


def test_retry_immediate_complete():
    with State(0.01) as state:
        state.results[0] = False
        return_tag = state.retry_thread.begin(try_limit=3,
                                              wait_delay=state.delay,
                                              try_callback=state.retry,
                                              timeout_callback=state.timeout)
        assert not return_tag
        assert state.callbacks == 1
        assert not state.got_tag
        assert not state.timed_out
        time.sleep(state.delay * 3)
        assert state.tries == 1
        assert state.callbacks == 1
        assert not state.got_tag
        assert not state.timed_out


def test_retry_return_complete():
    with State(0.01) as state:
        state.results[1] = False
        return_tag = state.retry_thread.begin(try_limit=3,
                                              wait_delay=state.delay,
                                              try_callback=state.retry,
                                              timeout_callback=state.timeout)
        assert return_tag == state.tag
        assert state.callbacks == 1
        assert state.got_tag is None
        assert not state.timed_out
        time.sleep(state.delay / 2.0)
        time.sleep(state.delay)
        assert state.tries == 2
        assert state.callbacks == 2
        assert state.got_tag == state.tag
        assert not state.timed_out

        time.sleep(state.delay)
        assert state.tries == 2
        assert state.callbacks == 2
        assert state.got_tag == state.tag
        assert not state.timed_out

        # check no more callbacks
        time.sleep(state.delay * 3.0)
        assert state.callbacks == 2
        assert state.tries == 2


def test_retry_set_complete():
    with State(0.01) as state:
        return_tag = state.retry_thread.begin(try_limit=3,
                                              wait_delay=state.delay,
                                              try_callback=state.retry,
                                              timeout_callback=state.timeout)
        assert return_tag == state.tag
        assert state.callbacks == 1
        assert state.got_tag is None
        assert not state.timed_out
        time.sleep(state.delay / 2.0)
        time.sleep(state.delay)
        assert state.tries == 2
        assert state.callbacks == 2
        assert state.got_tag == state.tag
        assert not state.timed_out

        state.retry_thread.complete(state.tag)

        time.sleep(state.delay)
        assert state.tries == 2
        assert state.callbacks == 2
        assert state.got_tag == state.tag
        assert not state.timed_out

        # check no more callbacks
        time.sleep(state.delay * 3.0)
        assert state.callbacks == 2
        assert state.tries == 2

