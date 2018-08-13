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

"""Simple Perspective API client library.

TODO: This would be better as a small standalone library.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import concurrent.futures
import datetime
import itertools
import json
import time
import requests
from requests import adapters

# Not sure why pylint detects an import error here.
# pylint: disable=import-error
from requests.packages.urllib3.util import retry

_PERSPECTIVE_BASE = 'https://commentanalyzer.googleapis.com/v1alpha1'
_OUT_OF_QUOTA_STATUS = 429
_QUOTA_DELAY_SECS = 5
_QUOTA_ERROR_INTERVAL = 15
_LAST_QUOTA_ERROR = None
_ERROR_TEXT_LIMIT = 300

def _timestamp():
  return datetime.datetime.now().strftime('[%H:%M:%S]')

# Hat tip https://www.peterbe.com/plog/best-practice-with-retries-with-requests
def _retrying_request_session(
    retries=10,
    backoff_factor=0.5):
  """Returns a requests session with retry logic."""
  retry_config = retry.Retry(total=retries, connect=retries, read=retries,
                             method_whitelist=['GET', 'POST'],
                             backoff_factor=backoff_factor)
  adapter = adapters.HTTPAdapter(max_retries=retry_config)
  session = requests.Session()
  session.mount('http://', adapter)
  session.mount('https://', adapter)
  return session

def _post_request(*args, **kwargs):
  """requests.post with retries, including out-of-quota handling."""
  # On out-of-quota errors, we try again forever.
  # Note: This will probably result in bursty traffic. It would be nicer to
  # smooth out the traffic according to the average QPS limit.
  # pylint: disable=global-statement
  global _LAST_QUOTA_ERROR
  while True:
    response = _retrying_request_session().post(*args, **kwargs)
    if response.status_code != _OUT_OF_QUOTA_STATUS:
      return response
    now = time.time()
    if _LAST_QUOTA_ERROR is None or (now - _LAST_QUOTA_ERROR
                                     > _QUOTA_ERROR_INTERVAL):
      print(_timestamp(), 'Out of quota! Sleeping...')
      _LAST_QUOTA_ERROR = now
    time.sleep(_QUOTA_DELAY_SECS)

def _nice_error(response, text):
  """Tries to return concise error message from API."""
  if len(text) > _ERROR_TEXT_LIMIT:
    text = (text[:_ERROR_TEXT_LIMIT] +
            ' [... truncated {} remaining characters]'.format(
                len(text) - _ERROR_TEXT_LIMIT))
  try:
    data = response.json()
    error_message = data['error']['message']
  except ValueError:
    error_message = response.text
  return u'\n===> request text: {}\n===> API error: {}'.format(
      text, error_message)

# Helper for printing status updates.
def _progress_points(frac, total):
  """Returns indices that represent fractional steps through the total."""
  int_step = max(1, int(round(frac * total)))
  return frozenset(xrange(0, total + int_step, int_step))


class PerspectiveClient(object):
  """Perspective API client."""

  def __init__(self, api_key):
    self._params = {'key': api_key}
    self._executor = concurrent.futures.ThreadPoolExecutor(
        thread_name_prefix='perspective_client', max_workers=5)

  # pylint: disable=too-many-arguments
  # pylint: disable=inconsistent-return-statements
  def score_text(self, text, models, language=None, raise_on_error=False,
                 do_not_store=True):
    """Returns dict from model names to model scores for the requested text.
    Args:
      text: Text to score.
      models: Requested Perspective models. Ssee API reference for available
        models:
        https://github.com/conversationai/perspectiveapi/blob/master/api_reference.md#models
      language: Language that the text is in (e.g., "en", "es", "fr"). If no
        language is supplied, the language is auto-detected by Perspective API.
        If the language isn't supported by the requested models, no scores are
        given.
      raise_on_error: If true, raises on on API errors. Otherwise, returns None.
        The API may return errors for various reasons, such as if the language
        is unsupported, or if the example is too long.
      do_not_store: Controls whether the API is allowed to store text data for
        research purposes.
    """
    request = {
        'comment': {'text': text},
        'requestedAttributes': {model: {} for model in models},
        'doNotStore': do_not_store,
    }
    if language:
      request['languages'] = [language]
    response = _post_request(_PERSPECTIVE_BASE + '/comments:analyze',
                             params=self._params,
                             data=json.dumps(request))
    # pylint: disable=no-member
    if response.status_code == requests.codes.ok:
      scores = response.json()['attributeScores']
      return {attr: attr_scores['summaryScore']['value']
              for (attr, attr_scores) in scores.iteritems()}
    print(_timestamp(), 'ERROR: score_text non-ok status:',
          response.status_code, _nice_error(response, text))
    if raise_on_error:
      response.raise_for_status()
    else:
      return None

  # pylint: disable=too-many-arguments
  def score_texts(self, texts, models, language, raise_on_error,
                  do_not_store, verbose = False):
    """Parallel version of score_text that returns an iterable."""
    every_5_percent = _progress_points(frac=0.05, total=len(texts))
    # pylint: disable=missing-docstring

    def score_one((i, text)):
      # Note: This can run out of order, which is a little weird.
      if i in every_5_percent and verbose:
        print('scoring {} of {} ({:.1f}%)'.format(
            i + 1, len(texts), 100 * (i + 1) / len(texts)))
      return self.score_text(text, models, language, raise_on_error,
                             do_not_store)
    return self._executor.map(score_one, enumerate(texts))


def _main():
  """Basic library test."""
  parser = argparse.ArgumentParser('Perspective API client test.')
  parser.add_argument('-api_key', help='Perspective API key', required=True)
  parser.add_argument('-texts', nargs='+', help='Texts to score', required=True)
  parser.add_argument('-models', nargs='+', help='Models to request',
                      default=['TOXICITY', 'SEVERE_TOXICITY'])
  args = parser.parse_args()
  print('models:', args.models)
  print('texts:', args.texts, '\n\n')
  perspective = PerspectiveClient(args.api_key)
  start = time.time()
  for text, scores in itertools.izip(
      args.texts,
      perspective.score_texts(args.texts, args.models, language=None,
                              raise_on_error=True, do_not_store=True)):
    print('text:', text)
    print('scores:', json.dumps(scores), '\n\n')
  elapsed = time.time() - start
  print('\nTook {:.1f} seconds for {} examples.\nAverage qps: {:.1f}'.format(
      elapsed, len(args.texts), len(args.texts) / elapsed))


if __name__ == '__main__':
  _main()
