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


REPORT_ACTION = 'report'
NOOP_ACTION = 'noop'


class Rule(object):
  """A class for checking and applying moderation rules.
  Args:
    name: (str) Short name/descriptor for the rule.
    model_rules: (dict) Model rules from the config file.
    comment_feature_rules: (dict) Comment feature rules from the config file.
    action_name: (str) The name of an action to take. Currently only 'report'
                 and 'noop' are supported.
    report_reason: (str) (optional) The reason for the report to provide to
                   moderators.
  """

  def __init__(self,
               name,
               model_rules,
               comment_feature_rules,
               action_name,
               report_reason=None):
    if not model_rules:
      raise ValueError('No model thresholds provided!')
    if not action_name:
      raise ValueError('No action_name provided!')
    if action_name not in (REPORT_ACTION, NOOP_ACTION):
      raise ValueError('action_name not supported: {}'.format(action_name))

    if not name:
      name = '__'.join(sorted(model_rules.iterkeys()))

    self.name = name
    self.model_rules = model_rules
    self.comment_feature_rules = comment_feature_rules
    self.action_name = action_name
    self.report_reason = report_reason
    self.rule_strings = ['%s %s' % (k, v) for k, v in model_rules.iteritems()]
    if report_reason:
      self.rule_description = report_reason
    else:
      self.rule_description = ('Perspective Bot rule triggered: '
                               + self.name + ': '
                               + ' & '.join(self.rule_strings))

  def __str__(self):
    return self.rule_description

  def check_model_rules(self, model_scores, comment):
    """Checks if a scored comment fulfills the conditions for this rule."""
    # Check that all model conditions hold.
    state = True
    for model, comparison in self.model_rules.iteritems():
      assert len(comparison.split()) == 2
      comparator, threshold = comparison.split()
      state = state and self._compare (model_scores[model],
                                      comparator,
                                      float(threshold))
    # Check that comment feature conditions hold.
    for feature, feature_value in self.comment_feature_rules.iteritems():
      if feature == 'toplevel_only' and feature_value:
        is_toplevel_comment = comment.link_id == comment.parent_id
        state = state and is_toplevel_comment
    return state

  def _compare(self, score, comparator, threshold):
    if comparator == '>':
      return score > threshold
    elif comparator == '<':
      return score < threshold
    else:
      raise ValueError('Rule must have a ">" or "<".')
