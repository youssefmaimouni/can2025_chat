import http.client

conn = http.client.HTTPSConnection("api-football-v1.p.rapidapi.com")

headers = {
    'x-rapidapi-key': "15fd3a62efmsh1faecb71eadbab3p1cffdcjsna7d1a04f5ccc",
    'x-rapidapi-host': "api-football-v1.p.rapidapi.com"
}

conn.request("GET", "/v3/leagues/seasons", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))