# conversationai-moderator-reddit  

## Ensure you have a running OSMOD environment before proceeding

An OSMOD environment is required to be running prior to a Discourse installation.  

This Reddit plugin reads from Subreddits noted in osmod/reddit-plugin/src/config/index.ts  
The cron jobs in osmod/reddit-plugin/cron.yaml pull in the posts and comments, as well as clears the database every 24 hours.  