# Based on the official Dockerfile in the AWS Emulator docs
# (getting-started-docker). One change: we COPY an RPM that 00_build.sh
# downloaded on the host, instead of ADD-ing it from the internet.
# Why: on a TLS-inspecting company network, the download inside
# `docker build` fails the certificate check. The host curl can use
# your company CA bundle.
FROM public.ecr.aws/amazonlinux/amazonlinux:2023-minimal
COPY aws-emulator.rpm /tmp/aws-emulator.rpm
RUN rpm -i /tmp/aws-emulator.rpm && rm /tmp/aws-emulator.rpm \
    && mkdir -p /home/emulator && chown 1000 /home/emulator
USER 1000
ENV HOME=/home/emulator
EXPOSE 9297
ENTRYPOINT ["aws-emulator", "-b", "0.0.0.0"]
