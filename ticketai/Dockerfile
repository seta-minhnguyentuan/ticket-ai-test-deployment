FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

RUN pip install jupyter nbconvert && \
    jupyter nbconvert --to script app.ipynb --output main.py

EXPOSE 5010

CMD ["python", "main.py"]