import re
import time

import httpx
import rsa
from bs4 import BeautifulSoup


class ZhengfangLogin:
    """正方教务系统异步登录客户端 (httpx)"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.csrftoken: str | None = None
        self.is_logged_in = False
        self.student_id: str | None = None

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    async def get_login_page(self, client: httpx.AsyncClient) -> dict[str, str]:
        resp = await client.get(self._url("/xtgl/login_slogin.html"), timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        hidden_fields: dict[str, str] = {}
        for inp in soup.find_all("input", {"type": "hidden"}):
            name = inp.get("name")
            if name:
                hidden_fields[name] = inp.get("value", "")
                if name == "csrftoken":
                    self.csrftoken = hidden_fields[name]
        return hidden_fields

    async def get_public_key(self, client: httpx.AsyncClient) -> tuple[str | None, str | None]:
        ts = int(time.time() * 1000)
        resp = await client.get(
            self._url(f"/xtgl/login_getPublicKey.html?time={ts}"), timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("modulus"), data.get("exponent")

    # ---- RSA helpers (same logic as sync version) ----

    @staticmethod
    def _b64tohex(b64_string: str) -> str:
        b64map = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
        BI_RM = "0123456789abcdefghijklmnopqrstuvwxyz"
        ret = ""
        k = 0
        slop = 0
        for ch in b64_string:
            if ch == "=":
                break
            v = b64map.find(ch)
            if v < 0:
                continue
            if k == 0:
                ret += BI_RM[v >> 2]
                slop = v & 3
                k = 1
            elif k == 1:
                ret += BI_RM[(slop << 2) | (v >> 4)]
                slop = v & 0xF
                k = 2
            elif k == 2:
                ret += BI_RM[slop] + BI_RM[v >> 2]
                slop = v & 3
                k = 3
            else:
                ret += BI_RM[(slop << 2) | (v >> 4)] + BI_RM[v & 0xF]
                k = 0
        if k == 1:
            ret += BI_RM[slop << 2]
        return ret

    @staticmethod
    def _hex2b64(hex_string: str) -> str:
        b64map = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
        ret = ""
        i = 0
        while i + 3 <= len(hex_string):
            c = int(hex_string[i : i + 3], 16)
            ret += b64map[c >> 6] + b64map[c & 63]
            i += 3
        if i + 1 == len(hex_string):
            ret += b64map[int(hex_string[i:], 16) << 2]
        elif i + 2 == len(hex_string):
            c = int(hex_string[i:], 16)
            ret += b64map[c >> 2] + b64map[(c & 3) << 4]
        while len(ret) & 3:
            ret += "="
        return ret

    def _parse_key(self, modulus_str: str, exponent_str: str) -> tuple[int | None, int | None]:
        try:
            if not any(c in modulus_str for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ+/"):
                return int(modulus_str, 16), int(exponent_str, 16)
            mod_hex = self._b64tohex(modulus_str)
            exp_hex = self._b64tohex(exponent_str)
            return int(mod_hex, 16), int(exp_hex, 16)
        except Exception:
            return None, None

    def rsa_encrypt(self, plaintext: str, modulus_str: str, exponent_str: str) -> str | None:
        try:
            modulus, exponent = self._parse_key(modulus_str, exponent_str)
            if not modulus or not exponent:
                return None
            public_key = rsa.PublicKey(modulus, exponent)
            encrypted = rsa.encrypt(plaintext.encode("utf-8"), public_key)
            return self._hex2b64(encrypted.hex())
        except Exception:
            return None

    async def do_login(self, client: httpx.AsyncClient, student_id: str, password: str) -> dict:
        self.student_id = student_id

        hidden_fields = await self.get_login_page(client)
        if not hidden_fields or "csrftoken" not in hidden_fields:
            return {"status": "fail", "msg": "获取登录页失败"}

        modulus, exponent = await self.get_public_key(client)
        if not modulus or not exponent:
            return {"status": "fail", "msg": "获取公钥失败"}

        needs_encryption = hidden_fields.get("mmsfjm", "1") == "1"
        encrypted_pwd = self.rsa_encrypt(password, modulus, exponent) if needs_encryption else password
        if needs_encryption and not encrypted_pwd:
            return {"status": "fail", "msg": "密码加密失败"}

        ts = int(time.time() * 1000)
        login_url = self._url(f"/xtgl/login_slogin.html?time={ts}")
        form_data = {**hidden_fields, "yhm": student_id, "mm": encrypted_pwd}
        if "hidMm" not in form_data:
            form_data["hidMm"] = encrypted_pwd

        resp = await client.post(login_url, data=form_data, timeout=15, follow_redirects=True)

        if "login_slogin" in str(resp.url):
            soup = BeautifulSoup(resp.text, "html.parser")
            text = soup.get_text()
            for pattern in ["用户名或密码错误", "密码错误", "登录失败", "不存在"]:
                if pattern in text:
                    return {"status": "fail", "msg": f"登录失败: {pattern}"}
            return {"status": "fail", "msg": "登录失败"}

        self.is_logged_in = True
        return {"status": "success", "msg": "登录成功"}

    async def get_real_name(self, client: httpx.AsyncClient) -> str | None:
        if not self.is_logged_in:
            return None

        info_url = self._url("/xsxxxggl/xsgrxxwh_cxXsgrxx.html")
        resp = await client.get(info_url, timeout=10)

        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text()

        if self.student_id and self.student_id in text:
            match = re.search(r"姓名[：:\s]*([一-龥]{2,4})", text)
            if match:
                return match.group(1)

            idx = text.find(self.student_id)
            context = text[max(0, idx - 200) : idx + 400]
            name_match = re.search(r"([一-龥]{2,4})", context)
            if name_match:
                name = name_match.group(1)
                if name not in ["查询", "信息", "维护", "系统", "页面", "学院", "大学", "登录", "退出", "首页", "菜单"]:
                    return name
        return None


async def verify_student(student_id: str, password: str, base_url: str) -> dict:
    """验证学生账号并返回真实姓名"""
    async with httpx.AsyncClient(trust_env=False) as client:
        client.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        zf = ZhengfangLogin(base_url)
        result = await zf.do_login(client, student_id, password)
        if result["status"] == "success":
            real_name = await zf.get_real_name(client)
            result["real_name"] = real_name
    return result
