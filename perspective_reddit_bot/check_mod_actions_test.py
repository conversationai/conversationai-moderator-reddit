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
import unittest

from check_mod_actions import get_comment_status, seek_past_ids
from test_mocks import MockComment


# Helper function to drop extraneous fields.
def _get_comment_status_mod_fields(comment, has_mod_creds):
  _cid, status_record = get_comment_status(comment, has_mod_creds)
  return {
      k: status_record[k]
      for k in ['approved', 'removed', 'deleted']
      if k in status_record
  }


class CheckModActionsTest(unittest.TestCase):

  def test_get_comment_status_normal_no_mod_creds(self):
    normal_comment = MockComment()
    self.assertEqual(
        {'removed': False, 'deleted': False},
        _get_comment_status_mod_fields(normal_comment, has_mod_creds=False))

  def test_get_comment_status_normal_has_mod_creds(self):
    normal_comment = MockComment()
    self.assertEqual(
        {'approved': False, 'removed': False, 'deleted': False},
        _get_comment_status_mod_fields(normal_comment, has_mod_creds=True))

  def test_get_comment_status_deleted_no_mod_creds(self):
    deleted_comment = MockComment(comment_text='[deleted]')
    deleted_comment.author = None
    self.assertEqual(
        {'removed': False, 'deleted': True},
        _get_comment_status_mod_fields(deleted_comment, has_mod_creds=False))

  def test_get_comment_status_deleted_has_mod_creds(self):
    deleted_comment = MockComment(comment_text='[deleted]')
    deleted_comment.author = None
    self.assertEqual(
        {'approved': False, 'removed': False, 'deleted': True},
        _get_comment_status_mod_fields(deleted_comment, has_mod_creds=True))

  def test_get_comment_status_removed_no_mod_creds(self):
    removed_comment = MockComment(comment_text='[removed]')
    removed_comment.author = None
    self.assertEqual(
        {'removed': True, 'deleted': False},
        _get_comment_status_mod_fields(removed_comment, has_mod_creds=False))

  def test_get_comment_status_removed_has_mod_creds(self):
    # If we have mod creds, we don't look at the comment_text to determine if
    # the comment is removed - we only check the 'removed' field.
    removed_comment = MockComment(comment_text='[removed]', removed=True)
    removed_comment.author = None
    self.assertEqual(
        {'approved': False, 'removed': True, 'deleted': False},
        _get_comment_status_mod_fields(removed_comment, has_mod_creds=True))

  def test_get_comment_status_approved_has_mod_creds(self):
    approved_comment = MockComment(approved=True)
    self.assertEqual(
        {'approved': True, 'removed': False, 'deleted': False},
         _get_comment_status_mod_fields(approved_comment, has_mod_creds=True))

  def test_seek_past_ids_success(self):
    input_handle = StringIO.StringIO(
        '{"comment_id": "1"}\n{"comment_id": "2"}\n')
    seek_past_ids(input_handle, {"1"})
    self.assertEqual('{"comment_id": "2"}\n', input_handle.readline())
    self.assertEqual('', input_handle.readline())

  def test_seek_past_ids_error_reached_eof(self):
    buf = '{"comment_id": "1"}\n{"comment_id": "2"}\n'
    input_handle = StringIO.StringIO(buf)
    with self.assertRaises(ValueError):
      seek_past_ids(input_handle, {"1", "2"})
    # Reached end of buffer.
    self.assertEqual(len(buf), input_handle.tell())

  def test_seek_past_ids_error_unexpected_skips(self):
    input_handle = StringIO.StringIO(
        '{"comment_id": "1"}\n{"comment_id": "2"}\n')
    with self.assertRaises(ValueError):
      # This fails because record 1 isn't in ids_to_skip, so we don't skip any
      # IDs, but we expected to skip 1.
      seek_past_ids(input_handle, {"2"})


if __name__ == '__main__':
    unittest.main()
