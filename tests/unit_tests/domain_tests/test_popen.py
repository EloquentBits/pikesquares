from subprocess import PIPE
from unittest import TestCase

from testfixtures import Replacer, ShouldRaise, compare
from testfixtures.mock import call
from testfixtures.popen import MockPopen

from pikesquares.domain.popen_testing import my_func


class TestMyFunc(TestCase):

    def setUp(self):
        self.Popen = MockPopen()
        self.r = Replacer()
        self.r.replace("pikesquares.domain.popen_testing.Popen", self.Popen)
        self.addCleanup(self.r.restore)

    def test_example(self):
        # set up
        self.Popen.set_command('git log -n 1', stdout=b'o', stderr=b'e')

        # testing of results
        compare(my_func(), b'o')

        # testing calls were in the right order and with the correct parameters:
        process = call.Popen(['git', 'log', '-n', '1'], stderr=PIPE, stdout=PIPE)
        compare(self.Popen.all_calls, expected=[process, process.communicate()])

    def test_example_bad_returncode(self):
        # set up
        self.Popen.set_command('git log -n 1', stdout=b'o', stderr=b'e', returncode=1)

        # testing of error
        with ShouldRaise(RuntimeError('something bad happened')):
            my_func()
