FROM alpine:latest

RUN apk add --no-cache git
RUN apk add --no-cache bash
RUN apk add --no-cache openssh
RUN apk add --no-cache python3
RUN apk add --no-cache py3-pip
RUN adduser -D git
RUN mkdir -p /home/git/.ssh /home/git/repo
RUN chown -R git:git /home/git
RUN pip install PyYAML --break-system-packages

WORKDIR /home/git/repo

COPY entrypoint.sh /entrypoint.sh
COPY gac.sh /home/git/repo/gac.sh
RUN chmod +x /entrypoint.sh /home/git/repo/gac.sh

EXPOSE 22

ENTRYPOINT ["/entrypoint.sh", "<your-key>"]
