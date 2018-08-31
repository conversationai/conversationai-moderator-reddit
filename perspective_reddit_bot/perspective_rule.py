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


class Rule(object):
  """A class for checking and applying moderation rules.
  Args:
    model_rules: (list) A list of model rule dictionaries as read from the
                 rules yaml file.
    action_name: (str) The name of an action to take. Currently only 'report'
                 is supported.
    report_reason: (str) (optional) The reason for the report to provide to
                   moderators.
  """

  def __init__(self,
               model_rules,
               action_name,
               report_reason=None):
    self.model_rules = model_rules
    self.action_name = action_name
    self.report_reason = report_reason
    self.rule_strings = ['%s %s' % (k, v) for k, v in model_rules.items()]
    if report_reason:
      self.rule_description = report_reason
    else:
      self.rule_description = 'Perspective bot detected ' + ' & '.join(self.rule_strings)

    # Check there is at least one model rule.
    assert len(self.model_rules) > 0, 'No model thresholds provided!'

  def __str__(self):
    return '\n'.join(self.rule_strings)

  def check_model_rules(self, model_scores):
    """Checks if a scored comment fulfills the conditions for this rule."""
    # Checks that all model conditions hold.
    state = True
    for model, comparison in self.model_rules.items():
      assert len(comparison.split()) == 2
      comparator, threshold = comparison.split()
      state = state and self._compare (model_scores[model],
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