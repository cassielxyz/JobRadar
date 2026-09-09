import os
import httpx

class SupabaseREST:
    def __init__(self):
        self.url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1"
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        self.headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        self.client = httpx.Client(timeout=30, headers=self.headers)

    def select(self, table, params=None):
        r = self.client.get(f"{self.url}/{table}", params=params or {"select":"*"})
        r.raise_for_status(); return r.json()

    def insert(self, table, payload, prefer="return=representation"):
        h = dict(self.headers); h["Prefer"] = prefer
        r = self.client.post(f"{self.url}/{table}", json=payload, headers=h)
        r.raise_for_status(); return r.json() if r.content else []

    def upsert(self, table, payload, on_conflict=None):
        h = dict(self.headers); h["Prefer"] = "resolution=merge-duplicates,return=representation"
        params = {"on_conflict": on_conflict} if on_conflict else None
        r = self.client.post(f"{self.url}/{table}", params=params, json=payload, headers=h)
        r.raise_for_status(); return r.json() if r.content else []

    def update(self, table, payload, filters):
        h = dict(self.headers); h["Prefer"] = "return=representation"
        r = self.client.patch(f"{self.url}/{table}", params=filters, json=payload, headers=h)
        r.raise_for_status(); return r.json() if r.content else []
