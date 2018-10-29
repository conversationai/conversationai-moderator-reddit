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

"""Small tool for scraping http://redditlist.com/"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import sys

from bs4 import BeautifulSoup
import requests


# Only getting SFW subreddits.
BASE = 'http://redditlist.com/sfw?page='


def fetch_page(page_num):
  print('fetching page', page_num)
  url = BASE + str(page_num)
  return BeautifulSoup(requests.get(url).text, 'html.parser')


def get_hot_list(soup):
  # First ".span4.listing" element gets the "Recent Activity" list.
  # The 2nd list is by subscribers, and the 3rd is by 24h growth.
  items = soup.select('#listing-parent .span4.listing')[0].select('.listing-item')
  return [i.get('data-target-subreddit') for i in items]


def main():
  outfile = sys.argv[1]
  all_subs = []
  # There are actually only 34 pages of results at the moment, but redditlist.com
  # doesn't throw errors, it just serves empty pages.
  for i in xrange(40):
    i += 1
    p = fetch_page(i)
    hots = get_hot_list(p)
    print('got', len(hots))  # should be 125 per page, except the last
    all_subs.extend(hots)
  print('got', len(all_subs), 'total')
  with open(outfile, 'w') as f:
    f.write('\n'.join(all_subs))
  print('done')


if __name__ == '__main__':
    main()
