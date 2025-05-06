FROM registry.access.redhat.com/ubi8/python-311:1-56.1712880527

LABEL Project="Herringbone"
LABEL Version="Beta 1.0.0"
LABEL Tool="Receiver"

USER root

EXPOSE 7002/udp
EXPOSE 7002/tcp

WORKDIR /herringbone/receiver

COPY . .

CMD ["python3", "receiver.py"]