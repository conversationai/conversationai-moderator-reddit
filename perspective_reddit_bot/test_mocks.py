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

"""Mocks for testing."""


# TODO: Check if PRAW provides mocks, which would let us get rid of these.


class MockAuthor(object):
  def __init__(self, name):
    self.name = name


class MockComment(object):
  def __init__(self, comment_text='hello', parent_id='pid', link_id='lid',
               approved=False, removed=False):
    self.id = 'cid'
    self.parent_id = parent_id
    self.link_id = link_id
    self.subreddit = 'SubReddit'
    self.permalink = 'r/SubReddit/blahblah'
    self.body = comment_text
    self.author = MockAuthor('username')
    self.created_utc = 123
    self.approved = approved
    self.removed = removed
