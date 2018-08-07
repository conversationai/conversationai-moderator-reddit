FROM gcr.io/google_appengine/nodejs

RUN apt-get update && apt-get install -y libcairo2-dev libjpeg62-turbo-dev libpango1.0-dev libgif-dev build-essential g++

RUN install_node v6.9.5

COPY . /app/

RUN npm install --unsafe-perm

EXPOSE 8080

CMD npm start
