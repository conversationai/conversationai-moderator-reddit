"use strict";
const convict = require("convict");
/**
 * Default/base configuration settings for OS Moderator
 */
const config = convict({
    subreddits: {
        doc: 'The subreddits to watch',
        format: Array,
        default: ['askscience', 'todayilearned', 'the_donald'],
        env: 'SUBREDDITS',
    },
    userAgent: {
        doc: 'Useragent to identify self to Reddit',
        format: String,
        default: 'OSMod',
        env: 'REDDIT_USER_AGENT',
    },
    clientId: {
        doc: 'Reddit API Client ID',
        format: String,
        default: 'OM7hlCxEjiUkyQ',
        env: 'REDDIT_CLIENT_ID',
    },
    clientSecret: {
        doc: 'Reddit API Client Secret',
        format: String,
        default: 'jqI4Ls-ULyc5XHFjAurhlcjdbfg',
        env: 'REDDIT_CLIENT_SECRET',
    },
    refreshToken: {
        doc: 'Reddit API Refresh Token',
        format: String,
        default: '1432690-4RKNN-srBEKGcXZKD01LqWTn1KM',
        env: 'REDDIT_REFRESH_TOKEN',
    },
    maxCommentsPerPoll: {
        doc: 'Maximum comments to insert per poll. Must complete in 60s',
        format: Number,
        default: 10,
        env: 'MAX_COMMENTS_PER_POLL',
    }
});
exports.config = config;
// Try to load (env name).json config file (defaults to 'local.json')
config.validate({ strict: true });
//# sourceMappingURL=index.js.map