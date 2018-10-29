# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""check_mod_actions tests"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
import StringIO

import StringIO
import unittest

import dedup_logs


class DedupLogsTest(unittest.TestCase):

  def test_get_counts_all_unique(self):
    input_handle = StringIO.StringIO('{"id": "1"}\n{"id": "2"}\n{"id": "3"}')
    total, unique = dedup_logs.get_counts(input_handle, 'id')
    self.assertEqual(3, total)
    self.assertEqual(3, unique)

  def test_get_counts_dupes(self):
    input_handle = StringIO.StringIO('{"id": "1"}\n{"id": "2"}\n{"id": "1"}')
    total, unique = dedup_logs.get_counts(input_handle, 'id')
    self.assertEqual(3, total)
    self.assertEqual(2, unique)

  def test_dedup_stream_all_unique(self):
    lines = ['{"id": "1"}\n', '{"id": "2"}\n', '{"id": "3"}\n']
    input_handle = StringIO.StringIO(''.join(lines))
    deduped = list(dedup_logs.dedup_stream(
        input_handle, 'id', window=10, expected_total=3, expected_unique=3))
    self.assertEqual(lines, deduped)

  def test_dedup_stream_dupes(self):
    unique_lines = ['{"id": "1"}\n', '{"id": "2"}\n']
    lines = unique_lines * 2
    input_handle = StringIO.StringIO(''.join(lines))
    deduped = list(dedup_logs.dedup_stream(
        input_handle, 'id', window=10, expected_total=4, expected_unique=2))
    self.assertEqual(unique_lines, deduped)

  def test_dedup_stream_raise_on_unexpected_dupes(self):
    # The window is not long enough to catch the duplicates, resulting in an
    # exception.
    input_handle = StringIO.StringIO('{"id": "1"}\n{"id": "2"}\n{"id": "1"}')
    with self.assertRaises(ValueError):
      # list() is needed to force the generator to run.
      list(dedup_logs.dedup_stream(
          input_handle, 'id', window=1, expected_total=3, expected_unique=2))


if __name__ == '__main__':
    unittest.main()
