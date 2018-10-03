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

"""A class for checking and applying moderation rules."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import unittest

from moderate_subreddit import remove_quotes, check_rules, create_output_record
from perspective_rule import Rule


class MockAuthor(object):
  def __init__(self, name):
    self.name = name


class MockComment(object):
  def __init__(self, comment_text):
    self.id = 'cid'
    self.parent_id = 'pid'
    self.link_id = 'lid'
    self.subreddit = 'SubReddit'
    self.permalink = 'r/SubReddit/blahblah'
    self.body = comment_text
    self.author = MockAuthor('username')
    self.created_utc = 123


class ModerateSubredditTest(unittest.TestCase):

  def test_remove_quotes(self):
    comment_without_quoting = 'hi\nyay'
    self.assertEqual(comment_without_quoting,
                     remove_quotes(comment_without_quoting))
    comment_with_quoting = '> hi\nhello there'
    self.assertEqual('hello there',
                     remove_quotes(comment_with_quoting))
    comment_with_lots_of_quoting = '''> hi
>blah
hello there
> yuck
gross'''
    self.assertEqual('hello there\ngross',
                     remove_quotes(comment_with_lots_of_quoting))

  def test_check_rules_simple(self):
    comment = None  # Comment features aren't used by this test.
    scores = { 'TOXICITY': 0.9 }
    rules = [
        Rule('hi_tox', {'TOXICITY': '> 0.5'}, {}, 'report'),
    ]
    actions = check_rules(comment, rules, scores)
    self.assertEqual(['report'], actions.keys())
    self.assertEqual(['hi_tox'], [r.name for r in actions['report']])

  def test_check_rules_multiple_triggered_rules(self):
    comment = None  # Comment features aren't used by this test.
    # hi_tox and hi_spam are triggered, but not hi_threat.
    scores = { 'TOXICITY': 0.9, 'SPAM': 0.9, 'THREAT': 0.2 }
    rules = [
        Rule('hi_tox', {'TOXICITY': '> 0.5'}, {}, 'report'),
        Rule('hi_spam', {'SPAM': '> 0.5'}, {}, 'report'),
        Rule('hi_threat', {'THREAT': '> 0.5'}, {}, 'report'),
    ]
    actions = check_rules(comment, rules, scores)
    self.assertEqual(['report'], actions.keys())
    self.assertEqual(['hi_tox', 'hi_spam'],
                     [r.name for r in actions['report']])

  def test_check_rules_multiple_actions(self):
    comment = None  # Comment features aren't used by this test.
    scores = { 'TOXICITY': 0.9, 'THREAT': 0.2 }
    rules = [
        Rule('hi_tox', {'TOXICITY': '> 0.5'}, {}, 'report'),
        Rule('hi_threat', {'THREAT': '> 0.9'}, {}, 'report'),
        Rule('med_threat', {'THREAT': '> 0.1'}, {}, 'noop'),
    ]
    actions = check_rules(comment, rules, scores)
    self.assertEqual(['noop', 'report'], sorted(actions.keys()))
    self.assertEqual(['hi_tox'],
                     [r.name for r in actions['report']])
    self.assertEqual(['med_threat'],
                     [r.name for r in actions['noop']])


  def test_create_output_record(self):
    comment = MockComment('hello')
    action_dict = {
        'report': [ Rule('hi_tox', {'TOXICITY': '> 0.5'}, {}, 'report') ],
    }
    scores = { 'TOXICITY': 0.8 }
    record = create_output_record(comment, 'hello', action_dict, scores)
    self.assertEqual('hello', record['orig_comment_text'])
    # This field is only present when different from the comment body.
    self.assertFalse('scored_comment_text' in record)
    self.assertEqual(0.8, record['TOXICITY'])
    self.assertEqual(['Perspective Bot rule triggered: hi_tox: TOXICITY > 0.5'],
                     record['report'])


if __name__ == '__main__':
    unittest.main()
