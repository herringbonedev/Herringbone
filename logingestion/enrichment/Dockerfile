FROM registry.access.redhat.com/ubi8/python-311:1-56.1712880527

LABEL Project="Herringbone"
LABEL app="enrichment"

USER root

WORKDIR /herringbone/enrichment

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python3", "enrichment.py"]