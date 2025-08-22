FROM registry.access.redhat.com/ubi8/python-311:1-56.1712880527

LABEL Project="Herringbone"

USER root

EXPOSE 7002/tcp 

WORKDIR /herringbone/ruleset

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python3", "ruleset.py"]