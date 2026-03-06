FROM alpine:3.21
RUN apk add --no-cache curl

COPY cron.sh /cron.sh
RUN chmod +x /cron.sh

CMD ["/cron.sh"]
