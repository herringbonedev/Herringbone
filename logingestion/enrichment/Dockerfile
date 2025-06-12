FROM registry.access.redhat.com/ubi8/python-311:1-56.1712880527

LABEL Project="Herringbone"
LABEL Version="Beta 1.0.0"
LABEL Tool="Enrichment"

USER root

WORKDIR /herringbone/enrichment

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python3", "enrichment.py"]