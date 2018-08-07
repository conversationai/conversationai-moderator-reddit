"""A class for checking and applying moderation rules.
"""

import praw

class Rule:
  """A class for checking and applying moderation rules.
  Args:
    model_rules: (list) A list of model rule dictionaries as read from the rules yaml file.
    action_name: (str) The name of an action to take. Must be one of ['report', 'remove', 'spam']
    report_reason: (str) (optional) The reason for the report to provide to moderators.
    
  """
  def __init__(self,
               model_rules,
               action_name,
               report_reason = None):
    self.model_rules = model_rules
    self.action_name = action_name
    self.report_reason = report_reason

  def __str__(self):
    rule_strings = ['%s %s' % (k,v) for k,v in self.model_rules.items()]
    return '\n'.join(rule_strings)

  def check_model_rules(self, scored_df):
    # Check there is at least one model rule
    assert len(self.model_rules) > 0, 'No model thresholds provided!'

    # Checks that all model conditions hold
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
      comment.mod.remove(spame = True)
    else:
      raise ValueError('Action "%s" not yet implemented.' % self.action_name)
