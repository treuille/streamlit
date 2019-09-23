# -*- coding: utf-8 -*-
# Copyright 2018-2019 Streamlit Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Magic unit test."""

import unittest
import ast
import sys

import streamlit.magic as magic

is_python_2 = sys.version_info[0] == 2


class MagicTest(unittest.TestCase):
    """Test for Magic
    The test counts the number of substitutions that magic.add_code do for
    a few code snippets. The test passes if the expected number of
    substitutions have been made.
    """

    def _testCode(self, code, expected_count):
        # Magic is not supported for python2.
        if is_python_2:
            return
        tree = magic.add_magic(code, "./")
        count = 0
        for node in ast.walk(tree):
            # count the nodes where a substitution has been made, i.e.
            # look for 'calls' to a 'streamlit' function
            if type(node) is ast.Call and "streamlit" in ast.dump(node.func):
                count += 1
        self.assertEqual(
            count,
            expected_count,
            ("There must be at least {} streamlit nodes," "but found {}").format(
                expected_count, count
            ),
        )

    def test_simple_statement(self):
        """Test simple statements"""
        CODE_SIMPLE_STATEMENTS = """
a = 1
b = 10
a
b
"""
        self._testCode(CODE_SIMPLE_STATEMENTS, 2)

    def test_if_statement(self):
        """Test if statements"""
        CODE_IF_STATEMENT = """
a = 1
if True:
    a
    if False:
        a
    elif False:
        a
    else:
        a
else:
    a
"""
        self._testCode(CODE_IF_STATEMENT, 5)

    def test_for_statement(self):
        """Test for statements"""
        CODE_FOR_STATEMENT = """
a = 1
for i in range(10):
    for j in range(2):
        a

"""
        self._testCode(CODE_FOR_STATEMENT, 1)

    def test_try_statement(self):
        """Test try statements"""
        CODE_TRY_STATEMENT = """
try:
    a = 10
    a
except Exception:
    try:
        a
    finally:
        a
finally:
    a
"""
        self._testCode(CODE_TRY_STATEMENT, 4)

    def test_function_call_statement(self):
        """Test with function calls"""
        CODE_FUNCTION_CALL = """
def myfunc(a):
    a
a =10
myfunc(a)
"""
        self._testCode(CODE_FUNCTION_CALL, 1)

    def test_with_statement(self):
        """Test with 'with' statements"""
        CODE_WITH_STATEMENT = """
a = 10
with None:
    a
"""
        self._testCode(CODE_WITH_STATEMENT, 1)
