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

"""log_subreddit_comments tests"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from datetime import datetime
import json
import unittest

import log_subreddit_comments
from test_mocks import MockAuthor, MockComment


class LogSubredditCommentsTest(unittest.TestCase):

  def test_create_comment_output_record(self):
    comment = MockComment(comment_text='hello', parent_id='abc', link_id='def')
    record = log_subreddit_comments.create_comment_output_record(comment)
    self.assertEqual('hello', record['orig_comment_text'])
    self.assertEqual('abc', record['parent_id'])
    self.assertEqual('def', record['link_id'])
    # Check that record is JSON-serializable.
    json_record = json.dumps(record)
    self.assertIn('hello', json_record)

  def test_posix_timestamp(self):
    self.assertEqual(
        '20181005_183111',
        log_subreddit_comments.posix_timestamp(1538764271.067776))

  def test_datetime_timestamp(self):
    dt = datetime(2018, 10, 05, 1, 2, 3, 4)
    self.assertEqual(
        '20181005_010203',
        log_subreddit_comments.datetime_timestamp(dt))


if __name__ == '__main__':
    unittest.main()
