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

import unittest

from check_mod_actions import get_comment_status
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


if __name__ == '__main__':
    unittest.main()
