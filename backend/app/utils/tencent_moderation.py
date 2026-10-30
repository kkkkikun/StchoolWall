"""Tencent Cloud TMS / IMS adapter; content is never logged on failures."""
import asyncio
import base64
import json

from app.config import settings


class ModerationProviderError(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(getattr(settings, "TENCENT_SECRET_ID", "") and getattr(settings, "TENCENT_SECRET_KEY", ""))


def _call(service: str, content: bytes) -> dict:
    from tencentcloud.common.credential import Credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
    from tencentcloud.ims.v20201229 import ims_client, models as ims_models
    from tencentcloud.tms.v20201229 import tms_client, models as tms_models

    credential = Credential(settings.TENCENT_SECRET_ID, settings.TENCENT_SECRET_KEY)
    profile = ClientProfile()
    profile.httpProfile = HttpProfile(reqTimeout=15)
    region = getattr(settings, "TENCENT_REGION", "ap-guangzhou")
    params = {"BizType": getattr(settings, "TENCENT_BIZ_TYPE", "")}
    params = {key: value for key, value in params.items() if value}
    if service == "text":
        params["Content"] = base64.b64encode(content).decode("ascii")
        request = tms_models.TextModerationRequest()
        request.from_json_string(json.dumps(params))
        response = tms_client.TmsClient(credential, region, profile).TextModeration(request)
    else:
        params["FileContent"] = base64.b64encode(content).decode("ascii")
        request = ims_models.ImageModerationRequest()
        request.from_json_string(json.dumps(params))
        response = ims_client.ImsClient(credential, region, profile).ImageModeration(request)
    return json.loads(response.to_json_string())


async def moderate(service: str, content: bytes) -> dict:
    if not is_configured():
        return {"Suggestion": "Review", "Label": "provider_not_configured"}
    try:
        return await asyncio.to_thread(_call, service, content)
    except Exception as exc:
        raise ModerationProviderError(type(exc).__name__) from None
