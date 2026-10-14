"""Run the local FlowSense & TrustGraph prototype API and built web app."""

import os
import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "src.app_v2:app", host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")), workers=1,
        proxy_headers=True, forwarded_allow_ips=os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1"),
        limit_concurrency=100, timeout_keep_alive=5,
    )
