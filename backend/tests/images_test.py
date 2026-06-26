"""Image-attachment integration test against a REAL MongoDB (GridFS).

mongomock-motor (used by http_test.py) does not implement GridFS, so this test
needs a live mongod — e.g. the `tm-mongo` Docker container on localhost:27017.
Run after backend/dev.ps1 has created the venv:  .venv\\Scripts\\python tests\\images_test.py
"""
import asyncio
import base64
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:  # make ✓ output safe on non-UTF-8 consoles (e.g. Windows cp874)
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

import app.database as database
from app.config import settings
from app.services.seed import seed_defaults

TEST_DB = "taskmanagement_images_test"

# A minimal valid 1x1 PNG (magic bytes make it pass the sniff).
PNG_1x1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _png_file(name):
    return ("files", (name, PNG_1x1, "image/png"))


async def main():
    client = AsyncIOMotorClient(settings.mongo_uri)
    await client.drop_database(TEST_DB)
    database.mongo.client = client
    database.mongo.db = client[TEST_DB]
    await seed_defaults()

    from app.main import app

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            # login as seeded admin
            r = await c.post("/api/auth/login", data={"username": "admin", "password": "admin1234"})
            assert r.status_code == 200, r.text
            h = {"Authorization": f"Bearer {r.json()['access_token']}"}
            print("✓ login as admin")

            # create a task to attach images to
            task = (await c.post("/api/tasks", json={"title": "Has images"}, headers=h)).json()
            tid = task["id"]
            assert task["images"] == [], task
            print("✓ new task starts with empty images[]")

            # upload two images in one multipart request
            up = await c.post(
                f"/api/tasks/{tid}/images",
                files=[_png_file("a.png"), _png_file("b.png")],
                headers=h,
            )
            assert up.status_code == 201, up.text
            images = up.json()["images"]
            assert len(images) == 2, images
            assert images[0]["content_type"] == "image/png"
            assert images[0]["size"] == len(PNG_1x1)
            print("✓ upload 2 images -> task.images length 2")

            # the task now reports 2 images
            got = (await c.get(f"/api/tasks/{tid}", headers=h)).json()
            assert len(got["images"]) == 2
            print("✓ GET task reflects attached images")

            # fetch an image's bytes
            img_id = images[0]["id"]
            ir = await c.get(f"/api/tasks/{tid}/images/{img_id}", headers=h)
            assert ir.status_code == 200, ir.text
            assert ir.headers["content-type"].startswith("image/png")
            assert ir.content == PNG_1x1
            print("✓ GET image streams the original bytes with correct content-type")

            # reject the 11th image (existing 2 + 9 new = 11 > 10)
            over = await c.post(
                f"/api/tasks/{tid}/images",
                files=[_png_file(f"x{i}.png") for i in range(9)],
                headers=h,
            )
            assert over.status_code == 400, over.status_code
            assert "limit" in over.json()["detail"].lower()
            print("✓ over-limit upload rejected (400)")

            # reject an oversize file (>5MB)
            big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (5 * 1024 * 1024 + 1)
            ov = await c.post(
                f"/api/tasks/{tid}/images",
                files=[("files", ("big.png", big, "image/png"))],
                headers=h,
            )
            assert ov.status_code == 400, ov.status_code
            print("✓ oversize file rejected (400)")

            # reject a spoofed content-type (text claiming to be a png)
            spoof = await c.post(
                f"/api/tasks/{tid}/images",
                files=[("files", ("evil.png", b"not really an image", "image/png"))],
                headers=h,
            )
            assert spoof.status_code == 400, spoof.status_code
            print("✓ spoofed content-type rejected via magic-byte sniff (400)")

            # delete one image
            d = await c.delete(f"/api/tasks/{tid}/images/{img_id}", headers=h)
            assert d.status_code == 204, d.status_code
            after = (await c.get(f"/api/tasks/{tid}", headers=h)).json()
            assert len(after["images"]) == 1, after["images"]
            # the deleted image's bytes are gone
            assert (await c.get(f"/api/tasks/{tid}/images/{img_id}", headers=h)).status_code == 404
            print("✓ delete removes the image ref and its bytes")

            # auth guards: no token, and a viewer cannot upload/delete
            assert (await c.post(f"/api/tasks/{tid}/images", files=[_png_file("n.png")])).status_code == 401
            await c.post("/api/users", json={
                "username": "viewer_img", "email": "vi@e.com", "password": "secret1", "role": "viewer",
            }, headers=h)
            vl = await c.post("/api/auth/login", data={"username": "viewer_img", "password": "secret1"})
            vh = {"Authorization": f"Bearer {vl.json()['access_token']}"}
            assert (await c.post(f"/api/tasks/{tid}/images", files=[_png_file("n.png")], headers=vh)).status_code == 403
            remaining = (await c.get(f"/api/tasks/{tid}", headers=h)).json()["images"][0]["id"]
            assert (await c.delete(f"/api/tasks/{tid}/images/{remaining}", headers=vh)).status_code == 403
            # viewer CAN still read an image
            assert (await c.get(f"/api/tasks/{tid}/images/{remaining}", headers=vh)).status_code == 200
            print("✓ RBAC: no-token 401, viewer blocked from upload/delete but can read")

        print("\nALL IMAGE INTEGRATION CHECKS PASSED")
    finally:
        await client.drop_database(TEST_DB)
        client.close()


asyncio.run(main())
