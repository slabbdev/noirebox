FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY noirebox/ noirebox/
COPY corpus/ corpus/
EXPOSE 8768
CMD ["uvicorn", "noirebox.main:app", "--host", "0.0.0.0", "--port", "8768"]
