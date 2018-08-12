"""A class for checking and applying moderation rules.

Copyright 2018 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

class Rule(object):
  """A class for checking and applying moderation rules.
  Args:
    model_rules: (list) A list of model rule dictionaries as read from the rules yaml file.
    action_name: (str) The name of an action to take. Must be one of ['report', 'remove', 'spam']
    report_reason: (str) (optional) The reason for the report to provide to moderators.
  """

  def __init__(self,
               model_rules,
               action_name,
               report_reason=None):
    self.model_rules = model_rules
    self.action_name = action_name
    self.report_reason = report_reason

    # Check there is at least one model rule.
    assert len(self.model_rules) > 0, 'No model thresholds provided!'

  def __str__(self):
    rule_strings = ['%s %s' % (k, v) for k, v in self.model_rules.items()]
    return '\n'.join(rule_strings)

  def check_model_rules(self, scored_df):
    """Checks to see if a scored comment fulfills all of the conditions for this rule."""

    # Currently only checks one comment at a time.
    assert scored_df.shape[0] == 1

    # Checks that all model conditions hold.
    state = True
    for model, comparison in self.model_rules.items():
      assert len(comparison.split()) == 2
      comparator, threshold = comparison.split()
      state = state and self._compare(scored_df['score:%s'%model][0],
                                      comparator,
                                      float(threshold))
    return state

  def _compare(self, score, comparator, threshold):
    if comparator == '>':
      return score > threshold
    elif comparator == '<':
      return score < threshold
    else:
      raise ValueError('Rule must have a ">" or "<".')

  def apply_action(self, comment):
    if self.action_name == 'report':
      comment.report(self.report_reason)
    elif self.action_name == 'remove':
      comment.mod.remove()
    elif self.action_name == 'spam':
      comment.mod.remove(spam=True)
    else:
      raise ValueError('Action "%s" not yet implemented.' % self.action_name)
