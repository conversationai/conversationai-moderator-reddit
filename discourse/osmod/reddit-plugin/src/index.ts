import * as express from 'express';
import * as Bluebird from 'bluebird';
const emojiStrip = require('emoji-strip');
const snoowrap = require('snoowrap');
import { Article, Category, Comment, postProcessComment, sendForScoring, denormalizeCommentCountsForCategory } from '@osmod/backend-core';
import { config } from './config';

let r: any;

function reddit(): any {
  r = r || new snoowrap({
    userAgent: config.get('userAgent'),
    clientId: config.get('clientId'),
    clientSecret: config.get('clientSecret'),
    refreshToken: config.get('refreshToken'),
  });

  return r;
}

async function pollSubreddit(
  subreddit: string,
): Promise<void> {
  const [category, createdCategory] = await Category.findOrCreate({
    where: {
      label: subreddit
    },

    defaults: {
      label: subreddit,
    }
  });

  if (createdCategory) {
    console.log(`Created category ${subreddit} as ${category.get('id')}`);
  }

  const sr = reddit().getSubreddit(subreddit);

  let submissionQuery: any = {
    time: 'day',
    limit: 100,
  };

  const lastSeenArticle = await Article.findOne({
    where: {
      categoryId: category.get('id'),
    },

    order: 'sourceCreatedAt DESC',
  })

  if (lastSeenArticle) {
    submissionQuery['after'] = lastSeenArticle.get('sourceId');
  }

  const submissions = await sr.search(submissionQuery);

  console.log(`Got ${submissions.length} submissions`);

  for (const submission of submissions) {
    const { name, title, selftext, url, created_utc } = submission;

    const [article, createdArticle] = await Article.findOrCreate({
      where: {
        sourceId: name
      },

      defaults: {
        sourceId: name,
        categoryId: category.get('id'),
        title: title.substring(0, 255),
        text: selftext,
        url,
        sourceCreatedAt: new Date(created_utc * 1000),
        extra: submission,
      },
    });

    if (createdArticle) {
      console.log(`Created article ${name} as ${article.get('id')}`);
    }
  }
}

async function pollComments(maxComments: number): Promise<void> {
  const articles = await Article.findAll();

  for (const article of articles) {
    const subId = article.get('sourceId');
    const sub = await reddit().getSubmission(subId);

    let commentQuery: any = {
      amount: 25,
    };

    const lastSeenComment = await Comment.findOne({
      where: {
        articleId: article.get('id'),
      },

      order: 'sourceCreatedAt DESC',
    })

    if (lastSeenComment) {
      commentQuery['after'] = lastSeenComment.get('sourceId');
    }

    const comments = await sub.comments.fetchMore(commentQuery);

    for (const comment of comments) {
      const { name, body, author, created_utc } = comment;

      try {
        const [c, createdComment] = await Comment.findOrCreate({
          where: {
            sourceId: name,
          },

          defaults: {
            sourceId: name,
            articleId: article.get('id'),
            authorSourceId: author.name,
            author: author.toJSON(),
            text: emojiStrip(body),
            sourceCreatedAt: new Date(created_utc * 1000),
            extra: comment,
          }
        });

        if (createdComment) {
          console.log(`Created comment ${name} as ${c.get('id')}`);

          await postProcessComment(c);
          await sendForScoring(c, true);

          maxComments -= 1;

          console.log(`${maxComments} remaining`);

          if (maxComments <= 0) {
            break;
          }
        }
      } catch (e) {
        console.error(e);
      }
    }

    if (maxComments <= 0) {
      break;
    }
  }
}

export function mountRedditTasks(): express.Router {
  const app = express.Router();

  app.get('/pollSubmissions', async (_req, res, next) => {
    console.log('Starting to poll reddit submissions.');

    try {
      for (const subreddit of config.get('subreddits')) {
        await pollSubreddit(subreddit);
      }

      res.status(200).send('ok');
    } catch (e) {
      console.error(e);
      next(e);
    }
  });

  app.get('/pollComments', async (_req, res, next) => {
    console.log('Starting to poll reddit comments.');

    try {
      await pollComments(config.get('maxCommentsPerPoll') as number);

      res.status(200).send('ok');
    } catch (e) {
      console.error(e);
      next(e);
    }
  });

  app.get('/clearComments', async (_req, res, next) => {
    try {
      console.log('Starting to clear reddit comments.');
      Comment.destroy({where:{}});
      res.status(200).send('ok');
    } catch (e) {
      console.error(e);
      next(e);
    }
    try {
      console.log('Starting to clear reddit articles.');
      Article.destroy({where:{}, force: true});
      res.status(200).send('ok');
    } catch (e) {
      console.error(e);
      next(e);
    }
    const categories = await Category.findAll();
    await Bluebird.mapSeries(categories, (c: ICategoryInstance) => {
      console.log('Denormalizing category ' + c.get('id'));
      return denormalizeCommentCountsForCategory(c);
    });
  });

  return app;
}
