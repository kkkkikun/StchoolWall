import asyncio
import json
import unittest
from pathlib import Path
import yaml
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

ROOT = Path(__file__).resolve().parents[2]

class ProductionProxyConfigurationTests(unittest.TestCase):
    def test_loopback_port_and_exact_bridge_gateway_define_the_trust_boundary(self):
        config = yaml.safe_load((ROOT / "deploy/docker-compose.prod.yml").read_text())
        self.assertEqual(config["services"]["backend"]["ports"], ["127.0.0.1:${API_PORT:-8000}:8000"])
        network = config["networks"]["default"]["ipam"]["config"][0]
        trusted = config["x-app"]["environment"]["FORWARDED_ALLOW_IPS"]
        self.assertEqual(trusted, network["gateway"])
        self.assertNotIn("*", trusted)
        dockerfile = (ROOT / "backend/Dockerfile").read_text()
        command = json.loads(next(line[4:] for line in dockerfile.splitlines() if line.startswith("CMD ")))
        self.assertNotIn("--forwarded-allow-ips=127.0.0.1", command)
        self.assertIn("--proxy-headers", command)
        self.assertIn("--no-access-log", command)

    def test_nginx_overwrites_forwarded_chain_and_initial_submissions_stay_closed(self):
        nginx = (ROOT / "deploy/nginx.schoolwall.conf").read_text()
        self.assertIn("proxy_set_header X-Forwarded-For $remote_addr;", nginx)
        self.assertNotIn("$proxy_add_x_forwarded_for", nginx)
        self.assertIn("PUBLISHING_ENABLED=false", (ROOT / "deploy/env.prod.example").read_text())

class TrustedProxyMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    async def observe(self, peer, forwarded, proto="https"):
        observed = {}
        async def downstream(scope, receive, send):
            observed.update(client=scope["client"], scheme=scope["scheme"])
        scope = {"type":"http", "client":(peer, 12345), "scheme":"http",
                 "headers":[(b"x-forwarded-for",forwarded.encode()),(b"x-forwarded-proto",proto.encode())]}
        middleware = ProxyHeadersMiddleware(downstream, trusted_hosts="172.30.0.1")
        await middleware(scope, None, None)
        return observed

    async def test_trusted_bridge_gateway_restores_real_client(self):
        result = await self.observe("172.30.0.1", "198.51.100.20")
        self.assertEqual(result, {"client":("198.51.100.20", 0), "scheme":"https"})

    async def test_untrusted_peer_cannot_spoof_forwarded_identity_or_scheme(self):
        result = await self.observe("172.30.0.27", "203.0.113.99")
        self.assertEqual(result, {"client":("172.30.0.27", 12345), "scheme":"http"})

    async def test_fake_prefix_cannot_replace_last_untrusted_client(self):
        result = await self.observe("172.30.0.1", "203.0.113.99, 198.51.100.20")
        self.assertEqual(result["client"], ("198.51.100.20", 0))
