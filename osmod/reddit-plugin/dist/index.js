"use strict";
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : new P(function (resolve) { resolve(result.value); }).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
const express = require("express");
const Bluebird = require("bluebird");
const emojiStrip = require('emoji-strip');
const snoowrap = require('snoowrap');
const backend_core_1 = require("@osmod/backend-core");
const config_1 = require("./config");
let r;
function reddit() {
    r = r || new snoowrap({
        userAgent: config_1.config.get('userAgent'),
        clientId: config_1.config.get('clientId'),
        clientSecret: config_1.config.get('clientSecret'),
        refreshToken: config_1.config.get('refreshToken'),
    });
    return r;
}
function pollSubreddit(subreddit) {
    return __awaiter(this, void 0, void 0, function* () {
        const [category, createdCategory] = yield backend_core_1.Category.findOrCreate({
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
        let submissionQuery = {
            time: 'day',
            limit: 100,
        };
        const lastSeenArticle = yield backend_core_1.Article.findOne({
            where: {
                categoryId: category.get('id'),
            },
            order: 'sourceCreatedAt DESC',
        });
        if (lastSeenArticle) {
            submissionQuery['after'] = lastSeenArticle.get('sourceId');
        }
        const submissions = yield sr.search(submissionQuery);
        console.log(`Got ${submissions.length} submissions`);
        for (const submission of submissions) {
            const { name, title, selftext, url, created_utc } = submission;
            const [article, createdArticle] = yield backend_core_1.Article.findOrCreate({
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
    });
}
function pollComments(maxComments) {
    return __awaiter(this, void 0, void 0, function* () {
        const articles = yield backend_core_1.Article.findAll();
        for (const article of articles) {
            const subId = article.get('sourceId');
            const sub = yield reddit().getSubmission(subId);
            let commentQuery = {
                amount: 25,
            };
            const lastSeenComment = yield backend_core_1.Comment.findOne({
                where: {
                    articleId: article.get('id'),
                },
                order: 'sourceCreatedAt DESC',
            });
            if (lastSeenComment) {
                commentQuery['after'] = lastSeenComment.get('sourceId');
            }
            const comments = yield sub.comments.fetchMore(commentQuery);
            for (const comment of comments) {
                const { name, body, author, created_utc } = comment;
                try {
                    const [c, createdComment] = yield backend_core_1.Comment.findOrCreate({
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
                        yield backend_core_1.postProcessComment(c);
                        yield backend_core_1.sendForScoring(c, true);
                        maxComments -= 1;
                        console.log(`${maxComments} remaining`);
                        if (maxComments <= 0) {
                            break;
                        }
                    }
                }
                catch (e) {
                    console.error(e);
                }
            }
            if (maxComments <= 0) {
                break;
            }
        }
    });
}
function mountRedditTasks() {
    const app = express.Router();
    app.get('/pollSubmissions', (_req, res, next) => __awaiter(this, void 0, void 0, function* () {
        console.log('Starting to poll reddit submissions.');
        try {
            for (const subreddit of config_1.config.get('subreddits')) {
                yield pollSubreddit(subreddit);
            }
            res.status(200).send('ok');
        }
        catch (e) {
            console.error(e);
            next(e);
        }
    }));
    app.get('/pollComments', (_req, res, next) => __awaiter(this, void 0, void 0, function* () {
        console.log('Starting to poll reddit comments.');
        try {
            yield pollComments(config_1.config.get('maxCommentsPerPoll'));
            res.status(200).send('ok');
        }
        catch (e) {
            console.error(e);
            next(e);
        }
    }));
    app.get('/clearComments', (_req, res, next) => __awaiter(this, void 0, void 0, function* () {
        try {
            console.log('Starting to clear reddit comments.');
            backend_core_1.Comment.destroy({ where: {} });
            res.status(200).send('ok');
        }
        catch (e) {
            console.error(e);
            next(e);
        }
        try {
            console.log('Starting to clear reddit articles.');
            backend_core_1.Article.destroy({ where: {}, force: true });
            res.status(200).send('ok');
        }
        catch (e) {
            console.error(e);
            next(e);
        }
        const categories = yield backend_core_1.Category.findAll();
        yield Bluebird.mapSeries(categories, (c) => {
            console.log('Denormalizing category ' + c.get('id'));
            return backend_core_1.denormalizeCommentCountsForCategory(c);
        });
        // for (const category in categories) {
        //   await denormalizeCommentCountsForCategory(category);
        // }
    }));
    return app;
}
exports.mountRedditTasks = mountRedditTasks;
//# sourceMappingURL=index.js.map